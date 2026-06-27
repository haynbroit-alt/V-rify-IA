import time
import docker
import logging
from docker.errors import ImageNotFound, APIError

from app.models import ExecutionResult, ExecutionStatus, ExecutionConstraints, Language

logger = logging.getLogger(__name__)

LANGUAGE_IMAGES = {
    Language.python: "python:3.11-slim",
    Language.javascript: "node:20-slim",
    Language.bash: "bash:5.2",
}

LANGUAGE_COMMANDS = {
    Language.python: lambda code: ["python", "-c", code],
    Language.javascript: lambda code: ["node", "-e", code],
    Language.bash: lambda code: ["bash", "-c", code],
}


class ExecutionKernel:
    """
    Isolated execution core — no AI code ever runs directly on the host.
    Each execution spawns a fresh, network-disabled, read-only container.
    """

    def __init__(self):
        try:
            self.client = docker.from_env()
            self.client.ping()
        except Exception as e:
            logger.warning(f"Docker unavailable: {e}. Kernel will use fallback mode.")
            self.client = None

    def execute(self, code: str, constraints: ExecutionConstraints) -> ExecutionResult:
        if self.client is None:
            return self._fallback_execute(code, constraints)
        return self._docker_execute(code, constraints)

    def _docker_execute(
        self, code: str, constraints: ExecutionConstraints
    ) -> ExecutionResult:
        language = constraints.language
        image = LANGUAGE_IMAGES[language]
        command = LANGUAGE_COMMANDS[language](code)
        start_time = time.time()
        container = None

        try:
            container = self.client.containers.run(
                image=image,
                command=command,
                detach=True,
                network_disabled=constraints.network_disabled,
                mem_limit=constraints.memory,
                read_only=True,
                remove=False,
                stdout=True,
                stderr=True,
            )

            try:
                result = container.wait(timeout=constraints.timeout)
                exit_code = result.get("StatusCode", 1)
                status = (
                    ExecutionStatus.success
                    if exit_code == 0
                    else ExecutionStatus.failure
                )
            except Exception:
                container.kill()
                return ExecutionResult(
                    status=ExecutionStatus.timeout,
                    exit_code=-1,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            logs = container.logs(stdout=True, stderr=False).decode(
                "utf-8", errors="replace"
            )
            err_logs = container.logs(stdout=False, stderr=True).decode(
                "utf-8", errors="replace"
            )

            return ExecutionResult(
                stdout=logs,
                stderr=err_logs,
                exit_code=exit_code,
                execution_time_ms=(time.time() - start_time) * 1000,
                status=status,
            )

        except ImageNotFound:
            return ExecutionResult(
                status=ExecutionStatus.failure,
                stderr=f"Docker image not found: {image}",
                exit_code=1,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except APIError as e:
            return ExecutionResult(
                status=ExecutionStatus.failure,
                stderr=f"Docker API error: {e}",
                exit_code=1,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

    def _fallback_execute(
        self, code: str, constraints: ExecutionConstraints
    ) -> ExecutionResult:
        """Subprocess fallback when Docker is unavailable (dev/test only)."""
        import subprocess

        start_time = time.time()
        language = constraints.language

        if language == Language.python:
            cmd = ["python", "-c", code]
        elif language == Language.javascript:
            cmd = ["node", "-e", code]
        else:
            cmd = ["bash", "-c", code]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=constraints.timeout,
            )
            return ExecutionResult(
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
                execution_time_ms=(time.time() - start_time) * 1000,
                status=ExecutionStatus.success
                if proc.returncode == 0
                else ExecutionStatus.failure,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                status=ExecutionStatus.timeout,
                exit_code=-1,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except FileNotFoundError as e:
            return ExecutionResult(
                status=ExecutionStatus.failure,
                stderr=str(e),
                exit_code=1,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
