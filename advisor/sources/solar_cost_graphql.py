"""Calls the operator's Solar Cost Explorer GraphQL API to fetch $/W cost bands."""

import re

import httpx
from pydantic import BaseModel

from . import SourceHttpError, SourceNetworkError, SourceParseError


class CostBand(BaseModel):
    id: str
    system_size_range: str
    panel_tier: str
    location: str
    installer_type: str
    p25: float | None
    p50: float | None
    p75: float | None
    p90: float | None
    sample_size: int


COST_BANDS_QUERY = """
query GetCostBands($filters: CostBandFilter, $first: Int) {
  costBands(first: $first, filters: $filters) {
    edges {
      node {
        id
        systemSizeRange
        panelTier
        location
        installerType
        p25
        p50
        p75
        p90
        sampleSize
      }
    }
    totalCount
  }
}
"""


def _camel_to_snake(d: dict) -> dict:
    return {re.sub(r"(?<!^)(?=[A-Z])", "_", k).lower(): v for k, v in d.items()}


async def fetch_cost_bands(
    *,
    url: str,
    location: str | None = None,
    system_size_range: str | None = None,
    panel_tier: str | None = None,
    installer_type: str | None = None,
    first: int = 20,
    timeout: float = 10.0,
) -> list[CostBand]:
    filters: dict[str, str] = {}
    if location:
        filters["location"] = location
    if system_size_range:
        filters["systemSizeRange"] = system_size_range
    if panel_tier:
        filters["panelTier"] = panel_tier
    if installer_type:
        filters["installerType"] = installer_type

    variables: dict = {"first": first}
    if filters:
        variables["filters"] = filters

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, json={"query": COST_BANDS_QUERY, "variables": variables})
    except httpx.HTTPError as e:
        raise SourceNetworkError(f"GraphQL request failed: {e}") from e

    if r.status_code != 200:
        raise SourceHttpError(r.status_code, r.text)

    try:
        body = r.json()
        if "errors" in body:
            raise SourceParseError(f"GraphQL errors: {body['errors']}")
        edges = body["data"]["costBands"]["edges"]
        return [CostBand.model_validate(_camel_to_snake(e["node"])) for e in edges]
    except (KeyError, TypeError, ValueError) as e:
        raise SourceParseError(f"Bad GraphQL response shape: {e}") from e
