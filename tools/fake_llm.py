"""An OFFLINE stand-in for an OpenAI-compatible provider, for testing the failure paths without spending quota.

It is NOT a model: it answers with a keyword heuristic. Real quality numbers must come from a real provider.

    FAKE_LLM_MODE=good uvicorn tools.fake_llm:app --port 9999
    # then in .env: LLM_BASE_URL=http://localhost:9999/v1  LLM_API_KEY=fake  LLM_MODEL=fake-1

Modes: good · fenced (chatty + ```json fence) · badenum (category outside the list) · badjson ·
       repairable (bad first, fixed after the repair message) · slow (sleeps 40 s) · 429 · 500 · 401
"""
import asyncio
import json
import os
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="fake LLM")
STATE = {"calls": 0}

KEYWORDS = [  # (words, category, priority)
    (("rent", "invoice", "tax", "bank", "pay "), "finance", "high"),
    (("dentist", "doctor", "pharmacy", "gym", "medicine"), "health", "normal"),
    (("deploy", "meeting", "report", "client", "boss", "slides"), "work", "normal"),
    (("buy", "groceries", "pick up", "post office", "laundry"), "errand", "low"),
    (("mom", "birthday", "friend", "call "), "personal", "normal"),
]


def guess(note: str) -> dict:
    low = note.lower()
    for words, category, priority in KEYWORDS:
        if any(w in low for w in words):
            urgent = any(w in low for w in ("asap", "today", "urgent", "!!", "tomorrow"))
            return {"title": note.strip().split(".")[0][:60].capitalize() or "Untitled task", "category": category,
                    "priority": "high" if urgent else priority, "confidence": 0.8,
                    "reason": f"Mentions {category}-related words."}
    return {"title": (note.strip()[:60] or "Unclear note").capitalize(), "category": "other", "priority": "normal",
            "confidence": 0.3, "reason": "The note does not clearly fit a category."}


def reply(content: str, prompt_tokens: int) -> dict:
    return {"id": f"fake-{STATE['calls']}", "object": "chat.completion", "created": int(time.time()), "model": "fake-1",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": max(1, len(content) // 4),
                      "total_tokens": prompt_tokens + max(1, len(content) // 4)}}


@app.post("/v1/chat/completions")
async def chat(request: Request):
    STATE["calls"] += 1
    mode = os.environ.get("FAKE_LLM_MODE", "good")
    body = await request.json()
    messages = body["messages"]
    prompt_tokens = sum(len(m.get("content") or "") for m in messages) // 4
    if mode == "401":
        return JSONResponse(status_code=401, content={"error": {"message": "Invalid API key", "code": 401}})
    if mode == "500":
        return JSONResponse(status_code=500, content={"error": {"message": "upstream exploded"}})
    if mode == "429" and STATE["calls"] % 2 == 1:     # every other call is rate-limited
        return JSONResponse(status_code=429, headers={"Retry-After": "1"}, content={"error": {"message": "slow down"}})
    if mode == "slow":
        await asyncio.sleep(40)
    last = messages[-1]["content"] or ""
    if "Reply with exactly the word" in last:
        return reply("ready", prompt_tokens)
    is_repair = "previous answer was rejected" in last
    user_msgs = [m["content"] for m in messages if m["role"] == "user"]
    try:
        note = json.loads(user_msgs[0])["note"]
    except (ValueError, KeyError, TypeError):
        note = user_msgs[0]
    answer = guess(note)
    if mode == "badenum" or (mode == "repairable" and not is_repair):
        answer["category"] = "urgent-stuff"
    if mode == "badjson":
        return reply('{"title": "Pay rent", "category": "finance", ', prompt_tokens)
    text = json.dumps(answer)
    if mode == "fenced":
        text = f"Sure! Here's the JSON:\n```json\n{json.dumps(answer, indent=2)}\n```"
    return reply(text, prompt_tokens)
