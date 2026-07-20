from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from omicstrust.cli.inspect import inspect_dataset_cli
from omicstrust.utils.serialization import write_json


@dataclass
class DatasetRecord:
    path: str
    suffix: str
    size_bytes: int | None
    status: str
    shape: list[int] | None
    obs_columns: list[str]
    suggested_keys: dict[str, str | None]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def discover_datasets(
    roots: Iterable[str | Path],
    *,
    suffixes: tuple[str, ...] = (".h5ad", ".csv", ".tsv", ".txt"),
    inspect: bool = True,
    max_files: int | None = None,
) -> list[DatasetRecord]:
    records: list[DatasetRecord] = []
    for root in roots:
        root_path = Path(root).expanduser()
        if root_path.is_file():
            candidates = [root_path]
        elif root_path.exists():
            candidates = [p for p in root_path.rglob("*") if p.is_file() and p.suffix.lower() in suffixes]
        else:
            records.append(
                DatasetRecord(
                    path=str(root_path),
                    suffix=root_path.suffix.lower(),
                    size_bytes=None,
                    status="missing_root",
                    shape=None,
                    obs_columns=[],
                    suggested_keys={},
                    error="Search root does not exist.",
                )
            )
            continue
        for candidate in sorted(candidates):
            if candidate.suffix.lower() not in suffixes:
                continue
            records.append(inspect_dataset_record(candidate) if inspect else _basic_record(candidate))
            if max_files is not None and len(records) >= max_files:
                return records
    return records


def inspect_dataset_record(path: str | Path) -> DatasetRecord:
    path = Path(path).expanduser()
    try:
        info = inspect_dataset_cli(path)
        return DatasetRecord(
            path=str(path),
            suffix=path.suffix.lower(),
            size_bytes=path.stat().st_size if path.exists() else None,
            status="ok",
            shape=info.get("shape"),
            obs_columns=list(info.get("obs_columns", [])),
            suggested_keys=dict(info.get("suggested_keys", {})),
            error=None,
        )
    except Exception as exc:
        return DatasetRecord(
            path=str(path),
            suffix=path.suffix.lower(),
            size_bytes=path.stat().st_size if path.exists() else None,
            status="error",
            shape=None,
            obs_columns=[],
            suggested_keys={},
            error=str(exc),
        )


def write_discovery_outputs(records: list[DatasetRecord], output: str | Path) -> None:
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    rows = [record.to_dict() for record in records]
    pd.DataFrame(rows).to_csv(output_path / "dataset_discovery.csv", index=False)
    write_json(output_path / "dataset_discovery.json", rows)


def _basic_record(path: Path) -> DatasetRecord:
    return DatasetRecord(
        path=str(path),
        suffix=path.suffix.lower(),
        size_bytes=path.stat().st_size,
        status="found",
        shape=None,
        obs_columns=[],
        suggested_keys={},
        error=None,
    )
