"""POST /triage: a messy note in, one validated task suggestion out."""
import os

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from llm import prompt, provider, triage as triage_service
from llm.schema import STUB, Category, Priority, Triage, TriageRequest

router = APIRouter(tags=["ai"])


def fallback(text: str) -> Triage:
    """Kill switch answer: deterministic, schema-valid, honest about being a fallback."""
    first_line = " ".join(text.split())[:80].strip()
    return Triage(title=first_line if len(first_line) >= 3 else "Review this note", category=Category.other,
                  priority=Priority.normal, confidence=0.0,
                  reason="AI triage is switched off (LLM_ENABLED=false); a human should file this task.")


def llm_enabled() -> bool:
    return os.environ.get("LLM_ENABLED", "true").strip().lower() not in ("false", "0", "no", "off")


@router.post("/triage", response_model=Triage, summary="Turn a messy note into a structured task (LLM)")
def triage(body: TriageRequest, response: Response):
    # input was already validated by Pydantic: a bad request never reaches this line, so it never costs a call
    if os.environ.get("LLM_STUB") == "1":
        response.headers["X-Triage-Source"] = "stub"
        return STUB
    if not llm_enabled():
        # the kill switch: zero model calls, instant answer. Flip it without touching code.
        response.headers["X-Triage-Source"] = "fallback"
        return fallback(body.text)
    version = prompt.prompt_version()
    try:
        result = triage_service.run(body.text, provider.from_env(), version)
    except provider.ProviderError as e:
        return JSONResponse(status_code=e.status, content={"error": f"AI triage failed: {e}"})
    except triage_service.OutputRejected as e:
        # never the raw model text: our own message, and the reason in schema terms
        return JSONResponse(status_code=422, content={
            "error": "The model's answer did not match the schema, even after one repair attempt. "
                     "It was quarantined for review.",
            "reason": str(e), "prompt_version": version})
    response.headers["X-Triage-Source"] = "model"
    response.headers["X-Triage-Repaired"] = str(result.repaired).lower()
    return result.triage
