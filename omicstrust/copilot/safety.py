from __future__ import annotations

from pathlib import Path

from omicstrust.copilot.schemas import SUPPORTED_WORKFLOWS


ALLOWED_INPUT_SUFFIXES = {".h5ad", ".csv", ".tsv", ".txt"}

CLINICAL_REQUEST_PATTERNS = [
    "which treatment should i give",
    "what treatment should i give",
    "recommend treatment",
    "choose treatment",
    "clinical decision",
    "diagnose this patient",
    "for this patient",
    "individual patient",
    "dose should",
    "prescribe",
]

CODE_EXECUTION_PATTERNS = [
    "run shell",
    "execute shell",
    "write python",
    "execute python",
    "run arbitrary code",
    "subprocess",
    "bash command",
    "terminal command",
]


def evaluate_request_safety(user_request: str) -> dict[str, object]:
    lowered = user_request.lower()
    if any(pattern in lowered for pattern in CLINICAL_REQUEST_PATTERNS):
        return {
            "status": "rejected",
            "reason": "clinical_decision_request_not_supported",
            "message": "OmicsTrust is Research Use Only and cannot recommend treatment for an individual patient.",
        }
    if any(pattern in lowered for pattern in CODE_EXECUTION_PATTERNS):
        return {
            "status": "rejected",
            "reason": "free_code_execution_not_supported",
            "message": "Evidence Copilot only routes requests to controlled OmicsTrust workflows; it does not execute arbitrary code.",
        }
    return {"status": "allowed", "reason": None, "message": None}


def safety_contract() -> dict[str, bool]:
    return {
        "ruo_only": True,
        "no_clinical_recommendation": True,
        "no_free_code_execution": True,
    }


def is_supported_workflow(workflow: str) -> bool:
    return workflow in SUPPORTED_WORKFLOWS


def validate_input_file(path: str | Path) -> tuple[bool, str | None]:
    suffix = Path(path).suffix.lower()
    if suffix not in ALLOWED_INPUT_SUFFIXES:
        return False, f"unsupported_file_type:{suffix or 'none'}"
    return True, None
