"""
backend/github_canary.py calls the real GitHub REST API - these tests mock
requests.post/put/get throughout so the suite never actually creates a repo,
issue, comment, PR, or hits GitHub in any way, same principle as never
invoking the real `claude` CLI or canarytokens.org (see tests/test_agents.py
and tests/test_thinkst.py).
"""

import asyncio
from unittest.mock import MagicMock, patch

from backend.github_canary import (
    _create_branch,
    _create_issue,
    _create_issue_comment,
    _create_pull_request,
    _get_branch_sha,
    _open_stray_pull_request,
    _repo_name,
    _seed_credential_issue,
    deploy_github_repo,
    poll_github_repos_once,
)
from backend.models import CanaryInstance, Task


def test_deploy_github_repo_noop_when_token_not_configured(monkeypatch):
    monkeypatch.setattr("backend.github_canary.GITHUB_TOKEN", None)
    instance = CanaryInstance(id="ci-1", canary_type_id="5", task_id="1", iom_ids=["3"])
    task = Task(id="1", company_id="1", prompt="Find sample solutions")

    with patch("requests.post") as mock_post:
        asyncio.run(deploy_github_repo(instance, "# fake readme", task))

    mock_post.assert_not_called()
    assert instance.deployment_health == "active"
    assert instance.target_url is not None
    assert "github_repo" not in instance.metadata


def test_deploy_github_repo_creates_repo_and_seeds_readme(monkeypatch):
    """Orchestration test: stubs out the credential-issue and stray-PR
    helpers (covered by their own tests below) to isolate deploy_github_repo's
    core repo-creation/README/registration behavior."""
    monkeypatch.setattr("backend.github_canary.GITHUB_TOKEN", "fake-token")
    monkeypatch.setattr("backend.github_canary._github_repos", [])
    monkeypatch.setattr("backend.github_canary._seed_credential_issue", lambda *a, **k: None)
    monkeypatch.setattr("backend.github_canary._open_stray_pull_request", lambda *a, **k: None)
    monkeypatch.setattr("backend.github_canary._pulls_count", lambda full_name: 0)

    create_response = MagicMock()
    create_response.json.return_value = {
        "full_name": "bot-account/find-sample-solutions-ci1abcde",
        "html_url": "https://github.com/bot-account/find-sample-solutions-ci1abcde",
        "default_branch": "main",
    }
    put_response = MagicMock()

    instance = CanaryInstance(id="ci1abcde-0000-0000-0000-000000000000", canary_type_id="5", task_id="1", iom_ids=["3"])
    task = Task(id="1", company_id="1", prompt="Find sample solutions")

    with patch("requests.post", return_value=create_response) as mock_post, \
         patch("requests.put", return_value=put_response) as mock_put:
        asyncio.run(deploy_github_repo(instance, "# fake readme", task))

    assert mock_post.call_args.kwargs["json"]["name"] == _repo_name(instance, task)
    assert mock_put.call_args.args[0].endswith("/contents/README.md")
    assert instance.metadata["github_repo"] == "bot-account/find-sample-solutions-ci1abcde"
    assert instance.target_url == "https://github.com/bot-account/find-sample-solutions-ci1abcde"
    assert instance.deployment_health == "active"

    from backend.github_canary import _github_repos

    assert len(_github_repos) == 1
    assert _github_repos[0]["instance_id"] == instance.id
    assert _github_repos[0]["iom_id"] == "3"
    assert _github_repos[0]["baseline_pulls"] == 0
    assert _github_repos[0]["reported"] is False


def test_deploy_github_repo_leaves_pending_on_create_failure(monkeypatch):
    monkeypatch.setattr("backend.github_canary.GITHUB_TOKEN", "fake-token")
    monkeypatch.setattr("backend.github_canary._github_repos", [])

    instance = CanaryInstance(id="ci-2", canary_type_id="5", task_id="1", iom_ids=["3"])
    task = Task(id="1", company_id="1", prompt="Find sample solutions")

    import requests

    with patch("requests.post", side_effect=requests.RequestException("boom")):
        asyncio.run(deploy_github_repo(instance, "# fake readme", task))

    assert instance.target_url is None
    assert instance.deployment_health == "pending"


# --- Issues / comments / PRs (new GitHub API helpers) -----------------------


def test_create_issue_posts_title_and_body():
    resp = MagicMock()
    resp.json.return_value = {"number": 42, "html_url": "https://github.com/x/y/issues/42"}
    with patch("requests.post", return_value=resp) as mock_post:
        result = _create_issue("bot/repo", "title", "body")

    assert result["number"] == 42
    assert mock_post.call_args.args[0] == "https://api.github.com/repos/bot/repo/issues"
    assert mock_post.call_args.kwargs["json"] == {"title": "title", "body": "body"}


def test_create_issue_comment_posts_body():
    resp = MagicMock()
    with patch("requests.post", return_value=resp) as mock_post:
        assert _create_issue_comment("bot/repo", 42, "comment body") is True
    assert mock_post.call_args.args[0] == "https://api.github.com/repos/bot/repo/issues/42/comments"
    assert mock_post.call_args.kwargs["json"] == {"body": "comment body"}


def test_get_branch_sha_returns_object_sha():
    resp = MagicMock()
    resp.json.return_value = {"object": {"sha": "deadbeef"}}
    with patch("requests.get", return_value=resp):
        assert _get_branch_sha("bot/repo", "main") == "deadbeef"


def test_create_branch_posts_ref():
    resp = MagicMock()
    with patch("requests.post", return_value=resp) as mock_post:
        assert _create_branch("bot/repo", "patch-1", "deadbeef") is True
    assert mock_post.call_args.kwargs["json"] == {"ref": "refs/heads/patch-1", "sha": "deadbeef"}


def test_create_pull_request_posts_head_and_base():
    resp = MagicMock()
    resp.json.return_value = {"number": 7}
    with patch("requests.post", return_value=resp) as mock_post:
        result = _create_pull_request("bot/repo", "title", "body", head="patch-1", base="main")

    assert result["number"] == 7
    assert mock_post.call_args.kwargs["json"] == {
        "title": "title",
        "body": "body",
        "head": "patch-1",
        "base": "main",
    }


def test_seed_credential_issue_noops_when_thinkst_not_configured(monkeypatch):
    monkeypatch.setattr("backend.thinkst.THINKST_ALERT_EMAIL", None)
    instance = CanaryInstance(id="ci-3", canary_type_id="5", task_id="1", iom_ids=["3"])
    task = Task(id="1", company_id="1", prompt="Find sample solutions")

    with patch("requests.post") as mock_post:
        assert _seed_credential_issue("bot/repo", instance, task) is None
    mock_post.assert_not_called()


def test_seed_credential_issue_pastes_aws_credential_into_a_comment(monkeypatch):
    monkeypatch.setattr("backend.thinkst.THINKST_ALERT_EMAIL", "test@example.com")
    instance = CanaryInstance(id="ci-4", canary_type_id="5", task_id="1", iom_ids=["3"])
    task = Task(id="1", company_id="1", prompt="Find sample solutions")

    aws_response = MagicMock()
    aws_response.json.return_value = {
        "token": "tok-aws",
        "auth_token": "auth-aws",
        "aws_access_key_id": "AKIAFAKE",
        "aws_secret_access_key": "fakesecret",
        "region": "us-east-1",
    }
    issue_response = MagicMock()
    issue_response.json.return_value = {"number": 1}
    comment_response = MagicMock()

    with patch("requests.post", side_effect=[aws_response, issue_response, comment_response]) as mock_post:
        result = _seed_credential_issue("bot/repo", instance, task)

    assert result["aws_access_key_id"] == "AKIAFAKE"
    comment_body = mock_post.call_args_list[2].kwargs["json"]["body"]
    assert "AKIAFAKE" in comment_body
    assert "fakesecret" in comment_body


def test_open_stray_pull_request_creates_branch_commit_and_pr():
    sha_response = MagicMock()
    sha_response.json.return_value = {"object": {"sha": "deadbeef"}}
    branch_response = MagicMock()
    put_response = MagicMock()
    pr_response = MagicMock()

    with patch("requests.get", return_value=sha_response), \
         patch("requests.post", side_effect=[branch_response, pr_response]) as mock_post, \
         patch("requests.put", return_value=put_response) as mock_put:
        _open_stray_pull_request("bot/repo", "main", Task(id="1", company_id="1", prompt="p"))

    assert mock_put.call_args.kwargs["json"]["branch"].startswith("patch-")
    pr_call = mock_post.call_args_list[1]
    assert pr_call.kwargs["json"]["base"] == "main"


def test_open_stray_pull_request_bails_if_branch_sha_lookup_fails():
    import requests

    with patch("requests.get", side_effect=requests.RequestException("boom")), \
         patch("requests.post") as mock_post:
        _open_stray_pull_request("bot/repo", "main", Task(id="1", company_id="1", prompt="p"))

    mock_post.assert_not_called()


# --- Polling ------------------------------------------------------------


def test_poll_github_repos_once_triggers_on_clone_increase(monkeypatch):
    instance = CanaryInstance(id="ci-5", canary_type_id="5", task_id="1", iom_ids=["3"])
    entry = {
        "instance_id": "ci-5",
        "iom_id": "3",
        "full_name": "bot-account/some-repo",
        "baseline_clones": 0,
        "baseline_views": 0,
        "baseline_pulls": 0,
        "reported": False,
    }
    monkeypatch.setattr("backend.github_canary._github_repos", [entry])

    clones_resp = MagicMock()
    clones_resp.json.return_value = {"count": 3}
    views_resp = MagicMock()
    views_resp.json.return_value = {"count": 0}
    pulls_resp = MagicMock()
    pulls_resp.json.return_value = []

    triggered = []

    def fake_trigger(inst, iom_id):
        triggered.append((inst.id, iom_id))

    with patch("requests.get", side_effect=[clones_resp, views_resp, pulls_resp]):
        asyncio.run(poll_github_repos_once([instance], fake_trigger))

    assert triggered == [("ci-5", "3")]
    assert entry["reported"] is True


def test_poll_github_repos_once_skips_when_no_activity(monkeypatch):
    instance = CanaryInstance(id="ci-6", canary_type_id="5", task_id="1", iom_ids=["3"])
    entry = {
        "instance_id": "ci-6",
        "iom_id": "3",
        "full_name": "bot-account/some-repo",
        "baseline_clones": 0,
        "baseline_views": 0,
        "baseline_pulls": 0,
        "reported": False,
    }
    monkeypatch.setattr("backend.github_canary._github_repos", [entry])

    zero_resp = MagicMock()
    zero_resp.json.return_value = {"count": 0}
    empty_pulls = MagicMock()
    empty_pulls.json.return_value = []

    triggered = []

    with patch("requests.get", side_effect=[zero_resp, zero_resp, empty_pulls]):
        asyncio.run(poll_github_repos_once([instance], lambda inst, iom_id: triggered.append(iom_id)))

    assert triggered == []
    assert entry["reported"] is False
