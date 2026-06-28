"""SIOS secure sandbox — wraps VERITY CORE to give every execution a cryptographic proof."""

from __future__ import annotations

from verity import VerityClient
from verity.client import VerityResult

_client: VerityClient | None = None


def _get_client(api_url: str) -> VerityClient:
    global _client
    if _client is None or _client.api_url != api_url:
        _client = VerityClient(api_url=api_url, timeout=60)
    return _client


def execute(
    code: str,
    *,
    agent_id: str = "sios",
    timeout: int = 10,
    api_url: str = "https://v-rify-ia.fly.dev",
) -> dict:
    """Execute Python code in the VERITY CORE sandbox.

    Returns a dict with output, exit_code, verified flag, and the Ed25519 proof.
    """
    result: VerityResult = _get_client(api_url).run(
        code,
        agent_id=agent_id,
        language="python",
        timeout=min(timeout, 30),
    )
    return {
        "output": result.output,
        "exit_code": result.exit_code,
        "execution_time_ms": result.execution_time_ms,
        "verified": result.verified,
        "status": result.status,
        "action_id": result.action_id,
        "proof": result.proof,
        "violations": result.violations,
        "security_flags": result.security_flags,
        "success": result.exit_code == 0,
    }
