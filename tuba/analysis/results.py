"""Persistent solver result-state records."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from tuba.solver.base import ElementResult, FEAResults, NodeResult
from tuba.analysis.study import AnalysisStudy


@dataclass(frozen=True)
class ResultState:
    id: str
    study_id: str
    model_revision: int
    solver_name: str
    load_case: str
    mesh_id: str | None
    node_displacements: dict[str, tuple[float, float, float, float, float, float]]
    node_reactions: dict[str, tuple[float, float, float, float, float, float]]
    element_results: dict[str, dict[str, Any]]
    files: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_nonempty(self.id, "ResultState id")
        _require_nonempty(self.study_id, "ResultState study_id")
        _require_nonempty(self.solver_name, "ResultState solver_name")
        _require_nonempty(self.load_case, "ResultState load_case")
        if self.model_revision < 0:
            raise ValueError("ResultState model_revision must be non-negative.")
        object.__setattr__(
            self,
            "node_displacements",
            {key: _float_tuple(value, 6, f"ResultState displacement {key}") for key, value in self.node_displacements.items()},
        )
        object.__setattr__(
            self,
            "node_reactions",
            {key: _float_tuple(value, 6, f"ResultState reaction {key}") for key, value in self.node_reactions.items()},
        )
        object.__setattr__(self, "element_results", {key: dict(value) for key, value in self.element_results.items()})
        object.__setattr__(self, "files", dict(self.files))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "study_id": self.study_id,
            "model_revision": self.model_revision,
            "solver_name": self.solver_name,
            "load_case": self.load_case,
            "mesh_id": self.mesh_id,
            "node_displacements": {key: list(value) for key, value in self.node_displacements.items()},
            "node_reactions": {key: list(value) for key, value in self.node_reactions.items()},
            "element_results": {key: dict(value) for key, value in self.element_results.items()},
            "files": dict(self.files),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResultState":
        return cls(
            id=data["id"],
            study_id=data["study_id"],
            model_revision=data["model_revision"],
            solver_name=data["solver_name"],
            load_case=data["load_case"],
            mesh_id=data.get("mesh_id"),
            node_displacements={key: tuple(value) for key, value in data.get("node_displacements", {}).items()},
            node_reactions={key: tuple(value) for key, value in data.get("node_reactions", {}).items()},
            element_results={key: dict(value) for key, value in data.get("element_results", {}).items()},
            files=dict(data.get("files", {})),
            metadata=dict(data.get("metadata", {})),
        )


def result_state_from_fea_results(*, model: Any, study: AnalysisStudy, results: FEAResults) -> ResultState:
    """Create a persistent result state from in-memory solver results."""
    model_revision = _model_revision(model)
    if model_revision != study.model_revision:
        raise ValueError(
            f"Cannot create ResultState for model revision {model_revision}; study uses revision {study.model_revision}."
        )

    node_displacements: dict[str, tuple[float, float, float, float, float, float]] = {}
    node_reactions: dict[str, tuple[float, float, float, float, float, float]] = {}
    for node_id, node_result in results.node_results.items():
        node_displacements[node_id] = _result_vector(node_result.displacement, f"displacement {node_id}")
        if node_result.reaction_force is not None:
            node_reactions[node_id] = _result_vector(node_result.reaction_force, f"reaction {node_id}")
    for node_id, node_result in results.analysis_node_results.items():
        node_displacements[node_id] = _result_vector(node_result.displacement, f"analysis displacement {node_id}")

    element_results: dict[str, dict[str, Any]] = {}
    for element_id, element_result in results.element_results.items():
        element_results[element_id] = {
            "forces_n1": list(_result_vector(element_result.forces_n1, f"forces_n1 {element_id}")),
            "forces_n2": list(_result_vector(element_result.forces_n2, f"forces_n2 {element_id}")),
            "von_mises_n1": float(element_result.von_mises_n1),
            "von_mises_n2": float(element_result.von_mises_n2),
            "max_von_mises": float(element_result.max_von_mises),
        }

    files: dict[str, str] = {}
    if results.result_file is not None:
        files["result"] = str(results.result_file)

    metadata: dict[str, Any] = {}
    if results.analysis_node_results:
        metadata["analysis_node_ids"] = sorted(results.analysis_node_results)
    if results.parser_diagnostics:
        metadata["parser_diagnostics"] = list(results.parser_diagnostics)
    if results.tuyau_subpoints:
        metadata["tuyau_subpoints"] = [dict(row) for row in results.tuyau_subpoints]

    return ResultState(
        id=f"result_state:{study.load_case}",
        study_id=study.id,
        model_revision=model_revision,
        solver_name=results.solver_name,
        load_case=results.load_case or study.load_case,
        mesh_id=study.mesh_id,
        node_displacements=node_displacements,
        node_reactions=node_reactions,
        element_results=element_results,
        files=files,
        metadata=metadata,
    )


def fea_results_from_result_state(*, model: Any, result_state: ResultState) -> FEAResults:
    """Reconstruct an in-memory ``FEAResults`` object from a persistent state."""
    model_revision = _model_revision(model)
    if model_revision != result_state.model_revision:
        raise ValueError(
            f"Cannot apply ResultState revision {result_state.model_revision} to model revision {model_revision}."
        )

    results = FEAResults(solver_name=result_state.solver_name, load_case=result_state.load_case)
    results._model = model
    if "result" in result_state.files:
        results.result_file = Path(result_state.files["result"])
    results.parser_diagnostics.extend(result_state.metadata.get("parser_diagnostics", []))
    results.tuyau_subpoints.extend(dict(row) for row in result_state.metadata.get("tuyau_subpoints", []))

    for node_id in getattr(model, "nodes", {}):
        displacement = np.asarray(result_state.node_displacements.get(node_id, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)), dtype=float)
        reaction = result_state.node_reactions.get(node_id)
        results.node_results[node_id] = NodeResult(
            node_id=node_id,
            displacement=displacement,
            reaction_force=np.asarray(reaction, dtype=float) if reaction is not None else None,
        )

    for node_id, displacement in result_state.node_displacements.items():
        if node_id in results.node_results:
            continue
        results.analysis_node_results[node_id] = NodeResult(
            node_id=node_id,
            displacement=np.asarray(displacement, dtype=float),
        )

    for element in getattr(model, "elements", []):
        data = result_state.element_results.get(element.id, {})
        results.element_results[element.id] = ElementResult(
            element_id=element.id,
            forces_n1=np.asarray(data.get("forces_n1", (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)), dtype=float),
            forces_n2=np.asarray(data.get("forces_n2", (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)), dtype=float),
            von_mises_n1=float(data.get("von_mises_n1", 0.0)),
            von_mises_n2=float(data.get("von_mises_n2", 0.0)),
            max_von_mises=float(data.get("max_von_mises", 0.0)),
        )
    return results


def _float_tuple(values: Any, length: int, label: str) -> tuple[float, ...]:
    data = tuple(float(value) for value in values)
    if len(data) != length:
        raise ValueError(f"{label} must have {length} values.")
    return data


def _require_nonempty(value: str, label: str) -> None:
    if not value:
        raise ValueError(f"{label} must not be empty.")


def _model_revision(model: Any) -> int:
    return int(getattr(model, "revision", 0))


def _result_vector(values: Any, label: str) -> tuple[float, float, float, float, float, float]:
    return _float_tuple(values, 6, label)
