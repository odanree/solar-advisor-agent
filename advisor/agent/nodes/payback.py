"""payback_estimate intent — composite calculation across 4 data sources.

Math:
    system_cost      = median_dollar_per_watt * system_capacity_kw * 1000
    federal_credit   = system_cost * 0.30 (Residential Clean Energy Credit)
    state_rebate_$$  = sum of state rebates expressible as $/W
    net_cost         = system_cost - federal_credit - state_rebate_$$
    annual_savings   = annual_kwh * (price_cents_per_kwh / 100)
    payback_years    = net_cost / annual_savings

If any source fails the agent still returns a partial answer with whichever
pieces succeeded, plus an error envelope per failed source.
"""

import asyncio
from typing import Any

from advisor.agent.intents import AdvisorState, Citation
from advisor.config import get_settings
from advisor.sources import SourceError
from advisor.sources.dsire import lookup_incentives
from advisor.sources.eia_rates import get_residential_rate
from advisor.sources.nrel_pvwatts import estimate_production
from advisor.sources.solar_cost_graphql import fetch_cost_bands


# State centroids for production estimates when the user doesn't give a ZIP/city.
# Sufficient for portfolio-grade payback estimates; an MVP could swap in real
# geocoding later (Nominatim or NREL's own geocoder).
_STATE_CENTROIDS: dict[str, tuple[float, float]] = {
    "California": (37.0, -119.4),
    "Texas": (31.5, -99.3),
    "Florida": (28.6, -82.5),
    "Arizona": (34.0, -111.7),
    "New York": (42.9, -75.6),
    "Massachusetts": (42.4, -71.5),
    "Washington": (47.4, -120.7),
    "Colorado": (39.0, -105.5),
    "Hawaii": (20.6, -157.5),
    "New Jersey": (40.2, -74.5),
    "North Carolina": (35.6, -79.4),
    "Nevada": (39.3, -116.6),
}


def _system_size_to_range(kw: float) -> str:
    if kw < 5:
        return "3-5 kW"
    if kw < 8:
        return "5-8 kW"
    if kw < 12:
        return "8-12 kW"
    return "12 kW+"


def _pick_median(bands: list, default: float = 3.5) -> float:
    """Median $/W from the highest-N standard/local band when available."""
    if not bands:
        return default
    standards = [b for b in bands if b.panel_tier == "standard" and b.p50 is not None]
    if standards:
        # Highest sample size wins
        return max(standards, key=lambda b: b.sample_size).p50  # type: ignore[return-value]
    return next((b.p50 for b in bands if b.p50 is not None), default)


async def run_payback(state: AdvisorState) -> dict[str, Any]:
    settings = get_settings()
    params = state.get("intent_params", {})
    location: str = params.get("location") or ""
    system_kw: float = float(params.get("system_capacity_kw") or 6.0)
    lat: float | None = params.get("lat")
    lon: float | None = params.get("lon")

    if lat is None or lon is None:
        centroid = _STATE_CENTROIDS.get(location)
        if centroid:
            lat, lon = centroid

    errors: list[dict[str, Any]] = []
    citations: list[Citation] = []

    # Fan out to all four sources concurrently.
    bands_task = fetch_cost_bands(
        url=settings.solar_cost_graphql_url,
        location=location,
        system_size_range=_system_size_to_range(system_kw),
    )
    production_task = (
        estimate_production(
            api_key=settings.nrel_api_key,
            lat=lat,
            lon=lon,
            system_capacity_kw=system_kw,
        )
        if lat is not None and lon is not None
        else None
    )
    incentives_task = lookup_incentives(location)
    rate_task = get_residential_rate(api_key=settings.eia_api_key, state=location)

    coros = [bands_task, incentives_task, rate_task]
    if production_task is not None:
        coros.append(production_task)
    results = await asyncio.gather(*coros, return_exceptions=True)

    bands = results[0] if not isinstance(results[0], BaseException) else None
    incentives = results[1] if not isinstance(results[1], BaseException) else None
    rate = results[2] if not isinstance(results[2], BaseException) else None
    production = None
    if production_task is not None:
        production = results[3] if not isinstance(results[3], BaseException) else None

    for label, r in zip(
        ["solar_cost_explorer", "dsire", "eia", "nrel_pvwatts"],
        [bands, incentives, rate, production],
    ):
        if r is None:
            # Find the matching result for diagnostic
            idx = ["solar_cost_explorer", "dsire", "eia", "nrel_pvwatts"].index(label)
            if idx < len(results):
                err = results[idx]
                kind = err.kind if isinstance(err, SourceError) else "unknown"
                errors.append(
                    {"node": "payback", "source": label, "kind": kind, "message": str(err)}
                )

    # Citations for whatever we got
    if bands:
        citations.append(
            {
                "source": "solar_cost_explorer",
                "detail": f"Cost band for {location} / {_system_size_to_range(system_kw)}: {len(bands)} rows",
                "url": settings.solar_cost_graphql_url,
            }
        )
    if production:
        citations.append(
            {
                "source": "nrel_pvwatts",
                "detail": (
                    f"NREL PVWatts v8: {system_kw} kW system at ({lat:.2f}, {lon:.2f}) → "
                    f"{production.ac_annual_kwh:,.0f} kWh/year"
                ),
                "url": "https://developer.nlr.gov/docs/solar/pvwatts/v8/",
            }
        )
    if incentives:
        names = ", ".join(i.name for i in incentives)
        citations.append(
            {
                "source": "dsire",
                "detail": f"Incentives applied: {names}",
                "url": "https://programs.dsireusa.org/",
            }
        )
    if rate:
        citations.append(
            {
                "source": "eia",
                "detail": (
                    f"EIA residential rate for {rate.state_code} (period {rate.period}): "
                    f"{rate.price_cents_per_kwh:.2f} ¢/kWh"
                ),
                "url": "https://api.eia.gov/v2/electricity/retail-sales/data/",
            }
        )

    # Compute payback if we have the minimum required pieces.
    median_dpw = _pick_median(bands or [])
    system_cost = median_dpw * system_kw * 1000
    federal_credit = system_cost * 0.30
    state_rebate_dollar = sum(
        (i.value_dollar_per_watt or 0) * system_kw * 1000 for i in (incentives or [])
    )
    net_cost = max(system_cost - federal_credit - state_rebate_dollar, 0)
    annual_savings = None
    payback_years = None
    if production and rate:
        annual_savings = production.ac_annual_kwh * (rate.price_cents_per_kwh / 100)
        if annual_savings > 0:
            payback_years = net_cost / annual_savings

    update: dict[str, Any] = {
        "cost_bands": bands or [],
        "production": production,
        "incentives": incentives or [],
        "rate": rate,
        "citations": citations,
        "errors": errors,
    }
    if payback_years is not None:
        update["payback_years"] = payback_years
    return update
