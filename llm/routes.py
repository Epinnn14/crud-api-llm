"""POST /triage: a messy note in, one validated task suggestion out."""
import os

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from llm import prompt, provider, triage as triage_service
from llm.schema import STUB, Triage, TriageRequest

router = APIRouter(tags=["ai"])


@router.post("/triage", response_model=Triage, summary="Turn a messy note into a structured task (LLM)")
def triage(body: TriageRequest, response: Response):
    # input was already validated by Pydantic: a bad request never reaches this line, so it never costs a call
    if os.environ.get("LLM_STUB") == "1":
        response.headers["X-Triage-Source"] = "stub"
        return STUB
    version = prompt.prompt_version()
    try:
        result = triage_service.run(body.text, provider.from_env(), version)
    except triage_service.OutputRejected as e:
        # never the raw model text: our own message, and the reason in schema terms
        return JSONResponse(status_code=422, content={
            "error": "The model's answer did not match the schema, even after one repair attempt. "
                     "It was quarantined for review.",
            "reason": str(e), "prompt_version": version})
    response.headers["X-Triage-Source"] = "model"
    response.headers["X-Triage-Repaired"] = str(result.repaired).lower()
    return result.triage
