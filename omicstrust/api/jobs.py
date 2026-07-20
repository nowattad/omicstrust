from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omicstrust.audit import run_audit
from omicstrust.tracking.sqlite_registry import register_run
from omicstrust.utils.serialization import make_json_safe, read_json


JOB_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    data_path TEXT NOT NULL,
    output_dir TEXT NOT NULL,
    batch_key TEXT,
    donor_key TEXT,
    label_key TEXT,
    config_path TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    error TEXT,
    summary_json TEXT,
    registry_run_id TEXT
);
"""

JOB_UPDATE_ASSIGNMENTS = {
    "status": "status = :status",
    "data_path": "data_path = :data_path",
    "output_dir": "output_dir = :output_dir",
    "batch_key": "batch_key = :batch_key",
    "donor_key": "donor_key = :donor_key",
    "label_key": "label_key = :label_key",
    "config_path": "config_path = :config_path",
    "started_at": "started_at = :started_at",
    "finished_at": "finished_at = :finished_at",
    "error": "error = :error",
    "summary_json": "summary_json = :summary_json",
    "registry_run_id": "registry_run_id = :registry_run_id",
}


class JobStore:
    def __init__(self, root: str | Path = "results/platform"):
        self.root = Path(root)
        self.uploads_dir = self.root / "uploads"
        self.runs_dir = self.root / "runs"
        self.db_path = self.root / "jobs.sqlite"
        self.registry_db = self.root / "audit_history.sqlite"
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(JOB_SCHEMA)

    def create_job(
        self,
        *,
        data_path: str | Path,
        output_dir: str | Path | None = None,
        batch_key: str | None = None,
        donor_key: str | None = None,
        label_key: str | None = None,
        config_path: str | Path | None = None,
    ) -> dict[str, Any]:
        job_id = uuid.uuid4().hex[:16]
        out = Path(output_dir) if output_dir else self.runs_dir / job_id
        record = {
            "job_id": job_id,
            "status": "queued",
            "data_path": str(Path(data_path).expanduser()),
            "output_dir": str(out),
            "batch_key": batch_key,
            "donor_key": donor_key,
            "label_key": label_key,
            "config_path": str(config_path) if config_path else None,
            "created_at": _utc_now(),
            "started_at": None,
            "finished_at": None,
            "error": None,
            "summary_json": None,
            "registry_run_id": None,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, status, data_path, output_dir, batch_key, donor_key, label_key,
                    config_path, created_at, started_at, finished_at, error, summary_json,
                    registry_run_id
                ) VALUES (
                    :job_id, :status, :data_path, :output_dir, :batch_key, :donor_key,
                    :label_key, :config_path, :created_at, :started_at, :finished_at,
                    :error, :summary_json, :registry_run_id
                )
                """,
                record,
            )
        return self.get_job(job_id)

    def run_job(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)
        self._update(job_id, status="running", started_at=_utc_now(), error=None)
        try:
            result = run_audit(
                job["data_path"],
                output=job["output_dir"],
                batch_key=job.get("batch_key"),
                donor_key=job.get("donor_key"),
                label_key=job.get("label_key"),
                config_path=job.get("config_path"),
                command=["omicstrust-api", "audit", job["data_path"]],
            )
            registry = register_run(job["output_dir"], db_path=self.registry_db)
            self._update(
                job_id,
                status="completed",
                finished_at=_utc_now(),
                summary_json=json.dumps(make_json_safe(result.get("summary", {})), sort_keys=True),
                registry_run_id=registry.get("run_id"),
            )
        except Exception as exc:
            self._update(job_id, status="failed", finished_at=_utc_now(), error=str(exc))
        return self.get_job(job_id)

    def save_upload(self, filename: str, content_file: Any) -> Path:
        safe = _safe_filename(filename)
        target = self.uploads_dir / f"{uuid.uuid4().hex[:8]}_{safe}"
        with target.open("wb") as handle:
            shutil.copyfileobj(content_file, handle)
        return target

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown job_id: {job_id}")
        return _row_to_dict(row)

    def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM jobs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def summary(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)
        summary_path = Path(job["output_dir"]) / "summary.json"
        if summary_path.exists():
            return read_json(summary_path)
        if job.get("summary_json"):
            return json.loads(job["summary_json"])
        return {"status": job["status"], "error": job.get("error")}

    def report_path(self, job_id: str, filename: str) -> Path:
        job = self.get_job(job_id)
        output_root = Path(job["output_dir"]).resolve()
        path = (output_root / filename).resolve()
        try:
            path.relative_to(output_root)
        except ValueError as exc:
            raise FileNotFoundError(f"Artifact path escapes job output directory: {filename}") from exc
        if not path.is_file():
            raise FileNotFoundError(f"Report artifact not found for job {job_id}: {filename}")
        return path

    def _update(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        unknown = sorted(set(fields) - set(JOB_UPDATE_ASSIGNMENTS))
        if unknown:
            raise ValueError(f"Unknown job update fields: {', '.join(unknown)}")
        assignments = ", ".join(JOB_UPDATE_ASSIGNMENTS[key] for key in fields)
        payload = dict(fields)
        payload["job_id"] = job_id
        with self._connect() as conn:
            conn.execute("UPDATE jobs SET " + assignments + " WHERE job_id = :job_id", payload)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute(JOB_SCHEMA)
        return conn


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    if data.get("summary_json"):
        try:
            data["summary"] = json.loads(data["summary_json"])
        except json.JSONDecodeError:
            data["summary"] = None
    data.pop("summary_json", None)
    return data


def _safe_filename(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in Path(name).name)
    return cleaned or "upload.dat"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
