import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITY_DB_PATH", str(tmp_path / "test_gateway.db"))
    from pathlib import Path

    import app.ledger as ledger_mod

    ledger_mod.DB_PATH = Path(os.environ["VERITY_DB_PATH"])


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_public_key_endpoint(client):
    resp = client.get("/v1/public-key")
    assert resp.status_code == 200
    pem = resp.json()["public_key"]
    assert "BEGIN PUBLIC KEY" in pem


def test_verify_valid_code(client):
    payload = {
        "agent_id": "test-agent",
        "action_type": "execute_code",
        "payload": "print('verity works')",
        "constraints": {"language": "python", "timeout": 5},
        "verification_rules": [
            {"rule_type": "exit_code", "value": 0},
            {"rule_type": "output_contains", "value": "verity works"},
        ],
    }
    resp = client.post("/v1/verify", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("SUCCESS", "REJECTED")
    assert data["action_id"] != ""
    assert data["proof"]["signature"] != ""
    assert data["verification"]["rules_evaluated"] == 2
    # v0.3: orchestrator fields
    assert data["state"] in ("COMPLETED", "FAILED_EXECUTION", "FAILED_PERSISTENCE")
    assert len(data["transitions"]) >= 3


def test_verify_failing_code(client):
    payload = {
        "agent_id": "bad-agent",
        "payload": "raise RuntimeError('intentional failure')",
        "constraints": {"language": "python", "timeout": 5},
        "verification_rules": [{"rule_type": "exit_code", "value": 0}],
    }
    resp = client.post("/v1/verify", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("FAILURE", "REJECTED")
    assert len(data["verification"]["violations"]) > 0


def test_get_proof_after_verify(client):
    payload = {
        "agent_id": "probe-agent",
        "payload": "print(99)",
        "constraints": {"language": "python", "timeout": 5},
    }
    resp = client.post("/v1/verify", json=payload)
    action_id = resp.json()["action_id"]

    proof_resp = client.get(f"/v1/proof/{action_id}")
    assert proof_resp.status_code == 200
    assert proof_resp.json()["proof"]["action_id"] == action_id


def test_get_proof_not_found(client):
    resp = client.get("/v1/proof/nonexistent-id")
    assert resp.status_code == 404


def test_security_flags_surfaced(client):
    payload = {
        "agent_id": "attacker",
        "payload": 'eval(\'__import__("os").system("ls")\')',
        "constraints": {"language": "python", "timeout": 5},
    }
    resp = client.post("/v1/verify", json=payload)
    data = resp.json()
    assert len(data["verification"]["security_flags"]) > 0
