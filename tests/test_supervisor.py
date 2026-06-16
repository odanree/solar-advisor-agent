"""End-to-end supervisor test — mocks Claude classifier/composer + all sources.

Verifies the graph wires correctly: classify → route → data node → answer →
governance → END, with citations and governance_report populated.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from advisor.agent.supervisor import build_graph
from advisor.sources.solar_cost_graphql import CostBand


@pytest.fixture
def fake_cost_band():
    return CostBand(
        id="1",
        system_size_range="5-8 kW",
        panel_tier="standard",
        location="California",
        installer_type="local",
        p25=2.95,
        p50=3.35,
        p75=3.75,
        p90=4.20,
        sample_size=120,
    )


def _make_anthropic_response(tool_name: str | None = None, text: str = "answer body"):
    """Build a fake Anthropic Messages response."""
    blocks = []
    if tool_name:
        tu = MagicMock()
        tu.type = "tool_use"
        tu.name = tool_name
        tu.input = {"location": "California"}
        blocks.append(tu)
    else:
        tb = MagicMock()
        tb.type = "text"
        tb.text = text
        blocks.append(tb)
    resp = MagicMock()
    resp.content = blocks
    return resp


async def test_cost_lookup_path(fake_cost_band, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setenv("SOLAR_COST_GRAPHQL_URL", "https://example.test/graphql/")

    classify_resp = _make_anthropic_response(tool_name="cost_lookup")
    compose_resp = _make_anthropic_response(text="The median cost in California is $3.35/W.")

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[classify_resp, compose_resp])

    with (
        patch("advisor.agent.nodes.classify.AsyncAnthropic", return_value=mock_client),
        patch("advisor.agent.nodes.answer.AsyncAnthropic", return_value=mock_client),
        patch(
            "advisor.agent.nodes.cost_lookup.fetch_cost_bands",
            new=AsyncMock(return_value=[fake_cost_band]),
        ),
    ):
        graph = build_graph()
        final = await graph.ainvoke({"question": "Median $/W in California?"})

    assert final["intent"] == "cost_lookup"
    assert len(final["cost_bands"]) == 1
    assert "California" in final["answer"]
    assert any(c["source"] == "solar_cost_explorer" for c in final["citations"])
    assert "governance_report" in final
    assert "computed_payback" not in final["governance_report"]["provenance_flags"]


async def test_unknown_intent_skips_data_nodes(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")

    # Classifier returns no tool call → falls back to "unknown" intent.
    classify_resp = MagicMock()
    classify_resp.content = []
    compose_resp = _make_anthropic_response(text="I can't classify that question.")

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[classify_resp, compose_resp])

    with (
        patch("advisor.agent.nodes.classify.AsyncAnthropic", return_value=mock_client),
        patch("advisor.agent.nodes.answer.AsyncAnthropic", return_value=mock_client),
    ):
        graph = build_graph()
        final = await graph.ainvoke({"question": "What is the meaning of life?"})

    assert final["intent"] == "unknown"
    assert final["cost_bands"] == [] or final.get("cost_bands") is None
    assert "governance_report" in final
