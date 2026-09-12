"""
backend/github_canary.py calls the real GitHub REST API - these tests mock
requests.post/put/get throughout so the suite never actually creates a repo
or hits GitHub, same principle as never invoking the real `claude` CLI or
canarytokens.org (see tests/test_agents.py).
"""

import asyncio
from unittest.mock import MagicMock, patch

from backend.github_canary import (
    _repo_name,
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
    monkeypatch.setattr("backend.github_canary.GITHUB_TOKEN", "fake-token")
    monkeypatch.setattr("backend.github_canary._github_repos", [])

    create_response = MagicMock()
    create_response.json.return_value = {
        "full_name": "bot-account/find-sample-solutions-ci1abcde",
        "html_url": "https://github.com/bot-account/find-sample-solutions-ci1abcde",
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


def test_poll_github_repos_once_triggers_on_clone_increase(monkeypatch):
    instance = CanaryInstance(id="ci-3", canary_type_id="5", task_id="1", iom_ids=["3"])
    entry = {
        "instance_id": "ci-3",
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

    assert triggered == [("ci-3", "3")]
    assert entry["reported"] is True


def test_poll_github_repos_once_skips_when_no_activity(monkeypatch):
    instance = CanaryInstance(id="ci-4", canary_type_id="5", task_id="1", iom_ids=["3"])
    entry = {
        "instance_id": "ci-4",
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
