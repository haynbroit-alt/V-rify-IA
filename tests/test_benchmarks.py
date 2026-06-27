"""
Performance baselines for VERITY CORE components.

These tests do not assert correctness — they measure and print timing so regressions
become visible in CI logs. Thresholds are deliberately generous to avoid flakiness
on shared runners; tighten them as the project matures.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.engine import VerificationEngine
from app.models import (
    ExecutionConstraints,
    ExecutionResult,
    ExecutionStatus,
    Language,
    VerificationRule,
)

# ── Engine benchmarks (no I/O) ─────────────────────────────────────────────────


@pytest.fixture
def engine():
    return VerificationEngine()


def _result(stdout="ok", exit_code=0):
    return ExecutionResult(
        stdout=stdout,
        exit_code=exit_code,
        status=ExecutionStatus.success,
        execution_time_ms=10.0,
    )


def test_engine_throughput_no_rules(engine):
    """Verification engine should handle ≥ 5 000 rule-free checks per second."""
    result = _result()
    iterations = 5_000
    start = time.perf_counter()
    for _ in range(iterations):
        engine.verify(result, [], "print('ok')")
    elapsed = time.perf_counter() - start
    rate = iterations / elapsed
    print(f"\n  Engine (no rules): {rate:.0f} checks/s  ({elapsed * 1000:.1f} ms total)")
    assert rate >= 1_000, f"Engine too slow: {rate:.0f} checks/s"


def test_engine_throughput_with_rules(engine):
    """Verification engine with 4 rules should handle ≥ 2 000 checks per second."""
    rules = [
        VerificationRule(rule_type="exit_code", value=0),
        VerificationRule(rule_type="output_contains", value="ok"),
        VerificationRule(rule_type="max_execution_ms", value=500),
        VerificationRule(rule_type="stderr_empty", value=True),
    ]
    result = _result()
    iterations = 2_000
    start = time.perf_counter()
    for _ in range(iterations):
        engine.verify(result, rules, "print('ok')")
    elapsed = time.perf_counter() - start
    rate = iterations / elapsed
    print(f"\n  Engine (4 rules): {rate:.0f} checks/s  ({elapsed * 1000:.1f} ms total)")
    assert rate >= 500, f"Engine too slow: {rate:.0f} checks/s"


def test_security_scan_throughput(engine):
    """Security scan should handle ≥ 1 000 payloads per second."""
    payload = "x = 1 + 1\nprint(x)\n" * 20
    iterations = 1_000
    start = time.perf_counter()
    for _ in range(iterations):
        engine._scan_code(payload)
    elapsed = time.perf_counter() - start
    rate = iterations / elapsed
    print(f"\n  Security scan: {rate:.0f} payloads/s  ({elapsed * 1000:.1f} ms total)")
    assert rate >= 200, f"Security scan too slow: {rate:.0f} payloads/s"


# ── Kernel benchmarks ──────────────────────────────────────────────────────────


def test_kernel_single_execution():
    """A single subprocess execution should complete in under 3 seconds."""
    from app.kernel import ExecutionKernel

    k = ExecutionKernel()
    constraints = ExecutionConstraints(language=Language.python, timeout=5)
    start = time.perf_counter()
    result = k.execute("print('bench')", constraints)
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"\n  Kernel single exec: {elapsed_ms:.1f} ms  (status={result.status})")
    assert elapsed_ms < 3_000, f"Kernel execution too slow: {elapsed_ms:.1f} ms"
    assert "bench" in result.stdout


# ── Gateway benchmarks (HTTP round-trip) ───────────────────────────────────────


@pytest.fixture
def client(tmp_path, monkeypatch):
    import os

    monkeypatch.setenv("VERITY_DB_PATH", str(tmp_path / "bench.db"))
    from pathlib import Path

    import app.ledger as ledger_mod

    ledger_mod.DB_PATH = Path(os.environ["VERITY_DB_PATH"])
    from app.main import app

    return TestClient(app)


def test_gateway_latency_p50(client):
    """Median gateway latency (subprocess kernel) should be under 500 ms."""
    payload = {
        "agent_id": "bench-agent",
        "payload": "print(1)",
        "constraints": {"language": "python", "timeout": 5},
    }
    timings = []
    for _ in range(10):
        start = time.perf_counter()
        resp = client.post("/v1/verify", json=payload)
        timings.append((time.perf_counter() - start) * 1000)
        assert resp.status_code == 200

    timings.sort()
    p50 = timings[len(timings) // 2]
    p95 = timings[int(len(timings) * 0.95)]
    print(f"\n  Gateway p50={p50:.1f} ms  p95={p95:.1f} ms")
    assert p50 < 500, f"Gateway p50 too high: {p50:.1f} ms"
