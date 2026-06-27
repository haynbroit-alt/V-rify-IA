import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status

from app.config import get_settings
from app.engine import VerificationEngine
from app.kernel import ExecutionKernel
from app.ledger import ProofLedger
from app.logging_config import configure_logging
from app.models import (
    AIActionPayload,
    ExecutionStatus,
    VerityResponse,
)

configure_logging()
logger = logging.getLogger(__name__)

settings = get_settings()
kernel = ExecutionKernel()
engine = VerificationEngine()
ledger = ProofLedger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("VERITY CORE gateway starting", extra={"version": settings.api_version})
    yield
    logger.info("VERITY CORE gateway stopping")


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=(
        "**VERITY CORE** — Trust infrastructure for AI agent actions.\n\n"
        "Every action submitted to this API is:\n"
        "- **Executed** in an isolated, network-disabled Docker sandbox\n"
        "- **Verified** against caller-defined rules and a built-in security scan\n"
        "- **Proven** with an HMAC-SHA256 signed proof record persisted to an audit ledger\n\n"
        "No AI-generated code ever runs directly on the host."
    ),
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "execution",
            "description": "Submit and verify AI-generated actions.",
        },
        {
            "name": "audit",
            "description": "Retrieve and validate signed proof records.",
        },
        {
            "name": "ops",
            "description": "Operational endpoints (health, readiness).",
        },
    ],
)


# ── Ops ────────────────────────────────────────────────────────────────────────


@app.get(
    "/health",
    tags=["ops"],
    summary="Health check",
    response_description="Service is up and accepting requests.",
)
async def health():
    return {"status": "ok", "service": "verity-core", "version": settings.api_version}


# ── Execution ──────────────────────────────────────────────────────────────────

_VERIFY_EXAMPLE = {
    "basic_python": {
        "summary": "Simple Python execution",
        "value": {
            "agent_id": "my-agent-v1",
            "payload": "print(2 ** 10)",
            "constraints": {"language": "python", "timeout": 5},
            "verification_rules": [
                {"rule_type": "exit_code", "value": 0},
                {"rule_type": "output_contains", "value": "1024"},
            ],
        },
    },
    "strict_validation": {
        "summary": "Strict output + timing assertion",
        "value": {
            "agent_id": "pipeline-agent",
            "payload": "import json; print(json.dumps({'ok': True}))",
            "constraints": {"language": "python", "timeout": 3},
            "verification_rules": [
                {"rule_type": "exit_code", "value": 0},
                {"rule_type": "output_contains", "value": "true"},
                {"rule_type": "max_execution_ms", "value": 2000},
                {"rule_type": "stderr_empty", "value": True},
            ],
        },
    },
}


@app.post(
    "/v1/verify",
    response_model=VerityResponse,
    status_code=status.HTTP_200_OK,
    tags=["execution"],
    summary="Submit an AI action for sandboxed execution",
    response_description="Signed execution result with verification report and proof record.",
    openapi_extra={"requestBody": {"content": {"application/json": {"examples": _VERIFY_EXAMPLE}}}},
)
async def verify_action(action: AIActionPayload):
    """
    Universal entry point for AI agents.

    **Pipeline**: receive → sandbox → verify → sign → respond

    The returned `proof` object contains a cryptographic signature over
    `(action_id, agent_id, payload_hash, result_hash, timestamp)`.
    Store it to prove what an agent did and when.

    **Security flags** in `verification.security_flags` are informational —
    they do not automatically reject an action, but are always recorded in the proof.
    """
    action_id = str(uuid.uuid4())
    logger.info("action.received", extra={"action_id": action_id, "agent_id": action.agent_id})

    result = kernel.execute(action.payload, action.constraints)
    logger.info(
        "action.executed",
        extra={
            "action_id": action_id,
            "status": result.status,
            "exit_code": result.exit_code,
            "ms": round(result.execution_time_ms, 1),
        },
    )

    report = engine.verify(result, action.verification_rules, action.payload)
    logger.info(
        "action.verified",
        extra={
            "action_id": action_id,
            "passed": report.passed,
            "security_flags": report.security_flags,
            "violations": report.violations,
        },
    )

    proof = ledger.record(action_id, action.agent_id, action.payload, result)

    final_status = result.status
    if not report.passed and final_status == ExecutionStatus.success:
        final_status = ExecutionStatus.rejected

    return VerityResponse(
        action_id=action_id,
        status=final_status,
        execution=result,
        verification=report,
        proof=proof,
        message="Verified and signed."
        if report.passed
        else "Action rejected by verification engine.",
    )


# ── Audit ──────────────────────────────────────────────────────────────────────


@app.get(
    "/v1/proof/{action_id}",
    response_model=VerityResponse,
    tags=["audit"],
    summary="Retrieve and validate a proof record",
    response_description="Proof record with signature validity status.",
)
async def get_proof(action_id: str):
    """
    Fetch a previously recorded proof and re-validate its HMAC signature.

    Returns `status: REJECTED` if the signature does not match — indicating
    the ledger entry was tampered with after recording.
    """
    record = ledger.get(action_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No proof found for action_id={action_id}")

    valid = ledger.verify_signature(record)
    logger.info("proof.retrieved", extra={"action_id": action_id, "valid": valid})

    return VerityResponse(
        action_id=action_id,
        status=ExecutionStatus.success if valid else ExecutionStatus.rejected,
        proof=record,
        message="Proof signature valid." if valid else "Proof signature INVALID — tampered record.",
    )
