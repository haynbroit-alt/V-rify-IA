"""SIOS FastAPI — Scientific Intelligence Open System API."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from sios.core.orchestrator import Orchestrator

app = FastAPI(
    title="SIOS — Scientific Intelligence Open System",
    description=(
        "Multi-agent scientific AI powered by Claude claude-opus-4-8 with adaptive thinking. "
        "Every code execution is cryptographically verified via VERITY CORE."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

_orc: Orchestrator | None = None


def _get_orc() -> Orchestrator:
    global _orc
    if _orc is None:
        _orc = Orchestrator()
    return _orc


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Scientific question or coding task")
    reset: bool = Field(default=False, description="Clear session memory before answering")


class ProofRecord(BaseModel):
    action_id: str
    verified: bool
    proof: dict
    exit_code: int


class AskResponse(BaseModel):
    answer: str
    category: str
    code: str
    output: str
    proofs: list[ProofRecord]
    verified: bool
    iterations: int


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@app.get("/v1/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "version": "0.1.0", "sandbox": "verity-core"}


@app.post("/v1/ask", response_model=AskResponse, tags=["sios"])
def ask(req: AskRequest) -> AskResponse:
    orc = _get_orc()
    if req.reset:
        orc.reset()
    try:
        result = orc.ask(req.query)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return AskResponse(
        answer=result["answer"],
        category=result["category"],
        code=result["code"],
        output=result["output"],
        proofs=[ProofRecord(**p) for p in result["proofs"]],
        verified=result["verified"],
        iterations=result["iterations"],
    )


@app.get("/v1/history", tags=["sios"])
def history(limit: int = Query(default=20, ge=1, le=100)) -> list[dict]:
    return _get_orc().history()[-limit:]


@app.delete("/v1/session", tags=["sios"])
def reset_session() -> dict:
    _get_orc().reset()
    return {"status": "reset"}
