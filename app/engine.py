import re
import logging
from typing import List

from app.models import ExecutionResult, VerificationReport, VerificationRule, ExecutionStatus

logger = logging.getLogger(__name__)

# Patterns that indicate potentially dangerous code regardless of sandbox
SECURITY_PATTERNS = [
    (r"import\s+os\s*;\s*os\.system", "os.system call detected"),
    (r"__import__\(['\"]os['\"]", "dynamic os import detected"),
    (r"subprocess\.(call|run|Popen|check_output)", "subprocess execution detected"),
    (r"open\s*\([^)]*['\"][/\\](?:etc|proc|sys|dev)", "sensitive filesystem access detected"),
    (r"socket\s*\.\s*socket", "raw socket creation detected"),
    (r"eval\s*\(", "eval() usage detected"),
    (r"exec\s*\(", "exec() usage detected"),
    (r"compile\s*\(", "compile() usage detected"),
    (r"ctypes\.", "ctypes usage detected"),
    (r"requests\.(get|post|put|delete|patch)", "HTTP request in code"),
    (r"urllib\.request", "urllib network call detected"),
    (r"http\.client", "http.client usage detected"),
]


class VerificationEngine:
    """
    Validates execution results against declared rules and security policies.
    Runs after the Kernel returns, before Proof Ledger signs.
    """

    def verify(
        self,
        result: ExecutionResult,
        rules: List[VerificationRule],
        raw_code: str,
    ) -> VerificationReport:
        violations: List[str] = []
        security_flags: List[str] = []
        rules_passed = 0

        security_flags = self._scan_code(raw_code)

        for rule in rules:
            ok = self._evaluate_rule(rule, result)
            if ok:
                rules_passed += 1
            else:
                violations.append(
                    f"Rule '{rule.rule_type}' failed (expected {rule.value!r})"
                )

        if result.status == ExecutionStatus.timeout:
            violations.append("Execution timed out — action rejected")

        passed = len(violations) == 0

        return VerificationReport(
            passed=passed,
            rules_evaluated=len(rules),
            rules_passed=rules_passed,
            violations=violations,
            security_flags=security_flags,
        )

    def _evaluate_rule(self, rule: VerificationRule, result: ExecutionResult) -> bool:
        rt = rule.rule_type
        val = rule.value

        if rt == "exit_code":
            return result.exit_code == int(val)
        elif rt == "output_contains":
            return str(val) in result.stdout
        elif rt == "output_not_contains":
            return str(val) not in result.stdout
        elif rt == "max_execution_ms":
            return result.execution_time_ms <= float(val)
        elif rt == "stderr_empty":
            return result.stderr.strip() == ""
        else:
            logger.warning(f"Unknown rule type: {rt}")
            return True

    def _scan_code(self, code: str) -> List[str]:
        flags: List[str] = []
        for pattern, label in SECURITY_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                flags.append(label)
        return flags
