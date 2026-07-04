from __future__ import annotations

from src.bootstrap import create_container
from src.core.config import get_settings
from src.core.logging import configure_logging


def execute_planner_run(run_id: str, job_id: str) -> None:
    settings = get_settings()
    configure_logging(settings)
    container = create_container(settings)
    try:
        container.workflow_runtime_service.run_async_job(run_id=run_id, job_id=job_id)
    finally:
        container.shutdown()
