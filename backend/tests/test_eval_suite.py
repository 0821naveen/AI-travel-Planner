from __future__ import annotations

from src.evals.regressions import check_prompt_contracts, check_regression_baseline
from src.evals.runner import run_eval_suite


def test_eval_suite_passes():
    report = run_eval_suite()
    assert report["passed"] is True, report


def test_prompt_contracts_and_regression_baseline_are_clean():
    assert check_prompt_contracts() == []
    assert check_regression_baseline() == []
