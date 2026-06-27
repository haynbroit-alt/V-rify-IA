import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from app.engine import VerificationEngine
from app.kernel import ExecutionKernel
from app.ledger import ProofLedger
from app.models import (
    ActionState,
    AIActionPayload,
    ExecutionResult,
    ExecutionStatus,
    ProofRecord,
    StateTransition,
    VerificationReport,
    VerityResponse,
)

logger = logging.getLogger(__name__)


@dataclass
class _Context:
    """Mutable state carrier for a single action run."""

    action_id: str
    current: ActionState = ActionState.pending
    transitions: list[StateTransition] = field(default_factory=list)
    _phase_start: float = field(default_factory=time.time)

    def advance(self, to: ActionState, reason: Optional[str] = None) -> None:
        now = time.time()
        duration_ms = (now - self._phase_start) * 1000
        self.transitions.append(
            StateTransition(
                from_state=self.current,
                to_state=to,
                timestamp=now,
                duration_ms=round(duration_ms, 2),
                reason=reason,
            )
        )
        logger.info(
            "orchestrator.transition",
            extra={
                "action_id": self.action_id,
                "from": self.current,
                "to": to,
                "ms": round(duration_ms, 1),
                **({"reason": reason} if reason else {}),
            },
        )
        self.current = to
        self._phase_start = now


class ActionOrchestrator:
    """
    Single entry point that drives an action through the full VERITY CORE pipeline.
    Each phase is independently guarded; failures produce a FAILED_* state
    but the pipeline continues to sign and persist the outcome.
    """

    def __init__(self, kernel: ExecutionKernel, engine: VerificationEngine, ledger: ProofLedger):
        self._kernel = kernel
        self._engine = engine
        self._ledger = ledger

    def run(self, action_id: str, action: AIActionPayload) -> VerityResponse:
        ctx = _Context(action_id=action_id)
        result: Optional[ExecutionResult] = None
        report: Optional[VerificationReport] = None
        proof: Optional[ProofRecord] = None

        # ── Phase 1: Validate ────────────────────────────────────────────────
        # Pydantic already validated the payload at the gateway boundary.
        # This step records the transition and allows future pre-exec checks.
        ctx.advance(ActionState.validating_request)
        ctx.advance(ActionState.executing)

        # ── Phase 2: Execute ─────────────────────────────────────────────────
        try:
            result = self._kernel.execute(action.payload, action.constraints)
        except Exception as exc:
            ctx.advance(ActionState.failed_execution, str(exc))
            result = ExecutionResult(
                status=ExecutionStatus.failure,
                exit_code=-1,
                stderr=f"Kernel error: {exc}",
            )
        else:
            ctx.advance(ActionState.verifying)

        # ── Phase 3: Verify ──────────────────────────────────────────────────
        if ctx.current == ActionState.verifying:
            try:
                report = self._engine.verify(result, action.verification_rules, action.payload)
                ctx.advance(ActionState.signing)
            except Exception as exc:
                ctx.advance(ActionState.failed_verification, str(exc))

        if report is None:
            report = VerificationReport(
                passed=False,
                rules_evaluated=0,
                rules_passed=0,
                violations=["Verification phase did not complete"],
            )

        # ── Phase 4: Sign + Persist ──────────────────────────────────────────
        if ctx.current == ActionState.signing:
            ctx.advance(ActionState.persisting)

        try:
            proof = self._ledger.record(action_id, action.agent_id, action.payload, result)
        except Exception as exc:
            ctx.advance(ActionState.failed_persistence, str(exc))
        else:
            if ctx.current == ActionState.persisting:
                ctx.advance(ActionState.completed)

        # ── Compute final execution status ───────────────────────────────────
        final_status = result.status
        if not report.passed and final_status == ExecutionStatus.success:
            final_status = ExecutionStatus.rejected

        message = _message(ctx.current, report)
        return VerityResponse(
            action_id=action_id,
            state=ctx.current,
            status=final_status,
            execution=result,
            verification=report,
            proof=proof,
            transitions=ctx.transitions,
            message=message,
        )


def _message(state: ActionState, report: VerificationReport) -> str:
    if state == ActionState.completed:
        return (
            "Verified and signed." if report.passed else "Action rejected by verification engine."
        )  # noqa: E501
    return f"Pipeline halted at {state.value}."
