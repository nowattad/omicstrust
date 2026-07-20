from __future__ import annotations

from pathlib import Path

from omicstrust.utils.serialization import read_json


def compare_runs(run_a: str | Path, run_b: str | Path) -> str:
    a = Path(run_a)
    b = Path(run_b)
    summary_a = read_json(a / "summary.json")
    summary_b = read_json(b / "summary.json")
    trust_a = read_json(a / "trust_report.json")
    trust_b = read_json(b / "trust_report.json")
    lines = [
        "OmicsTrust Run Comparison",
        f"{a}: trust={trust_a.get('trust_score')} level={trust_a.get('trust_level')} safe={summary_a.get('safe_to_interpret')}",
        f"{b}: trust={trust_b.get('trust_score')} level={trust_b.get('trust_level')} safe={summary_b.get('safe_to_interpret')}",
    ]
    return "\n".join(lines)
