"""Renderer-independent records for engineering review packages."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Any


class EngineeringReviewError(ValueError):
    """Raised when an engineering review package violates its contract."""


_PORTABLE_TABLE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_WINDOWS_RESERVED_FILENAMES = {
    "aux",
    "clock$",
    "con",
    "nul",
    "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


def _validate_report_table_id(table_id: str) -> None:
    if (
        not _PORTABLE_TABLE_ID.fullmatch(table_id)
        or table_id in _WINDOWS_RESERVED_FILENAMES
    ):
        raise EngineeringReviewError(
            f"Report table id {table_id!r} must be a portable lowercase "
            "filename-safe identifier using only a-z, 0-9, '_' or '-', and "
            "must not be a reserved Windows filename."
        )


def _json_value(value: Any) -> Any:
    """Return a deterministic value composed only of JSON-native types."""
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise EngineeringReviewError("Report data mapping keys must be strings.")
        return {key: _json_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, float) and not isfinite(value):
        raise EngineeringReviewError(
            f"Report data contains a non-finite JSON number {value!r}."
        )
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise EngineeringReviewError(
        f"Report data contains a non-JSON value of type {type(value).__name__!r}."
    )


@dataclass(frozen=True)
class ReportColumn:
    id: str
    label: str
    unit: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            **({"unit": self.unit} if self.unit else {}),
            **({"description": self.description} if self.description else {}),
        }


@dataclass(frozen=True)
class ReviewDiagnostic:
    severity: str
    code: str
    source: str
    message: str
    target: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "source": self.source,
            "message": self.message,
            **({"target": self.target} if self.target else {}),
        }


@dataclass(frozen=True)
class ReviewProvenance:
    kind: str
    id: str
    solver_name: str | None = None
    load_case: str | None = None
    files: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            **({"solver_name": self.solver_name} if self.solver_name else {}),
            **({"load_case": self.load_case} if self.load_case else {}),
            "files": _json_value(dict(self.files)),
            "metadata": _json_value(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ReportTable:
    id: str
    title: str
    columns: tuple[ReportColumn, ...]
    rows: tuple[Mapping[str, Any], ...]
    source: str
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        _validate_report_table_id(self.id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "columns": [column.to_dict() for column in self.columns],
            "rows": [_json_value(dict(row)) for row in self.rows],
            **(
                {"unavailable_reason": self.unavailable_reason}
                if self.unavailable_reason
                else {}
            ),
        }


@dataclass(frozen=True)
class EngineeringReviewPackage:
    package_id: str
    created_at: str
    project_name: str
    model_standard: str
    model_revision: int
    analysis_status: str
    tables: tuple[ReportTable, ...]
    schema_version: str = "engineering_review.v1"
    units: Mapping[str, str] = field(
        default_factory=lambda: {"length": "m", "force": "N", "stress": "Pa"}
    )
    coordinate_system: Mapping[str, Any] = field(
        default_factory=lambda: {"up_axis": "Z"}
    )
    provenance: tuple[ReviewProvenance, ...] = ()
    diagnostics: tuple[ReviewDiagnostic, ...] = ()
    scene_uri: str | None = None

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for table in self.tables:
            if table.id in seen:
                raise EngineeringReviewError(f"Duplicate report table {table.id!r}.")
            seen.add(table.id)

    def table(self, table_id: str) -> ReportTable:
        try:
            return self.tables_by_id[table_id]
        except KeyError as error:
            raise EngineeringReviewError(f"Unknown report table {table_id!r}.") from error

    @property
    def tables_by_id(self) -> dict[str, ReportTable]:
        return {table.id: table for table in self.tables}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "package_id": self.package_id,
            "created_at": self.created_at,
            "project_name": self.project_name,
            "model_standard": self.model_standard,
            "model_revision": self.model_revision,
            "analysis_status": self.analysis_status,
            "units": _json_value(dict(self.units)),
            "coordinate_system": _json_value(dict(self.coordinate_system)),
            "provenance": [record.to_dict() for record in self.provenance],
            "tables": {table.id: table.to_dict() for table in self.tables},
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
            **({"scene_uri": self.scene_uri} if self.scene_uri else {}),
        }
