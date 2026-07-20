from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omicstrust.audit import run_audit
from omicstrust.benchmarks.comparative import run_real_dataset_benchmark
from omicstrust.case_studies.registry import list_case_studies
from omicstrust.copilot.data_discovery import (
    critical_missing_for_workflow,
    inspect_copilot_data,
    merge_selected_keys,
)
from omicstrust.copilot.openai_layer import (
    apply_gpt_workflow_suggestion,
    explain_result_with_gpt,
    interpret_request_with_gpt,
)
from omicstrust.copilot.planner import build_copilot_plan
from omicstrust.copilot.public_search import PublicDatasetSearchQuery, parse_public_dataset_request, search_public_datasets
from omicstrust.copilot.schemas import CopilotRequest
from omicstrust.copilot.safety import validate_input_file
from omicstrust.copilot.workflow_router import route_workflow
from omicstrust.utils.serialization import make_json_safe, read_json, write_json
from omicstrust.workflows.de_novo_treatment_response import run_de_novo_treatment_response_discovery
from omicstrust.workflows.locked_validation import validate_locked_axis


JOB_FILENAME = "copilot_job.json"
PLAN_FILENAME = "copilot_plan.json"
RESULT_FILENAME = "copilot_result.json"


class CopilotJobStore:
    def __init__(self, root: str | Path = "results/copilot"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def create_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        job_id = uuid.uuid4().hex[:16]
        job_dir = self.job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=False)
        record = {
            "job_id": job_id,
            "status": "queued",
            "created_at": _utc_now(),
            "started_at": None,
            "finished_at": None,
            "progress": ["queued"],
            "error": None,
            "job_dir": str(job_dir),
            "payload": make_json_safe(payload),
        }
        self._write_job(job_id, record)
        return record

    def save_upload(self, job_id: str, filename: str, content_file: Any) -> Path:
        safe = _safe_filename(filename)
        target = self.job_dir(job_id) / "uploads" / safe
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as handle:
            shutil.copyfileobj(content_file, handle)
        return target

    def set_payload(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = self.get_job(job_id)
        record["payload"] = make_json_safe(payload)
        self._write_job(job_id, record)
        return record

    def run_job(self, job_id: str) -> dict[str, Any]:
        record = self.get_job(job_id)
        self._update(job_id, status="running", started_at=_utc_now(), progress=["understanding request"])
        try:
            result = run_copilot_job(self.job_dir(job_id), record["payload"], progress_callback=lambda stage: self._append_progress(job_id, stage))
            self._update(
                job_id,
                status=result.get("status", "completed"),
                finished_at=_utc_now(),
                error=result.get("error"),
            )
        except Exception as exc:
            failure = {
                "status": "failed",
                "short_answer": "Evidence Copilot failed before producing an audit result.",
                "error": str(exc),
                "ruo_disclaimer": _ruo(),
            }
            write_json(self.job_dir(job_id) / RESULT_FILENAME, failure)
            self._update(job_id, status="failed", finished_at=_utc_now(), error=str(exc), progress=["failed"])
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict[str, Any]:
        path = self.job_dir(job_id) / JOB_FILENAME
        if not path.exists():
            raise KeyError(f"Unknown copilot job_id: {job_id}")
        return read_json(path)

    def plan(self, job_id: str) -> dict[str, Any]:
        return read_json(self.job_dir(job_id) / PLAN_FILENAME)

    def result(self, job_id: str) -> dict[str, Any]:
        return read_json(self.job_dir(job_id) / RESULT_FILENAME)

    def job_dir(self, job_id: str) -> Path:
        return self.root / job_id

    def _write_job(self, job_id: str, record: dict[str, Any]) -> None:
        write_json(self.job_dir(job_id) / JOB_FILENAME, record)

    def _update(self, job_id: str, **fields: Any) -> None:
        record = self.get_job(job_id)
        record.update(make_json_safe(fields))
        self._write_job(job_id, record)

    def _append_progress(self, job_id: str, stage: str) -> None:
        record = self.get_job(job_id)
        progress = list(record.get("progress", []))
        if stage not in progress:
            progress.append(stage)
        record["progress"] = progress
        self._write_job(job_id, record)


def run_copilot_job(job_dir: str | Path, payload: dict[str, Any], *, progress_callback: Any | None = None) -> dict[str, Any]:
    job_dir = Path(job_dir)
    request = CopilotRequest.from_payload(payload)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "input_prompt.txt").write_text(request.user_request, encoding="utf-8")
    _append_execution_log(job_dir, "started")
    _progress(progress_callback, "understanding request")
    plan = build_copilot_plan(request)
    if plan.status != "rejected":
        ai_plan = interpret_request_with_gpt(request, plan)
        if ai_plan.get("status") == "completed":
            _progress(progress_callback, "interpreting intent with GPT-5.6")
        plan = apply_gpt_workflow_suggestion(request, plan, ai_plan)
    else:
        ai_plan = {
            "status": "not_used",
            "reason": "deterministic_safety_rejection",
            "boundary": {"clinical_decision_making": False, "ruo_only": True},
        }
        plan.ai_assistance = ai_plan

    data_path = request.data_path
    metadata_path = request.metadata_path
    if request.uploaded_files and not data_path:
        data_path = _first_data_file(request.uploaded_files)
        metadata_path = metadata_path or _first_metadata_file(request.uploaded_files)
    if data_path:
        ok, reason = validate_input_file(data_path)
        if not ok:
            plan.status = "needs_clarification"
            plan.missing.append(reason or "supported omics input file")
            plan.message = "Provide a supported .h5ad, .csv, .tsv, or .txt dataset."

    data_report: dict[str, Any] = {"available": False}
    selected_keys = {
        "batch_key": request.batch_key,
        "donor_key": request.donor_key,
        "label_key": request.label_key,
        "treatment_key": request.treatment_key,
        "outcome_key": request.outcome_key,
        "patient_id_key": request.patient_id_key,
        "sample_id_key": request.patient_id_key,
    }
    if data_path and plan.status == "planned":
        _progress(progress_callback, "inspecting data")
        data_report = inspect_copilot_data(data_path, metadata_path)
        detected = data_report.get("candidate_columns", {})
        selected_keys = merge_selected_keys(selected_keys, detected, plan.workflow)
        plan.required_columns.update(
            {
                "sample_id": selected_keys.get("sample_id_key"),
                "patient_id": selected_keys.get("donor_key"),
                "treatment": selected_keys.get("treatment_key"),
                "outcome": selected_keys.get("outcome_key"),
                "batch": selected_keys.get("batch_key"),
                "donor": selected_keys.get("donor_key"),
                "label": selected_keys.get("label_key"),
            }
        )
        plan.selected_keys = selected_keys
        critical_missing = critical_missing_for_workflow(plan.workflow, selected_keys)
        if critical_missing:
            plan.status = "needs_clarification"
            plan.missing.extend(item for item in critical_missing if item not in plan.missing)
            plan.message = "Evidence Copilot needs one clear metadata mapping before running this workflow."

    write_json(job_dir / PLAN_FILENAME, plan.to_dict())
    _progress(progress_callback, "selecting workflow")
    route = route_workflow(plan)
    if not route.runnable:
        result = _non_runnable_result(plan, route, data_report)
        result["ai_copilot"] = {"planning": ai_plan, "interpretation": {"status": "not_used", "reason": "workflow_not_run"}}
        write_json(job_dir / RESULT_FILENAME, result)
        return result

    if route.action == "inspect":
        result = _inspection_result(plan, route.to_dict(), data_report)
    elif route.action == "public_search":
        result = _public_search_result(job_dir, plan, route.to_dict(), request.user_request, progress_callback)
    elif route.action == "case_study":
        result = _case_study_result(plan, route.to_dict())
    elif route.action == "benchmark":
        result = _benchmark_result(job_dir, plan, route.to_dict(), data_path, selected_keys, request.config_path, progress_callback)
    elif route.action == "locked_validation":
        result = _locked_validation_result(job_dir, plan, route.to_dict(), request.locked_axis_path, data_path, selected_keys, request.config_path, progress_callback)
    elif route.action == "de_novo_discovery":
        result = _de_novo_discovery_result(job_dir, plan, route.to_dict(), request, data_path, selected_keys, progress_callback)
    else:
        result = _audit_result(job_dir, plan, route.to_dict(), data_path, selected_keys, request.config_path, progress_callback)
    result = _attach_ai_interpretation(request, result, ai_plan, progress_callback)
    write_json(job_dir / RESULT_FILENAME, result)
    if result.get("selected_workflow") == "public_dataset_search":
        write_json(job_dir / "result.json", result)
    _progress(progress_callback, "completed")
    _append_execution_log(job_dir, f"finished:{result.get('status') or result.get('final_status')}")
    return result


def _attach_ai_interpretation(
    request: CopilotRequest,
    result: dict[str, Any],
    ai_plan: dict[str, Any],
    progress_callback: Any | None,
) -> dict[str, Any]:
    interpretation = explain_result_with_gpt(request, result)
    if interpretation.get("status") == "completed":
        _progress(progress_callback, "explaining evidence with GPT-5.6")
    result["ai_copilot"] = {
        "planning": ai_plan,
        "interpretation": interpretation,
        "statistics_authority": "deterministic_omicstrust_engine",
    }
    return result


def _audit_result(
    job_dir: Path,
    plan: Any,
    route: dict[str, Any],
    data_path: str | None,
    selected_keys: dict[str, str | None],
    config_path: str | None,
    progress_callback: Any | None,
) -> dict[str, Any]:
    if not data_path:
        return _needs_clarification("local data path", plan, route)
    _progress(progress_callback, "running audit")
    audit_dir = job_dir / "audit"
    context = run_audit(
        data_path,
        output=audit_dir,
        batch_key=selected_keys.get("batch_key"),
        donor_key=selected_keys.get("donor_key"),
        label_key=selected_keys.get("label_key"),
        config_path=config_path,
        command=["omicstrust", "copilot", plan.workflow, str(data_path)],
    )
    _progress(progress_callback, "generating report")
    summary = context.get("summary", {})
    claim_matrix = _read_optional(audit_dir / "claim_matrix.json")
    return {
        "status": "completed",
        "short_answer": _short_answer(summary),
        "selected_workflow": plan.workflow,
        "route": route,
        "data_qc": summary.get("data_qc"),
        "signal_summary": summary.get("structural_signal"),
        "batch_risk": summary.get("batch_risk"),
        "metadata_risk": summary.get("metadata_risk") or summary.get("main_failure"),
        "stability": summary.get("stability"),
        "trust_verdict": summary.get("trust_level"),
        "safe_to_interpret": summary.get("safe_to_interpret"),
        "selected_keys": selected_keys,
        "what_can_be_claimed": claim_matrix.get("can_claim", []),
        "what_cannot_be_claimed": claim_matrix.get("cannot_claim", []),
        "report_links": _report_links(audit_dir),
        "ruo_disclaimer": _ruo(),
    }


def _benchmark_result(
    job_dir: Path,
    plan: Any,
    route: dict[str, Any],
    data_path: str | None,
    selected_keys: dict[str, str | None],
    config_path: str | None,
    progress_callback: Any | None,
) -> dict[str, Any]:
    if not data_path:
        return _needs_clarification("local data path", plan, route)
    _progress(progress_callback, "running audit")
    output = job_dir / "benchmark"
    report = run_real_dataset_benchmark(
        data_path,
        output=output,
        batch_key=selected_keys.get("batch_key"),
        donor_key=selected_keys.get("donor_key"),
        label_key=selected_keys.get("label_key"),
        config_path=config_path,
    )
    _progress(progress_callback, "generating report")
    return {
        "status": "completed",
        "short_answer": "Comparative benchmark wrapper completed; interpret all results as RUO audit evidence.",
        "selected_workflow": plan.workflow,
        "route": route,
        "benchmark": report,
        "report_links": {"benchmark_json": str(output / "comparative_benchmark.json"), "benchmark_csv": str(output / "comparative_benchmark.csv")},
        "ruo_disclaimer": _ruo(),
    }


def _de_novo_discovery_result(
    job_dir: Path,
    plan: Any,
    route: dict[str, Any],
    request: CopilotRequest,
    data_path: str | None,
    selected_keys: dict[str, str | None],
    progress_callback: Any | None,
) -> dict[str, Any]:
    if not data_path:
        return _needs_clarification("local data path", plan, route)
    _progress(progress_callback, "running de novo discovery")
    output = job_dir / "de_novo_discovery"
    raw = run_de_novo_treatment_response_discovery(
        data_path=data_path,
        output_dir=output,
        treatment_key=request.treatment_key or selected_keys.get("treatment_key"),
        outcome_key=request.outcome_key or selected_keys.get("outcome_key"),
        covariate_keys=request.covariate_keys,
        patient_id_key=request.patient_id_key or selected_keys.get("patient_id_key"),
        batch_key=request.batch_key,
        known_endotype_key=request.known_endotype_key,
        dataset_adapter=request.dataset_adapter,
        n_top_variable_features=request.n_top_variable_features or 5000,
        n_axes=request.n_axes,
        n_pcs=request.n_pcs or 25,
        model_family=request.model_family or "logistic",
        permutation_n=request.permutation_n or 1000,
        bootstrap_n=request.bootstrap_n or 1000,
    )
    if raw.get("status") in {"missing_inputs", "unsupported_workflow", "failed"}:
        return {
            "status": raw.get("status"),
            "short_answer": raw.get("message") or raw.get("reason") or "De novo discovery could not run.",
            "selected_workflow": plan.workflow,
            "route": route,
            "missing": raw.get("missing", []),
            "reason": raw.get("reason"),
            "dataset_summary": {},
            "result_summary": {},
            "key_findings": [],
            "statistics": {},
            "limitations": ["No discovery result was produced."],
            "what_can_be_claimed": [],
            "what_cannot_be_claimed": ["No treatment-response discovery claim can be made because the workflow did not complete."],
            "ruo_disclaimer": _ruo(),
            "execution_artifacts": _discovery_artifacts(output),
        }

    normalized = _normalize_discovery_result(plan.workflow, route, raw, output)
    write_json(output / "copilot_normalized_discovery_result.json", normalized)
    return normalized


def _non_runnable_result(plan: Any, route: Any, data_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": plan.status,
        "short_answer": plan.message or _status_message(plan.status),
        "selected_workflow": plan.workflow,
        "route": route.to_dict(),
        "missing": plan.missing,
        "reason": plan.reason,
        "data_inspection": data_report,
        "safety": plan.safety,
        "ruo_disclaimer": _ruo(),
    }


def _normalize_discovery_result(workflow: str, route: dict[str, Any], raw: dict[str, Any], output: Path) -> dict[str, Any]:
    top = raw.get("top_candidate") or {}
    perm = raw.get("top_candidate_permutation") or {}
    boot = raw.get("top_candidate_bootstrap") or {}
    meta = raw.get("top_candidate_metadata_r2") or {}
    group_mortality = raw.get("top_candidate_group_mortality") or []
    verdict = raw.get("verdict") or {}
    top_axis = top.get("pc") or verdict.get("top_pc")
    interaction_term = top.get("term")
    beta = top.get("beta")
    odds_ratio = top.get("or_per_1sd")
    wald_p = top.get("wald_p")
    lrt_p = top.get("lrt_p")
    fdr = top.get("lrt_fdr_bh")
    permutation_p = perm.get("p_value_lrt_ge_observed")
    bootstrap_stability = _bootstrap_direction_stability(boot)
    metadata_r2 = meta.get("r2")
    validation_required = True
    clinical_use_allowed = False
    verdict_text = _discovery_verdict_text(verdict)
    limitations = [
        "This is a de novo retrospective discovery screen, not a locked validation.",
        "External validation in an independent cohort with the same treatment/outcome labels is required.",
        "Subgroup mortality summaries are descriptive and must not be used for patient-level treatment selection.",
    ]
    can_claim = [
        "A controlled RUO discovery workflow screened latent molecular axes for treatment-by-axis outcome interaction.",
        "The reported axis, statistics, resampling checks, and metadata explanation are internal evidence for follow-up.",
    ]
    cannot_claim = [
        "This does not establish a clinical biomarker, treatment recommendation, or prospective treatment rule.",
        "This does not prove novelty without literature review and independent validation.",
        "This does not permit diagnosis, prognosis, or regulated clinical decision-making.",
    ]
    statistics = {
        "top_candidate_axis": top_axis,
        "interaction_term": interaction_term,
        "beta": beta,
        "effect_size": {"OR_per_1_SD": odds_ratio},
        "OR": odds_ratio,
        "p_value": wald_p,
        "wald_p": wald_p,
        "lrt_p": lrt_p,
        "fdr": fdr,
        "permutation_p": permutation_p,
        "bootstrap_direction_stability": bootstrap_stability,
        "bootstrap": boot,
        "metadata_r2": metadata_r2,
        "metadata_explanation": meta,
        "subgroup_descriptive_summary": group_mortality,
    }
    result_summary = {
        "top_candidate_axis": top_axis,
        "interaction_term": interaction_term,
        "verdict": verdict,
        "verdict_text": verdict_text,
        "validation_required": validation_required,
        "clinical_use_allowed": clinical_use_allowed,
    }
    return {
        "status": "completed",
        "selected_workflow": workflow,
        "short_answer": f"De novo treatment-response discovery completed. Top candidate: {top_axis}; verdict: {verdict_text}",
        "route": route,
        "dataset_summary": {
            "n_patients": raw.get("n_patients"),
            "n_features": raw.get("n_features"),
            "n_top_variable_features": raw.get("n_top_variable_features"),
            "n_pcs_screened": raw.get("n_pcs_screened"),
            "dataset_adapter": raw.get("dataset_adapter"),
            "mapping": raw.get("mapping"),
        },
        "result_summary": result_summary,
        "key_findings": [
            f"Top candidate axis: {top_axis}",
            f"Interaction term: {interaction_term}",
            f"OR per 1 SD: {odds_ratio}",
            f"Wald p: {wald_p}; LRT p: {lrt_p}; FDR: {fdr}",
            f"Permutation p: {permutation_p}; bootstrap direction stability: {bootstrap_stability}",
            f"Metadata R2 for candidate axis: {metadata_r2}",
        ],
        "statistics": statistics,
        "limitations": limitations,
        "what_can_be_claimed": can_claim,
        "what_cannot_be_claimed": cannot_claim,
        "ruo_disclaimer": _ruo(),
        "ruo_claim_boundary": raw.get("ruo_claim_boundary") or _ruo(),
        "validation_required": validation_required,
        "clinical_use_allowed": clinical_use_allowed,
        "top_candidate_axis": top_axis,
        "interaction_term": interaction_term,
        "beta": beta,
        "OR": odds_ratio,
        "wald_p": wald_p,
        "lrt_p": lrt_p,
        "FDR": fdr,
        "fdr": fdr,
        "permutation_p": permutation_p,
        "bootstrap_direction_stability": bootstrap_stability,
        "metadata_R2": metadata_r2,
        "metadata_r2": metadata_r2,
        "subgroup_mortality": group_mortality,
        "verdict": verdict,
        "raw_discovery_result": raw,
        "report_links": _discovery_report_links(output),
        "execution_artifacts": _discovery_artifacts(output),
    }


def _inspection_result(plan: Any, route: dict[str, Any], data_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "completed",
        "short_answer": "Dataset inspection completed. Use the suggested metadata keys before making biological claims.",
        "selected_workflow": plan.workflow,
        "route": route,
        "data_inspection": data_report,
        "what_can_be_claimed": ["The dataset was inspected for shape, format, and candidate metadata columns."],
        "what_cannot_be_claimed": ["No biological signal, trust, or clinical claim is supported by inspection alone."],
        "ruo_disclaimer": _ruo(),
    }


def _case_study_result(plan: Any, route: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "completed",
        "short_answer": "Packaged RUO case studies are available for buyer-demo review.",
        "selected_workflow": plan.workflow,
        "route": route,
        "case_studies": list_case_studies(),
        "what_can_be_claimed": ["These are structured RUO case-study packages for demo and pilot planning."],
        "what_cannot_be_claimed": ["Case-study packaging alone does not prove clinical validity or treatment guidance."],
        "ruo_disclaimer": _ruo(),
    }


def _public_search_result(job_dir: Path, plan: Any, route: dict[str, Any], user_request: str, progress_callback: Any | None) -> dict[str, Any]:
    _progress(progress_callback, "searching public metadata")
    _append_execution_log(job_dir, "public_dataset_search:metadata_only")
    query = _public_query_from_plan(plan, user_request)
    write_json(job_dir / "public_search_query.json", query.to_dict())
    if _requires_download_confirmation(user_request):
        result = {
            "status": "needs_confirmation_for_download",
            "final_status": "needs_confirmation_for_download",
            "selected_workflow": "public_dataset_search",
            "short_answer": "Public metadata search can run, but large dataset download requires explicit confirmation and will not start automatically.",
            "route": route,
            "query": query.to_dict(),
            "candidates": [],
            "warnings": ["large_download_not_started"],
            "next_best_action": "Run metadata search first, select one candidate, then explicitly confirm any download.",
            "no_large_download_performed": True,
            "what_can_be_claimed": ["No data download or analysis was performed."],
            "what_cannot_be_claimed": ["No clinical, biological, or treatment-efficacy claim can be made from a download request."],
            "ruo": _ruo(),
            "ruo_disclaimer": _ruo(),
        }
        write_json(job_dir / "public_dataset_candidates.json", {"query": query.to_dict(), "candidates": [], "warnings": result["warnings"], "ruo_disclaimer": _ruo()})
        return result
    search_result = search_public_datasets(query)
    search_payload = search_result.to_dict()
    write_json(job_dir / "public_dataset_candidates.json", search_payload)
    _write_public_search_report(job_dir / "public_search_report.html", search_payload)
    candidates = search_payload["candidates"]
    weak_leads = search_payload.get("weak_literature_leads", [])
    if candidates:
        final_status = "completed"
    elif weak_leads:
        final_status = "no_high_suitability_candidates_found"
    else:
        final_status = "no_candidates_found"
    short_answer = (
        "Found candidate public datasets. No analysis was run because no dataset was downloaded yet."
        if candidates
        else (
            "No high-suitability public dataset candidates were found after adaptive metadata search. Weak literature leads are listed separately for manual review."
            if weak_leads
            else "No suitable public dataset candidates were found after adaptive metadata search. Refine disease, treatment, response, or omics terms."
        )
    )
    compact_mode = _public_search_compact_mode(user_request)
    return {
        "status": final_status,
        "final_status": final_status,
        "selected_workflow": "public_dataset_search",
        "short_answer": short_answer,
        "route": route,
        "query": query.to_dict(),
        "candidates": candidates,
        "candidate_count": len(candidates),
        "compact_mode": compact_mode,
        "high_suitability_candidates": search_payload.get("high_suitability_candidates", []),
        "medium_suitability_candidates": search_payload.get("medium_suitability_candidates", []),
        "weak_literature_leads": weak_leads,
        "weak_leads_count": len(weak_leads),
        "excluded_or_low_relevance": search_payload.get("excluded_or_low_relevance", []),
        "search_strategy": search_payload.get("search_strategy", {}),
        "queries_attempted": search_payload.get("search_strategy", {}).get("queries_run", []),
        "why_candidates_were_rejected": search_payload.get("search_strategy", {}).get("why_candidates_were_rejected", []),
        "suggested_refined_queries": search_payload.get("search_strategy", {}).get("suggested_refined_queries", []),
        "warnings": search_result.warnings,
        "next_best_action": (
            "Select one candidate for metadata inspection/download confirmation."
            if candidates
            else "Refine the query or search by known accession, disease, treatment, response, and omics terms."
        ),
        "no_large_download_performed": True,
        "what_can_be_claimed": [
            "Public metadata sources were searched for candidate datasets matching the RUO discovery request.",
            "Candidate suitability is a metadata-based triage score, not an analysis result.",
        ],
        "what_cannot_be_claimed": [
            "No expression matrix was downloaded or audited in this phase.",
            "No biological, clinical, diagnostic, prognostic, or treatment-efficacy claim is supported by search results alone.",
        ],
        "ruo": _ruo(),
        "ruo_disclaimer": _ruo(),
    }


def _write_public_search_report(path: Path, payload: dict[str, Any]) -> None:
    def esc(value: Any) -> str:
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def cards(title: str, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return ""
        body = []
        for row in rows:
            body.append(
                f"""
                <article>
                  <h3>{esc(row.get('accession_id'))}: {esc(row.get('title'))}</h3>
                  <dl>
                    <dt>Source</dt><dd>{esc(row.get('source'))}</dd>
                    <dt>Confidence</dt><dd>{esc(row.get('source_confidence'))}</dd>
                    <dt>Disease Match</dt><dd>{esc(row.get('disease_match'))}</dd>
                    <dt>Treatment Match</dt><dd>{esc(row.get('treatment_match'))}</dd>
                    <dt>Omics</dt><dd>{esc(row.get('omics_type'))}</dd>
                    <dt>Score</dt><dd>{esc(row.get('suitability_score'))}</dd>
                  </dl>
                  <p>{esc('; '.join(row.get('limitations', [])))}</p>
                  <p><a href="{esc(row.get('url'))}">Source metadata</a></p>
                </article>
                """
            )
        return f"<section><h2>{esc(title)}</h2>{''.join(body)}</section>"

    strategy = payload.get("search_strategy") or {}
    parsed = strategy.get("parsed") or {}
    strategy_rows = "".join(
        f"<li><code>{esc(query)}</code></li>" for query in (strategy.get("queries_run") or [])[:16]
    )
    strategy_html = f"""
  <details open>
    <summary>Search strategy</summary>
    <p>Explicit disease terms: {esc(', '.join(parsed.get('disease_terms_explicit') or []))}</p>
    <p>Expanded disease terms: {esc(', '.join(parsed.get('disease_terms_expanded') or []))}</p>
    <p>Explicit treatment terms: {esc(', '.join(parsed.get('treatment_terms_explicit') or []))}</p>
    <p>Expanded treatment terms: {esc(', '.join(parsed.get('treatment_terms_expanded') or []))}</p>
    <p>Response terms: {esc(', '.join(parsed.get('response_terms') or []))}</p>
    <p>Omics terms: {esc(', '.join(parsed.get('omics_terms') or []))}</p>
    <p>Sample terms: {esc(', '.join(parsed.get('sample_terms') or []))}</p>
    <p>Excluded diseases: {esc(', '.join(parsed.get('excluded_diseases') or []))}</p>
    <p>Excluded treatments: {esc(', '.join(parsed.get('excluded_treatments') or []))}</p>
    <p>Excluded contexts: {esc(', '.join(parsed.get('excluded_contexts') or []))}</p>
    <p>Sources searched: {esc(', '.join(strategy.get('sources_searched') or []))}</p>
    <p>Raw hits: {esc(strategy.get('raw_hits_by_source') or {})}</p>
    <p>Candidates kept: {esc(strategy.get('candidates_kept'))}; weak leads: {esc(strategy.get('weak_leads_count'))}; excluded: {esc(strategy.get('excluded_count'))}</p>
    <ul>{strategy_rows}</ul>
  </details>
    """

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>OmicsTrust Public Dataset Search</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #172033; }}
    article {{ border: 1px solid #d7dee8; border-radius: 8px; padding: 14px; margin: 12px 0; }}
    dl {{ display: grid; grid-template-columns: 160px 1fr; gap: 6px 12px; }}
    dt {{ font-weight: 700; color: #344054; }}
    dd {{ margin: 0; }}
  </style>
</head>
<body>
  <h1>OmicsTrust Public Dataset Search</h1>
  <p>{esc(payload.get('ruo_disclaimer'))}</p>
  {strategy_html}
  {cards('High Suitability Candidates', payload.get('high_suitability_candidates', []))}
  {cards('Medium Suitability Candidates', payload.get('medium_suitability_candidates', []))}
  {cards('Weak Literature Leads', payload.get('weak_literature_leads', []))}
</body>
</html>"""
    path.write_text(html, encoding="utf-8")


def _locked_validation_result(
    job_dir: Path,
    plan: Any,
    route: dict[str, Any],
    locked_axis_path: str | None,
    data_path: str | None,
    selected_keys: dict[str, str | None],
    config_path: str | None,
    progress_callback: Any | None,
) -> dict[str, Any]:
    if not locked_axis_path or not data_path:
        return _locked_validation_placeholder(plan, route)
    _progress(progress_callback, "running audit")
    output = job_dir / "locked_validation"
    report = validate_locked_axis(
        locked_axis_path,
        data_path,
        output=output,
        batch_key=selected_keys.get("batch_key"),
        donor_key=selected_keys.get("donor_key"),
        label_key=selected_keys.get("label_key"),
        config_path=config_path,
    )
    _progress(progress_callback, "generating report")
    return {
        "status": "completed",
        "short_answer": "Locked-axis validation completed. Interpret the decision as RUO validation evidence only.",
        "selected_workflow": plan.workflow,
        "route": route,
        "trust_verdict": report.get("decision"),
        "safe_to_interpret": "yes" if report.get("passed") else "no",
        "selected_keys": selected_keys,
        "locked_validation": report,
        "report_links": {"locked_validation_report.json": str(output / "locked_validation_report.json")},
        "what_can_be_claimed": [report.get("allowed_claim", "Locked-axis validation evidence for RUO follow-up only.")],
        "what_cannot_be_claimed": report.get("forbidden_claims", []),
        "ruo_disclaimer": _ruo(),
    }


def _locked_validation_placeholder(plan: Any, route: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "needs_clarification",
        "short_answer": "Locked validation requires a locked axis path and a compatible dataset path.",
        "selected_workflow": plan.workflow,
        "route": route,
        "missing": plan.missing or ["locked axis path", "local data path"],
        "ruo_disclaimer": _ruo(),
    }


def _needs_clarification(item: str, plan: Any, route: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "needs_clarification",
        "short_answer": f"Evidence Copilot needs {item} before running this workflow.",
        "selected_workflow": plan.workflow,
        "route": route,
        "missing": [item],
        "ruo_disclaimer": _ruo(),
    }


def _short_answer(summary: dict[str, Any]) -> str:
    safe = summary.get("safe_to_interpret")
    trust = summary.get("trust_level")
    signal = summary.get("structural_signal")
    if safe == "yes":
        return f"OmicsTrust detected {signal} with {trust} trust under the supplied metadata. Keep claims RUO and externally validate."
    return f"OmicsTrust completed the audit, but biological interpretation is limited or unsafe. Trust verdict: {trust}."


def _report_links(audit_dir: Path) -> dict[str, str]:
    names = ["report.html", "report.pdf", "summary.json", "claim_matrix.json", "evidence_ledger.json", "failure_report.json"]
    return {name: str(audit_dir / name) for name in names if (audit_dir / name).exists()}


def _discovery_report_links(output: Path) -> dict[str, str]:
    names = [
        "vanish_denovo_vasopressin_endotype_discovery.json",
        "de_novo_treatment_response_discovery.json",
        "copilot_normalized_discovery_result.json",
    ]
    return {name: str(output / name) for name in names if (output / name).exists()}


def _discovery_artifacts(output: Path) -> dict[str, str]:
    names = [
        "vanish_denovo_vasopressin_endotype_discovery.json",
        "vanish_denovo_vasopressin_pc_scores.csv",
        "vanish_denovo_vasopressin_candidate_groups.csv",
        "de_novo_treatment_response_discovery.json",
        "de_novo_pc_scores.csv",
        "de_novo_candidate_groups.csv",
        "copilot_normalized_discovery_result.json",
    ]
    return {name: str(output / name) for name in names if (output / name).exists()}


def _bootstrap_direction_stability(boot: dict[str, Any]) -> float | None:
    values = [boot.get("prop_beta_positive"), boot.get("prop_beta_negative")]
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    return max(numeric) if numeric else None


def _discovery_verdict_text(verdict: dict[str, Any]) -> str:
    signal = verdict.get("discovery_signal", "unknown_signal")
    metadata = verdict.get("metadata_explanation", "unknown_metadata_explanation")
    bootstrap = verdict.get("bootstrap_direction", "unknown_bootstrap_direction")
    return f"{signal}; {metadata}; {bootstrap}; external_validation_required"


def _read_optional(path: Path) -> dict[str, Any]:
    if path.exists():
        return read_json(path)
    return {}


def _public_query_from_plan(plan: Any, user_request: str) -> PublicDatasetSearchQuery:
    payload = getattr(plan, "public_search_query", None) or {}
    if not payload:
        return parse_public_dataset_request(user_request)
    return PublicDatasetSearchQuery(
        user_goal=payload.get("user_goal"),
        disease=payload.get("disease"),
        disease_terms_explicit=list(payload.get("disease_terms_explicit", [])),
        disease_terms_expanded=list(payload.get("disease_terms_expanded", [])),
        disease_terms=list(payload.get("disease_terms", [])),
        disease_synonyms=list(payload.get("disease_synonyms", [])),
        treatment=payload.get("treatment"),
        treatment_terms_explicit=list(payload.get("treatment_terms_explicit", [])),
        treatment_terms_expanded=list(payload.get("treatment_terms_expanded", [])),
        treatment_terms=list(payload.get("treatment_terms", [])),
        treatment_synonyms=list(payload.get("treatment_synonyms", [])),
        response_terms_explicit=list(payload.get("response_terms_explicit", [])),
        response_terms_expanded=list(payload.get("response_terms_expanded", [])),
        response_terms=list(payload.get("response_terms", [])),
        omics_types=list(payload.get("omics_types", [])),
        omics_terms_explicit=list(payload.get("omics_terms_explicit", [])),
        omics_terms_expanded=list(payload.get("omics_terms_expanded", [])),
        omics_terms=list(payload.get("omics_terms", [])),
        organism=payload.get("organism") or "Homo sapiens",
        sample_context=list(payload.get("sample_context", [])),
        sample_terms_explicit=list(payload.get("sample_terms_explicit", [])),
        sample_terms_expanded=list(payload.get("sample_terms_expanded", [])),
        sample_terms=list(payload.get("sample_terms", [])),
        sources=list(payload.get("sources", [])) or ["GEO", "PubMed", "ArrayExpress", "BioStudies", "local_reference_registry"],
        require_baseline=bool(payload.get("require_baseline", False)),
        baseline_terms_explicit=list(payload.get("baseline_terms_explicit", [])),
        baseline_terms_expanded=list(payload.get("baseline_terms_expanded", [])),
        baseline_terms=list(payload.get("baseline_terms", [])),
        constraints=list(payload.get("constraints", [])),
        excluded_diseases=list(payload.get("excluded_diseases", [])),
        excluded_treatments=list(payload.get("excluded_treatments", [])),
        excluded_contexts=list(payload.get("excluded_contexts", [])),
        excluded_organisms=list(payload.get("excluded_organisms", [])),
        excluded_dataset_types=list(payload.get("excluded_dataset_types", [])),
        human_only=bool(payload.get("human_only", True)),
        baseline_preferred=bool(payload.get("baseline_preferred", False)),
        return_candidates_only=bool(payload.get("return_candidates_only", True)),
        ruo_only=bool(payload.get("ruo_only", True)),
        max_results=int(payload.get("max_results", 10) or 10),
        metadata_only=bool(payload.get("metadata_only", True)),
        allow_download=bool(payload.get("allow_download", False)),
    )


def _first_data_file(paths: list[str]) -> str | None:
    for path in paths:
        if Path(path).suffix.lower() in {".h5ad", ".csv", ".tsv", ".txt"} and "metadata" not in Path(path).name.lower():
            return path
    return paths[0] if paths else None


def _first_metadata_file(paths: list[str]) -> str | None:
    for path in paths:
        name = Path(path).name.lower()
        if "metadata" in name and Path(path).suffix.lower() in {".csv", ".tsv", ".txt"}:
            return path
    return None


def _safe_filename(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in Path(name).name)
    return cleaned or "upload.dat"


def _status_message(status: str) -> str:
    if status == "rejected":
        return "Evidence Copilot rejected this request because it violates RUO or safety boundaries."
    if status == "unsupported_workflow":
        return "Evidence Copilot does not support the explicitly requested workflow."
    if status == "missing_inputs":
        return "Evidence Copilot needs required inputs before running the explicitly requested workflow."
    if status == "needs_clarification":
        return "Evidence Copilot needs one clarification before running a controlled workflow."
    if status == "unsupported_request":
        return "Evidence Copilot does not support this request yet."
    return "Evidence Copilot did not run an audit."


def _requires_download_confirmation(user_request: str) -> bool:
    lowered = user_request.lower()
    if "download" not in lowered:
        return False
    metadata_only_patterns = [
        "do not download",
        "don't download",
        "dont download",
        "no download",
        "without download",
        "without downloading",
        "not download",
        "metadata only",
        "metadata-only",
        "candidate datasets only",
        "candidates only",
    ]
    if any(pattern in lowered for pattern in metadata_only_patterns):
        return False
    return any(term in lowered for term in ["large", "huge", "matrix", "raw", "fastq", "bam", "all files", "automatically"])


def _public_search_compact_mode(user_request: str) -> bool:
    lowered = user_request.lower()
    return any(pattern in lowered for pattern in ["candidate accessions only", "accessions only", "ids only", "compact mode"])


def _progress(callback: Any | None, stage: str) -> None:
    if callback is not None:
        callback(stage)


def _append_execution_log(job_dir: Path, line: str) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    with (job_dir / "execution_log.txt").open("a", encoding="utf-8") as handle:
        handle.write(f"{_utc_now()} {line}\n")


def _ruo() -> str:
    return "Research Use Only. Not for diagnosis, prognosis, treatment selection, or regulated clinical decision-making."


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
