"""FastAPI HTTP entry point."""

import logging
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from advisor.agent.supervisor import build_graph
from advisor.config import get_settings


logging.basicConfig(level=get_settings().log_level)
log = logging.getLogger("advisor.api")


app = FastAPI(title="Solar Advisor Agent", version="0.1.0")
_GRAPH = build_graph()


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    intent: str | None = None
    citations: list[dict[str, Any]] = []
    payback_years: float | None = None
    governance_report: dict[str, Any] | None = None
    errors: list[dict[str, Any]] = []


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    log.info("query received: %s", req.question[:100])
    initial = {"question": req.question, "citations": [], "errors": []}
    final = await _GRAPH.ainvoke(initial)
    return QueryResponse(
        answer=final.get("answer", ""),
        intent=final.get("intent"),
        citations=final.get("citations", []),
        payback_years=final.get("payback_years"),
        governance_report=final.get("governance_report"),
        errors=final.get("errors", []),
    )
