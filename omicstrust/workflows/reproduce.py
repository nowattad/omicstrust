from __future__ import annotations

from pathlib import Path
from typing import Any

from omicstrust.ingest.fingerprint import fingerprint_input
from omicstrust.utils.serialization import read_json, write_json
from omicstrust.workflows.environment_capture import capture_package_versions


def check_reproducibility(run_dir: str | Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    provenance_dir = run_dir / "provenance"
    report = {
        "status": "checked",
        "exact_reproduction": False,
        "reasons": [],
        "package_version_differences": {},
        "input_fingerprint_match": None,
    }
    fingerprint_path = provenance_dir / "input_fingerprints.json"
    if fingerprint_path.exists():
        recorded = read_json(fingerprint_path)
        for input_path, expected in recorded.items():
            if Path(input_path).exists():
                observed = fingerprint_input(input_path)
                report["input_fingerprint_match"] = observed == expected
                if observed != expected:
                    report["reasons"].append(f"Input fingerprint changed for {input_path}.")
            else:
                report["input_fingerprint_match"] = False
                report["reasons"].append(f"Input file is not available: {input_path}.")
    else:
        report["reasons"].append("No recorded input fingerprints were found.")
    packages_path = provenance_dir / "package_versions.json"
    if packages_path.exists():
        old = read_json(packages_path)
        current = capture_package_versions(list(old.keys()))
        diffs = {k: {"recorded": old[k], "current": current.get(k)} for k in old if old[k] != current.get(k)}
        report["package_version_differences"] = diffs
        if diffs:
            report["reasons"].append("Package versions differ from the recorded run.")
    report["exact_reproduction"] = not report["reasons"]
    if report["exact_reproduction"]:
        report["status"] = "reproduced"
    write_json(run_dir / "reproducibility_report.json", report)
    return report
