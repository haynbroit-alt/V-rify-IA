"""SIOS Orchestrator — classifies queries and routes to the right agent."""

from __future__ import annotations

from sios.agents.base import AgentResult
from sios.agents.coding_agent import CodingAgent
from sios.agents.data_agent import DataAgent
from sios.agents.math_agent import MathAgent
from sios.config.settings import settings
from sios.core.memory import Memory
from sios.models.llm import LLMClient

_CLASSIFIER_SYSTEM = """\
Classify the user's request into exactly one category. Reply with a single word only.

Categories:
- math      — equations, proofs, calculus, algebra, linear algebra, statistics theory, geometry
- data      — data analysis, CSV/DataFrame work, visualization, ML, statistics on datasets
- coding    — algorithms, software tasks, scripting, APIs, general Python programming

Reply with: math, data, or coding
"""


class Orchestrator:
    """Routes scientific queries to specialised agents backed by VERITY CORE."""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or settings.anthropic_api_key or None
        self.llm = LLMClient(api_key=key)
        self.memory = Memory()
        self._agents: dict[str, CodingAgent | MathAgent | DataAgent] = {
            "math": MathAgent(
                self.llm,
                agent_id=settings.agent_id,
                api_url=settings.verity_api_url,
                max_iterations=settings.max_iterations,
            ),
            "data": DataAgent(
                self.llm,
                agent_id=settings.agent_id,
                api_url=settings.verity_api_url,
                max_iterations=settings.max_iterations,
            ),
            "coding": CodingAgent(
                self.llm,
                agent_id=settings.agent_id,
                api_url=settings.verity_api_url,
                max_iterations=settings.max_iterations,
            ),
        }

    def _classify(self, query: str) -> str:
        response = self.llm.complete(
            [{"role": "user", "content": query}],
            system=_CLASSIFIER_SYSTEM,
            max_tokens=16,
        )
        label = ""
        for block in response.content:
            if block.type == "text":
                label = block.text.strip().lower()
                break
        return label if label in self._agents else "coding"

    def ask(self, query: str) -> dict:
        self.memory.add("user", query)
        category = self._classify(query)
        agent = self._agents[category]
        result: AgentResult = agent.run(query)
        self.memory.add(
            "assistant",
            result.answer,
            category=category,
            proofs=result.proofs,
        )
        return {
            "answer": result.answer,
            "category": category,
            "code": result.code,
            "output": result.output,
            "proofs": result.proofs,
            "verified": result.verified,
            "iterations": result.iterations,
        }

    def history(self) -> list[dict]:
        return self.memory.history()

    def reset(self) -> None:
        self.memory.clear()
