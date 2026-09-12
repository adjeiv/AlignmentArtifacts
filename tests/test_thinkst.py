"""
backend/thinkst.py calls the real canarytokens.org API - these tests mock
requests.post/get throughout so the suite never actually creates or checks
a real Thinkst token.
"""

import asyncio
from unittest.mock import MagicMock, patch

from backend.thinkst import create_canarytoken, poll_thinkst_tokens_once
from backend.models import CanaryInstance


def test_create_canarytoken_noops_when_email_not_configured(monkeypatch):
    monkeypatch.setattr("backend.thinkst.THINKST_ALERT_EMAIL", None)
    with patch("requests.post") as mock_post:
        assert create_canarytoken("aws_keys", "memo") is None
    mock_post.assert_not_called()


def test_create_canarytoken_posts_generate_request(monkeypatch):
    monkeypatch.setattr("backend.thinkst.THINKST_ALERT_EMAIL", "test@example.com")
    fake_response = MagicMock()
    fake_response.json.return_value = {
        "token": "tok123",
        "auth_token": "auth123",
        "aws_access_key_id": "AKIAFAKE",
        "aws_secret_access_key": "fakesecret",
        "region": "us-east-1",
    }
    with patch("requests.post", return_value=fake_response) as mock_post:
        result = create_canarytoken("aws_keys", "some memo")

    assert result["aws_access_key_id"] == "AKIAFAKE"
    kwargs = mock_post.call_args.kwargs
    assert kwargs["json"] == {"token_type": "aws_keys", "memo": "some memo", "email": "test@example.com"}


def test_create_canarytoken_returns_none_on_error_response(monkeypatch):
    monkeypatch.setattr("backend.thinkst.THINKST_ALERT_EMAIL", "test@example.com")
    fake_response = MagicMock()
    fake_response.json.return_value = {"error": "2", "error_message": "No memo supplied"}
    with patch("requests.post", return_value=fake_response):
        assert create_canarytoken("aws_keys", "") is None


def test_poll_thinkst_tokens_once_triggers_on_a_hit(monkeypatch):
    instance = CanaryInstance(id="ci-thinkst", canary_type_id="1", task_id="1", iom_ids=["4"])
    entry = {"token": "tok", "auth": "auth", "instance_id": "ci-thinkst", "iom_id": "4", "reported": False}
    monkeypatch.setattr("backend.thinkst._thinkst_tokens", [entry])

    fired_response = MagicMock()
    fired_response.json.return_value = {"history": {"hits": [{"time_of_hit": 123}]}}

    triggered = []

    with patch("requests.get", return_value=fired_response):
        asyncio.run(poll_thinkst_tokens_once([instance], lambda inst, iom_id: triggered.append((inst.id, iom_id))))

    assert triggered == [("ci-thinkst", "4")]
    assert entry["reported"] is True


def test_poll_thinkst_tokens_once_skips_unfired_tokens(monkeypatch):
    instance = CanaryInstance(id="ci-thinkst-2", canary_type_id="1", task_id="1", iom_ids=["4"])
    entry = {"token": "tok", "auth": "auth", "instance_id": "ci-thinkst-2", "iom_id": "4", "reported": False}
    monkeypatch.setattr("backend.thinkst._thinkst_tokens", [entry])

    unfired_response = MagicMock()
    unfired_response.json.return_value = {"history": {"hits": []}}

    triggered = []

    with patch("requests.get", return_value=unfired_response):
        asyncio.run(poll_thinkst_tokens_once([instance], lambda inst, iom_id: triggered.append(iom_id)))

    assert triggered == []
    assert entry["reported"] is False
