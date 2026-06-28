"""BaseAgent — agentic loop with VERITY CORE tool execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from sios.models.llm import LLMClient
from sios.sandbox.runner import execute

_EXECUTE_CODE_TOOL: dict = {
    "name": "execute_code",
    "description": (
        "Execute Python code in VERITY CORE's secure, network-isolated sandbox. "
        "Every execution is cryptographically signed with Ed25519 — the proof can be "
        "independently verified. Returns stdout, exit_code, and verified status. "
        "Use this for all computation: math, data analysis, simulations, algorithms."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Print results you want to see.",
            },
            "timeout": {
                "type": "integer",
                "default": 10,
                "description": "Max wall-clock seconds (1–30).",
            },
        },
        "required": ["code"],
    },
}


@dataclass
class AgentResult:
    answer: str
    code: str = ""
    output: str = ""
    proofs: list[dict] = field(default_factory=list)
    verified: bool = False
    iterations: int = 0


class BaseAgent(ABC):
    def __init__(
        self,
        llm: LLMClient,
        *,
        agent_id: str = "sios",
        api_url: str = "https://v-rify-ia.fly.dev",
        max_iterations: int = 6,
    ) -> None:
        self.llm = llm
        self.agent_id = agent_id
        self.api_url = api_url
        self.max_iterations = max_iterations

    @property
    @abstractmethod
    def system_prompt(self) -> str: ...

    def run(self, query: str) -> AgentResult:
        messages: list[dict] = [{"role": "user", "content": query}]
        code_parts: list[str] = []
        output_parts: list[str] = []
        proofs: list[dict] = []
        last_response = None

        for iteration in range(self.max_iterations):
            response = self.llm.complete(
                messages,
                system=self.system_prompt,
                tools=[_EXECUTE_CODE_TOOL],
                max_tokens=8192,
            )
            last_response = response

            # Separate tool calls from text/thinking blocks
            tool_calls = [b for b in response.content if b.type == "tool_use"]

            if not tool_calls or response.stop_reason == "end_turn":
                # Extract final answer text
                answer = "\n".join(
                    b.text for b in response.content if b.type == "text"
                ).strip()
                return AgentResult(
                    answer=answer,
                    code="\n\n".join(code_parts),
                    output="\n".join(output_parts),
                    proofs=proofs,
                    verified=bool(proofs) and all(p["verified"] for p in proofs),
                    iterations=iteration + 1,
                )

            # Append full assistant content (includes thinking blocks)
            messages.append({"role": "assistant", "content": response.content})

            # Run each tool call through VERITY CORE
            tool_results: list[dict] = []
            for tc in tool_calls:
                code: str = tc.input.get("code", "")
                timeout: int = int(tc.input.get("timeout", 10))
                execution = execute(
                    code,
                    agent_id=self.agent_id,
                    timeout=timeout,
                    api_url=self.api_url,
                )
                code_parts.append(code)
                output_parts.append(execution["output"])
                proofs.append(
                    {
                        "action_id": execution["action_id"],
                        "verified": execution["verified"],
                        "proof": execution["proof"],
                        "exit_code": execution["exit_code"],
                    }
                )

                status_line = (
                    f"exit_code: {execution['exit_code']}\n"
                    f"verified: {execution['verified']}\n"
                    f"stdout:\n{execution['output'] or '(empty)'}"
                )
                if execution["violations"]:
                    status_line += f"\nviolations: {', '.join(execution['violations'])}"
                if execution["security_flags"]:
                    status_line += f"\nsecurity_flags: {', '.join(execution['security_flags'])}"

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": status_line,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        # Max iterations — return what we have
        answer = ""
        if last_response:
            answer = "\n".join(
                b.text for b in last_response.content if b.type == "text"
            ).strip()
        return AgentResult(
            answer=answer or "Max iterations reached without a final answer.",
            code="\n\n".join(code_parts),
            output="\n".join(output_parts),
            proofs=proofs,
            verified=bool(proofs) and all(p["verified"] for p in proofs),
            iterations=self.max_iterations,
        )
