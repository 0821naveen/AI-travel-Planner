from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from typing import Any

from src.agents.travel_planner import nodes as planner_nodes
from src.agents.travel_planner.graph import TravelPlannerGraph
from src.agents.travel_planner.research_clients import ResearchClientError
from src.agents.travel_planner.schemas import ResearchSource
from src.agents.travel_planner.tooling.base import ToolUsage
from src.evals.golden_cases import FAILURE_CASES, GOLDEN_CASES, EvalCase
from src.evals.regressions import check_prompt_contracts, check_regression_baseline, write_regression_baseline
from src.evals.scoring import score_context


class _FakeRegistry:
    def __init__(self, case: EvalCase) -> None:
        self.case = case

    def is_available(self, name: str) -> bool:
        return True


class _FakePayloadResult:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.usage = ToolUsage()


class _FakeSearchResult:
    def __init__(self, summary: str) -> None:
        self.summary = summary
        self.sources = [
            ResearchSource(
                title="Eval source",
                url="https://example.com/eval-source",
                snippet="Deterministic evaluation source for offline quality testing.",
            )
        ]
        self.usage = ToolUsage()


class _FakeToolExecutor:
    def __init__(self, case: EvalCase, agent_name: str) -> None:
        self.case = case
        self.agent_name = agent_name
        self.registry = _FakeRegistry(case)

    def execute(self, name: str, payload: Any) -> Any:
        if name in self.case.failing_tools:
            raise ResearchClientError(self.case.failing_tools[name])

        if name == "weather_lookup":
            return _FakePayloadResult(self.case.weather_payload)
        if name == "web_search":
            return _FakeSearchResult(self.case.web_search_summary)
        if name == "json_completion":
            if self.agent_name in self.case.failing_agents:
                raise ResearchClientError(self.case.failing_agents[self.agent_name])
            try:
                response_payload = self.case.agent_outputs[self.agent_name]
            except KeyError as exc:
                raise ResearchClientError(f"Missing mocked output for agent {self.agent_name}") from exc
            return _FakePayloadResult(response_payload)
        raise ResearchClientError(f"Unknown tool requested in eval runner: {name}")


def _run_case(case: EvalCase):
    original = planner_nodes.build_tool_executor
    planner_nodes.build_tool_executor = lambda context, agent_name: _FakeToolExecutor(case, agent_name)
    try:
        graph = TravelPlannerGraph()
        context = graph.bootstrap_trip(
            trip_id=f"eval-trip-{case.case_id}",
            request=case.request,
            run_id=f"eval-run-{case.case_id}",
        )
        return context
    finally:
        planner_nodes.build_tool_executor = original


def _check_case(case: EvalCase, context) -> dict[str, Any]:
    scores = score_context(context)
    issues: list[str] = []

    for label, min_score in case.expectation.min_scores.items():
        actual = getattr(scores, label)
        if actual < min_score:
            issues.append(f"{case.case_id}: score '{label}'={actual} is below threshold {min_score}")

    for flag in case.expectation.required_flags:
        if flag not in context.governance_flags:
            issues.append(f"{case.case_id}: required governance flag missing: {flag}")

    for flag in case.expectation.forbidden_flags:
        if flag in context.governance_flags:
            issues.append(f"{case.case_id}: forbidden governance flag present: {flag}")

    if case.expectation.expected_status and context.status.value != case.expectation.expected_status:
        issues.append(
            f"{case.case_id}: expected status {case.expectation.expected_status!r} but got {context.status.value!r}"
        )

    for step_name in case.expectation.expected_route_contains:
        if step_name not in context.route_trace:
            issues.append(f"{case.case_id}: expected route trace to include {step_name}")

    return {
        "case_id": case.case_id,
        "kind": case.kind,
        "scores": asdict(scores),
        "status": context.status.value,
        "governance_flags": list(context.governance_flags),
        "route_trace": list(context.route_trace),
        "issues": issues,
    }


def run_eval_suite() -> dict[str, Any]:
    prompt_issues = check_prompt_contracts()
    baseline_issues = check_regression_baseline()
    case_reports = [_check_case(case, _run_case(case)) for case in [*GOLDEN_CASES, *FAILURE_CASES]]
    case_issues = [issue for report in case_reports for issue in report["issues"]]
    all_issues = [*prompt_issues, *baseline_issues, *case_issues]
    return {
        "passed": not all_issues,
        "issues": all_issues,
        "cases": case_reports,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic offline evals for the travel planner.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any eval issue is found.")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Write the current prompt/workflow regression baseline and exit.",
    )
    args = parser.parse_args(argv)

    if args.update_baseline:
        manifest = write_regression_baseline()
        print(json.dumps({"updated_baseline": True, "manifest": manifest}, indent=2, sort_keys=True))
        return 0

    report = run_eval_suite()
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.strict and not report["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
