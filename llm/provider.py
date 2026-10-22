"""The provider behind one small interface. The route never knows which provider (or none) is answering."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI


@dataclass
class Completion:
    text: str | None          # None when the model returned no content (e.g. a refusal)
    input_tokens: int
    output_tokens: int
    model: str


class Provider(Protocol):
    model: str

    def complete(self, messages: list[dict]) -> Completion: ...


class OpenAICompatible:
    """Any provider that speaks the OpenAI chat-completions shape: OpenRouter, Ollama, Gemini, Groq, OpenAI..."""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.model = model
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def complete(self, messages: list[dict]) -> Completion:
        res = self.client.chat.completions.create(model=self.model, messages=messages, temperature=0)
        usage = res.usage
        return Completion(text=res.choices[0].message.content if res.choices else None,
                          input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                          output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                          model=res.model or self.model)


def from_env() -> OpenAICompatible:
    return OpenAICompatible(os.environ["LLM_BASE_URL"], os.environ["LLM_API_KEY"], os.environ["LLM_MODEL"])
