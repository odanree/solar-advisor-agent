"""LangGraph supervisor — wires the classifier, intent nodes, and answer composer."""

from langgraph.graph import END, StateGraph

from advisor.agent.intents import AdvisorState
from advisor.agent.nodes.answer import compose_answer
from advisor.agent.nodes.classify import classify_intent
from advisor.agent.nodes.cost_lookup import run_cost_lookup
from advisor.agent.nodes.payback import run_payback
from advisor.governance import attach_governance


def _route_by_intent(state: AdvisorState) -> str:
    intent = state.get("intent")
    if intent == "cost_lookup":
        return "cost_lookup"
    if intent == "payback_estimate":
        return "payback"
    # unknown / fallback: skip data nodes, go straight to answer (which will
    # explain that the question wasn't classifiable).
    return "answer"


def build_graph():
    g = StateGraph(AdvisorState)

    g.add_node("classify", classify_intent)
    g.add_node("cost_lookup", run_cost_lookup)
    g.add_node("payback", run_payback)
    g.add_node("answer", compose_answer)
    g.add_node("governance", attach_governance)

    g.set_entry_point("classify")
    g.add_conditional_edges(
        "classify",
        _route_by_intent,
        {"cost_lookup": "cost_lookup", "payback": "payback", "answer": "answer"},
    )
    g.add_edge("cost_lookup", "answer")
    g.add_edge("payback", "answer")
    g.add_edge("answer", "governance")
    g.add_edge("governance", END)

    return g.compile()
