from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from enum import Enum


class ActionType(str, Enum):
    execute_code = "execute_code"
    api_call = "api_call"
    shell_command = "shell_command"


class Language(str, Enum):
    python = "python"
    javascript = "javascript"
    bash = "bash"


class ExecutionConstraints(BaseModel):
    timeout: int = Field(default=5, ge=1, le=30, description="Timeout in seconds")
    memory: str = Field(default="128m", description="Memory limit (e.g. '128m', '256m')")
    language: Language = Field(default=Language.python)
    network_disabled: bool = Field(default=True)


class VerificationRule(BaseModel):
    rule_type: str = Field(..., description="'exit_code', 'output_contains', 'output_not_contains'")
    value: Any = Field(..., description="Expected value for the rule")


class AIActionPayload(BaseModel):
    agent_id: str = Field(..., description="Unique identifier for the emitting AI agent")
    action_type: ActionType = Field(default=ActionType.execute_code)
    payload: str = Field(..., description="Raw code or payload to execute")
    constraints: ExecutionConstraints = Field(default_factory=ExecutionConstraints)
    verification_rules: List[VerificationRule] = Field(default_factory=list)


class ExecutionStatus(str, Enum):
    pending = "PENDING"
    running = "RUNNING"
    success = "SUCCESS"
    failure = "FAILURE"
    timeout = "TIMEOUT"
    rejected = "REJECTED"


class ExecutionResult(BaseModel):
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    execution_time_ms: float = 0.0
    status: ExecutionStatus = ExecutionStatus.pending


class VerificationReport(BaseModel):
    passed: bool
    rules_evaluated: int
    rules_passed: int
    violations: List[str] = Field(default_factory=list)
    security_flags: List[str] = Field(default_factory=list)


class ProofRecord(BaseModel):
    action_id: str
    payload_hash: str
    result_hash: str
    signature: str
    timestamp: float
    agent_id: str


class VerityResponse(BaseModel):
    action_id: str
    status: ExecutionStatus
    execution: Optional[ExecutionResult] = None
    verification: Optional[VerificationReport] = None
    proof: Optional[ProofRecord] = None
    message: str = ""
