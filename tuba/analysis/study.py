"""Traceable solver study records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AnalysisStudy:
    id: str
    model_revision: int
    solver_name: str
    load_case: str
    work_dir: str | None
    input_files: dict[str, str]
    mesh_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_nonempty(self.id, "AnalysisStudy id")
        _require_nonempty(self.solver_name, "AnalysisStudy solver_name")
        _require_nonempty(self.load_case, "AnalysisStudy load_case")
        _require_nonempty(self.mesh_id, "AnalysisStudy mesh_id")
        if self.model_revision < 0:
            raise ValueError("AnalysisStudy model_revision must be non-negative.")
        object.__setattr__(self, "input_files", dict(self.input_files))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "model_revision": self.model_revision,
            "solver_name": self.solver_name,
            "load_case": self.load_case,
            "input_files": dict(self.input_files),
            "mesh_id": self.mesh_id,
        }
        if self.work_dir is not None:
            data["work_dir"] = self.work_dir
        if self.metadata:
            data["metadata"] = dict(self.metadata)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnalysisStudy":
        return cls(
            id=data["id"],
            model_revision=data["model_revision"],
            solver_name=data["solver_name"],
            load_case=data["load_case"],
            work_dir=data.get("work_dir"),
            input_files=dict(data.get("input_files", {})),
            mesh_id=data["mesh_id"],
            metadata=dict(data.get("metadata", {})),
        )


def _require_nonempty(value: str, label: str) -> None:
    if not value:
        raise ValueError(f"{label} must not be empty.")
