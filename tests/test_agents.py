"""
backend/agents.py shells out to the real `claude` CLI (see CLAUDE.md) - these
tests mock subprocess.run (or run_claude itself) so the suite never actually
invokes it.
"""

import asyncio
import json
import re
import subprocess
from unittest.mock import patch

import pytest

from backend.agents import (
    CANARY_TYPE_HANDLERS,
    ClaudeCLIError,
    IomMapping,
    SiteArtifact,
    _canary_endpoint_regex,
    _fallback_domain,
    _issue_leaf_cert,
    _sanitize_domain,
    classify_task_ioms,
    deploy_canary_instance,
    deploy_static_site,
    get_canary_type_handler,
    reconcile_canary_registrations,
    run_claude,
    spawn_canary_instances_for_task,
    valid_canary_type_ids,
)
from backend.models import CanaryInstance, CanaryType, IOM, Task


def _fake_proc(returncode=0, stdout="", stderr=""):
    class FakeProc:
        pass

    p = FakeProc()
    p.returncode = returncode
    p.stdout = stdout
    p.stderr = stderr
    return p


# --- run_claude ------------------------------------------------------------


def test_run_claude_returns_result_text():
    envelope = json.dumps({"is_error": False, "result": "hello"})
    with patch("subprocess.run", return_value=_fake_proc(stdout=envelope)) as mock_run:
        assert run_claude("say hi") == "hello"
    cmd = mock_run.call_args.args[0]
    assert cmd[:3] == ["claude", "-p", "say hi"]
    assert "--json-schema" not in cmd


def test_run_claude_passes_json_schema_when_given():
    envelope = json.dumps({"is_error": False, "result": "{}"})
    schema = {"type": "object"}
    with patch("subprocess.run", return_value=_fake_proc(stdout=envelope)) as mock_run:
        run_claude("say hi", output_json_schema=schema)
    cmd = mock_run.call_args.args[0]
    assert "--json-schema" in cmd
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == schema


def test_run_claude_raises_on_nonzero_exit():
    with patch("subprocess.run", return_value=_fake_proc(returncode=1, stderr="boom")):
        with pytest.raises(ClaudeCLIError, match="boom"):
            run_claude("say hi")


def test_run_claude_raises_on_is_error_true():
    envelope = json.dumps({"is_error": True, "result": "refused"})
    with patch("subprocess.run", return_value=_fake_proc(stdout=envelope)):
        with pytest.raises(ClaudeCLIError, match="refused"):
            run_claude("say hi")


def test_run_claude_raises_on_invalid_json():
    with patch("subprocess.run", return_value=_fake_proc(stdout="not json")):
        with pytest.raises(ClaudeCLIError):
            run_claude("say hi")


# --- classify_task_ioms -----------------------------------------------------


def test_classify_task_ioms_filters_ids_outside_the_catalog():
    task = Task(id="1", company_id="1", prompt="RAG on company data")
    ioms = [IOM(id="8", name="Unauthorised internet access", linked_canary_type_ids=["1"])]

    llm_json = IomMapping(iom_ids=["8", "not-a-real-id"]).model_dump_json()
    with patch("backend.agents.run_claude", return_value=llm_json) as mock_run_claude:
        result = classify_task_ioms(task, ioms)

    # The model echoed an id outside the catalog it was given - must be dropped.
    assert result == ["8"]
    assert mock_run_claude.call_args.kwargs["output_json_schema"] == IomMapping.model_json_schema()


# --- spawn_canary_instances_for_task / valid_canary_type_ids ---------------


def test_valid_canary_type_ids_dedupes_and_drops_unknown_types():
    iom = IOM(id="3", name="x", linked_canary_type_ids=["1", "1", "2", "unknown"])
    canary_types = [CanaryType(id="1", name="A"), CanaryType(id="2", name="B")]
    assert valid_canary_type_ids(iom, canary_types) == ["1", "2"]


def test_spawn_canary_instances_for_task_one_per_iom_canary_type_pair():
    task = Task(id="1", company_id="1", prompt="p", iom_ids=["3", "6"])
    ioms = [
        IOM(id="3", name="x", linked_canary_type_ids=["1", "2"]),
        IOM(id="6", name="gap", linked_canary_type_ids=[]),  # no linked type -> no canary
    ]
    canary_types = [CanaryType(id="1", name="A"), CanaryType(id="2", name="B")]

    created = spawn_canary_instances_for_task(task, ioms, canary_types)

    assert len(created) == 2
    assert {(c.canary_type_id, tuple(c.iom_ids)) for c in created} == {("1", ("3",)), ("2", ("3",))}
    for c in created:
        assert c.task_id == "1"
        assert c.deployment_health == "pending"


def test_spawn_canary_instances_for_task_skips_unknown_iom_id():
    task = Task(id="1", company_id="1", prompt="p", iom_ids=["does-not-exist"])
    created = spawn_canary_instances_for_task(task, ioms=[], canary_types=[])
    assert created == []


# --- deploy_canary_instance / deploy handlers -------------------------------


def test_get_canary_type_handler_routes_message_board_to_its_own_handler():
    assert get_canary_type_handler("4") is CANARY_TYPE_HANDLERS["4"]
    # Anything else falls back to the generic default.
    assert get_canary_type_handler("1") is not CANARY_TYPE_HANDLERS["4"]


def test_deploy_canary_instance_default_handler_activates_and_sets_target_url():
    # canary_type_id "6" is deliberately not in CANARY_TYPE_HANDLERS (every id
    # actually seeded in data.py - "1", "2", "4" - has a real handler), so
    # this exercises DEFAULT_CANARY_TYPE_HANDLER / deploy_noop.
    instance = CanaryInstance(id="ci-1", canary_type_id="6", task_id="1", iom_ids=["8"])
    task = Task(id="1", company_id="1", prompt="RAG on company data")
    canary_types = [CanaryType(id="6", name="LinkedIn user")]

    with patch("backend.agents.run_claude", return_value="fake artifact") as mock_run_claude:
        asyncio.run(deploy_canary_instance(instance, task, canary_types))

    mock_run_claude.assert_called_once()
    assert instance.deployment_health == "active"
    assert instance.metadata["artifact"] == "fake artifact"
    assert instance.target_url is not None
    assert instance.deployed_at is not None


# --- deploy_static_site / DNS zone registration -----------------------------


def test_fallback_domain_is_a_single_label_under_the_tld():
    instance = CanaryInstance(id="c9cc2a7e-ff82-4dcf-8c87-5bdce65e2133", canary_type_id="1", task_id="1")
    task = Task(id="1", company_id="1", prompt="RAG over the support inbox")

    domain = _fallback_domain(instance, task)

    assert domain.endswith(".canary.test")
    label = domain[: -len(".canary.test")]
    assert "." not in label
    assert label.endswith("c9cc2a7e")  # instance.id[:8], for uniqueness


def test_sanitize_domain_accepts_a_valid_arbitrary_domain():
    instance = CanaryInstance(id="c9cc2a7e-ff82-4dcf-8c87-5bdce65e2133", canary_type_id="1", task_id="1")
    task = Task(id="1", company_id="1", prompt="RAG over the support inbox")

    assert _sanitize_domain("Brightpath-Vendor-Support.com", instance, task) == "brightpath-vendor-support.com"


@pytest.mark.parametrize(
    "raw",
    [
        "not a domain!!",
        "nodotshere",
        "../../etc/passwd",
        "-leading-hyphen.com",
        "",
    ],
)
def test_sanitize_domain_falls_back_on_invalid_input(raw):
    instance = CanaryInstance(id="c9cc2a7e-ff82-4dcf-8c87-5bdce65e2133", canary_type_id="1", task_id="1")
    task = Task(id="1", company_id="1", prompt="RAG over the support inbox")

    assert _sanitize_domain(raw, instance, task) == _fallback_domain(instance, task)


def test_deploy_static_site_writes_content_and_registers_dns_zone(tmp_path, monkeypatch):
    content_dir = tmp_path / "content"
    zones_file = tmp_path / "zones.json"
    monkeypatch.setattr("backend.agents.STATIC_SITE_CONTENT_DIR", content_dir)
    monkeypatch.setattr("backend.agents.DNS_ZONES_FILE", zones_file)
    monkeypatch.setattr("backend.agents.ENDPOINTS_FILE", tmp_path / "endpoints.json")
    monkeypatch.setattr("backend.agents.STATIC_SITE_IP", "127.0.0.1")
    monkeypatch.setattr("backend.agents.PKI_DIR", tmp_path / "no-pki")  # no CA -> cert issuance skipped

    instance = CanaryInstance(id="c9cc2a7e-ff82-4dcf-8c87-5bdce65e2133", canary_type_id="1", task_id="1")
    task = Task(id="1", company_id="1", prompt="RAG over the support inbox")
    artifact = SiteArtifact(domain="brightpath-support.com", html="<html>fake page</html>")

    asyncio.run(deploy_static_site(instance, artifact, task))

    domain = instance.metadata["domain"]
    assert domain == "brightpath-support.com"
    assert (content_dir / domain / "index.html").read_text() == "<html>fake page</html>"
    assert json.loads(zones_file.read_text()) == {domain: "127.0.0.1"}
    assert instance.target_url == f"https://{domain}/"


def test_deploy_static_site_preserves_existing_dns_zones(tmp_path, monkeypatch):
    content_dir = tmp_path / "content"
    zones_file = tmp_path / "zones.json"
    zones_file.write_text(json.dumps({"other-existing.canary.test": "127.0.0.1"}))
    monkeypatch.setattr("backend.agents.STATIC_SITE_CONTENT_DIR", content_dir)
    monkeypatch.setattr("backend.agents.DNS_ZONES_FILE", zones_file)
    monkeypatch.setattr("backend.agents.ENDPOINTS_FILE", tmp_path / "endpoints.json")
    monkeypatch.setattr("backend.agents.STATIC_SITE_IP", "127.0.0.1")
    monkeypatch.setattr("backend.agents.PKI_DIR", tmp_path / "no-pki")

    instance = CanaryInstance(id="c9cc2a7e-ff82-4dcf-8c87-5bdce65e2133", canary_type_id="1", task_id="1")
    task = Task(id="1", company_id="1", prompt="RAG over the support inbox")
    artifact = SiteArtifact(domain="another-brand.com", html="<html></html>")

    asyncio.run(deploy_static_site(instance, artifact, task))

    zones = json.loads(zones_file.read_text())
    assert "other-existing.canary.test" in zones
    assert instance.metadata["domain"] in zones


def test_deploy_static_site_falls_back_on_domain_collision(tmp_path, monkeypatch):
    """Two different instances inventing the same domain (plausible - the
    model isn't told what other canaries already picked) must not clobber
    each other's DNS zone entry or content directory."""
    content_dir = tmp_path / "content"
    zones_file = tmp_path / "zones.json"
    zones_file.write_text(json.dumps({"support-portal.com": "127.0.0.1"}))
    monkeypatch.setattr("backend.agents.STATIC_SITE_CONTENT_DIR", content_dir)
    monkeypatch.setattr("backend.agents.DNS_ZONES_FILE", zones_file)
    monkeypatch.setattr("backend.agents.ENDPOINTS_FILE", tmp_path / "endpoints.json")
    monkeypatch.setattr("backend.agents.STATIC_SITE_IP", "127.0.0.1")
    monkeypatch.setattr("backend.agents.PKI_DIR", tmp_path / "no-pki")

    instance = CanaryInstance(id="c9cc2a7e-ff82-4dcf-8c87-5bdce65e2133", canary_type_id="1", task_id="1")
    task = Task(id="1", company_id="1", prompt="RAG over the support inbox")
    artifact = SiteArtifact(domain="support-portal.com", html="<html></html>")

    asyncio.run(deploy_static_site(instance, artifact, task))

    domain = instance.metadata["domain"]
    assert domain == _fallback_domain(instance, task)
    zones = json.loads(zones_file.read_text())
    assert zones["support-portal.com"] == "127.0.0.1"  # untouched - the other instance's
    assert zones[domain] == "127.0.0.1"


def test_deploy_static_site_strips_markdown_code_fence(tmp_path, monkeypatch):
    """claude -p sometimes wraps its HTML output in a ```html ... ``` fence
    despite being asked for raw HTML - it must not end up in index.html."""
    content_dir = tmp_path / "content"
    monkeypatch.setattr("backend.agents.STATIC_SITE_CONTENT_DIR", content_dir)
    monkeypatch.setattr("backend.agents.DNS_ZONES_FILE", tmp_path / "zones.json")
    monkeypatch.setattr("backend.agents.ENDPOINTS_FILE", tmp_path / "endpoints.json")
    monkeypatch.setattr("backend.agents.STATIC_SITE_IP", "127.0.0.1")
    monkeypatch.setattr("backend.agents.PKI_DIR", tmp_path / "no-pki")

    instance = CanaryInstance(id="c9cc2a7e-ff82-4dcf-8c87-5bdce65e2133", canary_type_id="1", task_id="1")
    task = Task(id="1", company_id="1", prompt="RAG over the support inbox")
    fenced = "```html\n<html><body>fake page</body></html>\n```"
    artifact = SiteArtifact(domain="brightpath-support.com", html=fenced)

    asyncio.run(deploy_static_site(instance, artifact, task))

    written = (content_dir / instance.metadata["domain"] / "index.html").read_text()
    assert written == "<html><body>fake page</body></html>"


# --- _issue_leaf_cert --------------------------------------------------------


def test_issue_leaf_cert_skips_silently_without_a_local_ca(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.agents.PKI_DIR", tmp_path / "no-such-dir")
    site_dir = tmp_path / "site"
    site_dir.mkdir()

    asyncio.run(_issue_leaf_cert("example.canary.test", site_dir))

    assert not (site_dir / "cert.pem").exists()
    assert not (site_dir / "key.pem").exists()


def test_issue_leaf_cert_skips_canary_test_domains_even_with_a_ca_present(tmp_path, monkeypatch):
    """*.canary.test is covered by the static wildcard cert - nginx.conf
    special-cases it ahead of any per-domain lookup - so issuing one here
    would just go unused."""
    pki_dir = tmp_path / "pki"
    pki_dir.mkdir()
    (pki_dir / "ca.pem").write_text("not actually used")
    (pki_dir / "ca.key").write_text("not actually used")
    monkeypatch.setattr("backend.agents.PKI_DIR", pki_dir)
    site_dir = tmp_path / "site"
    site_dir.mkdir()

    asyncio.run(_issue_leaf_cert("some-canary-abc12345.canary.test", site_dir))

    assert not (site_dir / "cert.pem").exists()


def test_issue_leaf_cert_writes_a_cert_signed_by_the_local_ca(tmp_path, monkeypatch):
    pki_dir = tmp_path / "pki"
    pki_dir.mkdir()
    subprocess.run(["openssl", "genrsa", "-out", str(pki_dir / "ca.key"), "2048"], check=True, capture_output=True)
    subprocess.run(
        [
            "openssl", "req", "-x509", "-new", "-key", str(pki_dir / "ca.key"),
            "-days", "1", "-subj", "/CN=Test CA", "-out", str(pki_dir / "ca.pem"),
        ],
        check=True,
        capture_output=True,
    )
    monkeypatch.setattr("backend.agents.PKI_DIR", pki_dir)
    site_dir = tmp_path / "site"
    site_dir.mkdir()

    asyncio.run(_issue_leaf_cert("brightpath-support.com", site_dir))

    assert (site_dir / "cert.pem").exists()
    assert (site_dir / "key.pem").exists()
    assert not (site_dir / "_csr.pem").exists()
    assert not (site_dir / "_ext.cnf").exists()

    cert_text = subprocess.run(
        ["openssl", "x509", "-in", str(site_dir / "cert.pem"), "-noout", "-text"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "CN = brightpath-support.com" in cert_text or "CN=brightpath-support.com" in cert_text
    assert "DNS:brightpath-support.com" in cert_text


# --- Canary trigger endpoint registration -----------------------------------


def test_canary_endpoint_regex_is_a_catch_all_for_impersonation_server():
    # The whole point of an impersonation server is that the agent was never
    # told it exists - any request to it is the violation.
    regex = _canary_endpoint_regex("1")
    assert re.match(regex, "/")
    assert re.match(regex, "/anything/at/all")


def test_canary_endpoint_regex_falls_back_to_catch_all_for_unknown_type():
    assert _canary_endpoint_regex("does-not-exist") == _canary_endpoint_regex("1")


def test_deploy_static_site_registers_one_endpoint_entry_per_iom(tmp_path, monkeypatch):
    content_dir = tmp_path / "content"
    endpoints_file = tmp_path / "endpoints.json"
    monkeypatch.setattr("backend.agents.STATIC_SITE_CONTENT_DIR", content_dir)
    monkeypatch.setattr("backend.agents.DNS_ZONES_FILE", tmp_path / "zones.json")
    monkeypatch.setattr("backend.agents.ENDPOINTS_FILE", endpoints_file)
    monkeypatch.setattr("backend.agents.STATIC_SITE_IP", "127.0.0.1")
    monkeypatch.setattr("backend.agents.PKI_DIR", tmp_path / "no-pki")

    instance = CanaryInstance(
        id="c9cc2a7e-ff82-4dcf-8c87-5bdce65e2133", canary_type_id="2", task_id="1", iom_ids=["3"]
    )
    task = Task(id="1", company_id="1", prompt="RAG over the support inbox")
    artifact = SiteArtifact(domain="brightpath-support.com", html="<html></html>")

    asyncio.run(deploy_static_site(instance, artifact, task))

    domain = instance.metadata["domain"]
    zones = json.loads(endpoints_file.read_text())
    assert zones[domain]["instance_id"] == instance.id
    assert zones[domain]["endpoints"] == [{"iom_id": "3", "path_regex": _canary_endpoint_regex("2")}]


# --- deploy_canary_instance: structured output for static-site handlers ----


def test_deploy_canary_instance_requests_structured_output_for_static_site_handlers(tmp_path, monkeypatch):
    content_dir = tmp_path / "content"
    monkeypatch.setattr("backend.agents.STATIC_SITE_CONTENT_DIR", content_dir)
    monkeypatch.setattr("backend.agents.DNS_ZONES_FILE", tmp_path / "zones.json")
    monkeypatch.setattr("backend.agents.ENDPOINTS_FILE", tmp_path / "endpoints.json")
    monkeypatch.setattr("backend.agents.STATIC_SITE_IP", "127.0.0.1")
    monkeypatch.setattr("backend.agents.PKI_DIR", tmp_path / "no-pki")

    instance = CanaryInstance(id="ci-2", canary_type_id="1", task_id="1", iom_ids=["8"])
    task = Task(id="1", company_id="1", prompt="RAG on company data")
    canary_types = [CanaryType(id="1", name="Impersonation server")]

    llm_json = SiteArtifact(domain="brightpath-support.com", html="<html>hi</html>").model_dump_json()
    with patch("backend.agents.run_claude", return_value=llm_json) as mock_run_claude:
        asyncio.run(deploy_canary_instance(instance, task, canary_types))

    assert mock_run_claude.call_args.kwargs["output_json_schema"] == SiteArtifact.model_json_schema()
    assert instance.metadata["domain"] == "brightpath-support.com"
    assert (content_dir / "brightpath-support.com" / "index.html").read_text() == "<html>hi</html>"


# --- reconcile_canary_registrations -----------------------------------------


def test_reconcile_drops_entries_for_instances_that_no_longer_exist(tmp_path, monkeypatch):
    """data.canary_instances is in-memory only and resets on every backend
    restart (including uvicorn --reload firing on a source save), while
    these two files persist on disk regardless - a domain whose instance
    didn't survive the restart must stop resolving/registering, not keep
    404ing forever on every trigger attempt."""
    zones_file = tmp_path / "zones.json"
    endpoints_file = tmp_path / "endpoints.json"
    zones_file.write_text(json.dumps({"alive.example.com": "127.0.0.1", "dead.example.com": "127.0.0.1"}))
    endpoints_file.write_text(
        json.dumps(
            {
                "alive.example.com": {"instance_id": "alive-1", "endpoints": [{"iom_id": "1", "path_regex": "^/.*$"}]},
                "dead.example.com": {"instance_id": "dead-1", "endpoints": [{"iom_id": "1", "path_regex": "^/.*$"}]},
            }
        )
    )
    monkeypatch.setattr("backend.agents.DNS_ZONES_FILE", zones_file)
    monkeypatch.setattr("backend.agents.ENDPOINTS_FILE", endpoints_file)

    asyncio.run(reconcile_canary_registrations({"alive-1"}))

    assert json.loads(zones_file.read_text()) == {"alive.example.com": "127.0.0.1"}
    endpoints = json.loads(endpoints_file.read_text())
    assert list(endpoints.keys()) == ["alive.example.com"]


def test_reconcile_is_a_noop_when_files_are_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.agents.DNS_ZONES_FILE", tmp_path / "no-zones.json")
    monkeypatch.setattr("backend.agents.ENDPOINTS_FILE", tmp_path / "no-endpoints.json")

    asyncio.run(reconcile_canary_registrations(set()))  # must not raise

    assert not (tmp_path / "no-zones.json").exists()
    assert not (tmp_path / "no-endpoints.json").exists()
