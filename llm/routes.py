"""POST /triage: a messy note in, one validated task suggestion out."""
import os

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from llm import provider, prompt
from llm.schema import STUB, Triage, TriageRequest

router = APIRouter(tags=["ai"])


@router.post("/triage", response_model=Triage, summary="Turn a messy note into a structured task (LLM)")
def triage(body: TriageRequest, response: Response):
    # input was already validated by Pydantic: a bad request never reaches this line, so it never costs a call
    if os.environ.get("LLM_STUB") == "1":
        response.headers["X-Triage-Source"] = "stub"
        return STUB
    version = prompt.prompt_version()
    completion = provider.from_env().complete(prompt.build_messages(body.text, version))
    # Stage 2 only: show what the model said, so we can read it with our own eyes. Stage 3 validates it.
    return JSONResponse({"raw": completion.text, "prompt_version": version, "model": completion.model})
