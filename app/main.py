import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

from app.models import (
    AIActionPayload,
    ExecutionStatus,
    VerityResponse,
)
from app.kernel import ExecutionKernel
from app.engine import VerificationEngine
from app.ledger import ProofLedger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

kernel = ExecutionKernel()
engine = VerificationEngine()
ledger = ProofLedger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("VERITY CORE gateway starting")
    yield
    logger.info("VERITY CORE gateway stopping")


app = FastAPI(
    title="VERITY CORE",
    description="Trust infrastructure for AI agent actions — execute, verify, prove.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "verity-core"}


@app.post("/v1/verify", response_model=VerityResponse, status_code=status.HTTP_200_OK)
async def verify_action(action: AIActionPayload):
    """
    Universal entry point for AI agents.
    Receives raw code/payload → isolates → executes → verifies → proves.
    Returns a signed proof with the execution outcome.
    """
    action_id = str(uuid.uuid4())
    logger.info(f"[{action_id}] Received action from agent={action.agent_id}")

    # 1. Execute in sandbox
    result = kernel.execute(action.payload, action.constraints)
    logger.info(f"[{action_id}] Execution status={result.status} exit={result.exit_code} ms={result.execution_time_ms:.1f}")

    # 2. Verify against rules + security scan
    report = engine.verify(result, action.verification_rules, action.payload)
    logger.info(f"[{action_id}] Verification passed={report.passed} flags={report.security_flags}")

    # 3. Record proof regardless of outcome
    proof = ledger.record(action_id, action.agent_id, action.payload, result)

    # 4. Override status if verification failed
    final_status = result.status
    if not report.passed and final_status == ExecutionStatus.success:
        final_status = ExecutionStatus.rejected

    return VerityResponse(
        action_id=action_id,
        status=final_status,
        execution=result,
        verification=report,
        proof=proof,
        message="Verified and signed." if report.passed else "Action rejected by verification engine.",
    )


@app.get("/v1/proof/{action_id}", response_model=VerityResponse)
async def get_proof(action_id: str):
    """Retrieve the proof record for a previously executed action."""
    record = ledger.get(action_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No proof found for action_id={action_id}")

    valid = ledger.verify_signature(record)
    return VerityResponse(
        action_id=action_id,
        status=ExecutionStatus.success if valid else ExecutionStatus.rejected,
        proof=record,
        message="Proof signature valid." if valid else "Proof signature INVALID — tampered record.",
    )
