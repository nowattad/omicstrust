from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omicstrust.utils.serialization import read_json


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    run_dir TEXT NOT NULL,
    input_path TEXT,
    created_at TEXT NOT NULL,
    data_qc TEXT,
    structural_signal TEXT,
    batch_risk TEXT,
    stability TEXT,
    trust_level TEXT,
    trust_score INTEGER,
    safe_to_interpret INTEGER,
    main_failure TEXT,
    summary_json TEXT NOT NULL,
    trust_json TEXT NOT NULL
);
"""


def register_run(run_dir: str | Path, db_path: str | Path = "results/omicstrust_registry.sqlite") -> dict[str, Any]:
    run_dir = Path(run_dir)
    if not (run_dir / "summary.json").exists():
        raise FileNotFoundError(f"Run directory does not contain summary.json: {run_dir}")
    summary = read_json(run_dir / "summary.json")
    trust = read_json(run_dir / "trust_report.json")
    provenance = _read_optional_json(run_dir / "provenance" / "input_fingerprints.json", {})
    input_path = next(iter(provenance.keys()), None)
    run_id = _run_id(run_dir, input_path)
    record = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "input_path": input_path,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data_qc": summary.get("data_qc"),
        "structural_signal": summary.get("structural_signal"),
        "batch_risk": summary.get("batch_risk"),
        "stability": summary.get("stability"),
        "trust_level": trust.get("trust_level"),
        "trust_score": trust.get("trust_score"),
        "safe_to_interpret": 1 if trust.get("safe_to_interpret") else 0,
        "main_failure": summary.get("main_failure"),
        "summary_json": json.dumps(summary, sort_keys=True),
        "trust_json": json.dumps(trust, sort_keys=True),
    }
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO runs (
                run_id, run_dir, input_path, created_at, data_qc, structural_signal,
                batch_risk, stability, trust_level, trust_score, safe_to_interpret,
                main_failure, summary_json, trust_json
            ) VALUES (
                :run_id, :run_dir, :input_path, :created_at, :data_qc, :structural_signal,
                :batch_risk, :stability, :trust_level, :trust_score, :safe_to_interpret,
                :main_failure, :summary_json, :trust_json
            )
            """,
            record,
        )
    return record


def list_registered_runs(db_path: str | Path = "results/omicstrust_registry.sqlite", limit: int = 50) -> list[dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT run_id, run_dir, input_path, created_at, data_qc, structural_signal,
                   batch_risk, stability, trust_level, trust_score, safe_to_interpret,
                   main_failure
            FROM runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    return [dict(row) for row in rows]


def get_registered_run(run_id: str, db_path: str | Path = "results/omicstrust_registry.sqlite") -> dict[str, Any] | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return dict(row) if row else None


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def _run_id(run_dir: Path, input_path: str | None) -> str:
    base = f"{run_dir.resolve()}::{input_path or ''}"
    import hashlib

    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def _read_optional_json(path: Path, default):
    if path.exists():
        return read_json(path)
    return default
