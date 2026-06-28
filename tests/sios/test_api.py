"""Integration tests for the SIOS FastAPI — mocks the orchestrator."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import sios.api.main as api_module
from sios.api.main import app

client = TestClient(app)

_MOCK_RESULT = {
    "answer": "The answer is 42.",
    "category": "coding",
    "code": "print(42)",
    "output": "42\n",
    "proofs": [{"action_id": "abc123", "verified": True, "proof": {}, "exit_code": 0}],
    "verified": True,
    "iterations": 1,
}


@pytest.fixture(autouse=True)
def reset_orc():
    api_module._orc = None
    yield
    api_module._orc = None


def test_health():
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ask_returns_answer():
    with patch("sios.api.main.Orchestrator") as MockOrc:
        MockOrc.return_value.ask.return_value = _MOCK_RESULT
        resp = client.post("/v1/ask", json={"query": "What is 6 × 7?"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "The answer is 42."
    assert data["category"] == "coding"
    assert data["verified"] is True


def test_ask_with_reset():
    with patch("sios.api.main.Orchestrator") as MockOrc:
        mock_instance = MockOrc.return_value
        mock_instance.ask.return_value = _MOCK_RESULT
        resp = client.post("/v1/ask", json={"query": "hello", "reset": True})

    assert resp.status_code == 200
    mock_instance.reset.assert_called_once()


def test_reset_session():
    with patch("sios.api.main.Orchestrator"):
        resp = client.delete("/v1/session")
    assert resp.status_code == 200
    assert resp.json()["status"] == "reset"


def test_history_returns_list():
    with patch("sios.api.main.Orchestrator") as MockOrc:
        MockOrc.return_value.history.return_value = []
        resp = client.get("/v1/history")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
