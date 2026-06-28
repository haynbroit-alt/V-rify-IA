"""Anthropic LLM interface for SIOS — claude-opus-4-8 with adaptive thinking."""

from __future__ import annotations

import anthropic

MODEL = "claude-opus-4-8"


class LLMClient:
    """Thin wrapper around the Anthropic SDK configured for SIOS."""

    def __init__(self, api_key: str | None = None) -> None:
        self._client = anthropic.Anthropic(api_key=api_key or None)

    def complete(
        self,
        messages: list[dict],
        *,
        system: str = "",
        tools: list[dict] | None = None,
        max_tokens: int = 8192,
    ) -> anthropic.types.Message:
        kwargs: dict = {
            "model": MODEL,
            "max_tokens": max_tokens,
            "thinking": {"type": "adaptive"},
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        return self._client.messages.create(**kwargs)

    def stream_complete(
        self,
        messages: list[dict],
        *,
        system: str = "",
        max_tokens: int = 8192,
    ) -> anthropic.types.Message:
        kwargs: dict = {
            "model": MODEL,
            "max_tokens": max_tokens,
            "thinking": {"type": "adaptive"},
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        with self._client.messages.stream(**kwargs) as stream:
            return stream.get_final_message()
