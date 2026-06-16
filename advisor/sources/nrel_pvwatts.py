"""NREL PVWatts v8 — annual production estimate for a given lat/lon + system."""

import httpx
from pydantic import BaseModel

from . import SourceHttpError, SourceNetworkError, SourceParseError


class PvWattsResult(BaseModel):
    ac_annual_kwh: float
    capacity_factor: float
    solrad_annual: float  # avg daily solar radiation kWh/m^2/day
    lat: float
    lon: float
    system_capacity_kw: float


async def estimate_production(
    *,
    api_key: str,
    lat: float,
    lon: float,
    system_capacity_kw: float,
    module_type: int = 0,  # 0=standard, 1=premium, 2=thin film
    losses_pct: float = 14.0,
    array_type: int = 1,  # 1=fixed roof mount, common residential default
    tilt_deg: float = 20.0,
    azimuth_deg: float = 180.0,  # south-facing
    timeout: float = 15.0,
) -> PvWattsResult:
    params = {
        "api_key": api_key,
        "lat": lat,
        "lon": lon,
        "system_capacity": system_capacity_kw,
        "module_type": module_type,
        "losses": losses_pct,
        "array_type": array_type,
        "tilt": tilt_deg,
        "azimuth": azimuth_deg,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(
                "https://developer.nrel.gov/api/pvwatts/v8.json", params=params
            )
    except httpx.HTTPError as e:
        raise SourceNetworkError(f"PVWatts request failed: {e}") from e

    if r.status_code != 200:
        raise SourceHttpError(r.status_code, r.text)

    try:
        body = r.json()
        if body.get("errors"):
            raise SourceParseError(f"PVWatts errors: {body['errors']}")
        outputs = body["outputs"]
        return PvWattsResult(
            ac_annual_kwh=float(outputs["ac_annual"]),
            capacity_factor=float(outputs["capacity_factor"]),
            solrad_annual=float(outputs["solrad_annual"]),
            lat=lat,
            lon=lon,
            system_capacity_kw=system_capacity_kw,
        )
    except (KeyError, TypeError, ValueError) as e:
        raise SourceParseError(f"Bad PVWatts response shape: {e}") from e
