from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_PC11_POSITIVE_GENES = [
    "PDIA6", "LILRB1", "LILRB4", "ANKRD57", "POLE4", "GOLGA3",
    "PDXK", "LILRA1", "PPARD", "NUDT9", "CCR2", "KLF10",
]

DEFAULT_PC11_NEGATIVE_GENES = [
    "PRPS2", "SLFN13", "N4BP2L1", "MX1", "HOXA5", "PCSK9",
    "OAS3", "OAS2", "SP110", "HERC5", "PSMB8", "GBP4",
]


PC11_VALIDATION_BOUNDARY = {
    "allowed_claims": [
        "PC11 external replication hypothesis",
        "locked PC11 score validation",
        "PC11 mortality association testing",
        "PC11 vasopressor-treatment interaction testing if treatment metadata exists",
        "PC11 biological annotation support",
        "PC11 cohort generalizability assessment",
    ],
    "forbidden_claims": [
        "treatment efficacy proven",
        "treatment safety proven",
        "clinical treatment recommendation",
        "bedside vasopressor selection",
        "dosing guidance",
        "diagnostic device claim",
        "FDA, IND, reimbursement, or regulatory readiness",
    ],
}


PC11_EXTERNAL_COHORTS = [
    {
        "cohort_id": "GSE65682_MARS",
        "name": "Genome-wide blood transcriptional profiling in critically ill patients - MARS consortium",
        "source": "NCBI GEO",
        "accession": "GSE65682",
        "reported_scale": "802 GEO samples; ICU admission and longitudinal whole-blood leukocyte transcriptomics",
        "sample_or_patient_count_for_planning": 802,
        "data_type": "whole_blood_microarray",
        "primary_validation_role": "large-scale PC11 biology, sepsis/septic-shock axis replication, mortality/endotype overlap where metadata permits",
        "treatment_response_role": "vasopressor-randomized treatment interaction likely not available; do not use as proof of vasopressin response unless treatment metadata confirms it",
        "priority": "tier_A_large_external",
        "required_metadata": ["mortality", "sepsis_or_septic_shock_status", "sampling_time", "severity", "vasopressor_if_available"],
        "limitations": ["samples may include longitudinal repeats", "patient-level de-duplication required", "treatment randomization not assumed"],
    },
    {
        "cohort_id": "MARS_ENDOTYPE_306_216_265",
        "name": "MARS/GAinS blood genomic sepsis endotype cohorts",
        "source": "published MARS/GAinS cohorts",
        "accession": "MARS discovery 306; validation 216; GAinS validation 265",
        "reported_scale": "306 + 216 + 265 patients reported in published cohort structure",
        "sample_or_patient_count_for_planning": 787,
        "data_type": "blood_genomewide_expression",
        "primary_validation_role": "external PC11 mortality/endotype/generalizability testing",
        "treatment_response_role": "not a vasopressin randomized validation unless vasopressor treatment metadata exists",
        "priority": "tier_A_large_external",
        "required_metadata": ["28_day_mortality", "cohort", "ICU_admission_sample", "severity", "infection_source"],
        "limitations": ["overlap with GEO/ArrayExpress datasets must be checked", "platform harmonization required"],
    },
    {
        "cohort_id": "GAINS_SRS_DISCOVERY_REPLICATION",
        "name": "GAinS SRS sepsis response signature cohorts",
        "source": "published GAinS/SRS cohorts",
        "accession": "discovery 265; replication 106",
        "reported_scale": "265 discovery patients plus 106 replication patients",
        "sample_or_patient_count_for_planning": 371,
        "data_type": "peripheral_blood_leukocyte_expression",
        "primary_validation_role": "test whether PC11 is independent of or nested within SRS1/SRS2 biology",
        "treatment_response_role": "not sufficient for vasopressin-response claim unless treatment metadata exists",
        "priority": "tier_A_srs_independence",
        "required_metadata": ["SRS_status", "mortality", "severity", "cohort"],
        "limitations": ["community-acquired pneumonia sepsis emphasis", "SRS adjustment required"],
    },
    {
        "cohort_id": "E_MTAB_4451",
        "name": "Microarray transcriptomic profiling of patients with sepsis",
        "source": "EMBL-EBI BioStudies / ArrayExpress",
        "accession": "E-MTAB-4451",
        "reported_scale": "about 106 sepsis cases with usable 28-day follow-up in published validation use",
        "sample_or_patient_count_for_planning": 106,
        "data_type": "leukocyte_microarray",
        "primary_validation_role": "independent mortality/prognosis validation of locked PC11 score",
        "treatment_response_role": "not sufficient for vasopressin-response claim unless treatment metadata exists",
        "priority": "tier_B_external_mortality",
        "required_metadata": ["28_day_mortality", "clinical_followup", "severity"],
        "limitations": ["moderate sample size", "metadata completeness must be audited"],
    },
    {
        "cohort_id": "E_MTAB_4421_5273_5274",
        "name": "Additional GAinS/ArrayExpress sepsis transcriptomic cohorts",
        "source": "EMBL-EBI BioStudies / ArrayExpress",
        "accession": "E-MTAB-4421; E-MTAB-5273; E-MTAB-5274",
        "reported_scale": "scale requires accession-level metadata audit",
        "sample_or_patient_count_for_planning": "",
        "data_type": "blood_microarray",
        "primary_validation_role": "additional platform and infection-source validation",
        "treatment_response_role": "not sufficient for vasopressin-response claim unless treatment metadata exists",
        "priority": "tier_B_external_expansion",
        "required_metadata": ["mortality", "infection_source", "sampling_time", "severity"],
        "limitations": ["must verify overlap with MARS/GAinS and available endpoints"],
    },
    {
        "cohort_id": "E_MTAB_7581_VANISH",
        "name": "VANISH transcriptomic trial dataset",
        "source": "EMBL-EBI BioStudies / ArrayExpress",
        "accession": "E-MTAB-7581",
        "reported_scale": "internal discovery dataset; OmicsTrust analyzed 116 patients",
        "sample_or_patient_count_for_planning": 116,
        "data_type": "whole_blood_transcriptomics_randomized_trial",
        "primary_validation_role": "internal discovery only; not external validation",
        "treatment_response_role": "vasopressin versus norepinephrine randomized treatment-response discovery",
        "priority": "internal_discovery_not_external",
        "required_metadata": ["vasopressor", "mortality", "steroid", "SRS", "age", "APACHE", "sex"],
        "limitations": ["retrospective post-hoc PC discovery", "locked score required before applying elsewhere"],
    },
    {
        "cohort_id": "MIMIC_IV_SEPSIS_EHR",
        "name": "MIMIC-IV sepsis/vasopressor EHR validation layer",
        "source": "clinical EHR, not transcriptomics",
        "accession": "MIMIC-IV derived cohort",
        "reported_scale": "large ICU EHR; no blood transcriptome",
        "sample_or_patient_count_for_planning": "",
        "data_type": "clinical_EHR_no_transcriptome",
        "primary_validation_role": "clinical confounding and vasopressor outcome modeling only",
        "treatment_response_role": "cannot validate PC11 without expression; can test clinical vasopressor model assumptions",
        "priority": "tier_C_clinical_context_only",
        "required_metadata": ["vasopressor_timing", "mortality", "severity", "shock_definition"],
        "limitations": ["cannot score PC11", "observational treatment confounding"],
    },
]


def run_pc11_external_validation_plan(
    report_input: str | Path,
    *,
    output: str | Path = "results/pc11_external_validation_package",
) -> dict[str, Any]:
    report_path = _resolve_report(report_input)
    payload = _read_json(report_path)
    axis = _extract_axis(payload)

    positive_genes = _dedupe(axis.get("up_genes") or DEFAULT_PC11_POSITIVE_GENES)
    negative_genes = _dedupe(axis.get("down_genes") or DEFAULT_PC11_NEGATIVE_GENES)
    all_genes = _dedupe(axis.get("genes") or positive_genes + negative_genes)

    locked_contract = _locked_axis_contract(axis, positive_genes, negative_genes, all_genes)
    protocol = _validation_protocol(locked_contract)
    cohorts = _cohort_registry()
    queries = _validation_queries(locked_contract, cohorts)
    readiness = _readiness_summary(locked_contract, cohorts)

    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)

    _write_json(out / "pc11_locked_axis_contract.json", locked_contract)
    _write_json(out / "pc11_external_validation_protocol.json", protocol)
    _write_json(out / "pc11_validation_readiness.json", readiness)
    _write_csv(out / "pc11_external_validation_cohorts.csv", cohorts)
    _write_csv(out / "pc11_validation_queries.csv", queries)
    _write_markdown(out / "pc11_readiness_report.md", locked_contract, protocol, cohorts, readiness)

    report = {
        "workflow": "pc11_external_validation_plan",
        "status": "validation_package_generated",
        "source_report": str(report_path),
        "axis_name": locked_contract["axis_name"],
        "locked_axis_contract": locked_contract,
        "validation_protocol": protocol,
        "cohort_count": len(cohorts),
        "query_count": len(queries),
        "readiness": readiness,
        "claim_boundary": PC11_VALIDATION_BOUNDARY,
        "verdict": {
            "pc11_external_validation_status": "planned_not_yet_validated",
            "treatment_guidance_allowed": False,
            "clinical_use_allowed": False,
            "therapeutic_claim_allowed": False,
            "regulatory_ready": False,
            "next_required_step": "download and harmonize external cohort expression matrices and patient-level metadata",
        },
        "report_links": {
            "locked_axis_contract": str(out / "pc11_locked_axis_contract.json"),
            "validation_protocol": str(out / "pc11_external_validation_protocol.json"),
            "cohort_registry": str(out / "pc11_external_validation_cohorts.csv"),
            "validation_queries": str(out / "pc11_validation_queries.csv"),
            "readiness_report": str(out / "pc11_readiness_report.md"),
        },
    }
    _write_json(out / "pc11_external_validation_package.json", report)
    return report


def _resolve_report(report_input: str | Path) -> Path:
    path = Path(report_input)
    if path.is_dir():
        for name in [
            "discovery_summary.json",
            "pc11_external_validation_package.json",
            "pc11_locked_axis_contract.json",
            "summary.json",
        ]:
            candidate = path / name
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"No supported report JSON found in {path}")
    if not path.exists():
        raise FileNotFoundError(f"Report input not found: {path}")
    return path


def _extract_axis(payload: dict[str, Any]) -> dict[str, Any]:
    if "axis_signature" in payload:
        return dict(payload["axis_signature"])
    if "axis_interpretation" in payload:
        return dict(payload["axis_interpretation"])
    if "locked_axis_contract" in payload:
        return dict(payload["locked_axis_contract"])
    if payload.get("case_study_id") == "vanish_vasogate_pc11":
        return {
            "axis_name": "VANISH PC11 / VasoGate Vasopressin Response Axis",
            "genes": DEFAULT_PC11_POSITIVE_GENES + DEFAULT_PC11_NEGATIVE_GENES,
            "up_genes": DEFAULT_PC11_POSITIVE_GENES,
            "down_genes": DEFAULT_PC11_NEGATIVE_GENES,
            "pathways": [
                "septic shock transcriptomic treatment-response axis",
                "interferon antiviral innate immunity",
                "myeloid immune receptor trafficking",
                "ER stress",
                "protein homeostasis",
            ],
            "phenotype": "PC11 candidate vasopressin-response axis in septic shock",
            "disease_context": "VANISH septic shock whole-blood transcriptomic treatment-response discovery",
        }
    axis_name = payload.get("axis_name", "VANISH PC11 / VasoGate Vasopressin Response Axis")
    return {
        "axis_name": axis_name,
        "genes": DEFAULT_PC11_POSITIVE_GENES + DEFAULT_PC11_NEGATIVE_GENES,
        "up_genes": DEFAULT_PC11_POSITIVE_GENES,
        "down_genes": DEFAULT_PC11_NEGATIVE_GENES,
        "pathways": [
            "septic shock transcriptomic treatment-response axis",
            "interferon antiviral innate immunity",
            "myeloid immune receptor trafficking",
            "ER stress",
            "protein homeostasis",
        ],
        "phenotype": "PC11 candidate vasopressin-response axis in septic shock",
        "disease_context": "VANISH septic shock whole-blood transcriptomic treatment-response discovery",
    }


def _locked_axis_contract(axis: dict[str, Any], positive_genes: list[str], negative_genes: list[str], all_genes: list[str]) -> dict[str, Any]:
    return {
        "contract_id": "PC11_VASOGATE_LOCKED_AXIS_CONTRACT_V1",
        "axis_name": axis.get("axis_name", "VANISH PC11 / VasoGate Vasopressin Response Axis"),
        "phenotype": axis.get("phenotype", "PC11 candidate vasopressin-response axis in septic shock"),
        "disease_context": axis.get("disease_context", "septic shock whole-blood transcriptomic treatment-response discovery"),
        "positive_direction_genes": positive_genes,
        "negative_direction_genes": negative_genes,
        "all_contract_genes": all_genes,
        "scoring_rule": {
            "method": "directional_zscore_difference_v1",
            "formula": "PC11_locked_score = mean(z(positive_direction_genes)) - mean(z(negative_direction_genes))",
            "orientation": "higher_score_should_match_the_VANISH_PC11_high_direction",
            "minimum_detected_genes_required": max(8, min(16, int(0.6 * len(all_genes)))),
            "platform_harmonization": [
                "map probes to HGNC gene symbols",
                "collapse duplicate probes by median or highest-variance probe",
                "z-score genes within validation cohort before scoring",
                "do not refit PCA in validation cohorts",
            ],
            "weighting_status": "direction_only_v1",
            "weighting_limitation": "Exact probe-level PC11 weights should replace direction-only scoring if original signed loadings CSV is available.",
        },
        "primary_claim_to_test": "A locked PC11 gene score externally replicates a septic-shock whole-blood treatment-response/mortality-associated axis.",
        "forbidden_claims": PC11_VALIDATION_BOUNDARY["forbidden_claims"],
    }


def _validation_protocol(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol_id": "PC11_EXTERNAL_VALIDATION_PROTOCOL_V1",
        "primary_objective": "Test whether the locked PC11 score generalizes to independent septic-shock/sepsis transcriptomic cohorts.",
        "validation_levels": [
            {
                "level": "L1_axis_detectability",
                "question": "Can the locked PC11 genes be detected and scored in the external platform?",
                "pass_criteria": ">= minimum_detected_genes_required and both positive/negative directions represented",
            },
            {
                "level": "L2_biology_replication",
                "question": "Does PC11 align with interferon/innate immunity, myeloid trafficking, immune proteasome, and proteostasis/stress biology?",
                "pass_criteria": "directional enrichment and gene-set overlap survive FDR within external cohorts",
            },
            {
                "level": "L3_mortality_association",
                "question": "Is locked PC11 associated with 28-day or ICU mortality independent of severity and cohort?",
                "model": "mortality ~ locked_PC11 + age + sex + severity + cohort + batch/platform",
                "pass_criteria": "consistent direction in >=70% evaluable cohorts and meta-analysis effect not crossing null after sensitivity review",
            },
            {
                "level": "L4_srs_independence",
                "question": "Is PC11 independent of SRS/MARS/CTS endotypes?",
                "model": "mortality ~ locked_PC11 + published_endotype + severity + cohort",
                "pass_criteria": "PC11 retains signal or explains a distinct axis beyond known endotypes",
            },
            {
                "level": "L5_treatment_interaction",
                "question": "If vasopressor assignment exists, does PC11 modify vasopressin versus norepinephrine/noradrenaline association with mortality?",
                "model": "mortality ~ vasopressor * locked_PC11 + severity + steroid + endotype + age + sex",
                "pass_criteria": "pre-specified interaction direction matches VANISH and survives permutation/sensitivity analysis",
                "note": "Only cohorts with vasopressor treatment metadata can evaluate this level.",
            },
        ],
        "safety_boundary": "Even successful validation does not prove treatment efficacy, safety, clinical utility, or regulatory readiness.",
    }


def _cohort_registry() -> list[dict[str, Any]]:
    return [dict(row) for row in PC11_EXTERNAL_COHORTS]


def _validation_queries(contract: dict[str, Any], cohorts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    genes = contract["all_contract_genes"]
    pathway_terms = ["sepsis", "septic shock", "whole blood", "mortality", "vasopressor", "vasopressin", "norepinephrine"]
    rows = []
    for cohort in cohorts:
        rows.append(
            {
                "cohort_id": cohort["cohort_id"],
                "source": cohort["source"],
                "accession": cohort["accession"],
                "query_type": "data_access",
                "query": f'{cohort["accession"]} expression matrix phenotype mortality metadata',
                "purpose": "locate external expression and phenotype files",
            }
        )
        rows.append(
            {
                "cohort_id": cohort["cohort_id"],
                "source": cohort["source"],
                "accession": cohort["accession"],
                "query_type": "gene_coverage",
                "query": " OR ".join(genes),
                "purpose": "verify PC11 locked gene coverage",
            }
        )
        rows.append(
            {
                "cohort_id": cohort["cohort_id"],
                "source": cohort["source"],
                "accession": cohort["accession"],
                "query_type": "clinical_metadata",
                "query": " AND ".join(pathway_terms),
                "purpose": "identify mortality, severity, SRS/endotype, and vasopressor fields",
            }
        )
    return rows


def _readiness_summary(contract: dict[str, Any], cohorts: list[dict[str, Any]]) -> dict[str, Any]:
    numeric_counts = []
    for row in cohorts:
        value = row.get("sample_or_patient_count_for_planning")
        if isinstance(value, int):
            numeric_counts.append(value)
    return {
        "current_internal_discovery_n": 116,
        "raw_external_scale_available_for_planning": sum(numeric_counts),
        "raw_external_scale_warning": "This is not an additive final patient count; cohorts/samples must be de-duplicated and filtered for usable baseline samples and metadata.",
        "primary_external_targets": [c["cohort_id"] for c in cohorts if c["priority"].startswith("tier_A")],
        "first_success_definition": [
            "locked PC11 score computable in at least two independent transcriptomic cohorts",
            "PC11 biology aligns with interferon/myeloid/proteostasis signatures",
            "mortality association or endotype independence is directionally consistent",
            "vasopressin interaction claim remains restricted to cohorts with treatment metadata",
        ],
        "not_ready_for": PC11_VALIDATION_BOUNDARY["forbidden_claims"],
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key, "")) for key in fields})


def _csv_value(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _write_markdown(path: Path, contract: dict[str, Any], protocol: dict[str, Any], cohorts: list[dict[str, Any]], readiness: dict[str, Any]) -> None:
    lines = [
        "# PC11 / VasoGate External Validation Package",
        "",
        "Research-use-only validation plan. This does not prove treatment efficacy, safety, clinical use, or regulatory readiness.",
        "",
        f"Axis: {contract['axis_name']}",
        f"Positive genes: {', '.join(contract['positive_direction_genes'])}",
        f"Negative genes: {', '.join(contract['negative_direction_genes'])}",
        "",
        "## Locked scoring rule",
        "",
        contract["scoring_rule"]["formula"],
        "",
        "## Validation levels",
    ]
    for level in protocol["validation_levels"]:
        lines.append(f"- **{level['level']}**: {level['question']}")
    lines.extend(["", "## External cohorts"])
    for cohort in cohorts:
        lines.append(f"- **{cohort['cohort_id']}**: {cohort['reported_scale']} — priority: {cohort['priority']}")
    lines.extend(["", "## Readiness"])
    lines.append(f"- Raw external scale for planning: {readiness['raw_external_scale_available_for_planning']}")
    lines.append(f"- Warning: {readiness['raw_external_scale_warning']}")
    lines.extend(["", "## Cannot claim"])
    for claim in PC11_VALIDATION_BOUNDARY["forbidden_claims"]:
        lines.append(f"- {claim}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        key = str(value).strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out
