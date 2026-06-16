"""EIA — latest residential electricity rate by state (¢/kWh)."""

import httpx
from pydantic import BaseModel

from . import SourceHttpError, SourceNetworkError, SourceParseError


US_STATE_ABBR: dict[str, str] = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}


class RateResult(BaseModel):
    state: str
    state_code: str
    period: str  # e.g. "2026-04"
    price_cents_per_kwh: float


async def get_residential_rate(
    *,
    api_key: str,
    state: str,
    timeout: float = 10.0,
) -> RateResult:
    state_code = US_STATE_ABBR.get(state)
    if state_code is None:
        raise SourceParseError(f"Unknown state: {state}")

    params = {
        "api_key": api_key,
        "frequency": "monthly",
        "data[0]": "price",
        "facets[stateid][]": state_code,
        "facets[sectorid][]": "RES",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "offset": 0,
        "length": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(
                "https://api.eia.gov/v2/electricity/retail-sales/data/", params=params
            )
    except httpx.HTTPError as e:
        raise SourceNetworkError(f"EIA request failed: {e}") from e

    if r.status_code != 200:
        raise SourceHttpError(r.status_code, r.text)

    try:
        body = r.json()
        rows = body["response"]["data"]
        if not rows:
            raise SourceParseError(f"No EIA data for state {state_code}")
        row = rows[0]
        return RateResult(
            state=state,
            state_code=state_code,
            period=str(row["period"]),
            price_cents_per_kwh=float(row["price"]),
        )
    except (KeyError, TypeError, ValueError) as e:
        raise SourceParseError(f"Bad EIA response shape: {e}") from e
