"""Unit tests for sios.core.orchestrator — mocks LLM and sandbox."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sios.agents.base import AgentResult
from sios.core.orchestrator import Orchestrator


def _make_text_response(text: str, stop_reason: str = "end_turn") -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    resp.stop_reason = stop_reason
    return resp


@pytest.fixture()
def patched_orchestrator():
    with patch("sios.core.orchestrator.LLMClient") as MockLLM:
        mock_llm = MockLLM.return_value
        # classify always returns "coding"
        mock_llm.complete.return_value = _make_text_response("coding")
        orc = Orchestrator(api_key="test-key")
        orc.llm = mock_llm
        # also patch each agent's llm
        for agent in orc._agents.values():
            agent.llm = mock_llm
        yield orc, mock_llm


def test_classify_routes_to_coding(patched_orchestrator):
    orc, mock_llm = patched_orchestrator

    agent_result = AgentResult(
        answer="The answer is 42.",
        code="print(42)",
        output="42\n",
        proofs=[{"action_id": "x", "verified": True, "proof": {}, "exit_code": 0}],
        verified=True,
        iterations=1,
    )
    with patch.object(orc._agents["coding"], "run", return_value=agent_result):
        result = orc.ask("Write a hello world program")

    assert result["category"] == "coding"
    assert result["answer"] == "The answer is 42."
    assert result["verified"] is True


def test_history_accumulates(patched_orchestrator):
    orc, mock_llm = patched_orchestrator
    agent_result = AgentResult(answer="done", iterations=1)
    with patch.object(orc._agents["coding"], "run", return_value=agent_result):
        orc.ask("first query")
        orc.ask("second query")

    hist = orc.history()
    assert len(hist) == 4  # 2 user + 2 assistant turns


def test_reset_clears_memory(patched_orchestrator):
    orc, mock_llm = patched_orchestrator
    agent_result = AgentResult(answer="done", iterations=1)
    with patch.object(orc._agents["coding"], "run", return_value=agent_result):
        orc.ask("something")

    orc.reset()
    assert orc.history() == []
