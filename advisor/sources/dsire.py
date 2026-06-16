"""Solar incentive lookup.

DSIRE's official API is unstable and undocumented for programmatic use. For
the MVP this module ships a curated baseline: the federal Residential Clean
Energy Credit (30% through 2032) plus a small set of known-active state
programs. A follow-up could swap this for a real DSIRE API call or a periodic
scraper into a cached table.

Returning baked-in data is honestly disclosed via `is_static_baseline=True`
on the result so the agent's answer can carry a freshness caveat.
"""

from pydantic import BaseModel


class Incentive(BaseModel):
    name: str
    kind: str  # "tax_credit" | "rebate" | "performance_payment"
    scope: str  # "federal" | "state"
    state: str | None
    value_description: str
    value_pct: float | None = None
    value_dollar_per_watt: float | None = None
    notes: str
    source_url: str
    is_static_baseline: bool = True


_FEDERAL = Incentive(
    name="Residential Clean Energy Credit (Federal)",
    kind="tax_credit",
    scope="federal",
    state=None,
    value_description="30% of total system cost",
    value_pct=30.0,
    notes=(
        "In effect through 2032 per the Inflation Reduction Act of 2022. "
        "Steps down to 26% in 2033 and 22% in 2034."
    ),
    source_url="https://www.irs.gov/credits-deductions/residential-clean-energy-credit",
)


_STATE_INCENTIVES: dict[str, list[Incentive]] = {
    "California": [
        Incentive(
            name="Self-Generation Incentive Program (SGIP) — paired storage",
            kind="rebate",
            scope="state",
            state="California",
            value_description="Rebate for paired battery storage; varies by utility and budget step",
            notes=(
                "SGIP rebates apply when solar is paired with a qualifying battery. "
                "Solar alone is not directly rebated since the California Solar Initiative ended."
            ),
            source_url="https://www.cpuc.ca.gov/sgip",
        ),
    ],
    "New York": [
        Incentive(
            name="NY-Sun Megawatt Block",
            kind="rebate",
            scope="state",
            state="New York",
            value_description="Per-watt incentive; varies by region and remaining MW block",
            value_dollar_per_watt=0.20,
            notes=(
                "Approximate; actual incentive depends on which Megawatt Block is "
                "currently active in your utility region."
            ),
            source_url="https://www.nyserda.ny.gov/All-Programs/NY-Sun",
        ),
    ],
    "Massachusetts": [
        Incentive(
            name="SMART (Solar Massachusetts Renewable Target)",
            kind="performance_payment",
            scope="state",
            state="Massachusetts",
            value_description="10-year per-kWh production payment",
            notes=(
                "Block-based; rate depends on current SMART block and utility territory."
            ),
            source_url="https://www.mass.gov/info-details/solar-massachusetts-renewable-target-smart",
        ),
    ],
}


async def lookup_incentives(state: str) -> list[Incentive]:
    """Return federal + any known state-specific incentives.

    Async for parity with other source modules so the LangGraph node interface
    is uniform; no IO happens here in the static-baseline build.
    """
    result = [_FEDERAL]
    result.extend(_STATE_INCENTIVES.get(state, []))
    return result
