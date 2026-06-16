"""Intent classifier — Claude Haiku with forced tool use for structured output.

Returns one of two intents plus a normalized `intent_params` dict. The two intent
"tools" are defined as schemas so Claude's tool-use forcing extracts the right
shape without prompt-engineering acrobatics or fragile JSON-in-text parsing.
"""

import json
from typing import Any

from anthropic import AsyncAnthropic

from advisor.agent.intents import AdvisorState


_CLASSIFIER_MODEL = "claude-haiku-4-5"


_TOOLS: list[dict[str, Any]] = [
    {
        "name": "cost_lookup",
        "description": (
            "Look up solar installation cost benchmarks ($/W) for a given location, "
            "optionally filtered by system size, panel tier, or installer type."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "US state name."},
                "system_size_range": {
                    "type": "string",
                    "enum": ["3-5 kW", "5-8 kW", "8-12 kW", "12 kW+"],
                },
                "panel_tier": {
                    "type": "string",
                    "enum": ["standard", "premium", "premium-plus"],
                },
                "installer_type": {
                    "type": "string",
                    "enum": ["local", "national"],
                },
            },
            "required": ["location"],
        },
    },
    {
        "name": "payback_estimate",
        "description": (
            "Estimate solar payback period in years by combining: cost band ($/W), "
            "production estimate (kWh/yr from NREL PVWatts), incentives (federal + state), "
            "and current state electricity rate. Use when user asks about ROI, payback, "
            "or 'is solar worth it'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "US state name. Required.",
                },
                "system_capacity_kw": {
                    "type": "number",
                    "description": "System size in kW. Default 6 if user doesn't specify.",
                },
                "lat": {
                    "type": "number",
                    "description": "Latitude if user gave a specific location.",
                },
                "lon": {"type": "number"},
            },
            "required": ["location"],
        },
    },
]


_SYSTEM_PROMPT = (
    "You are an intent classifier for a solar-economics advisor. Read the user "
    "question and call EXACTLY ONE of the provided tools with extracted parameters. "
    "If the question is about cost/price benchmarks, use cost_lookup. If it's about "
    "ROI, payback, or 'is solar worth it', use payback_estimate. If the question is "
    "out of scope (not about solar economics), still pick the closest tool — the "
    "downstream nodes will produce a graceful error."
)


async def classify_intent(state: AdvisorState) -> dict[str, Any]:
    client = AsyncAnthropic()
    response = await client.messages.create(
        model=_CLASSIFIER_MODEL,
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        tools=_TOOLS,
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": state["question"]}],
    )

    for block in response.content:
        if block.type == "tool_use":
            return {
                "intent": block.name,
                "intent_params": dict(block.input) if block.input else {},
            }

    # Fallback if Claude returned text instead of a tool call (shouldn't happen
    # with tool_choice="any" but defend against it anyway).
    return {
        "intent": "unknown",
        "intent_params": {},
        "errors": [{"node": "classify", "message": "No tool call in response"}],
    }
