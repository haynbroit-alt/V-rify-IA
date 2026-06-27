import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request, status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.engine import VerificationEngine
from app.kernel import ExecutionKernel
from app.ledger import ProofLedger, get_public_key_pem
from app.logging_config import configure_logging
from app.models import (
    AIActionPayload,
    ExecutionStatus,
    HistoryResponse,
    VerityResponse,
)
from app.orchestrator import ActionOrchestrator

configure_logging()
logger = logging.getLogger(__name__)

settings = get_settings()
_orchestrator = ActionOrchestrator(
    kernel=ExecutionKernel(),
    engine=VerificationEngine(),
    ledger=ProofLedger(),
)

limiter = Limiter(key_func=get_remote_address)


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
        "- **Proven** with an Ed25519 signature verifiable by any third party\n\n"
        "No AI-generated code ever runs directly on the host."
    ),
    lifespan=lifespan,
    openapi_tags=[
        {"name": "execution", "description": "Submit and verify AI-generated actions."},
        {"name": "audit", "description": "Retrieve and validate signed proof records."},
        {"name": "ops", "description": "Operational endpoints (health, public key)."},
    ],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Ops ────────────────────────────────────────────────────────────────────────


@app.get("/health", tags=["ops"], summary="Health check")
async def health():
    return {"status": "ok", "service": "verity-core", "version": settings.api_version}


@app.get(
    "/v1/public-key",
    tags=["ops"],
    summary="Ed25519 public key (PEM)",
    response_description="PEM-encoded public key for independent proof verification.",
)
async def public_key():
    """
    Returns the Ed25519 public key used to sign all proof records.

    Any client can use this key to independently verify a `ProofRecord.signature`
    without any access to VERITY CORE internals.
    """
    return {"public_key": get_public_key_pem()}


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
    response_description="Signed result with verification report, proof, and state transitions.",
    openapi_extra={"requestBody": {"content": {"application/json": {"examples": _VERIFY_EXAMPLE}}}},
)
@limiter.limit("60/minute")
async def verify_action(request: Request, action: AIActionPayload):
    """
    Universal entry point for AI agents.

    **Pipeline**: PENDING → VALIDATING → EXECUTING → VERIFYING → SIGNING → PERSISTING → COMPLETED

    The `transitions` field in the response exposes each phase with its timestamp
    and duration, enabling fine-grained observability and debugging.

    The `proof.signature` is an Ed25519 signature verifiable with the public key
    at `GET /v1/public-key` — no server access required to validate.

    **Rate limit**: 60 requests per minute per IP.
    """
    action_id = str(uuid.uuid4())
    logger.info("action.received", extra={"action_id": action_id, "agent_id": action.agent_id})
    response = _orchestrator.run(action_id, action)
    logger.info(
        "action.completed",
        extra={"action_id": action_id, "state": response.state, "status": response.status},
    )
    return response


# ── Audit ──────────────────────────────────────────────────────────────────────


@app.get(
    "/v1/proof/{action_id}",
    response_model=VerityResponse,
    tags=["audit"],
    summary="Retrieve and validate a proof record",
)
async def get_proof(action_id: str):
    """
    Fetch a previously recorded proof and re-validate its Ed25519 signature.

    Returns `status: REJECTED` if the signature does not match — indicating
    the ledger entry was tampered with after recording.
    """
    from app.ledger import ProofLedger

    ledger = ProofLedger()
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


@app.get(
    "/v1/history/{agent_id}",
    response_model=HistoryResponse,
    tags=["audit"],
    summary="List proof records for an agent",
    response_description="Chronological list of signed proofs emitted by this agent.",
)
async def get_history(
    agent_id: str,
    limit: int = Query(default=50, ge=1, le=100, description="Max records to return"),
):
    """
    Returns the most recent proof records for a given `agent_id`, newest first.

    Useful for auditing all actions an agent has taken, or replaying an agent's
    execution history. Each record carries a verifiable Ed25519 signature.
    """
    ledger = ProofLedger()
    records = ledger.list_by_agent(agent_id, limit)
    logger.info("history.retrieved", extra={"agent_id": agent_id, "count": len(records)})
    return HistoryResponse(agent_id=agent_id, count=len(records), records=records)
