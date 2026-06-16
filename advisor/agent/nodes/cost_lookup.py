"""cost_lookup intent — calls Solar Cost Explorer GraphQL with extracted filters."""

from typing import Any

from advisor.agent.intents import AdvisorState, Citation
from advisor.config import get_settings
from advisor.sources import SourceError
from advisor.sources.solar_cost_graphql import fetch_cost_bands


async def run_cost_lookup(state: AdvisorState) -> dict[str, Any]:
    settings = get_settings()
    params = state.get("intent_params", {})

    try:
        bands = await fetch_cost_bands(
            url=settings.solar_cost_graphql_url,
            location=params.get("location"),
            system_size_range=params.get("system_size_range"),
            panel_tier=params.get("panel_tier"),
            installer_type=params.get("installer_type"),
            first=10,
        )
    except SourceError as e:
        return {
            "errors": [
                {"node": "cost_lookup", "source": "solar_cost_explorer", "kind": e.kind, "message": str(e)}
            ],
            "cost_bands": [],
        }

    citation: Citation = {
        "source": "solar_cost_explorer",
        "detail": (
            f"Queried Solar Cost Explorer GraphQL for "
            f"location={params.get('location')}, "
            f"size={params.get('system_size_range') or 'any'}, "
            f"tier={params.get('panel_tier') or 'any'}, "
            f"installer={params.get('installer_type') or 'any'} "
            f"→ {len(bands)} bands returned"
        ),
        "url": settings.solar_cost_graphql_url,
    }
    return {"cost_bands": bands, "citations": [citation]}
