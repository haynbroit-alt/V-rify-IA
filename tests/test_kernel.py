from unittest.mock import patch

import pytest

from app.kernel import ExecutionKernel
from app.models import ExecutionConstraints, ExecutionStatus, Language


@pytest.fixture
def kernel(monkeypatch):
    monkeypatch.setenv("VERITY_ALLOW_SUBPROCESS_FALLBACK", "true")
    return ExecutionKernel()


@pytest.fixture
def default_constraints():
    return ExecutionConstraints(language=Language.python, timeout=5)


def test_simple_print(kernel, default_constraints):
    result = kernel.execute("print('hello verity')", default_constraints)
    assert result.status == ExecutionStatus.success
    assert "hello verity" in result.stdout
    assert result.exit_code == 0


def test_exit_code_nonzero(kernel, default_constraints):
    result = kernel.execute("raise ValueError('boom')", default_constraints)
    assert result.exit_code != 0
    assert result.status == ExecutionStatus.failure


def test_timeout_enforcement(kernel):
    constraints = ExecutionConstraints(language=Language.python, timeout=2)
    result = kernel.execute("import time; time.sleep(60)", constraints)
    assert result.status == ExecutionStatus.timeout


def test_math_computation(kernel, default_constraints):
    result = kernel.execute("print(2 ** 10)", default_constraints)
    assert "1024" in result.stdout
    assert result.status == ExecutionStatus.success


def test_syntax_error(kernel, default_constraints):
    result = kernel.execute("def foo(: pass", default_constraints)
    assert result.exit_code != 0
    assert result.status == ExecutionStatus.failure


def test_docker_unavailable_without_fallback_raises(monkeypatch):
    """When Docker is unreachable and fallback is disabled, execute() must raise."""
    monkeypatch.setenv("VERITY_ALLOW_SUBPROCESS_FALLBACK", "false")
    with patch("docker.from_env", side_effect=Exception("Docker not found")):
        kernel = ExecutionKernel()
    with pytest.raises(RuntimeError, match="Secure execution backend unavailable"):
        kernel.execute("print('hi')", ExecutionConstraints())
