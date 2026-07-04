from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import datetime
from logging import Logger
from typing import Optional
from uuid import uuid4

from src.agents.travel_planner.graph import TravelPlannerGraph
from src.agents.travel_planner.multi_agent.runtime import CoordinatorRuntime
from src.agents.travel_planner.schemas import CreateTripResponse, TripRequest
from src.agents.travel_planner.state import PlannerContext
from src.application.trips.mappers import create_trip_response_from_record, trip_record_from_context
from src.core.config import Settings
from src.domain.jobs.models import JobStatus, PlannerJob
from src.domain.jobs.repositories import JobRepository
from src.domain.trips.repositories import TripRepository
from src.domain.workflows.models import WorkflowExecutionMode, WorkflowRun, WorkflowRunStatus
from src.domain.workflows.repositories import WorkflowRunRepository
from src.domain.workflows.step_models import WorkflowRunStep, WorkflowRunStepStatus
from src.domain.workflows.step_repositories import WorkflowRunStepRepository
from src.services.audit_service import AuditService


class WorkflowCancellationRequested(RuntimeError):
    pass


class WorkflowRuntimeService:
    def __init__(
        self,
        *,
        settings: Settings,
        graph: TravelPlannerGraph,
        coordinator_runtime: CoordinatorRuntime | None = None,
        trip_repository: TripRepository,
        job_repository: JobRepository,
        workflow_run_repository: WorkflowRunRepository,
        workflow_run_step_repository: WorkflowRunStepRepository,
        audit_service: AuditService | None = None,
        workflow_queue,
        logger: Logger,
    ) -> None:
        self.settings = settings
        self.graph = graph
        self.coordinator_runtime = coordinator_runtime
        self.trip_repository = trip_repository
        self.job_repository = job_repository
        self.workflow_run_repository = workflow_run_repository
        self.workflow_run_step_repository = workflow_run_step_repository
        self.audit_service = audit_service
        self.workflow_queue = workflow_queue
        self.logger = logger

    def execute_sync(self, request: TripRequest, *, idempotency_key: Optional[str] = None) -> CreateTripResponse:
        existing = self._find_idempotent_run(idempotency_key, WorkflowExecutionMode.SYNC)
        if existing is not None:
            self.logger.info(
                "workflow.run.idempotent_hit",
                extra={"run_id": existing.run_id, "trip_id": existing.trip_id, "status": existing.status.value},
            )
            return self._response_from_run(existing)

        run = self._build_run(
            request=request,
            execution_mode=WorkflowExecutionMode.SYNC,
            idempotency_key=idempotency_key,
            rerun_of_run_id=None,
        )
        self.workflow_run_repository.save(run)
        self.logger.info(
            "workflow.run.sync_started",
            extra={"run_id": run.run_id, "trip_id": run.trip_id, "status": run.status.value},
        )
        return self._execute_run(run.run_id)

    def enqueue_async(self, request: TripRequest, *, idempotency_key: Optional[str] = None) -> PlannerJob:
        existing = self._find_idempotent_run(idempotency_key, WorkflowExecutionMode.ASYNC)
        if existing is not None and existing.job_id:
            existing_job = self.job_repository.get(existing.job_id)
            if existing_job is not None:
                self.logger.info(
                    "workflow.run.async_idempotent_hit",
                    extra={"run_id": existing.run_id, "trip_id": existing.trip_id, "job_id": existing_job.job_id},
                )
                return existing_job

        run = self._build_run(
            request=request,
            execution_mode=WorkflowExecutionMode.ASYNC,
            idempotency_key=idempotency_key,
            rerun_of_run_id=None,
        )
        now = datetime.utcnow()
        job = PlannerJob(
            job_id=str(uuid4()),
            job_type="create_trip",
            status=JobStatus.QUEUED,
            created_at=now,
            updated_at=now,
            run_id=run.run_id,
            trip_id=run.trip_id,
            retry_count=0,
            max_retries=self.settings.workflow_runtime.max_retries,
            timeout_seconds=self.settings.workflow_runtime.job_timeout_seconds,
            idempotency_key=idempotency_key,
            metadata={"execution_mode": WorkflowExecutionMode.ASYNC.value},
        )
        run.job_id = job.job_id
        run.status = WorkflowRunStatus.QUEUED
        run.max_retries = job.max_retries
        run.timeout_seconds = job.timeout_seconds
        self.workflow_run_repository.save(run)
        enqueued = self.workflow_queue.enqueue(run=run, job=job)
        job.queue_job_id = enqueued.queue_job_id
        run.queue_job_id = enqueued.queue_job_id
        self.job_repository.save(job)
        self.workflow_run_repository.save(run)
        self.logger.info(
            "workflow.run.enqueued",
            extra={"run_id": run.run_id, "trip_id": run.trip_id, "job_id": job.job_id, "status": run.status.value},
        )
        return job

    def run_async_job(self, *, run_id: str, job_id: str) -> None:
        job = self.job_repository.get(job_id)
        run = self.workflow_run_repository.get(run_id)
        if job is None or run is None:
            raise ValueError("Workflow job or run not found.")

        if run.cancellation_requested or job.cancellation_requested:
            self._mark_cancelled(run, job, error="Cancellation requested before execution started.")
            return

        job.status = JobStatus.RUNNING
        job.updated_at = datetime.utcnow()
        run.status = WorkflowRunStatus.RUNNING
        run.updated_at = datetime.utcnow()
        self.job_repository.save(job)
        self.workflow_run_repository.save(run)
        self.logger.info(
            "workflow.run.job_started",
            extra={"run_id": run.run_id, "trip_id": run.trip_id, "job_id": job.job_id, "status": run.status.value},
        )

        try:
            self._execute_run_with_timeout(run_id=run.run_id, timeout_seconds=job.timeout_seconds)
        except WorkflowCancellationRequested as exc:
            self._mark_cancelled(run, job, error=str(exc))
            return
        except Exception as exc:
            self._handle_async_failure(run, job, error=str(exc))
            return

        completed_run = self.workflow_run_repository.get(run_id)
        completed_job = self.job_repository.get(job_id)
        if completed_run is None or completed_job is None:
            return

        completed_job.status = JobStatus.SUCCEEDED
        completed_job.updated_at = datetime.utcnow()
        completed_job.trip_id = completed_run.trip_id
        completed_job.error = None
        self.job_repository.save(completed_job)
        self.logger.info(
            "workflow.run.job_succeeded",
            extra={
                "run_id": completed_run.run_id,
                "trip_id": completed_run.trip_id,
                "job_id": completed_job.job_id,
                "status": completed_run.status.value,
                "retry_count": completed_job.retry_count,
            },
        )

    def cancel_job(self, *, job_id: str) -> PlannerJob | None:
        job = self.job_repository.get(job_id)
        if job is None:
            return None

        job.cancellation_requested = True
        job.updated_at = datetime.utcnow()
        if job.status in {JobStatus.QUEUED, JobStatus.PENDING}:
            job.status = JobStatus.CANCELLED
            job.cancelled_at = datetime.utcnow()
        self.job_repository.save(job)

        run = self.workflow_run_repository.get_by_job_id(job_id)
        if run is not None:
            run.cancellation_requested = True
            run.updated_at = datetime.utcnow()
            if run.status in {WorkflowRunStatus.QUEUED, WorkflowRunStatus.PENDING}:
                run.status = WorkflowRunStatus.CANCELLED
                run.cancelled_at = datetime.utcnow()
            self.workflow_run_repository.save(run)
            self.workflow_queue.request_cancel(queue_job_id=run.queue_job_id)
            self.logger.warning(
                "workflow.run.cancel_requested",
                extra={"run_id": run.run_id, "trip_id": run.trip_id, "job_id": job.job_id, "status": run.status.value},
            )

        return job

    def rerun_job(self, *, job_id: str) -> PlannerJob | None:
        original_run = self.workflow_run_repository.get_by_job_id(job_id)
        if original_run is None:
            return None
        return self.enqueue_async(original_run.request, idempotency_key=None if original_run.idempotency_key else None)

    def get_run(self, run_id: str) -> WorkflowRun | None:
        return self.workflow_run_repository.get(run_id)

    def list_recent_runs(self, *, limit: int = 20) -> list[WorkflowRun]:
        return self.workflow_run_repository.list_recent(limit=limit)

    def list_run_steps(self, run_id: str) -> list[WorkflowRunStep]:
        return self.workflow_run_step_repository.list_by_run_id(run_id)

    def cancel_run(self, *, run_id: str) -> WorkflowRun | None:
        run = self.workflow_run_repository.get(run_id)
        if run is None:
            return None

        run.cancellation_requested = True
        run.updated_at = datetime.utcnow()
        if run.status in {WorkflowRunStatus.QUEUED, WorkflowRunStatus.PENDING}:
            run.status = WorkflowRunStatus.CANCELLED
            run.cancelled_at = datetime.utcnow()
        self.workflow_run_repository.save(run)

        job = self.job_repository.get_by_run_id(run_id)
        if job is not None:
            job.cancellation_requested = True
            job.updated_at = datetime.utcnow()
            if job.status in {JobStatus.QUEUED, JobStatus.PENDING}:
                job.status = JobStatus.CANCELLED
                job.cancelled_at = datetime.utcnow()
            self.job_repository.save(job)
            self.workflow_queue.request_cancel(queue_job_id=job.queue_job_id)

        return self.workflow_run_repository.get(run_id)

    def rerun_run(self, *, run_id: str) -> WorkflowRun | None:
        original_run = self.workflow_run_repository.get(run_id)
        if original_run is None:
            return None

        rerun = self._build_run(
            request=original_run.request,
            execution_mode=WorkflowExecutionMode.ASYNC,
            idempotency_key=None,
            rerun_of_run_id=original_run.run_id,
        )
        now = datetime.utcnow()
        job = PlannerJob(
            job_id=str(uuid4()),
            job_type="create_trip",
            status=JobStatus.QUEUED,
            created_at=now,
            updated_at=now,
            run_id=rerun.run_id,
            trip_id=rerun.trip_id,
            retry_count=0,
            max_retries=self.settings.workflow_runtime.max_retries,
            timeout_seconds=self.settings.workflow_runtime.job_timeout_seconds,
            metadata={"execution_mode": WorkflowExecutionMode.ASYNC.value, "rerun_of_run_id": original_run.run_id},
        )
        rerun.job_id = job.job_id
        rerun.status = WorkflowRunStatus.QUEUED
        rerun.max_retries = job.max_retries
        rerun.timeout_seconds = job.timeout_seconds
        self.workflow_run_repository.save(rerun)
        enqueued = self.workflow_queue.enqueue(run=rerun, job=job)
        job.queue_job_id = enqueued.queue_job_id
        rerun.queue_job_id = enqueued.queue_job_id
        self.job_repository.save(job)
        self.workflow_run_repository.save(rerun)
        self.logger.info(
            "workflow.run.rerun_enqueued",
            extra={"run_id": rerun.run_id, "trip_id": rerun.trip_id, "job_id": job.job_id, "status": rerun.status.value},
        )
        return rerun

    def _execute_run_with_timeout(self, *, run_id: str, timeout_seconds: int) -> CreateTripResponse:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._execute_run, run_id)
            try:
                return future.result(timeout=timeout_seconds)
            except FutureTimeoutError as exc:
                raise RuntimeError(f"Workflow run timed out after {timeout_seconds} seconds") from exc

    def _execute_run(self, run_id: str) -> CreateTripResponse:
        run = self.workflow_run_repository.get(run_id)
        if run is None:
            raise ValueError(f"Workflow run not found: {run_id}")

        if run.terminal:
            return self._response_from_run(run)

        if self.coordinator_runtime is not None:
            return self._execute_run_with_coordinator(run)

        context = run.context or PlannerContext(trip_id=run.trip_id, request=run.request, run_id=run.run_id)
        context.run_id = run.run_id
        next_step = run.current_step or self.graph.initial_step()

        while next_step is not None:
            run = self.workflow_run_repository.get(run_id) or run
            if run.cancellation_requested:
                raise WorkflowCancellationRequested("Workflow run cancelled before step execution.")

            run.status = WorkflowRunStatus.RUNNING
            run.current_step = next_step
            run.updated_at = datetime.utcnow()
            run.context = context
            self.workflow_run_repository.save(run)

            step_record = WorkflowRunStep(
                step_id=str(uuid4()),
                run_id=run.run_id,
                step_name=next_step,
                sequence=len(self.workflow_run_step_repository.list_by_run_id(run.run_id)) + 1,
                status=WorkflowRunStepStatus.RUNNING,
                started_at=datetime.utcnow(),
                retry_count=run.retry_count,
                metadata={"execution_mode": run.execution_mode.value},
            )
            self.workflow_run_step_repository.save(step_record)
            self.logger.info(
                "workflow.step.started",
                extra={
                    "run_id": run.run_id,
                    "trip_id": run.trip_id,
                    "node_name": next_step,
                    "retry_count": run.retry_count,
                    "status": "running",
                },
            )

            try:
                context = self.graph.execute_step(next_step, context)
                upcoming_step = self.graph.next_step(next_step, context)
            except Exception as exc:
                step_record.status = WorkflowRunStepStatus.FAILED
                step_record.completed_at = datetime.utcnow()
                step_record.error = str(exc)
                self.workflow_run_step_repository.save(step_record)
                self.logger.exception(
                    "workflow.step.failed",
                    extra={
                        "run_id": run.run_id,
                        "trip_id": run.trip_id,
                        "node_name": next_step,
                        "retry_count": run.retry_count,
                        "status": "failed",
                    },
                )
                raise

            step_record.status = WorkflowRunStepStatus.SUCCEEDED
            step_record.completed_at = datetime.utcnow()
            self.workflow_run_step_repository.save(step_record)
            self.logger.info(
                "workflow.step.succeeded",
                extra={
                    "run_id": run.run_id,
                    "trip_id": run.trip_id,
                    "node_name": next_step,
                    "status": "succeeded",
                    "latency_ms": round((step_record.completed_at - step_record.started_at).total_seconds() * 1000, 2),
                },
            )

            run.context = context
            run.current_step = upcoming_step
            run.last_completed_step = next_step
            run.updated_at = datetime.utcnow()
            self.workflow_run_repository.save(run)
            next_step = upcoming_step

        record = trip_record_from_context(run.trip_id, context)
        self.trip_repository.save(record)
        self._flush_context_audit_events(run, context)
        run.status = WorkflowRunStatus.SUCCEEDED
        run.current_step = None
        run.error = None
        run.context = context
        run.updated_at = datetime.utcnow()
        self.workflow_run_repository.save(run)
        self.logger.info(
            "workflow.run.succeeded",
            extra={"run_id": run.run_id, "trip_id": run.trip_id, "status": run.status.value},
        )
        return create_trip_response_from_record(record, run_id=run.run_id)

    def _execute_run_with_coordinator(self, run) -> CreateTripResponse:
        open_steps: dict[str, str] = {}

        def _persist_progress(event: dict[str, object]) -> None:
            latest_run = self.workflow_run_repository.get(run.run_id) or run
            step_name = str(event.get("step_name") or "").strip()
            status = str(event.get("status") or "").strip()
            event_type = str(event.get("event_type") or "").strip()
            now = datetime.utcnow()

            if step_name:
                latest_run.current_step = step_name if status == "running" else latest_run.current_step
            latest_run.updated_at = now

            if event_type == "specialist_started" and step_name:
                step_id = str(uuid4())
                open_steps[step_name] = step_id
                self.workflow_run_step_repository.save(
                    WorkflowRunStep(
                        step_id=step_id,
                        run_id=latest_run.run_id,
                        step_name=step_name,
                        sequence=len(self.workflow_run_step_repository.list_by_run_id(latest_run.run_id)) + 1,
                        status=WorkflowRunStepStatus.RUNNING,
                        started_at=now,
                        retry_count=latest_run.retry_count,
                        metadata={"execution_mode": "coordinator_runtime"},
                    )
                )
            elif event_type == "specialist_completed" and step_name:
                open_step_id = open_steps.pop(step_name, None)
                latest_run.last_completed_step = step_name
                latest_run.current_step = "coordinator_agent"
                if open_step_id is not None:
                    for step in self.workflow_run_step_repository.list_by_run_id(latest_run.run_id):
                        if step.step_id == open_step_id:
                            step.status = WorkflowRunStepStatus.SUCCEEDED
                            step.completed_at = now
                            self.workflow_run_step_repository.save(step)
                            break
            elif event_type == "parallel_batch_started":
                latest_run.current_step = "parallel_batch"
            elif event_type == "coordinator_decision":
                latest_run.current_step = "coordinator_agent"

            self.workflow_run_repository.save(latest_run)
            self._record_runtime_audit_event(latest_run, event)

        runtime_state = self.coordinator_runtime.bootstrap_trip_with_progress(
            trip_id=run.trip_id,
            request=run.request,
            run_id=run.run_id,
            progress_callback=_persist_progress,
        )
        context = runtime_state["context"]
        context.run_id = run.run_id

        self._persist_synthetic_steps(run.run_id, context)

        record = trip_record_from_context(run.trip_id, context)
        self.trip_repository.save(record)
        run.status = WorkflowRunStatus.SUCCEEDED
        run.current_step = None
        run.last_completed_step = context.route_trace[-1] if context.route_trace else None
        run.error = None
        run.context = context
        run.updated_at = datetime.utcnow()
        if runtime_state.get("terminal_reason") is not None:
            run.metadata["terminal_reason"] = runtime_state["terminal_reason"]
            self._record_runtime_audit_event(
                run,
                {
                    "event_type": "workflow_terminal_decision",
                    "step_name": "coordinator_agent",
                    "status": "succeeded",
                    "terminal_reason": runtime_state["terminal_reason"],
                },
            )
        self._flush_context_audit_events(run, context)
        self.workflow_run_repository.save(run)
        self.logger.info(
            "workflow.run.succeeded",
            extra={"run_id": run.run_id, "trip_id": run.trip_id, "status": run.status.value, "runtime": "coordinator"},
        )
        return create_trip_response_from_record(record, run_id=run.run_id)

    def _persist_synthetic_steps(self, run_id: str, context: PlannerContext) -> None:
        existing = self.workflow_run_step_repository.list_by_run_id(run_id)
        existing_by_name = {item.step_name: item for item in existing}
        now = datetime.utcnow()
        for sequence, step_name in enumerate(context.route_trace, start=1):
            existing_step = existing_by_name.get(step_name)
            if existing_step is not None:
                existing_step.sequence = min(existing_step.sequence, sequence)
                existing_step.status = WorkflowRunStepStatus.SUCCEEDED
                existing_step.completed_at = existing_step.completed_at or now
                existing_step.metadata = {
                    **existing_step.metadata,
                    "execution_mode": "coordinator_runtime",
                }
                self.workflow_run_step_repository.save(existing_step)
                continue
            self.workflow_run_step_repository.save(
                WorkflowRunStep(
                    step_id=str(uuid4()),
                    run_id=run_id,
                    step_name=step_name,
                    sequence=sequence,
                    status=WorkflowRunStepStatus.SUCCEEDED,
                    started_at=now,
                    completed_at=now,
                    retry_count=0,
                    metadata={"execution_mode": "coordinator_runtime"},
                )
            )

    def _response_from_run(self, run: WorkflowRun) -> CreateTripResponse:
        record = self.trip_repository.get(run.trip_id)
        if record is None:
            raise ValueError(f"Trip record not found for run {run.run_id}")
        return create_trip_response_from_record(record, run_id=run.run_id)

    def _record_runtime_audit_event(self, run: WorkflowRun, event: dict[str, object]) -> None:
        if self.audit_service is None:
            return
        event_type = str(event.get("event_type") or "").strip()
        if not event_type:
            return

        payload = {
            key: value
            for key, value in event.items()
            if key not in {"event_type", "status", "step_name"}
        }
        self.audit_service.record_event(
            event_type=event_type,
            trip_id=run.trip_id,
            run_id=run.run_id,
            job_id=run.job_id,
            status=str(event.get("status") or "") or None,
            node_name=str(event.get("step_name") or "") or None,
            payload=payload,
        )

    def _flush_context_audit_events(self, run: WorkflowRun, context: PlannerContext) -> None:
        if self.audit_service is None:
            return

        for event in context.audit_events:
            event_type = str(event.get("event_type") or "").strip()
            if event_type not in {"tool_called", "tool_failed"}:
                continue
            payload = {
                key: value
                for key, value in event.items()
                if key
                not in {
                    "event_type",
                    "request_id",
                    "trip_id",
                    "run_id",
                    "job_id",
                    "actor_id",
                    "actor_role",
                    "status",
                    "node_name",
                    "tool_name",
                    "provider_name",
                    "provider_endpoint",
                    "model_name",
                    "prompt_version",
                    "source_references",
                }
            }
            self.audit_service.record_event(
                event_type=event_type,
                request_id=str(event.get("request_id") or "") or None,
                trip_id=str(event.get("trip_id") or run.trip_id) or run.trip_id,
                run_id=str(event.get("run_id") or run.run_id) or run.run_id,
                job_id=str(event.get("job_id") or run.job_id or "") or run.job_id,
                actor_id=str(event.get("actor_id") or "") or None,
                actor_role=str(event.get("actor_role") or "") or None,
                status=str(event.get("status") or "") or None,
                node_name=str(event.get("node_name") or "") or None,
                tool_name=str(event.get("tool_name") or "") or None,
                provider_name=str(event.get("provider_name") or "") or None,
                provider_endpoint=str(event.get("provider_endpoint") or "") or None,
                model_name=str(event.get("model_name") or "") or None,
                prompt_version=str(event.get("prompt_version") or "") or None,
                source_references=list(event.get("source_references") or []),
                payload=payload,
            )

    def _build_run(
        self,
        *,
        request: TripRequest,
        execution_mode: WorkflowExecutionMode,
        idempotency_key: Optional[str],
        rerun_of_run_id: Optional[str],
    ) -> WorkflowRun:
        now = datetime.utcnow()
        return WorkflowRun(
            run_id=str(uuid4()),
            trip_id=str(uuid4()),
            request=request,
            execution_mode=execution_mode,
            status=WorkflowRunStatus.PENDING if execution_mode == WorkflowExecutionMode.SYNC else WorkflowRunStatus.QUEUED,
            created_at=now,
            updated_at=now,
            current_step="coordinator_agent" if self.coordinator_runtime is not None else self.graph.initial_step(),
            idempotency_key=idempotency_key,
            max_retries=self.settings.workflow_runtime.max_retries,
            timeout_seconds=self.settings.workflow_runtime.job_timeout_seconds,
            rerun_of_run_id=rerun_of_run_id,
            metadata={
                "route": "coordinator_agent" if self.coordinator_runtime is not None else self.graph.initial_step(),
            },
        )

    def _handle_async_failure(self, run: WorkflowRun, job: PlannerJob, *, error: str) -> None:
        now = datetime.utcnow()
        job.retry_count += 1
        run.retry_count = job.retry_count
        job.error = error
        run.error = error
        job.updated_at = now
        run.updated_at = now

        if job.retry_count <= job.max_retries and not run.cancellation_requested:
            job.status = JobStatus.QUEUED
            run.status = WorkflowRunStatus.QUEUED
            self.job_repository.save(job)
            self.workflow_run_repository.save(run)
            enqueued = self.workflow_queue.enqueue(run=run, job=job)
            job.queue_job_id = enqueued.queue_job_id
            run.queue_job_id = enqueued.queue_job_id
            self.job_repository.save(job)
            self.workflow_run_repository.save(run)
            self.logger.warning(
                "workflow.run.retry_scheduled",
                extra={
                    "run_id": run.run_id,
                    "trip_id": run.trip_id,
                    "job_id": job.job_id,
                    "retry_count": job.retry_count,
                    "status": run.status.value,
                    "provider_endpoint": error[:200],
                },
            )
            return

        job.status = JobStatus.DEAD_LETTERED
        run.status = WorkflowRunStatus.DEAD_LETTERED
        job.dead_lettered_at = now
        run.dead_lettered_at = now
        self.job_repository.save(job)
        self.workflow_run_repository.save(run)
        self.logger.error(
            "workflow.run.dead_lettered",
            extra={
                "run_id": run.run_id,
                "trip_id": run.trip_id,
                "job_id": job.job_id,
                "retry_count": job.retry_count,
                "status": run.status.value,
            },
        )

    def _mark_cancelled(self, run: WorkflowRun, job: PlannerJob, *, error: str) -> None:
        now = datetime.utcnow()
        run.status = WorkflowRunStatus.CANCELLED
        run.cancelled_at = now
        run.error = error
        run.updated_at = now
        job.status = JobStatus.CANCELLED
        job.cancelled_at = now
        job.error = error
        job.updated_at = now
        self.workflow_run_repository.save(run)
        self.job_repository.save(job)
        self.logger.warning(
            "workflow.run.cancelled",
            extra={"run_id": run.run_id, "trip_id": run.trip_id, "job_id": job.job_id, "status": run.status.value},
        )

        if run.current_step:
            self.workflow_run_step_repository.save(
                WorkflowRunStep(
                    step_id=str(uuid4()),
                    run_id=run.run_id,
                    step_name=run.current_step,
                    sequence=len(self.workflow_run_step_repository.list_by_run_id(run.run_id)) + 1,
                    status=WorkflowRunStepStatus.CANCELLED,
                    started_at=now,
                    completed_at=now,
                    error=error,
                    retry_count=run.retry_count,
                    metadata={"cancellation_requested": True},
                )
            )

    def _find_idempotent_run(
        self,
        idempotency_key: str | None,
        execution_mode: WorkflowExecutionMode,
    ) -> WorkflowRun | None:
        if not idempotency_key:
            return None
        return self.workflow_run_repository.find_by_idempotency_key(
            idempotency_key=idempotency_key,
            execution_mode=execution_mode,
        )
