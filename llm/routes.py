"""POST /triage: a messy note in, one validated task suggestion out."""
import os

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from llm.schema import STUB, Triage, TriageRequest

router = APIRouter(tags=["ai"])


@router.post("/triage", response_model=Triage, summary="Turn a messy note into a structured task (LLM)")
def triage(body: TriageRequest, response: Response):
    # input was already validated by Pydantic: a bad request never reaches this line, so it never costs a call
    if os.environ.get("LLM_STUB") == "1":
        response.headers["X-Triage-Source"] = "stub"
        return STUB
    return JSONResponse(status_code=501, content={"error": "Model call not wired yet (Stage 2). Set LLM_STUB=1."})
