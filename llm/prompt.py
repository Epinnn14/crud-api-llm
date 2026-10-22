"""Prompts are code: they live in prompts/<name>-v<N>.md, get a version number, and go through review."""
import json
import os
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def prompt_version() -> str:
    return os.environ.get("TRIAGE_PROMPT", "triage-v1")


@lru_cache
def load(version: str) -> str:
    return (PROMPTS_DIR / f"{version}.md").read_text(encoding="utf-8")


def build_messages(note: str, version: str) -> list[dict]:
    # the user's text goes in its OWN message, JSON-encoded, so it can't break out of its quotes or
    # blend into the instructions. The system prompt never contains user content.
    return [{"role": "system", "content": load(version)},
            {"role": "user", "content": json.dumps({"note": note}, ensure_ascii=False)}]
