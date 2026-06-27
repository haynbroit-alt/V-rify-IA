"""VERITY CORE × LangChain — sandboxed code execution with cryptographic proof.

Install:
    pip install verity-core langchain-core

Usage:
    from examples.langchain_tool import VerityTool
    from langchain_openai import ChatOpenAI
    from langchain.agents import AgentExecutor, create_tool_calling_agent
    from langchain_core.prompts import ChatPromptTemplate

    llm = ChatOpenAI(model="gpt-4o")
    tools = [VerityTool()]
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant. Always run code through the sandbox."),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools)
    result = executor.invoke({"input": "What is 2 to the power of 10?"})
    print(result["output"])
"""

from __future__ import annotations

from typing import Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from verity import VerityClient, VerityResult


class VerityInput(BaseModel):
    code: str = Field(description="Python code to execute safely in the sandbox")
    agent_id: str = Field(default="langchain-agent", description="Identifier for this agent")
    timeout: int = Field(default=5, ge=1, le=30, description="Max execution time in seconds")


class VerityTool(BaseTool):
    """LangChain tool that executes Python code in VERITY CORE's sandbox.

    Every execution is:
    - Isolated (Docker, no network, read-only FS, 128 MB RAM)
    - Signed with Ed25519 (tamper-proof)
    - Stored in an immutable ledger

    Returns output + a cryptographic proof that can be verified by anyone.
    """

    name: str = "verity_sandbox"
    description: str = (
        "Execute Python code safely in an isolated sandbox. "
        "Returns stdout, exit code, and a cryptographic proof of execution. "
        "Use this for any code that needs to be run, verified, or audited."
    )
    args_schema: Type[BaseModel] = VerityInput
    api_url: str = "https://v-rify-ia.fly.dev"

    def _run(
        self,
        code: str,
        agent_id: str = "langchain-agent",
        timeout: int = 5,
        run_manager: Optional[object] = None,
    ) -> str:
        client = VerityClient(api_url=self.api_url)
        result: VerityResult = client.run(code, agent_id=agent_id, timeout=timeout)

        lines = [
            f"stdout: {result.output.strip() or '(empty)'}",
            f"exit_code: {result.exit_code}",
            f"verified: {result.verified}",
            f"action_id: {result.action_id}",
        ]
        if result.violations:
            lines.append(f"violations: {', '.join(result.violations)}")

        return "\n".join(lines)

    async def _arun(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use _run — verity-core SDK is synchronous")


# ---------------------------------------------------------------------------
# Minimal demo (no LLM required)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    tool = VerityTool()
    output = tool.invoke({"code": "print(2 ** 10)", "agent_id": "demo"})
    print(output)
    # stdout: 1024
    # exit_code: 0
    # verified: True
    # action_id: <uuid>
