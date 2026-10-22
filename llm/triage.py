"""Parse → validate → repair once → give up cleanly. The model's answer is untrusted input until it passes here."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from pydantic import ValidationError

from llm import logs, prompt
from llm.provider import Provider
from llm.schema import Triage

FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


class OutputRejected(Exception):
    """The model's answer failed the schema twice. Carries OUR description of why, never the model's text."""


@dataclass
class Result:
    triage: Triage
    repaired: bool


def parse(text: str | None) -> dict:
    if not text or not text.strip():
        raise ValueError("the answer was empty (possibly a refusal)")
    fenced = FENCE.search(text)                     # "Sure! Here's the JSON: ```json {...} ```"
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    if start == -1:
        raise ValueError("no JSON object found in the answer")
    try:
        obj, _ = json.JSONDecoder().raw_decode(candidate[start:])
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON ({e.msg} at character {e.pos})") from None
    if not isinstance(obj, dict):
        raise ValueError("the JSON is not an object")
    return obj


def describe(error: Exception) -> str:
    # Built from field names and Pydantic's own messages only: the model's raw text never leaks out through here.
    if isinstance(error, ValidationError):
        return "; ".join(f"{'.'.join(map(str, e['loc'])) or 'answer'}: {e['msg']}" for e in error.errors()[:5])
    return str(error)


def validate(text: str | None) -> Triage:
    return Triage.model_validate(parse(text))


def run(note: str, llm: Provider, version: str) -> Result:
    messages = prompt.build_messages(note, version)
    first = llm.complete(messages)
    try:
        return Result(validate(first.text), repaired=False)
    except (ValueError, ValidationError) as e:
        first_error = describe(e)

    # Repair retry, exactly once: hand the model its own answer and the exact reason it was rejected.
    repair = messages + [
        {"role": "assistant", "content": first.text or ""},
        {"role": "user", "content": f"Your previous answer was rejected for this reason: {first_error}. "
                                    "Return only corrected JSON matching the schema."},
    ]
    second = llm.complete(repair)
    try:
        return Result(validate(second.text), repaired=True)
    except (ValueError, ValidationError) as e:
        second_error = describe(e)

    logs.quarantine({"prompt_version": version, "model": second.model, "input": note,
                     "errors": [first_error, second_error], "raw_outputs": [first.text, second.text]})
    raise OutputRejected(second_error)
