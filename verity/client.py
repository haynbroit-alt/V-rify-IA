"""VERITY CORE Python SDK — verifiable AI code execution."""

from __future__ import annotations

from dataclasses import dataclass, field

import requests

DEFAULT_API = "https://v-rify-ia.fly.dev"


@dataclass
class VerityResult:
    """Result of a sandboxed execution with cryptographic proof."""

    output: str
    exit_code: int
    execution_time_ms: float
    verified: bool
    status: str
    action_id: str
    proof: dict
    transitions: list[dict] = field(default_factory=list)
    security_flags: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        """True when execution succeeded and all rules passed."""
        return self.status == "SUCCESS" and self.verified


class VerityClient:
    """Client for the VERITY CORE API.

    Usage:
        client = VerityClient()
        result = client.run("print(2**10)")
        print(result.output)   # "1024\\n"
        print(result.verified) # True
    """

    def __init__(self, api_url: str = DEFAULT_API, timeout: int = 30) -> None:
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout

    def run(
        self,
        code: str,
        *,
        agent_id: str = "sdk-client",
        language: str = "python",
        timeout: int = 5,
        rules: list[dict] | None = None,
    ) -> VerityResult:
        """Execute code in the sandbox and return a verifiable result.

        Args:
            code: Python (or other language) code to execute.
            agent_id: Identifier for the calling agent — appears in the proof.
            language: "python", "javascript", or "bash".
            timeout: Max execution time in seconds (1–30).
            rules: Optional list of verification rules, e.g.
                   [{"rule_type": "exit_code", "value": 0}]

        Returns:
            VerityResult — truthy when execution succeeded and rules passed.

        Raises:
            requests.HTTPError: on non-2xx API responses.
        """
        resp = requests.post(
            f"{self.api_url}/v1/verify",
            json={
                "agent_id": agent_id,
                "payload": code,
                "constraints": {"language": language, "timeout": timeout},
                "verification_rules": rules or [],
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        execution = data.get("execution") or {}
        verification = data.get("verification") or {}

        return VerityResult(
            output=execution.get("stdout", ""),
            exit_code=execution.get("exit_code", -1),
            execution_time_ms=execution.get("execution_time_ms", 0.0),
            verified=verification.get("passed", False),
            status=data.get("status", "UNKNOWN"),
            action_id=data.get("action_id", ""),
            proof=data.get("proof") or {},
            transitions=data.get("transitions", []),
            security_flags=verification.get("security_flags", []),
            violations=verification.get("violations", []),
        )

    def get_proof(self, action_id: str) -> dict:
        """Retrieve and re-validate a stored proof by action_id."""
        resp = requests.get(f"{self.api_url}/v1/proof/{action_id}", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def history(self, agent_id: str, limit: int = 50) -> list[dict]:
        """Return recent proof records for an agent, newest first."""
        resp = requests.get(
            f"{self.api_url}/v1/history/{agent_id}",
            params={"limit": limit},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["records"]


def run(
    code: str,
    *,
    agent_id: str = "sdk-client",
    language: str = "python",
    timeout: int = 5,
    rules: list[dict] | None = None,
    api_url: str = DEFAULT_API,
) -> VerityResult:
    """Execute code and return a verifiable result. Module-level convenience function.

    Example:
        from verity import run
        result = run("print(2**10)")
        print(result.output)   # "1024\\n"
        print(result.verified) # True
        print(bool(result))    # True
    """
    return VerityClient(api_url=api_url).run(
        code, agent_id=agent_id, language=language, timeout=timeout, rules=rules
    )
