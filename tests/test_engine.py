import pytest
from app.engine import VerificationEngine
from app.models import ExecutionResult, ExecutionStatus, VerificationRule


@pytest.fixture
def engine():
    return VerificationEngine()


def _result(stdout="", stderr="", exit_code=0, status=ExecutionStatus.success, ms=10.0):
    return ExecutionResult(stdout=stdout, stderr=stderr, exit_code=exit_code, status=status, execution_time_ms=ms)


def test_passes_with_no_rules(engine):
    report = engine.verify(_result(stdout="ok"), [], "print('ok')")
    assert report.passed is True
    assert report.rules_evaluated == 0


def test_exit_code_rule_pass(engine):
    rules = [VerificationRule(rule_type="exit_code", value=0)]
    report = engine.verify(_result(exit_code=0), rules, "x=1")
    assert report.passed is True
    assert report.rules_passed == 1


def test_exit_code_rule_fail(engine):
    rules = [VerificationRule(rule_type="exit_code", value=0)]
    report = engine.verify(_result(exit_code=1, status=ExecutionStatus.failure), rules, "raise")
    assert report.passed is False
    assert len(report.violations) == 1


def test_output_contains_rule(engine):
    rules = [VerificationRule(rule_type="output_contains", value="42")]
    report = engine.verify(_result(stdout="the answer is 42"), rules, "print(42)")
    assert report.passed is True


def test_output_not_contains_rule(engine):
    rules = [VerificationRule(rule_type="output_not_contains", value="error")]
    report = engine.verify(_result(stdout="all good"), rules, "print('all good')")
    assert report.passed is True


def test_security_scan_detects_eval(engine):
    report = engine.verify(_result(), [], "eval('1+1')")
    assert "eval() usage detected" in report.security_flags


def test_security_scan_detects_subprocess(engine):
    report = engine.verify(_result(), [], "import subprocess; subprocess.run(['ls'])")
    assert any("subprocess" in f for f in report.security_flags)


def test_timeout_always_fails(engine):
    result = _result(status=ExecutionStatus.timeout, exit_code=-1)
    report = engine.verify(result, [], "import time; time.sleep(99)")
    assert report.passed is False
    assert any("timed out" in v for v in report.violations)


def test_max_execution_ms_rule(engine):
    rules = [VerificationRule(rule_type="max_execution_ms", value=1000)]
    report = engine.verify(_result(ms=500.0), rules, "x=1")
    assert report.passed is True

    report_fail = engine.verify(_result(ms=2000.0), rules, "x=1")
    assert report_fail.passed is False
