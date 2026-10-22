"""The provider behind one small interface. The route never knows which provider (or none) is answering.

Policy, set explicitly instead of left to SDK defaults:
- timeout: LLM_TIMEOUT seconds per call (default 30). The SDK default is 10 minutes, which is no timeout at all.
- the SDK's own retries are OFF (max_retries=0). Our loop below retries ONLY timeouts, connection errors,
  429 and 5xx, at most 3 attempts, with exponential backoff + jitter (1 s, 2 s, ...), and obeys Retry-After.
  400/401/403/404 are never retried: a bad key is still a bad key in four seconds.
- every attempt writes one cost line to logs/llm-calls.jsonl.
- one request-wide deadline (LLM_DEADLINE, default 45 s) covers every attempt, the repair call included.
"""
from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from typing import Protocol

import openai
from openai import OpenAI

from llm import logs

MAX_ATTEMPTS = 3
RETRYABLE = (openai.APITimeoutError, openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError)


@dataclass
class Completion:
    text: str | None          # None when the model returned no content (e.g. a refusal)
    input_tokens: int
    output_tokens: int
    model: str


class ProviderError(Exception):
    status = 502              # the HTTP status OUR endpoint should answer with


class ProviderTimeout(ProviderError):
    status = 504


class ProviderUnavailable(ProviderError):
    status = 503              # rate-limited or down, even after retries


class ProviderRejected(ProviderError):
    status = 502              # 400/401/403/404 from the provider: our config is wrong, retrying won't help


class Provider(Protocol):
    model: str

    def complete(self, messages: list[dict], *, deadline: float, tag: dict) -> Completion: ...


def env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def backoff(attempt: int, error: Exception) -> float:
    retry_after = None
    if isinstance(error, openai.APIStatusError):
        try:
            retry_after = float(error.response.headers.get("retry-after", ""))
        except ValueError:
            retry_after = None
    if retry_after is not None:
        return min(retry_after, 10.0)                     # the provider told us how long: obey (capped)
    return 2 ** (attempt - 1) + random.uniform(0, 0.5)   # 1 s, 2 s, ... plus jitter so clients don't stampede


def outcome_of(error: Exception) -> str:
    if isinstance(error, openai.APITimeoutError):
        return "timeout"
    if isinstance(error, openai.APIStatusError):
        return f"http_{error.status_code}"
    return "connection_error"


class OpenAICompatible:
    """Any provider that speaks the OpenAI chat-completions shape: OpenRouter, Ollama, Gemini, Groq, OpenAI..."""

    def __init__(self, base_url: str, api_key: str, model: str, http_client=None):
        self.model = model
        self.timeout = env_float("LLM_TIMEOUT", 30.0)
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=self.timeout, max_retries=0,
                             http_client=http_client)

    def complete(self, messages: list[dict], *, deadline: float, tag: dict) -> Completion:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            remaining = deadline - time.monotonic()
            if remaining < 1:
                raise ProviderTimeout("the request ran out of time before the model answered")
            started = time.monotonic()
            base = {**tag, "model": self.model, "attempt": attempt}
            try:
                res = self.client.chat.completions.create(model=self.model, messages=messages, temperature=0,
                                                          timeout=min(self.timeout, remaining))
            except RETRYABLE as e:
                logs.call({**base, "outcome": outcome_of(e), "input_tokens": 0, "output_tokens": 0,
                           "duration_ms": round((time.monotonic() - started) * 1000)})
                wait = backoff(attempt, e)
                if attempt == MAX_ATTEMPTS or deadline - time.monotonic() < wait + 1:
                    if isinstance(e, openai.APITimeoutError):
                        raise ProviderTimeout(f"the model did not answer within {self.timeout:g} s") from None
                    raise ProviderUnavailable(f"the provider is unavailable ({outcome_of(e)}) after {attempt} attempt(s)") from None
                time.sleep(wait)
                continue
            except openai.APIStatusError as e:            # 400/401/403/404...: never retried
                logs.call({**base, "outcome": outcome_of(e), "input_tokens": 0, "output_tokens": 0,
                           "duration_ms": round((time.monotonic() - started) * 1000)})
                raise ProviderRejected(f"the provider refused the request (HTTP {e.status_code}); "
                                       "check LLM_API_KEY / LLM_MODEL / LLM_BASE_URL") from None
            usage = res.usage
            completion = Completion(text=res.choices[0].message.content if res.choices else None,
                                    input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                                    output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                                    model=res.model or self.model)
            record = {**base, "model": completion.model, "outcome": "ok", "input_tokens": completion.input_tokens,
                      "output_tokens": completion.output_tokens,
                      "duration_ms": round((time.monotonic() - started) * 1000)}
            price_in, price_out = env_float("LLM_PRICE_IN_PER_M", 0), env_float("LLM_PRICE_OUT_PER_M", 0)
            record["cost_usd"] = round((completion.input_tokens * price_in + completion.output_tokens * price_out) / 1e6, 8)
            logs.call(record)
            return completion
        raise ProviderUnavailable("unreachable")  # pragma: no cover


def from_env() -> OpenAICompatible:
    missing = [v for v in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL") if not os.environ.get(v)]
    if missing:
        raise ProviderRejected(f"missing configuration: {', '.join(missing)} (see .env.example)")
    return OpenAICompatible(os.environ["LLM_BASE_URL"], os.environ["LLM_API_KEY"], os.environ["LLM_MODEL"])
