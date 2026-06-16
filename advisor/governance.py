"""Governance node — runs after the answer composer.

Attaches a `governance_report` to the state with provenance flags, freshness
disclaimers (DSIRE incentives are baked-in static data; state-centroid lat/lon
is an approximation), and source-error telemetry.

Designed to mirror the agent-governance package's shape so this can be swapped
to a versioned dependency later. Inlined here for MVP to avoid the round-trip.
"""

from typing import Any, TypedDict

from advisor.agent.intents import AdvisorState


class GovernanceReport(TypedDict, total=False):
    provenance_flags: list[str]
    disclaimer: str
    source_errors: list[dict[str, Any]]
    telemetry: dict[str, Any]


def _build_disclaimer(state: AdvisorState) -> str:
    notes: list[str] = []

    incentives = state.get("incentives") or []
    if any(getattr(i, "is_static_baseline", False) for i in incentives):
        notes.append(
            "Incentive data is from a static baseline (federal Residential Clean "
            "Energy Credit + curated state programs), not a live DSIRE pull."
        )

    params = state.get("intent_params") or {}
    if (params.get("lat") is None or params.get("lon") is None) and state.get("production"):
        notes.append(
            "Production estimate used the state centroid as fallback latitude/longitude "
            "since no ZIP or city was provided — accuracy improves with a specific location."
        )

    if not notes:
        return ""
    return " ".join(notes)


def attach_governance(state: AdvisorState) -> dict[str, Any]:
    flags: list[str] = []
    if state.get("payback_years") is not None:
        flags.append("computed_payback")
    if state.get("errors"):
        flags.append("partial_data")
    if not state.get("cost_bands"):
        flags.append("no_cost_band_match")

    report: GovernanceReport = {
        "provenance_flags": flags,
        "disclaimer": _build_disclaimer(state),
        "source_errors": state.get("errors") or [],
        "telemetry": {
            "citation_count": len(state.get("citations") or []),
            "sources_used": list({c["source"] for c in state.get("citations") or []}),
        },
    }

    # Append disclaimer to the answer text so it can't be stripped by clients
    # that ignore governance metadata.
    answer = state.get("answer", "")
    if report["disclaimer"]:
        answer = f"{answer}\n\n_{report['disclaimer']}_"

    return {"answer": answer, "governance_report": report}
