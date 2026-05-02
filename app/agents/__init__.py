"""Agent orchestration: assistant pipeline, language detection, intent signals, humanization.

Imports of :class:`AssistantAgent` are lazy so ``import app.agents.intent_signals`` does not
load the full LLM / HTTP stack.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["AssistantAgent", "ModelUnavailableError"]


def __getattr__(name: str) -> Any:
    if name == "AssistantAgent":
        from app.agents.assistant_agent import AssistantAgent

        return AssistantAgent
    if name == "ModelUnavailableError":
        from app.agents.assistant_agent import ModelUnavailableError

        return ModelUnavailableError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if TYPE_CHECKING:
    from app.agents.assistant_agent import AssistantAgent, ModelUnavailableError
