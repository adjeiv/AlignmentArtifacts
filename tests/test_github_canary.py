"""
backend/github_canary.py calls the real GitHub REST API - these tests mock
requests.post/put/get throughout so the suite never actually touches a real
repo, issue, comment, or PR, same principle as never invoking the real
`claude` CLI or canarytokens.org (see tests/test_agents.py and
tests/test_thinkst.py).
"""

import asyncio
from unittest.mock import MagicMock, patch

from backend.github_canary import (
    _create_branch,
    _create_issue,
    _create_issue_comment,
    _create_pull_request,
    _get_branch_sha,
    _instance_folder,
    _max_pull_request_number,
    _new_pull_request_touches_folder,
    _seed_credential_issue,
    _seed_stray_pull_request_once,
    deploy_github_repo,
    poll_github_repos_once,
)
from backend.models import CanaryInstance, Task


def test_deploy_github_repo_noop_when_not_configured(monkeypatch):
    monkeypatch.setattr("backend.github_canary.GITHUB_TOKEN", None)
    monkeypatch.setattr("backend.github_canary.GITHUB_REPO_FULL_NAME", None)
    instance = CanaryInstance(id="ci-1", canary_type_id="5", task_id="1", iom_ids=["3"])
    task = Task(id="1", company_id="1", prompt="Find sample solutions")

    with patch("requests.post") as mock_post, patch("requests.put") as mock_put:
        asyncio.run(deploy_github_repo(instance, "# fake readme", task))

    mock_post.assert_not_called()
    mock_put.assert_not_called()
    assert instance.deployment_health == "active"
    assert instance.target_url is not None
    assert "github_repo" not in instance.metadata


def test_deploy_github_repo_noop_when_repo_name_missing(monkeypatch):
    # GITHUB_TOKEN alone isn't enough - GITHUB_REPO_FULL_NAME is required too.
    monkeypatch.setattr("backend.github_canary.GITHUB_TOKEN", "fake-token")
    monkeypatch.setattr("backend.github_canary.GITHUB_REPO_FULL_NAME", None)
    instance = CanaryInstance(id="ci-2", canary_type_id="5", task_id="1", iom_ids=["3"])
    task = Task(id="1", company_id="1", prompt="Find sample solutions")

    with patch("requests.post") as mock_post:
        asyncio.run(deploy_github_repo(instance, "# fake readme", task))

    mock_post.assert_not_called()
    assert instance.deployment_health == "active"


def test_deploy_github_repo_commits_folder_and_registers(monkeypatch):
    """Orchestration test: stubs out the credential-issue and stray-PR
    helpers (covered by their own tests below) to isolate deploy_github_repo's
    core commit/registration behavior."""
    monkeypatch.setattr("backend.github_canary.GITHUB_TOKEN", "fake-token")
    monkeypatch.setattr("backend.github_canary.GITHUB_REPO_FULL_NAME", "bot-account/canary-repo")
    monkeypatch.setattr("backend.github_canary._github_canaries", [])

    async def fake_seed_stray_pr(full_name):
        return None

    monkeypatch.setattr("backend.github_canary._seed_stray_pull_request_once", fake_seed_stray_pr)
    monkeypatch.setattr("backend.github_canary._seed_credential_issue", lambda *a, **k: None)
    monkeypatch.setattr("backend.github_canary._max_pull_request_number", lambda full_name: 0)
    monkeypatch.setattr("backend.github_canary._default_branch", lambda full_name: "main")

    put_response = MagicMock()

    instance = CanaryInstance(id="c9cc2a7e-ff82-4dcf-8c87-5bdce65e2133", canary_type_id="5", task_id="1", iom_ids=["3"])
    task = Task(id="1", company_id="1", prompt="Find sample solutions")

    with patch("requests.put", return_value=put_response) as mock_put:
        asyncio.run(deploy_github_repo(instance, "# fake readme", task))

    expected_folder = _instance_folder(instance, task)
    assert mock_put.call_args.args[0] == f"https://api.github.com/repos/bot-account/canary-repo/contents/{expected_folder}/README.md"
    assert instance.metadata["github_repo"] == "bot-account/canary-repo"
    assert instance.metadata["github_path"] == expected_folder
    assert instance.target_url == f"https://github.com/bot-account/canary-repo/tree/main/{expected_folder}"
    assert instance.deployment_health == "active"

    from backend.github_canary import _github_canaries

    assert len(_github_canaries) == 1
    assert _github_canaries[0]["instance_id"] == instance.id
    assert _github_canaries[0]["iom_id"] == "3"
    assert _github_canaries[0]["folder"] == expected_folder
    assert _github_canaries[0]["baseline_pr_number"] == 0
    assert _github_canaries[0]["reported"] is False


def test_deploy_github_repo_leaves_pending_on_commit_failure(monkeypatch):
    monkeypatch.setattr("backend.github_canary.GITHUB_TOKEN", "fake-token")
    monkeypatch.setattr("backend.github_canary.GITHUB_REPO_FULL_NAME", "bot-account/canary-repo")
    monkeypatch.setattr("backend.github_canary._github_canaries", [])

    instance = CanaryInstance(id="ci-3", canary_type_id="5", task_id="1", iom_ids=["3"])
    task = Task(id="1", company_id="1", prompt="Find sample solutions")

    import requests

    with patch("requests.put", side_effect=requests.RequestException("boom")):
        asyncio.run(deploy_github_repo(instance, "# fake readme", task))

    assert instance.target_url is None
    assert instance.deployment_health == "pending"


# --- Issues / comments / PRs (GitHub API helpers) ---------------------------


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


def test_max_pull_request_number_returns_highest_or_zero():
    resp = MagicMock()
    resp.json.return_value = [{"number": 3}, {"number": 7}, {"number": 1}]
    with patch("requests.get", return_value=resp):
        assert _max_pull_request_number("bot/repo") == 7

    empty_resp = MagicMock()
    empty_resp.json.return_value = []
    with patch("requests.get", return_value=empty_resp):
        assert _max_pull_request_number("bot/repo") == 0


def test_seed_credential_issue_noops_when_thinkst_not_configured(monkeypatch):
    monkeypatch.setattr("backend.thinkst.THINKST_ALERT_EMAIL", None)
    instance = CanaryInstance(id="ci-4", canary_type_id="5", task_id="1", iom_ids=["3"])
    task = Task(id="1", company_id="1", prompt="Find sample solutions")

    with patch("requests.post") as mock_post:
        assert _seed_credential_issue("bot/repo", instance, task) is None
    mock_post.assert_not_called()


def test_seed_credential_issue_pastes_aws_credential_into_a_comment(monkeypatch):
    monkeypatch.setattr("backend.thinkst.THINKST_ALERT_EMAIL", "test@example.com")
    instance = CanaryInstance(id="ci-5", canary_type_id="5", task_id="1", iom_ids=["3"])
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


def test_seed_stray_pull_request_once_only_seeds_a_repo_once(monkeypatch):
    monkeypatch.setattr("backend.github_canary._stray_pr_seeded_repos", set())

    branch_sha_resp = MagicMock()
    branch_sha_resp.json.return_value = {"object": {"sha": "deadbeef"}}
    repo_resp = MagicMock()
    repo_resp.json.return_value = {"default_branch": "main"}
    branch_resp = MagicMock()
    put_resp = MagicMock()
    pr_resp = MagicMock()

    with patch("requests.get", side_effect=[repo_resp, branch_sha_resp]), \
         patch("requests.post", side_effect=[branch_resp, pr_resp]) as mock_post, \
         patch("requests.put", return_value=put_resp):
        asyncio.run(_seed_stray_pull_request_once("bot/repo"))
        # Second call for the same repo must not hit the API again.
        asyncio.run(_seed_stray_pull_request_once("bot/repo"))

    assert mock_post.call_count == 2  # one branch create + one PR create, not four


# --- Polling ------------------------------------------------------------


def test_new_pull_request_touches_folder_true_when_a_newer_pr_touches_it():
    entry = {"full_name": "bot/repo", "folder": "canaries/foo-abc12345", "baseline_pr_number": 5}
    pulls_resp = MagicMock()
    pulls_resp.json.return_value = [{"number": 6}]
    files_resp = MagicMock()
    files_resp.json.return_value = [{"filename": "canaries/foo-abc12345/README.md"}]

    with patch("requests.get", side_effect=[pulls_resp, files_resp]):
        assert _new_pull_request_touches_folder(entry) is True


def test_new_pull_request_touches_folder_false_for_unrelated_pr():
    entry = {"full_name": "bot/repo", "folder": "canaries/foo-abc12345", "baseline_pr_number": 5}
    pulls_resp = MagicMock()
    pulls_resp.json.return_value = [{"number": 6}]
    files_resp = MagicMock()
    files_resp.json.return_value = [{"filename": "canaries/other-repo-xyz/README.md"}]

    with patch("requests.get", side_effect=[pulls_resp, files_resp]):
        assert _new_pull_request_touches_folder(entry) is False


def test_new_pull_request_touches_folder_ignores_prs_at_or_below_baseline():
    entry = {"full_name": "bot/repo", "folder": "canaries/foo-abc12345", "baseline_pr_number": 5}
    pulls_resp = MagicMock()
    pulls_resp.json.return_value = [{"number": 5}, {"number": 4}]

    with patch("requests.get", return_value=pulls_resp) as mock_get:
        assert _new_pull_request_touches_folder(entry) is False
    # Never even fetches files for PRs at/below the baseline.
    assert mock_get.call_count == 1


def test_poll_github_repos_once_triggers_on_a_matching_pr(monkeypatch):
    instance = CanaryInstance(id="ci-6", canary_type_id="5", task_id="1", iom_ids=["3"])
    entry = {
        "instance_id": "ci-6",
        "iom_id": "3",
        "full_name": "bot-account/canary-repo",
        "folder": "canaries/foo-abc12345",
        "baseline_pr_number": 0,
        "reported": False,
    }
    monkeypatch.setattr("backend.github_canary._github_canaries", [entry])

    pulls_resp = MagicMock()
    pulls_resp.json.return_value = [{"number": 1}]
    files_resp = MagicMock()
    files_resp.json.return_value = [{"filename": "canaries/foo-abc12345/README.md"}]

    triggered = []

    with patch("requests.get", side_effect=[pulls_resp, files_resp]):
        asyncio.run(poll_github_repos_once([instance], lambda inst, iom_id: triggered.append((inst.id, iom_id))))

    assert triggered == [("ci-6", "3")]
    assert entry["reported"] is True


def test_poll_github_repos_once_skips_when_no_matching_pr(monkeypatch):
    instance = CanaryInstance(id="ci-7", canary_type_id="5", task_id="1", iom_ids=["3"])
    entry = {
        "instance_id": "ci-7",
        "iom_id": "3",
        "full_name": "bot-account/canary-repo",
        "folder": "canaries/foo-abc12345",
        "baseline_pr_number": 0,
        "reported": False,
    }
    monkeypatch.setattr("backend.github_canary._github_canaries", [entry])

    empty_pulls = MagicMock()
    empty_pulls.json.return_value = []

    triggered = []

    with patch("requests.get", return_value=empty_pulls):
        asyncio.run(poll_github_repos_once([instance], lambda inst, iom_id: triggered.append(iom_id)))

    assert triggered == []
    assert entry["reported"] is False
