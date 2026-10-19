"""Test helpers: a scripted chat model, so no test needs an API key or the network."""

from dataclasses import replace

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from chordsai.config import load_settings


class FakeLLM(BaseChatModel):
    """Answers with the scripted messages in order and records what it was sent."""

    responses: list = Field(default_factory=list)
    received: list = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.received.append(messages)
        message = self.responses.pop(0) if self.responses else AIMessage("(no more scripted answers)")
        return ChatResult(generations=[ChatGeneration(message=message)])

    def bind_tools(self, tools, **kwargs):
        return self


def tool_call(tool_name: str, /, call_id: str = "call_1", **args) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": tool_name, "args": args, "id": call_id, "type": "tool_call"}])


@pytest.fixture
def settings():
    """Settings without any key, whatever the local .env contains."""
    return replace(load_settings(), groq_api_key=None, tavily_api_key=None, model=None)
