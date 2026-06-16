"""Run the golden set through the agent and score with evalkit.

Usage:
    python -m advisor.eval.run                 # full run, requires API keys
    python -m advisor.eval.run --intent-only   # skip Claude calls, only verify intent classification

CI uses --intent-only by default (no LLM cost). Full eval is run manually before
shipping schema/prompt changes.
"""

import argparse
import asyncio
import sys
from pathlib import Path

import yaml

from advisor.agent.supervisor import build_graph


_GOLDEN_PATH = Path(__file__).parent / "golden_set.yaml"


async def _run_intent_only() -> int:
    cases = yaml.safe_load(_GOLDEN_PATH.read_text())["cases"]
    graph = build_graph()

    correct = 0
    for case in cases:
        # Only run classification, not the full graph.
        from advisor.agent.nodes.classify import classify_intent

        result = await classify_intent({"question": case["question"]})
        got = result["intent"]
        expected = case["expected_intent"]
        status = "✓" if got == expected else "✗"
        print(f"{status} {case['id']}: expected={expected} got={got}")
        if got == expected:
            correct += 1

    pct = 100 * correct / len(cases)
    print(f"\nIntent classification: {correct}/{len(cases)} ({pct:.0f}%)")
    return 0 if correct == len(cases) else 1


async def _run_full() -> int:
    try:
        from evalkit import Evaluator, Faithfulness  # type: ignore
    except ImportError:
        print("evalkit not installed; install with: pip install -e '.[eval]'", file=sys.stderr)
        return 2

    cases = yaml.safe_load(_GOLDEN_PATH.read_text())["cases"]
    graph = build_graph()
    evaluator = Evaluator(metrics=[Faithfulness()])

    total = 0.0
    for case in cases:
        result = await graph.ainvoke({"question": case["question"]})
        answer = result.get("answer", "")
        score = await evaluator.score(
            output=answer,
            reference=case["reference"],
            context=[c["detail"] for c in result.get("citations", [])],
        )
        print(f"{case['id']}: faithfulness={score.value:.2f}")
        total += score.value

    avg = total / len(cases)
    print(f"\nAverage faithfulness: {avg:.2f}")
    return 0 if avg >= 0.7 else 1  # Fail CI if below floor.


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intent-only", action="store_true")
    args = parser.parse_args()
    if args.intent_only:
        return asyncio.run(_run_intent_only())
    return asyncio.run(_run_full())


if __name__ == "__main__":
    raise SystemExit(main())
