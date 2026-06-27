import os

import pytest

from app.ledger import ProofLedger
from app.models import ExecutionResult, ExecutionStatus


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITY_DB_PATH", str(tmp_path / "test_ledger.db"))
    from pathlib import Path

    import app.ledger as ledger_mod

    ledger_mod.DB_PATH = Path(os.environ["VERITY_DB_PATH"])


@pytest.fixture
def ledger():
    return ProofLedger()


def _result():
    return ExecutionResult(
        stdout="42\n",
        exit_code=0,
        status=ExecutionStatus.success,
        execution_time_ms=12.5,
    )


def test_record_and_retrieve(ledger):
    record = ledger.record("action-1", "agent-007", "print(42)", _result())
    assert record.action_id == "action-1"
    assert record.agent_id == "agent-007"
    assert len(record.signature) == 64
    assert record.payload_hash != ""
    assert record.result_hash != ""

    retrieved = ledger.get("action-1")
    assert retrieved is not None
    assert retrieved.action_id == "action-1"
    assert retrieved.signature == record.signature


def test_signature_valid(ledger):
    record = ledger.record("action-2", "agent-x", "x=1", _result())
    assert ledger.verify_signature(record) is True


def test_signature_invalid_on_tamper(ledger):
    record = ledger.record("action-3", "agent-x", "x=1", _result())
    record.result_hash = "tampered"
    assert ledger.verify_signature(record) is False


def test_get_nonexistent(ledger):
    assert ledger.get("does-not-exist") is None


def test_deterministic_hash(ledger):
    r1 = ledger.record("a1", "ag1", "print(1)", _result())
    r2 = ledger.record("a2", "ag1", "print(1)", _result())
    assert r1.payload_hash == r2.payload_hash
