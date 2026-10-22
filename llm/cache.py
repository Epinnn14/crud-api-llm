"""Extra: a small in-memory answer cache. The key includes the prompt version and the model, because changing
either makes yesterday's answers stale. Honest note: for free-text notes almost nothing repeats, so the hit rate
is low; it mostly saves quota while testing the same inputs over and over."""
import hashlib
import os
from collections import OrderedDict

from llm.schema import Triage

_CACHE: "OrderedDict[str, Triage]" = OrderedDict()
MAX_ITEMS = 256


def key(text: str, version: str) -> str:
    raw = f"{version}\x00{os.environ.get('LLM_MODEL', '')}\x00{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get(k: str) -> Triage | None:
    if os.environ.get("LLM_CACHE", "true").lower() in ("false", "0", "off"):
        return None
    if k in _CACHE:
        _CACHE.move_to_end(k)
        return _CACHE[k]
    return None


def put(k: str, value: Triage) -> None:
    _CACHE[k] = value
    _CACHE.move_to_end(k)
    while len(_CACHE) > MAX_ITEMS:
        _CACHE.popitem(last=False)


def clear() -> None:
    _CACHE.clear()
