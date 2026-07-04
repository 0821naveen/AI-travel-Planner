from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from src.agents.travel_planner import research_prompts
from src.agents.travel_planner.graph import TravelPlannerGraph
from src.agents.travel_planner.schemas import BudgetTier, TravelerConstraints, TripPurpose, TripRequest
from src.core.config import BACKEND_DIR

BASELINE_PATH = Path(BACKEND_DIR) / "evals" / "regression_baseline.json"


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def current_regression_manifest() -> dict[str, Any]:
    sample_request = TripRequest(
        origin_city="Sample Origin",
        destination="Sample Destination",
        start_date="2099-01-10",
        end_date="2099-01-12",
        traveler_count=2,
        trip_purpose=TripPurpose.LEISURE,
        total_budget=20000,
        budget_tier=BudgetTier.MID_RANGE,
        pace="balanced",
        interests=["food", "history"],
        accommodation_preference="hotel",
        transport_preference="public transit",
        constraints=TravelerConstraints(),
    )
    prompt_contracts = {
        "destination_developer_prompt": research_prompts.DESTINATION_RESEARCH_DEVELOPER_PROMPT,
        "itinerary_developer_prompt": research_prompts.ITINERARY_PLANNING_DEVELOPER_PROMPT,
        "budget_developer_prompt": research_prompts.BUDGET_OPTIMIZATION_DEVELOPER_PROMPT,
        "review_developer_prompt": research_prompts.REVIEW_AND_CONSISTENCY_DEVELOPER_PROMPT,
        "safety_developer_prompt": research_prompts.SOLO_WOMEN_SAFETY_DEVELOPER_PROMPT,
        "stay_developer_prompt": research_prompts.STAY_RECOMMENDATION_DEVELOPER_PROMPT,
        "transport_developer_prompt": research_prompts.LOCAL_TRANSPORT_DEVELOPER_PROMPT,
        "food_developer_prompt": research_prompts.FOOD_RECOMMENDATION_DEVELOPER_PROMPT,
        "destination_prompt_template": research_prompts.build_destination_research_prompt(
            sample_request,
            {"days": 3, "budget_per_day": 6000},
            "Weather evidence",
            "Flight evidence",
            "Web evidence",
        ),
        "itinerary_prompt_template": research_prompts.build_itinerary_planning_prompt(
            sample_request,
            {"days": 3, "budget_per_day": 6000},
            "Destination summary",
            ["Area A", "Area B"],
            ["Highlight"],
            ["Transit note"],
            ["Risk"],
        ),
        "budget_prompt_template": research_prompts.build_budget_optimization_prompt(
            sample_request,
            {"days": 3, "budget_per_day": 6000},
            "Destination summary",
            "Itinerary summary",
            [{"day_number": 1}],
            "Stay summary",
            "Transport summary",
            "Food summary",
        ),
    }
    workflow_steps = list(TravelPlannerGraph().step_handlers.keys())
    return {
        "workflow_steps": workflow_steps,
        "workflow_hash": _hash_text(json.dumps(workflow_steps)),
        "prompt_hashes": {key: _hash_text(value) for key, value in prompt_contracts.items()},
    }


def write_regression_baseline() -> dict[str, Any]:
    manifest = current_regression_manifest()
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def check_prompt_contracts() -> list[str]:
    issues: list[str] = []
    prompt_checks = {
        "destination": (
            research_prompts.DESTINATION_RESEARCH_DEVELOPER_PROMPT,
            ["Return a single JSON object and nothing else.", "Ground the answer in the provided evidence."],
        ),
        "itinerary": (
            research_prompts.ITINERARY_PLANNING_DEVELOPER_PROMPT,
            ["Return a single JSON object and nothing else.", "Keep each day realistic."],
        ),
        "budget": (
            research_prompts.BUDGET_OPTIMIZATION_DEVELOPER_PROMPT,
            ["Do not invent booking-grade prices.", "lower confidence"],
        ),
        "review": (
            research_prompts.REVIEW_AND_CONSISTENCY_DEVELOPER_PROMPT,
            ["Assess whether the researched destination, itinerary, and budget assessment are coherent together."],
        ),
    }
    for label, (prompt, required_phrases) in prompt_checks.items():
        for phrase in required_phrases:
            if phrase not in prompt:
                issues.append(f"{label} prompt is missing required phrase: {phrase}")

    itinerary_prompt = research_prompts.build_itinerary_planning_prompt(
        TripRequest(
            origin_city="A",
            destination="B",
            start_date="2099-01-10",
            end_date="2099-01-12",
            traveler_count=2,
            trip_purpose=TripPurpose.LEISURE,
            total_budget=10000,
            budget_tier=BudgetTier.MID_RANGE,
            pace="balanced",
            interests=["food"],
            accommodation_preference="hotel",
            transport_preference="public transit",
            constraints=TravelerConstraints(),
        ),
        {"days": 3},
        "summary",
        ["Area"],
        ["Highlight"],
        ["Transit"],
        ["Risk"],
    )
    required_itinerary_sections = [
        "Generate exactly one day for each calendar day in the trip.",
        "Each item in days must contain exactly these keys:",
        "- morning",
        "- warnings",
    ]
    for phrase in required_itinerary_sections:
        if phrase not in itinerary_prompt:
            issues.append(f"itinerary prompt template is missing required phrase: {phrase}")
    return issues


def check_regression_baseline() -> list[str]:
    if not BASELINE_PATH.exists():
        return [f"Regression baseline file is missing: {BASELINE_PATH}"]

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    current = current_regression_manifest()
    issues: list[str] = []

    if baseline.get("workflow_hash") != current.get("workflow_hash"):
        issues.append("Workflow step order changed. Review and update regression baseline intentionally.")

    baseline_hashes = baseline.get("prompt_hashes", {})
    current_hashes = current.get("prompt_hashes", {})
    for key, current_hash in current_hashes.items():
        if baseline_hashes.get(key) != current_hash:
            issues.append(f"Prompt regression detected for '{key}'. Review and update regression baseline intentionally.")

    return issues
