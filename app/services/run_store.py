"""
Durable storage for research runs.

Two interchangeable backends:

  PostgresRunStore  — used when settings.database_url is set. Runs survive
                      process restarts; GET /research/{id} answers from the
                      DB even after a crash mid-run.
  InMemoryRunStore  — dev/test fallback with the same interface.

Schema (created on startup, idempotent):

  runs(
    id          TEXT PRIMARY KEY,
    prompt      TEXT NOT NULL,
    status      TEXT NOT NULL,          -- running | completed | failed
    created_at  TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    report_json JSONB,
    error       TEXT
  )
"""

import json
from datetime import UTC, datetime
from typing import Any

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

RUN_RUNNING = "running"
RUN_COMPLETED = "completed"
RUN_FAILED = "failed"


class InMemoryRunStore:
    """Dict-backed run store for local dev and tests (not durable)."""

    def __init__(self):
        self._runs: dict[str, dict[str, Any]] = {}

    async def init(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def create_run(self, run_id: str, prompt: str) -> None:
        self._runs[run_id] = {
            "id": run_id,
            "prompt": prompt,
            "status": RUN_RUNNING,
            "created_at": datetime.now(UTC).isoformat(),
            "finished_at": None,
            "report": None,
            "error": None,
        }

    async def mark_completed(self, run_id: str, report: dict[str, Any]) -> None:
        run = self._runs.get(run_id)
        if run:
            run.update(
                status=RUN_COMPLETED,
                finished_at=datetime.now(UTC).isoformat(),
                report=report,
            )

    async def mark_failed(self, run_id: str, error: str) -> None:
        run = self._runs.get(run_id)
        if run:
            run.update(
                status=RUN_FAILED,
                finished_at=datetime.now(UTC).isoformat(),
                error=error,
            )

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self._runs.get(run_id)

    async def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        runs = sorted(self._runs.values(), key=lambda r: r["created_at"], reverse=True)
        return [{k: v for k, v in r.items() if k != "report"} for r in runs[:limit]]


class PostgresRunStore:
    """Postgres-backed run store (psycopg3 async pool)."""

    def __init__(self, database_url: str):
        self._database_url = database_url
        self._pool = None

    async def init(self) -> None:
        from psycopg_pool import AsyncConnectionPool

        self._pool = AsyncConnectionPool(
            self._database_url,
            min_size=1,
            max_size=5,
            open=False,
        )
        await self._pool.open()
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id          TEXT PRIMARY KEY,
                    prompt      TEXT NOT NULL,
                    status      TEXT NOT NULL,
                    created_at  TIMESTAMPTZ NOT NULL,
                    finished_at TIMESTAMPTZ,
                    report_json JSONB,
                    error       TEXT
                )
                """
            )
        logger.info("Postgres run store initialised")

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def ping(self) -> bool:
        """Health-check the database connection."""
        try:
            async with self._pool.connection() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception as exc:
            logger.warning(f"Run store ping failed: {exc}")
            return False

    async def create_run(self, run_id: str, prompt: str) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                "INSERT INTO runs (id, prompt, status, created_at) VALUES (%s, %s, %s, %s)",
                (run_id, prompt, RUN_RUNNING, datetime.now(UTC)),
            )

    async def mark_completed(self, run_id: str, report: dict[str, Any]) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                "UPDATE runs SET status = %s, finished_at = %s, report_json = %s WHERE id = %s",
                (RUN_COMPLETED, datetime.now(UTC), json.dumps(report), run_id),
            )

    async def mark_failed(self, run_id: str, error: str) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                "UPDATE runs SET status = %s, finished_at = %s, error = %s WHERE id = %s",
                (RUN_FAILED, datetime.now(UTC), error[:2000], run_id),
            )

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT id, prompt, status, created_at, finished_at, report_json, error "
                "FROM runs WHERE id = %s",
                (run_id,),
            )
            row = await cur.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row, include_report=True)

    async def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT id, prompt, status, created_at, finished_at, NULL, error "
                "FROM runs ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            rows = await cur.fetchall()
        return [self._row_to_dict(row, include_report=False) for row in rows]

    @staticmethod
    def _row_to_dict(row, include_report: bool) -> dict[str, Any]:
        run = {
            "id": row[0],
            "prompt": row[1],
            "status": row[2],
            "created_at": row[3].isoformat() if row[3] else None,
            "finished_at": row[4].isoformat() if row[4] else None,
            "error": row[6],
        }
        if include_report:
            run["report"] = row[5]
        return run


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_run_store = None


def get_run_store():
    """Return the run store singleton (Postgres when configured)."""
    global _run_store
    if _run_store is None:
        if settings.database_url:
            _run_store = PostgresRunStore(settings.database_url)
            logger.info("Run store backend: Postgres")
        else:
            _run_store = InMemoryRunStore()
            logger.info("Run store backend: in-memory (set DATABASE_URL for durability)")
    return _run_store
