"""Answer composer — Claude Sonnet, given the structured state, produces NL response.

Per ADR-style discipline: the LLM only renders pre-computed facts. It does not
re-derive numbers from data, which keeps faithfulness scores high (the evalkit
golden set asserts citation precision/recall).
"""

import json
from typing import Any

from anthropic import AsyncAnthropic

from advisor.agent.intents import AdvisorState


_COMPOSER_MODEL = "claude-sonnet-4-6"


_SYSTEM = (
    "You are a solar-economics advisor. The user's question is followed by a "
    "structured facts block computed by the agent's data nodes.\n\n"
    "HARD RULES:\n"
    "1. Use ONLY the numbers, percentages, source names, and definitions present "
    "in the facts block. Do NOT draw on general knowledge of solar incentives, "
    "federal tax credits, market norms, or industry rules of thumb — even when "
    "you believe such information is correct and helpful. If the federal "
    "Residential Clean Energy Credit is not in the facts block, do not mention "
    "it.\n"
    "2. If the user asked about something the facts block doesn't cover "
    "(payback when production data is missing, incentives when DSIRE wasn't "
    "called, etc.), say so explicitly. Never fill the gap from training.\n"
    "3. Cite specific data sources by name (Solar Cost Explorer, NREL PVWatts, "
    "DSIRE, EIA) inline when you state a number from them.\n\n"
    "Respond in 2-4 concise paragraphs."
)


def _summarize_state_for_prompt(state: AdvisorState) -> str:
    parts: list[str] = []
    parts.append(f"Intent: {state.get('intent')}")

    bands = state.get("cost_bands") or []
    if bands:
        b = bands[0]
        parts.append(
            f"Cost band sample: {b.system_size_range} / {b.panel_tier} / {b.location} / "
            f"{b.installer_type} → p25=${b.p25}/W, p50=${b.p50}/W, p75=${b.p75}/W, "
            f"p90={'$' + str(b.p90) + '/W' if b.p90 is not None else 'gated'}, N={b.sample_size}"
        )

    prod = state.get("production")
    if prod:
        parts.append(
            f"NREL PVWatts: {prod.system_capacity_kw} kW at ({prod.lat:.2f}, {prod.lon:.2f}) → "
            f"{prod.ac_annual_kwh:,.0f} kWh/year, capacity factor {prod.capacity_factor:.1f}%, "
            f"solar resource {prod.solrad_annual:.2f} kWh/m²/day."
        )

    incentives = state.get("incentives") or []
    for i in incentives:
        parts.append(f"Incentive: {i.name} — {i.value_description}. {i.notes}")

    rate = state.get("rate")
    if rate:
        parts.append(
            f"EIA residential rate for {rate.state_code} ({rate.period}): "
            f"{rate.price_cents_per_kwh:.2f} ¢/kWh"
        )

    payback = state.get("payback_years")
    if payback is not None:
        parts.append(f"Computed payback period: {payback:.1f} years")

    errors = state.get("errors") or []
    if errors:
        parts.append("Source errors: " + "; ".join(f"{e['source']}={e['kind']}" for e in errors))

    return "\n".join(parts) if parts else "(no facts gathered)"


async def compose_answer(state: AdvisorState) -> dict[str, Any]:
    client = AsyncAnthropic()
    facts = _summarize_state_for_prompt(state)
    user_msg = f"Question: {state['question']}\n\nFacts:\n{facts}"

    response = await client.messages.create(
        model=_COMPOSER_MODEL,
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    return {"answer": text}
