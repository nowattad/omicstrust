from __future__ import annotations

from pathlib import Path
from typing import Any

from omicstrust.utils.serialization import write_json


CASE_STUDIES: list[dict[str, Any]] = [
    {
        "id": "vanish_vasogate_pc11",
        "title": "VANISH / VasoGate PC11",
        "data_path": "data/real/vanish_steroid_safety_gate.h5ad",
        "data_availability": "customer_or_researcher_supplied",
        "required_metadata": [
            "technology_type",
            "individual",
            "audit_death_28",
            "audit_vasopressor",
            "audit_steroid",
            "audit_srs",
            "audit_age",
            "audit_sex",
            "audit_apache_ii",
        ],
        "dataset_description": "Retrospective whole-blood transcriptomic treatment-response discovery in the VANISH septic shock trial.",
        "command": "omicstrust copilot 'Run the locked VANISH de novo treatment-response discovery.' --workflow de_novo_treatment_response_discovery --data data/real/vanish_steroid_safety_gate.h5ad --output results/case_vanish_vasogate",
        "output": "results/case_vanish_vasogate",
        "preserved_report": "case_studies/vanish_pc11/evidence/OmicsTrust_VANISH_PC11_Vasopressin_Response_Axis_Report.pdf",
        "preserved_summary": "case_studies/vanish_pc11/discovery_summary.json",
        "expected_decision": "research_stage_candidate_requires_external_validation",
        "claim_level": "retrospective_transcriptomic_treatment_response_discovery",
        "scientific_claim": "A prespecified OmicsTrust workflow recovered PC11 as the strongest internal candidate treatment-response axis among 25 screened components in the analyzed VANISH cohort.",
        "limitations": [
            "Retrospective and post-hoc discovery within VANISH.",
            "Moderate analyzed sample size of 116 patients.",
            "PCA component identity is cohort-dependent.",
            "Not an externally validated biomarker or treatment rule.",
            "Requires locked independent-cohort validation.",
        ],
        "ruo_disclaimer": "Research Use Only. Not for treatment guidance or clinical decision-making.",
    }
]


def list_case_studies() -> list[dict[str, Any]]:
    return [dict(study) for study in CASE_STUDIES]


def get_case_study(case_id: str) -> dict[str, Any]:
    for study in CASE_STUDIES:
        if study["id"] == case_id:
            return dict(study)
    raise KeyError(f"Unknown case study: {case_id}")


def write_case_study_docs(output: str | Path) -> Path:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "case_studies.md"
    lines = [
        "# OmicsTrust Case Study",
        "",
        "The Build Week release is deliberately centered on one preserved RUO proof: VANISH PC11 / VasoGate.",
        "",
    ]
    for study in CASE_STUDIES:
        lines.extend(
            [
                f"## {study['title']}",
                "",
                f"- ID: `{study['id']}`",
                f"- Data availability: {study['data_availability']}",
                f"- Required metadata: {', '.join(study['required_metadata'])}",
                f"- Dataset: {study['dataset_description']}",
                f"- Command: `{study['command']}`",
                f"- Preserved report: `{study['preserved_report']}`",
                f"- Preserved summary: `{study['preserved_summary']}`",
                f"- Decision: {study['expected_decision']}",
                f"- Scientific claim: {study['scientific_claim']}",
                "- Limitations:",
            ]
        )
        lines.extend([f"  - {item}" for item in study["limitations"]])
        lines.extend([f"- RUO: {study['ruo_disclaimer']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_case_study_json(output: str | Path) -> Path:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "case_studies.json"
    write_json(path, {"case_studies": CASE_STUDIES})
    return path
