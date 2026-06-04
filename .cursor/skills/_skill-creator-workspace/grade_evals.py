#!/usr/bin/env python3
"""Grade product-teams-orchestrator eval outputs against assertions."""
import json
import re
from pathlib import Path

WORKSPACE = Path(__file__).parent / "iteration-1"

ASSERTIONS = {
    "call-everyone-bear-hardstop": {
        "with_skill": [
            ("routes_council", r"COUNCIL|five-agent-council"),
            ("routes_india_markets", r"india-markets-(orchestrator|portfolio|macro)"),
            ("routes_build", r"BUILD|software-product-backend|software-product-orchestrator"),
            ("mentions_regression", r"test_v2_regression|regression"),
            ("all_layer_or_three", r"all-layer|three layer|Research.*Governance.*Engineering|all three"),
            ("no_skip_council", r"Do NOT.*skip.*COUNCIL|Council required.*YES"),
        ],
        "without_skill": [
            ("mentions_hard_stop", r"hard.?stop|BEAR"),
            ("mentions_regression", r"test_v2_regression|regression"),
        ],
    },
    "build-dashboard-ui": {
        "with_skill": [
            ("council_not_required", r"Council required.*NO|no council|skip.*COUNCIL|Do NOT.*COUNCIL"),
            ("routes_frontend", r"software-product-frontend|Frontend"),
            ("serve_dashboard", r"serve_dashboard"),
            ("presentation_only", r"presentation|same data|no scoring|non-breaking"),
        ],
        "without_skill": [
            ("routes_frontend", r"frontend|Frontend"),
            ("council_not_required", r"Council required.*NO|no council|skip.*council"),
        ],
    },
    "full-view-tcs": {
        "with_skill": [
            ("routes_india_markets", r"india-markets-orchestrator"),
            ("no_council_implement", r"Do NOT.*COUNCIL|Council.*NO|skip.*COUNCIL|NOT.*COUNCIL"),
            ("multi_desk", r"fundamental|technical|macro|portfolio"),
            ("disclaimer", r"disclaimer|SEBI"),
        ],
        "without_skill": [
            ("routes_india_markets", r"india-markets-orchestrator"),
            ("multi_desk", r"fundamental|technical|macro|portfolio"),
        ],
    },
    "council-debate-quality-lvm": {
        "with_skill": [
            ("debate_only", r"DEBATE ONLY|Round 3|no Round 4|no BUILD|STOP"),
            ("five_agent_council", r"five-agent-council|COUNCIL"),
            ("no_implement", r"Do NOT implement|no code|not executed|debate only"),
            ("product_teams_entry", r"product-teams-orchestrator|Classify"),
        ],
        "without_skill": [
            ("debate_only", r"DEBATE ONLY|no Round 4|no BUILD|STOP"),
            ("five_agent_council", r"five-agent-council|COUNCIL"),
        ],
    },
}


def grade(text: str, assertions: list) -> dict:
    results = []
    for name, pattern in assertions:
        found = bool(re.search(pattern, text, re.I | re.S))
        results.append({"text": name, "passed": found, "evidence": pattern if found else "not found"})
    passed = sum(1 for r in results if r["passed"])
    return {
        "expectations": results,
        "pass_rate": passed / len(results) if results else 0,
        "passed": passed,
        "total": len(results),
    }


def main():
    summary = {"evals": [], "with_skill_total": 0, "with_skill_passed": 0,
               "without_skill_total": 0, "without_skill_passed": 0}

    for eval_name, configs in ASSERTIONS.items():
        row = {"eval_name": eval_name}
        for variant in ("with_skill", "without_skill"):
            out_dir = WORKSPACE / eval_name / variant / "outputs"
            md_files = list(out_dir.glob("*.md"))
            if not md_files:
                # read from transcript placeholder - use combined if missing
                text = (out_dir / "routing-plan.md").read_text() if (out_dir / "routing-plan.md").exists() else ""
            else:
                text = md_files[0].read_text()
            g = grade(text, configs[variant])
            row[variant] = g
            summary[f"{variant}_total"] += g["total"]
            summary[f"{variant}_passed"] += g["passed"]
        summary["evals"].append(row)

    summary["with_skill_rate"] = (
        summary["with_skill_passed"] / summary["with_skill_total"]
        if summary["with_skill_total"] else 0
    )
    summary["without_skill_rate"] = (
        summary["without_skill_passed"] / summary["without_skill_total"]
        if summary["without_skill_total"] else 0
    )
    summary["delta_pp"] = round((summary["with_skill_rate"] - summary["without_skill_rate"]) * 100, 1)

    out = WORKSPACE / "benchmark.json"
    out.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
