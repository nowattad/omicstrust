import os
from importlib.resources import files as package_files
from pathlib import Path
from typing import Any

from omicstrust.api.auth import AuthConfig
from omicstrust.api.jobs import JobStore
from omicstrust.api.schemas import AuditPathRequest, InspectPathRequest
from omicstrust.api.web_ui import render_dashboard_html
from omicstrust.case_studies.registry import get_case_study, list_case_studies
from omicstrust.cli.inspect import inspect_dataset_cli
from omicstrust.copilot.execution import CopilotJobStore
from omicstrust.copilot.openai_layer import DEFAULT_OPENAI_MODEL
from omicstrust.utils.serialization import read_json


def register_routes(app: Any, *, job_store: JobStore | None = None, private_mode: bool = True, auth: AuthConfig | None = None) -> None:
    try:
        from fastapi import BackgroundTasks, File, Form, HTTPException, Request, UploadFile
        from fastapi.responses import FileResponse, HTMLResponse
    except Exception as exc:  # pragma: no cover - API dependency is optional.
        raise NotImplementedError("The API layer requires fastapi, uvicorn, and python-multipart.") from exc

    store = job_store or JobStore()
    copilot_store = CopilotJobStore(store.root / "copilot")
    auth = auth or AuthConfig()
    pc11_resource_root = Path(str(package_files("omicstrust") / "resources" / "case_studies" / "vanish_pc11"))

    def require_auth(request: Any) -> None:
        if not auth.verify_request(request):
            raise HTTPException(status_code=401, detail="Missing or invalid OmicsTrust API token.")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return render_dashboard_html()

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "omicstrust-api",
            "private_mode": bool(private_mode),
            "auth_required": auth.enabled,
            "results_root": str(store.root),
            "evidence_copilot": {
                "openai_configured": bool(os.environ.get("OPENAI_API_KEY")),
                "default_model": os.environ.get("OMICSTRUST_OPENAI_MODEL") or DEFAULT_OPENAI_MODEL,
                "raw_expression_data_sent": False,
            },
        }

    @app.post("/api/inspect/path")
    def inspect_path(request: InspectPathRequest, http_request: Request):
        require_auth(http_request)
        try:
            return inspect_dataset_cli(request.data_path)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/audits")
    def create_audit(request: AuditPathRequest, http_request: Request, background_tasks: BackgroundTasks):
        require_auth(http_request)
        payload = request.model_dump() if hasattr(request, "model_dump") else request.__dict__.copy()
        try:
            job = store.create_job(
                data_path=payload["data_path"],
                output_dir=payload.get("output_dir"),
                batch_key=payload.get("batch_key") or None,
                donor_key=payload.get("donor_key") or None,
                label_key=payload.get("label_key") or None,
                config_path=payload.get("config_path") or None,
            )
            if payload.get("background"):
                background_tasks.add_task(store.run_job, job["job_id"])
                return job
            return store.run_job(job["job_id"])
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/audits/upload")
    def upload_audit(
        http_request: Request,
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        batch_key: str | None = Form(None),
        donor_key: str | None = Form(None),
        label_key: str | None = Form(None),
        config_path: str | None = Form(None),
        background: bool = Form(False),
    ):
        require_auth(http_request)
        try:
            upload_path = store.save_upload(file.filename or "upload.dat", file.file)
            job = store.create_job(
                data_path=upload_path,
                batch_key=batch_key or None,
                donor_key=donor_key or None,
                label_key=label_key or None,
                config_path=config_path or None,
            )
            if background:
                background_tasks.add_task(store.run_job, job["job_id"])
                return job
            return store.run_job(job["job_id"])
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/jobs")
    def list_jobs(request: Request, limit: int = 50):
        require_auth(request)
        return store.list_jobs(limit=limit)

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str, request: Request):
        require_auth(request)
        try:
            return store.get_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}/summary")
    @app.get("/api/jobs/{job_id}/summary.json")
    def get_summary(job_id: str, request: Request):
        require_auth(request)
        try:
            return store.summary(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}/report.html", response_class=HTMLResponse)
    def get_html_report(job_id: str, request: Request):
        require_auth(request)
        try:
            return store.report_path(job_id, "report.html").read_text(encoding="utf-8")
        except (KeyError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}/reviewer_report.md")
    def get_reviewer_report(job_id: str, request: Request):
        require_auth(request)
        try:
            return FileResponse(store.report_path(job_id, "reviewer_report.md"), media_type="text/markdown")
        except (KeyError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}/report.pdf")
    def get_pdf_report(job_id: str, request: Request):
        require_auth(request)
        try:
            return FileResponse(store.report_path(job_id, "report.pdf"), media_type="application/pdf")
        except (KeyError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}/figures/{filename}")
    def get_report_figure(job_id: str, filename: str, request: Request):
        require_auth(request)
        if Path(filename).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".svg"}:
            raise HTTPException(status_code=404, detail="Unsupported report figure type.")
        try:
            return FileResponse(store.report_path(job_id, f"figures/{filename}"))
        except (KeyError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}/evidence_ledger.json")
    def get_evidence_ledger(job_id: str, request: Request):
        require_auth(request)
        try:
            return read_json(store.report_path(job_id, "evidence_ledger.json"))
        except (KeyError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}/claim_matrix.json")
    def get_claim_matrix(job_id: str, request: Request):
        require_auth(request)
        try:
            return read_json(store.report_path(job_id, "claim_matrix.json"))
        except (KeyError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}/trust_report.json")
    def get_trust_report(job_id: str, request: Request):
        require_auth(request)
        try:
            return read_json(store.report_path(job_id, "trust_report.json"))
        except (KeyError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}/failure_report.json")
    def get_failure_report(job_id: str, request: Request):
        require_auth(request)
        try:
            return read_json(store.report_path(job_id, "failure_report.json"))
        except (KeyError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/case-studies")
    def case_studies(request: Request):
        require_auth(request)
        return list_case_studies()

    @app.get("/api/case-studies/{case_id}")
    def case_study(case_id: str, request: Request):
        require_auth(request)
        try:
            return get_case_study(case_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/case-studies/vanish_vasogate_pc11/report.pdf")
    def pc11_case_study_report(request: Request):
        require_auth(request)
        path = pc11_resource_root / "evidence" / "OmicsTrust_VANISH_PC11_Vasopressin_Response_Axis_Report.pdf"
        if not path.exists():
            raise HTTPException(status_code=404, detail="Preserved PC11 report is not available in this checkout.")
        return FileResponse(path, media_type="application/pdf", filename=path.name)

    @app.get("/api/case-studies/vanish_vasogate_pc11/discovery-summary.json")
    def pc11_case_study_summary(request: Request):
        require_auth(request)
        path = pc11_resource_root / "discovery_summary.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="Preserved PC11 summary is not available in this checkout.")
        return read_json(path)

    @app.post("/api/copilot/jobs")
    async def create_copilot_job(http_request: Request, background_tasks: BackgroundTasks):
        require_auth(http_request)
        try:
            payload, uploads = await _parse_copilot_payload(http_request)
            job = copilot_store.create_job(payload)
            saved_uploads = []
            metadata_path = payload.get("metadata_path") or None
            for field_name, upload in uploads:
                saved = copilot_store.save_upload(job["job_id"], upload.filename or "upload.dat", upload.file)
                saved_uploads.append(str(saved))
                if field_name == "metadata_file":
                    metadata_path = str(saved)
            if saved_uploads:
                payload["uploaded_files"] = saved_uploads
                payload["data_mode"] = "uploaded"
                payload["data_path"] = payload.get("data_path") or saved_uploads[0]
                if metadata_path:
                    payload["metadata_path"] = metadata_path
            copilot_store.set_payload(job["job_id"], payload)
            if payload.get("background"):
                background_tasks.add_task(copilot_store.run_job, job["job_id"])
                return copilot_store.get_job(job["job_id"])
            return copilot_store.run_job(job["job_id"])
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/copilot/jobs/{job_id}")
    def get_copilot_job(job_id: str, request: Request):
        require_auth(request)
        try:
            return copilot_store.get_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/copilot/jobs/{job_id}/result")
    def get_copilot_result(job_id: str, request: Request):
        require_auth(request)
        try:
            return copilot_store.result(job_id)
        except (KeyError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/copilot/jobs/{job_id}/plan")
    def get_copilot_plan(job_id: str, request: Request):
        require_auth(request)
        try:
            return copilot_store.plan(job_id)
        except (KeyError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/copilot/jobs/{job_id}/audit/{filename}")
    def get_copilot_audit_artifact(job_id: str, filename: str, request: Request):
        require_auth(request)
        allowed = {
            "report.html",
            "report.pdf",
            "summary.json",
            "claim_matrix.json",
            "evidence_ledger.json",
            "failure_report.json",
        }
        if filename not in allowed:
            raise HTTPException(status_code=404, detail="Unknown copilot audit artifact.")
        path = copilot_store.job_dir(job_id) / "audit" / filename
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Copilot audit artifact not found: {filename}")
        if filename.endswith(".html"):
            return HTMLResponse(path.read_text(encoding="utf-8"))
        if filename.endswith(".pdf"):
            return FileResponse(path, media_type="application/pdf")
        return read_json(path)

    @app.get("/api/copilot/jobs/{job_id}/audit/figures/{filename}")
    def get_copilot_audit_figure(job_id: str, filename: str, request: Request):
        require_auth(request)
        if Path(filename).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".svg"}:
            raise HTTPException(status_code=404, detail="Unsupported report figure type.")
        try:
            job = copilot_store.get_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        audit_root = Path(job["output_dir"]).resolve() / "audit"
        path = (audit_root / "figures" / filename).resolve()
        try:
            path.relative_to(audit_root)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Invalid Copilot artifact path.") from exc
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"Copilot audit figure not found: {filename}")
        return FileResponse(path)

    @app.get("/runs/{run_id}/summary")
    def legacy_run_summary(run_id: str, request: Request):
        require_auth(request)
        path = Path(run_id)
        try:
            return read_json(path / "summary.json")
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    async def _parse_copilot_payload(http_request: Request):
        content_type = http_request.headers.get("content-type", "")
        if "multipart/form-data" in content_type:
            form = await http_request.form()
            payload = {
                "user_request": str(form.get("user_request") or form.get("prompt") or "").strip(),
                "workflow": _form_optional(form.get("workflow")),
                "data_mode": str(form.get("data_mode") or "uploaded"),
                "data_path": _form_optional(form.get("data_path")),
                "metadata_path": _form_optional(form.get("metadata_path")),
                "config_path": _form_optional(form.get("config_path")),
                "batch_key": _form_optional(form.get("batch_key")),
                "donor_key": _form_optional(form.get("donor_key")),
                "label_key": _form_optional(form.get("label_key")),
                "treatment_key": _form_optional(form.get("treatment_key")),
                "outcome_key": _form_optional(form.get("outcome_key")),
                "patient_id_key": _form_optional(form.get("patient_id_key") or form.get("patient_key")),
                "covariate_keys": _form_optional(form.get("covariate_keys")),
                "known_endotype_key": _form_optional(form.get("known_endotype_key")),
                "dataset_adapter": _form_optional(form.get("dataset_adapter") or form.get("adapter")),
                "n_top_variable_features": _form_optional(form.get("n_top_variable_features")),
                "n_axes": _form_optional(form.get("n_axes")),
                "n_pcs": _form_optional(form.get("n_pcs")),
                "model_family": _form_optional(form.get("model_family")),
                "permutation_n": _form_optional(form.get("permutation_n") or form.get("n_permutations")),
                "bootstrap_n": _form_optional(form.get("bootstrap_n") or form.get("n_bootstraps")),
                "use_ai": (
                    str(form.get("use_ai") or "").lower() in {"1", "true", "yes", "on"}
                    if "use_ai" in form
                    else None
                ),
                "ai_model": _form_optional(form.get("ai_model")),
                "locked_axis_path": _form_optional(form.get("locked_axis_path")),
                "public_dataset_search": str(form.get("public_dataset_search") or "").lower() in {"1", "true", "yes", "on"},
                "background": str(form.get("background") or "").lower() in {"1", "true", "yes", "on"},
            }
            uploads = []
            for field_name in ["file", "data_file", "metadata_file"]:
                item = form.get(field_name)
                if getattr(item, "filename", None) and getattr(item, "file", None):
                    uploads.append((field_name, item))
            return payload, uploads
        payload = await http_request.json()
        if not isinstance(payload, dict):
            raise ValueError("Copilot request body must be a JSON object or multipart form.")
        payload.setdefault("background", False)
        return payload, []

    def _form_optional(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
