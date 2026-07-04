from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from src.core.config import BACKEND_DIR, Settings


@dataclass(frozen=True)
class DependencyCheck:
    name: str
    healthy: bool
    detail: str


class ReadinessService:
    def __init__(self, *, settings: Settings, engine: Engine, workflow_queue) -> None:
        self.settings = settings
        self.engine = engine
        self.workflow_queue = workflow_queue

    def check_database(self) -> DependencyCheck:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return DependencyCheck(name="database", healthy=True, detail="Database connection is healthy.")
        except Exception as exc:
            return DependencyCheck(name="database", healthy=False, detail=f"Database check failed: {exc}")

    def check_migrations(self) -> DependencyCheck:
        try:
            config = Config(str(Path(BACKEND_DIR) / "alembic.ini"))
            config.set_main_option("sqlalchemy.url", self.settings.database.url)
            config.set_main_option("script_location", str(Path(BACKEND_DIR) / "alembic"))
            script = ScriptDirectory.from_config(config)
            expected_head = script.get_current_head()
            with self.engine.connect() as connection:
                context = MigrationContext.configure(connection)
                current_revision = context.get_current_revision()
            if current_revision != expected_head:
                return DependencyCheck(
                    name="migrations",
                    healthy=False,
                    detail=f"Database revision {current_revision!r} does not match head {expected_head!r}.",
                )

            required_tables = {
                "trips",
                "planner_jobs",
                "workflow_runs",
                "workflow_run_steps",
                "audit_events",
                "alembic_version",
            }
            existing_tables = set(inspect(self.engine).get_table_names())
            missing_tables = sorted(required_tables - existing_tables)
            if missing_tables:
                return DependencyCheck(
                    name="migrations",
                    healthy=False,
                    detail=f"Missing required tables: {', '.join(missing_tables)}",
                )
            return DependencyCheck(name="migrations", healthy=True, detail="Schema revision is current.")
        except Exception as exc:
            return DependencyCheck(name="migrations", healthy=False, detail=f"Migration check failed: {exc}")

    def check_redis(self) -> DependencyCheck:
        client = getattr(self.workflow_queue, "redis_client", None)
        if client is None:
            if self.settings.app.environment == "test":
                return DependencyCheck(name="redis", healthy=True, detail="Test runtime uses in-memory queue.")
            return DependencyCheck(name="redis", healthy=False, detail="Redis client is not configured.")
        try:
            client.ping()
            return DependencyCheck(name="redis", healthy=True, detail="Redis connection is healthy.")
        except Exception as exc:
            return DependencyCheck(name="redis", healthy=False, detail=f"Redis check failed: {exc}")

    def check_worker(self) -> DependencyCheck:
        queue = getattr(self.workflow_queue, "queue", None)
        if queue is None:
            if self.settings.app.environment == "test":
                return DependencyCheck(name="worker", healthy=True, detail="Test runtime uses in-memory queue.")
            return DependencyCheck(name="worker", healthy=False, detail="Workflow queue is not configured.")
        try:
            from rq import Worker

            workers = Worker.all(connection=queue.connection, queue=queue)
            if not workers:
                return DependencyCheck(name="worker", healthy=False, detail="No active RQ workers registered.")
            return DependencyCheck(name="worker", healthy=True, detail=f"{len(workers)} active worker(s).")
        except Exception as exc:
            return DependencyCheck(name="worker", healthy=False, detail=f"Worker check failed: {exc}")

    def readiness_report(self) -> dict[str, object]:
        checks = {
            "database": self.check_database(),
            "migrations": self.check_migrations(),
            "redis": self.check_redis(),
            "worker": self.check_worker(),
        }
        healthy = all(check.healthy for check in checks.values())
        return {
            "healthy": healthy,
            "checks": {
                name: {"healthy": check.healthy, "detail": check.detail}
                for name, check in checks.items()
            },
        }

    def assert_startup_ready(self) -> None:
        database_check = self.check_database()
        if not database_check.healthy:
            raise RuntimeError(database_check.detail)

        if self.settings.workflow_runtime.require_current_migrations_on_startup:
            migration_check = self.check_migrations()
            if not migration_check.healthy:
                raise RuntimeError(migration_check.detail)

        redis_check = self.check_redis()
        if not redis_check.healthy:
            raise RuntimeError(redis_check.detail)

        if self.settings.workflow_runtime.require_worker_on_startup:
            worker_check = self.check_worker()
            if not worker_check.healthy:
                raise RuntimeError(worker_check.detail)
