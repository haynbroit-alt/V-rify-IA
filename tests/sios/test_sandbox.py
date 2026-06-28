"""Unit tests for sios.sandbox.runner — mocks VERITY CORE."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sios.sandbox.runner import execute


@pytest.fixture()
def mock_verity_result():
    r = MagicMock()
    r.output = "42\n"
    r.exit_code = 0
    r.execution_time_ms = 15.0
    r.verified = True
    r.status = "SUCCESS"
    r.action_id = "test-action-id"
    r.proof = {"signature": "abc", "algorithm": "Ed25519"}
    r.violations = []
    r.security_flags = []
    return r


def test_execute_returns_expected_keys(mock_verity_result):
    with patch("sios.sandbox.runner.VerityClient") as MockClient:
        MockClient.return_value.run.return_value = mock_verity_result
        result = execute("print(42)", agent_id="test", api_url="http://localhost:8080")

    assert result["output"] == "42\n"
    assert result["exit_code"] == 0
    assert result["verified"] is True
    assert result["action_id"] == "test-action-id"
    assert "proof" in result
    assert result["success"] is True


def test_execute_failed_run(mock_verity_result):
    mock_verity_result.exit_code = 1
    mock_verity_result.output = "Traceback...\nNameError: name 'x' is not defined"
    mock_verity_result.verified = False
    mock_verity_result.status = "FAILED"

    with patch("sios.sandbox.runner.VerityClient") as MockClient:
        MockClient.return_value.run.return_value = mock_verity_result
        result = execute("print(x)", agent_id="test", api_url="http://localhost:8080")

    assert result["exit_code"] == 1
    assert result["success"] is False
    assert result["verified"] is False


def test_execute_clamps_timeout(mock_verity_result):
    with patch("sios.sandbox.runner.VerityClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.run.return_value = mock_verity_result
        execute("pass", agent_id="test", timeout=999, api_url="http://localhost:8080")
        _, kwargs = mock_client.run.call_args
        assert kwargs["timeout"] <= 30
