"""Structured JSON-lines logs: one for every model call (cost), one for every answer we refused (quarantine)."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _write(name: str, record: dict) -> None:
    log_dir = Path(os.environ.get("LLM_LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    record = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), **record}
    with (log_dir / name).open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def quarantine(record: dict) -> None:
    _write("quarantine.jsonl", record)


def call(record: dict) -> None:
    _write("llm-calls.jsonl", record)
