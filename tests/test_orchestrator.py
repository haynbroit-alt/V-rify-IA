import os
from unittest.mock import MagicMock

import pytest

from app.models import (
    ActionState,
    AIActionPayload,
    ExecutionConstraints,
    ExecutionStatus,
    Language,
    VerificationRule,
)
from app.orchestrator import ActionOrchestrator


def _make_orchestrator(kernel=None, engine=None, ledger=None):
    from app.engine import VerificationEngine
    from app.kernel import ExecutionKernel
    from app.ledger import ProofLedger

    return ActionOrchestrator(
        kernel=kernel or ExecutionKernel(),
        engine=engine or VerificationEngine(),
        ledger=ledger or ProofLedger(),
    )


def _action(payload="print('ok')", rules=None):
    return AIActionPayload(
        agent_id="test-agent",
        payload=payload,
        constraints=ExecutionConstraints(language=Language.python, timeout=5),
        verification_rules=rules or [],
    )


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITY_DB_PATH", str(tmp_path / "orch_test.db"))
    monkeypatch.setenv("VERITY_ALLOW_SUBPROCESS_FALLBACK", "true")
    from pathlib import Path

    import app.ledger as ledger_mod

    ledger_mod.DB_PATH = Path(os.environ["VERITY_DB_PATH"])


# ── Happy path ────────────────────────────────────────────────────────────────


def test_full_pipeline_reaches_completed():
    orch = _make_orchestrator()
    resp = orch.run("action-001", _action())

    assert resp.state == ActionState.completed
    assert resp.status == ExecutionStatus.success
    assert resp.proof is not None
    assert resp.verification is not None


def test_transitions_are_ordered_and_complete():
    orch = _make_orchestrator()
    resp = orch.run("action-002", _action())

    states = [t.to_state for t in resp.transitions]
    assert ActionState.validating_request in states
    assert ActionState.executing in states
    assert ActionState.verifying in states
    assert ActionState.signing in states
    assert ActionState.persisting in states
    assert ActionState.completed in states


def test_transitions_have_positive_durations():
    orch = _make_orchestrator()
    resp = orch.run("action-003", _action())
    for t in resp.transitions:
        assert t.duration_ms >= 0
        assert t.timestamp > 0


def test_transitions_are_chronological():
    orch = _make_orchestrator()
    resp = orch.run("action-004", _action())
    timestamps = [t.timestamp for t in resp.transitions]
    assert timestamps == sorted(timestamps)


def test_rule_violation_reaches_completed_with_rejected_status():
    rules = [VerificationRule(rule_type="exit_code", value=99)]
    orch = _make_orchestrator()
    resp = orch.run("action-005", _action(rules=rules))

    assert resp.state == ActionState.completed
    assert resp.status == ExecutionStatus.rejected
    assert resp.verification is not None
    assert not resp.verification.passed


# ── Kernel failure handling ───────────────────────────────────────────────────


def test_kernel_exception_produces_failed_execution_state():
    bad_kernel = MagicMock()
    bad_kernel.execute.side_effect = RuntimeError("Docker daemon not running")

    orch = _make_orchestrator(kernel=bad_kernel)
    resp = orch.run("action-006", _action())

    states = [t.to_state for t in resp.transitions]
    assert ActionState.failed_execution in states
    assert resp.execution.status == ExecutionStatus.failure
    # proof is still recorded
    assert resp.proof is not None


def test_failed_execution_transition_carries_reason():
    bad_kernel = MagicMock()
    bad_kernel.execute.side_effect = RuntimeError("boom")

    orch = _make_orchestrator(kernel=bad_kernel)
    resp = orch.run("action-007", _action())

    failed_t = next(t for t in resp.transitions if t.to_state == ActionState.failed_execution)
    assert "boom" in failed_t.reason


# ── Ledger failure handling ───────────────────────────────────────────────────


def test_persistence_failure_produces_failed_persistence_state():
    bad_ledger = MagicMock()
    bad_ledger.record.side_effect = OSError("disk full")

    orch = _make_orchestrator(ledger=bad_ledger)
    resp = orch.run("action-008", _action())

    states = [t.to_state for t in resp.transitions]
    assert ActionState.failed_persistence in states
    assert resp.proof is None


# ── Proof integrity ───────────────────────────────────────────────────────────


def test_proof_signature_is_valid():
    from app.ledger import ProofLedger

    orch = _make_orchestrator()
    resp = orch.run("action-009", _action())

    ledger = ProofLedger()
    assert ledger.verify_signature(resp.proof) is True


def test_proof_action_id_matches_request():
    orch = _make_orchestrator()
    resp = orch.run("my-unique-id", _action())
    assert resp.proof.action_id == "my-unique-id"
    assert resp.action_id == "my-unique-id"


def test_proof_contains_key_id_and_algorithm():
    orch = _make_orchestrator()
    resp = orch.run("action-key-id", _action())

    assert resp.proof is not None
    assert len(resp.proof.key_id) == 16  # 16-char hex fingerprint
    assert resp.proof.algorithm == "Ed25519"
