"""Intent types + shared state shape for the LangGraph supervisor."""

from typing import Any, Literal, TypedDict

from advisor.sources.dsire import Incentive
from advisor.sources.eia_rates import RateResult
from advisor.sources.nrel_pvwatts import PvWattsResult
from advisor.sources.solar_cost_graphql import CostBand


Intent = Literal["cost_lookup", "payback_estimate", "unknown"]


class Citation(TypedDict):
    source: str  # "solar_cost_explorer" | "nrel_pvwatts" | "dsire" | "eia"
    detail: str  # short human-readable provenance string
    url: str | None


class AdvisorState(TypedDict, total=False):
    """LangGraph state. `total=False` so partial updates from each node are valid."""

    question: str
    intent: Intent
    intent_params: dict[str, Any]
    cost_bands: list[CostBand]
    production: PvWattsResult
    incentives: list[Incentive]
    rate: RateResult
    payback_years: float
    answer: str
    citations: list[Citation]
    errors: list[dict[str, Any]]
    governance_report: dict[str, Any]
