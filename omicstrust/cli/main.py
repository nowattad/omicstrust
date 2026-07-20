from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from omicstrust.audit import run_audit
from omicstrust.benchmarks.comparative import run_real_dataset_benchmark
from omicstrust.benchmarks.benchmark_runner import run_synthetic_benchmark
from omicstrust.case_studies.registry import list_case_studies, write_case_study_docs, write_case_study_json
from omicstrust.cli.compare import compare_runs
from omicstrust.cli.inspect import inspect_dataset_cli
from omicstrust.cli.report import regenerate_report
from omicstrust.cli.validate import validate_dataset_cli
from omicstrust.copilot.execution import run_copilot_job
from omicstrust.datasets.discovery import discover_datasets, write_discovery_outputs
from omicstrust.suite.runner import run_audit_suite
from omicstrust.tracking.sqlite_registry import list_registered_runs, register_run
from omicstrust.workflows.doctor import run_doctor
from omicstrust.workflows.locked_validation import lock_axis_from_run, validate_locked_axis
from omicstrust.workflows.pc11_external_validation import run_pc11_external_validation_plan
from omicstrust.workflows.pc11_validation_runner import run_pc11_validation
from omicstrust.workflows.reproduce import check_reproducibility

app = typer.Typer(help="OmicsTrust scientific trust audits for omics data.")
console = Console()


@app.command()
def audit(
    data: Path,
    batch_key: str | None = typer.Option(None, "--batch-key"),
    donor_key: str | None = typer.Option(None, "--donor-key"),
    label_key: str | None = typer.Option(None, "--label-key"),
    output: Path = typer.Option(Path("results/study_001"), "--output", "-o"),
    config: Path | None = typer.Option(None, "--config"),
):
    """Run a CellAudit trust audit."""

    result = _run_or_exit(
        lambda: run_audit(
            data,
            batch_key=batch_key,
            donor_key=donor_key,
            label_key=label_key,
            output=output,
            config_path=config,
        )
    )
    summary = result["summary"]
    console.print("OmicsTrust Audit Summary")
    for key in ["data_qc", "structural_signal", "empirical_null", "batch_risk", "stability", "trust_level", "safe_to_interpret"]:
        console.print(f"{key.replace('_', ' ').title()}: {summary.get(key)}")
    console.print(f"Output: {output}")


@app.command()
def benchmark(
    config: Path | None = typer.Option(None, "--config"),
    output: Path = typer.Option(Path("results/benchmark_001"), "--output", "-o"),
):
    """Run the synthetic benchmark suite."""

    _run_or_exit(lambda: run_synthetic_benchmark(output=output, config_path=config))
    console.print(f"Benchmark outputs written to {output}")


@app.command("benchmark-real")
def benchmark_real(
    data: Path,
    output: Path = typer.Option(Path("results/real_benchmark_001"), "--output", "-o"),
    config: Path | None = typer.Option(None, "--config"),
    batch_key: str | None = typer.Option(None, "--batch-key"),
    donor_key: str | None = typer.Option(None, "--donor-key"),
    label_key: str | None = typer.Option(None, "--label-key"),
):
    """Run a real-dataset comparative benchmark around the OmicsTrust audit."""

    report = _run_or_exit(
        lambda: run_real_dataset_benchmark(
            data,
            output=output,
            batch_key=batch_key,
            donor_key=donor_key,
            label_key=label_key,
            config_path=config,
        )
    )
    console.print(report)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
    results_root: Path = typer.Option(Path("results/platform"), "--results-root"),
    api_token: str | None = typer.Option(None, "--api-token", envvar="OMICSTRUST_API_TOKEN", help="Optional API token for private deployments."),
    public: bool = typer.Option(False, "--public", help="Bind for a non-private deployment; use carefully."),
):
    """Start the local private OmicsTrust Web/API console."""

    def _serve():
        try:
            import uvicorn
        except Exception as exc:
            raise NotImplementedError("Serving the web UI requires uvicorn and fastapi. Install with .[api].") from exc
        from omicstrust.api.server import create_app

        app_obj = create_app(results_root=results_root, private_mode=not public, api_token=api_token)
        uvicorn.run(app_obj, host=host, port=int(port))

    _run_or_exit(_serve)


@app.command("copilot")
def copilot(
    user_request: str = typer.Argument(..., help="Research-use-only omics question in natural language."),
    data: Path | None = typer.Option(None, "--data", help="Optional local .h5ad, .csv, .tsv, or .txt input."),
    workflow: str | None = typer.Option(None, "--workflow", help="Optional exact workflow ID."),
    output: Path = typer.Option(Path("results/copilot_cli"), "--output", "-o"),
    batch_key: str | None = typer.Option(None, "--batch-key"),
    donor_key: str | None = typer.Option(None, "--donor-key"),
    label_key: str | None = typer.Option(None, "--label-key"),
    treatment_key: str | None = typer.Option(None, "--treatment-key"),
    outcome_key: str | None = typer.Option(None, "--outcome-key"),
    use_ai: bool = typer.Option(True, "--ai/--no-ai", help="Use GPT-5.6 when OPENAI_API_KEY is configured."),
    ai_model: str = typer.Option("gpt-5.6", "--ai-model"),
):
    """Run the optional GPT-5.6 Evidence Copilot over the deterministic engine."""

    payload = {
        "user_request": user_request,
        "workflow": workflow,
        "data_mode": "local_path" if data else "no_data",
        "data_path": str(data) if data else None,
        "batch_key": batch_key,
        "donor_key": donor_key,
        "label_key": label_key,
        "treatment_key": treatment_key,
        "outcome_key": outcome_key,
        "use_ai": use_ai,
        "ai_model": ai_model,
    }
    result = _run_or_exit(lambda: run_copilot_job(output, payload))
    ai = result.get("ai_copilot", {})
    console.print("OmicsTrust Evidence Copilot")
    console.print(f"Status: {result.get('status')}")
    console.print(f"Workflow: {result.get('selected_workflow')}")
    console.print(f"GPT Planning: {ai.get('planning', {}).get('status')}")
    console.print(f"GPT Interpretation: {ai.get('interpretation', {}).get('status')}")
    console.print(f"Answer: {result.get('short_answer')}")
    console.print(f"Output: {output}")


@app.command("case-studies")
def case_studies(
    output: Path | None = typer.Option(None, "--output", "-o", help="Optional directory for case_studies.md."),
):
    """List packaged RUO case studies."""

    studies = list_case_studies()
    if output:
        path = write_case_study_docs(output)
        json_path = write_case_study_json(output)
        console.print(f"Case study docs written to {path}")
        console.print(f"Case study JSON written to {json_path}")
    console.print(studies)


@app.command("lock-axis")
def lock_axis(
    run_dir: Path,
    output: Path = typer.Option(Path("results/locked_axis"), "--output", "-o"),
    axis_name: str = typer.Option("locked_axis", "--axis-name"),
    component: int = typer.Option(1, "--component"),
    hypothesis: str = typer.Option("", "--hypothesis"),
):
    """Create a locked RUO validation contract from an audited component."""

    report = _run_or_exit(
        lambda: lock_axis_from_run(
            run_dir,
            output=output,
            axis_name=axis_name,
            component=component,
            hypothesis=hypothesis,
        )
    )
    console.print(report)


@app.command("validate-axis")
def validate_axis(
    locked_axis: Path,
    data: Path,
    output: Path = typer.Option(Path("results/locked_validation"), "--output", "-o"),
    config: Path | None = typer.Option(None, "--config"),
    batch_key: str | None = typer.Option(None, "--batch-key"),
    donor_key: str | None = typer.Option(None, "--donor-key"),
    label_key: str | None = typer.Option(None, "--label-key"),
):
    """Validate a prespecified locked axis on a new dataset."""

    report = _run_or_exit(
        lambda: validate_locked_axis(
            locked_axis,
            data,
            output=output,
            batch_key=batch_key,
            donor_key=donor_key,
            label_key=label_key,
            config_path=config,
        )
    )
    console.print(report)


@app.command("pc11-run-validation")
def pc11_run_validation(
    contract: Path = typer.Option(..., "--contract", help="PC11 locked axis contract JSON."),
    expression: Path = typer.Option(..., "--expression", help="Sample-by-gene expression CSV."),
    metadata: Path = typer.Option(..., "--metadata", help="Sample metadata CSV."),
    output: Path = typer.Option(Path("results/pc11_validation_run"), "--output", "-o"),
    cohort_id: str = typer.Option("external_cohort", "--cohort-id"),
    sample_id_column: str = typer.Option("sample_id", "--sample-id-column"),
    outcome_column: str | None = typer.Option(None, "--outcome-column"),
    treatment_column: str | None = typer.Option(None, "--treatment-column"),
    treatment_active_value: str = typer.Option("vasopressin", "--treatment-active-value"),
    treatment_reference_value: str = typer.Option("norepinephrine", "--treatment-reference-value"),
    endotype_cohort_column: str = typer.Option("endotype_cohort", "--endotype-cohort-column"),
    endotype_class_column: str = typer.Option("endotype_class", "--endotype-class-column"),
):
    """Run locked PC11 validation on a harmonized external cohort."""

    report = _run_or_exit(
        lambda: run_pc11_validation(
            contract,
            expression,
            metadata,
            output=output,
            cohort_id=cohort_id,
            sample_id_column=sample_id_column,
            outcome_column=outcome_column,
            treatment_column=treatment_column,
            treatment_active_value=treatment_active_value,
            treatment_reference_value=treatment_reference_value,
            endotype_cohort_column=endotype_cohort_column,
            endotype_class_column=endotype_class_column,
        )
    )
    console.print("PC11 Locked Validation Run")
    console.print(f"Cohort: {report.get('cohort_id')}")
    console.print(f"Matched Samples: {report.get('n_matched_samples')}")
    console.print(f"PC11 Score Computable: {report.get('verdict', {}).get('pc11_score_computable')}")
    console.print(f"Treatment Guidance Allowed: {report.get('verdict', {}).get('treatment_guidance_allowed')}")
    console.print(f"Clinical Use Allowed: {report.get('verdict', {}).get('clinical_use_allowed')}")
    console.print(f"External Biology/Endotype: {report.get('validation_conclusion', {}).get('external_biology_endotype_structure')}")
    console.print(f"Mortality Association: {report.get('validation_conclusion', {}).get('mortality_association')}")
    console.print(f"Treatment Response Replication: {report.get('validation_conclusion', {}).get('vasopressin_response_replication')}")
    console.print(f"Output: {output}")


@app.command("pc11-validate-plan")
def pc11_validate_plan(
    report_input: Path = typer.Argument(..., help="PC11 discovery summary, locked contract, or validation package."),
    output: Path = typer.Option(Path("results/pc11_external_validation_package"), "--output", "-o"),
):
    """Generate the PC11/VasoGate external validation package."""

    report = _run_or_exit(
        lambda: run_pc11_external_validation_plan(
            report_input,
            output=output,
        )
    )
    console.print("PC11 / VasoGate External Validation Package")
    console.print(f"Axis: {report.get('axis_name')}")
    console.print(f"Cohorts: {report.get('cohort_count')}")
    console.print(f"Queries: {report.get('query_count')}")
    console.print(f"PC11 External Validation Status: {report.get('verdict', {}).get('pc11_external_validation_status')}")
    console.print(f"Treatment Guidance Allowed: {report.get('verdict', {}).get('treatment_guidance_allowed')}")
    console.print(f"Clinical Use Allowed: {report.get('verdict', {}).get('clinical_use_allowed')}")
    console.print(f"Output: {output}")


@app.command()
def discover(
    root: list[Path] | None = typer.Option(None, "--root", "-r", help="Directory or file to scan. Can be repeated."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Optional directory for discovery JSON/CSV."),
    no_inspect: bool = typer.Option(False, "--no-inspect", help="Only find files; do not open them."),
    max_files: int | None = typer.Option(None, "--max-files"),
):
    """Discover supported omics input files and inspect metadata columns."""

    roots = root or [Path("~/Desktop"), Path("~/Downloads"), Path("~/Documents")]
    records = _run_or_exit(lambda: discover_datasets(roots, inspect=not no_inspect, max_files=max_files))
    if output:
        _run_or_exit(lambda: write_discovery_outputs(records, output))
        console.print(f"Discovery outputs written to {output}")
    console.print([record.to_dict() for record in records])


@app.command()
def doctor(
    data: list[Path] | None = typer.Option(None, "--data", help="Optional dataset path to verify. Can be repeated."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Optional output directory for doctor_report.json."),
):
    """Check environment, writable paths, dependencies, and optional datasets."""

    console.print(_run_or_exit(lambda: run_doctor(data_paths=data or [], output=output)))


@app.command()
def suite(
    inputs: list[Path] = typer.Argument(..., help="One or more input datasets."),
    output: Path = typer.Option(Path("results/audit_suite"), "--output", "-o"),
    config: Path | None = typer.Option(None, "--config"),
    batch_key: str | None = typer.Option(None, "--batch-key"),
    donor_key: str | None = typer.Option(None, "--donor-key"),
    label_key: str | None = typer.Option(None, "--label-key"),
    no_infer_keys: bool = typer.Option(False, "--no-infer-keys"),
    stop_on_error: bool = typer.Option(False, "--stop-on-error"),
):
    """Run CellAudit over multiple datasets and write a suite-level report."""

    report = _run_or_exit(
        lambda: run_audit_suite(
            inputs,
            output=output,
            config_path=config,
            batch_key=batch_key,
            donor_key=donor_key,
            label_key=label_key,
            infer_keys=not no_infer_keys,
            continue_on_error=not stop_on_error,
        )
    )
    console.print(report)


@app.command()
def register(
    run_dir: Path,
    db: Path = typer.Option(Path("results/omicstrust_registry.sqlite"), "--db"),
):
    """Register an audit run in the local SQLite registry."""

    console.print(_run_or_exit(lambda: register_run(run_dir, db_path=db)))


@app.command("runs")
def runs_command(
    db: Path = typer.Option(Path("results/omicstrust_registry.sqlite"), "--db"),
    limit: int = typer.Option(50, "--limit"),
):
    """List registered audit runs."""

    console.print(_run_or_exit(lambda: list_registered_runs(db_path=db, limit=limit)))


@app.command()
def compare(run_a: Path, run_b: Path):
    """Compare two OmicsTrust run directories."""

    console.print(_run_or_exit(lambda: compare_runs(run_a, run_b)))


@app.command()
def reproduce(run_dir: Path):
    """Check whether a run can be reproduced from recorded provenance."""

    report = _run_or_exit(lambda: check_reproducibility(run_dir))
    console.print(report)


@app.command()
def validate(
    data: Path,
    batch_key: str | None = typer.Option(None, "--batch-key"),
    donor_key: str | None = typer.Option(None, "--donor-key"),
    label_key: str | None = typer.Option(None, "--label-key"),
    config: Path | None = typer.Option(None, "--config"),
):
    """Validate input shape and metadata availability."""

    console.print(_run_or_exit(lambda: validate_dataset_cli(data, batch_key=batch_key, donor_key=donor_key, label_key=label_key, config_path=config)))


@app.command("inspect")
def inspect_command(data: Path):
    """Inspect input shape and metadata columns."""

    console.print(_run_or_exit(lambda: inspect_dataset_cli(data)))


@app.command()
def report(run_dir: Path):
    """Regenerate report.html and reviewer_report.md from JSON outputs."""

    _run_or_exit(lambda: regenerate_report(run_dir))
    console.print(f"Reports regenerated in {run_dir}")


def _run_or_exit(fn):
    try:
        return fn()
    except (
        FileNotFoundError,
        ValueError,
        KeyError,
        ImportError,
        NotImplementedError,
        MemoryError,
    ) as exc:
        console.print(f"[bold red]OmicsTrust error:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
