"""Persistent solver result-state records."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from tuba.solver.base import ElementResult, FEAResults, NodeResult
from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.study import AnalysisStudy
from tuba.analysis.provenance import (
    CODE_ASTER_COMPILER_ID,
    MIXED_CODE_ASTER_COMPILER_ID,
    VOLUME_CODE_ASTER_COMPILER_ID,
    SolverInputIdentity,
    require_matching_solver_input_identities,
    validate_solver_input_identity,
)


@dataclass(frozen=True)
class ResultState:
    id: str
    study_id: str
    model_revision: int
    solver_name: str
    load_case: str
    mesh_id: str | None
    node_displacements: dict[
        str,
        tuple[float | None, float | None, float | None, float | None, float | None, float | None],
    ]
    node_reactions: dict[str, tuple[float | None, float | None, float | None, float | None, float | None, float | None]]
    element_results: dict[str, dict[str, Any]]
    files: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    solver_input_identity: SolverInputIdentity | None = None

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
            {
                key: _optional_float_tuple(value, 6, f"ResultState displacement {key}")
                for key, value in self.node_displacements.items()
            },
        )
        object.__setattr__(
            self,
            "node_reactions",
            {
                key: _optional_float_tuple(value, 6, f"ResultState reaction {key}")
                for key, value in self.node_reactions.items()
            },
        )
        object.__setattr__(self, "element_results", {key: dict(value) for key, value in self.element_results.items()})
        object.__setattr__(self, "files", dict(self.files))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        data = {
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
        if self.solver_input_identity is not None:
            data["solver_input_identity"] = self.solver_input_identity.to_dict()
        return data

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
            solver_input_identity=(
                SolverInputIdentity.from_dict(data["solver_input_identity"])
                if data.get("solver_input_identity") is not None
                else None
            ),
        )


def result_state_from_fea_results(
    *,
    model: Any,
    study: AnalysisStudy,
    results: FEAResults,
    analysis_mesh: AnalysisMesh | None = None,
) -> ResultState:
    """Create a persistent result state from in-memory solver results."""
    model_revision = _model_revision(model)
    if model_revision != study.model_revision:
        raise ValueError(
            f"Cannot create ResultState for model revision {model_revision}; study uses revision {study.model_revision}."
        )
    if study.metadata.get("mixed_analysis"):
        compiler_id = MIXED_CODE_ASTER_COMPILER_ID
    elif study.metadata.get("volume_analysis"):
        compiler_id = VOLUME_CODE_ASTER_COMPILER_ID
    else:
        compiler_id = CODE_ASTER_COMPILER_ID
    compiler_inputs = study.metadata.get("compiler_inputs")
    validate_solver_input_identity(
        model,
        study.solver_input_identity,
        context=f"Study {study.id!r}",
        expected_load_case=study.load_case,
        expected_compiler_id=compiler_id,
        compiler_inputs=compiler_inputs,
    )
    if analysis_mesh is not None:
        validate_solver_input_identity(
            model,
            analysis_mesh.solver_input_identity,
            context=f"Analysis mesh {analysis_mesh.id!r}",
            expected_load_case=study.load_case,
            expected_compiler_id=compiler_id,
            compiler_inputs=compiler_inputs,
        )
        require_matching_solver_input_identities(
            study.solver_input_identity,
            analysis_mesh.solver_input_identity,
            context=f"Study {study.id!r} and analysis mesh {analysis_mesh.id!r}",
        )
    analysis_node_ids = _validated_analysis_node_ids(
        model=model,
        study=study,
        results=results,
        analysis_mesh=analysis_mesh,
    )

    node_displacements: dict[str, tuple[float | None, ...]] = {}
    node_reactions: dict[str, tuple[float | None, ...]] = {}
    for node_id, node_result in results.node_results.items():
        node_displacements[node_id] = tuple(
            _persistent_result_vector(node_result.displacement, f"displacement {node_id}")
        )
        if node_result.reaction_force is not None:
            node_reactions[node_id] = tuple(
                _persistent_result_vector(node_result.reaction_force, f"reaction {node_id}")
            )
    for node_id, node_result in results.analysis_node_results.items():
        node_displacements[node_id] = tuple(
            _persistent_result_vector(node_result.displacement, f"analysis displacement {node_id}")
        )
        if node_result.reaction_force is not None:
            node_reactions[node_id] = tuple(
                _persistent_result_vector(node_result.reaction_force, f"analysis reaction {node_id}")
            )

    element_results: dict[str, dict[str, Any]] = {}
    for element_id, element_result in results.element_results.items():
        data = {
            "forces_n1": _persistent_result_vector(element_result.forces_n1, f"forces_n1 {element_id}"),
            "forces_n2": _persistent_result_vector(element_result.forces_n2, f"forces_n2 {element_id}"),
        }
        for key in ("von_mises_n1", "von_mises_n2", "max_von_mises"):
            value = float(getattr(element_result, key))
            if np.isfinite(value):
                data[key] = value
        element_results[element_id] = data

    files: dict[str, str] = {}
    if results.result_file is not None:
        files["result"] = str(results.result_file)

    metadata: dict[str, Any] = {}
    if study.metadata.get("mixed_analysis"):
        metadata["mixed_analysis"] = True
    if analysis_node_ids:
        metadata["analysis_node_ids"] = analysis_node_ids
    if results.parser_diagnostics:
        metadata["parser_diagnostics"] = list(results.parser_diagnostics)
    if results.tuyau_subpoints:
        metadata["tuyau_subpoints"] = [dict(row) for row in results.tuyau_subpoints]
    if results.volume_von_mises:
        metadata.update(
            {
                "volume_analysis": True,
                "compiler_inputs": dict(compiler_inputs or {}),
                "volume_von_mises": dict(results.volume_von_mises),
                "stress_basis": "Code_Aster SIEQ_ELNO VMIS averaged at surface nodes",
                "compliance_role": "visualization_only_not_asme_code_stress",
            }
        )

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
        solver_input_identity=(
            study.solver_input_identity
            or (analysis_mesh.solver_input_identity if analysis_mesh is not None else None)
        ),
    )


def _validated_analysis_node_ids(
    *,
    model: Any,
    study: AnalysisStudy,
    results: FEAResults,
    analysis_mesh: AnalysisMesh | None,
) -> list[str]:
    node_ids = set(results.analysis_node_results)
    if not node_ids:
        return []
    if analysis_mesh is None:
        raise ValueError(
            "FEAResults with analysis-node results require an authoritative analysis mesh."
        )
    if analysis_mesh.id != study.mesh_id:
        raise ValueError(
            f"Analysis mesh {analysis_mesh.id!r} does not match study mesh {study.mesh_id!r}."
        )
    if analysis_mesh.model_revision != study.model_revision:
        raise ValueError(
            f"Analysis mesh {analysis_mesh.id!r} model revision "
            f"{analysis_mesh.model_revision} does not match study revision "
            f"{study.model_revision}."
        )
    if analysis_mesh.solver_name.casefold() != study.solver_name.casefold():
        raise ValueError(
            f"Analysis mesh {analysis_mesh.id!r} solver {analysis_mesh.solver_name!r} "
            f"does not match study solver {study.solver_name!r}."
        )
    model_node_ids = set(getattr(model, "nodes", {}))
    misclassified = node_ids & model_node_ids
    if misclassified:
        raise ValueError(
            "Analysis-node results contain authoring-model node IDs: "
            f"{sorted(misclassified)}."
        )
    unknown = node_ids - set(analysis_mesh.nodes)
    if unknown:
        raise ValueError(
            "Analysis-node results are not present in the authoritative analysis mesh: "
            f"{sorted(unknown)}."
        )
    return sorted(node_ids)


def fea_results_from_result_state(*, model: Any, result_state: ResultState) -> FEAResults:
    """Reconstruct an in-memory ``FEAResults`` object from a persistent state."""
    model_revision = _model_revision(model)
    if model_revision != result_state.model_revision:
        raise ValueError(
            f"Cannot apply ResultState revision {result_state.model_revision} to model revision {model_revision}."
        )
    is_volume = bool(result_state.metadata.get("volume_analysis"))
    is_mixed = bool(result_state.metadata.get("mixed_analysis"))
    validate_solver_input_identity(
        model,
        result_state.solver_input_identity,
        context=f"ResultState {result_state.id!r}",
        expected_load_case=result_state.load_case,
        expected_compiler_id=(
            MIXED_CODE_ASTER_COMPILER_ID
            if is_mixed
            else VOLUME_CODE_ASTER_COMPILER_ID
            if is_volume
            else CODE_ASTER_COMPILER_ID
        ),
        compiler_inputs=result_state.metadata.get("compiler_inputs"),
    )

    results = FEAResults(solver_name=result_state.solver_name, load_case=result_state.load_case)
    results._model = model
    if "result" in result_state.files:
        results.result_file = Path(result_state.files["result"])
    results.parser_diagnostics.extend(result_state.metadata.get("parser_diagnostics", []))
    results.tuyau_subpoints.extend(dict(row) for row in result_state.metadata.get("tuyau_subpoints", []))
    results.volume_von_mises.update(result_state.metadata.get("volume_von_mises", {}))

    if not is_volume or is_mixed:
        model_node_ids = set(getattr(model, "nodes", {}))
        required_node_ids = (
            model_node_ids & set(result_state.node_displacements)
            if is_mixed
            else model_node_ids
        )
        for node_id in required_node_ids:
            if node_id not in result_state.node_displacements:
                raise ValueError(f"ResultState {result_state.id!r} is missing displacement for model node {node_id!r}.")
            displacement = _element_result_array(
                result_state.node_displacements[node_id],
                f"displacement {node_id}",
            )
            reaction = result_state.node_reactions.get(node_id)
            results.node_results[node_id] = NodeResult(
                node_id=node_id,
                displacement=displacement,
                reaction_force=(
                    _element_result_array(reaction, f"reaction {node_id}")
                    if reaction is not None
                    else None
                ),
            )

    for node_id, displacement in result_state.node_displacements.items():
        if node_id in results.node_results:
            continue
        results.analysis_node_results[node_id] = NodeResult(
            node_id=node_id,
            displacement=_element_result_array(displacement, f"displacement {node_id}"),
            reaction_force=(
                _element_result_array(result_state.node_reactions[node_id], f"reaction {node_id}")
                if node_id in result_state.node_reactions
                else None
            ),
        )

    element_ids = (
        result_state.element_results
        if is_volume
        else [element.id for element in getattr(model, "elements", [])]
    )
    for element_id in element_ids:
        element = model.get_element(element_id)
        if element is None:
            raise ValueError(f"ResultState {result_state.id!r} references missing model element {element_id!r}.")
        if element.id not in result_state.element_results:
            raise ValueError(f"ResultState {result_state.id!r} is missing element result for {element.id!r}.")
        data = result_state.element_results[element.id]
        for field_name in ("forces_n1", "forces_n2"):
            if field_name not in data:
                raise ValueError(
                    f"ResultState {result_state.id!r} element {element.id!r} is missing result field {field_name!r}."
                )
        results.element_results[element.id] = ElementResult(
            element_id=element.id,
            forces_n1=_element_result_array(data["forces_n1"], f"forces_n1 {element.id}"),
            forces_n2=_element_result_array(data["forces_n2"], f"forces_n2 {element.id}"),
            von_mises_n1=float(data.get("von_mises_n1", np.nan)),
            von_mises_n2=float(data.get("von_mises_n2", np.nan)),
            max_von_mises=float(data.get("max_von_mises", np.nan)),
        )
    return results


def _float_tuple(values: Any, length: int, label: str) -> tuple[float, ...]:
    data = tuple(float(value) for value in values)
    if len(data) != length:
        raise ValueError(f"{label} must have {length} values.")
    return data


def _optional_float_tuple(values: Any, length: int, label: str) -> tuple[float | None, ...]:
    data = tuple(None if value is None or not np.isfinite(float(value)) else float(value) for value in values)
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


def _persistent_result_vector(values: Any, label: str) -> list[float | None]:
    return [value if np.isfinite(value) else None for value in _result_vector(values, label)]


def _element_result_array(values: Any, label: str) -> np.ndarray:
    data = tuple(np.nan if value is None else float(value) for value in values)
    if len(data) != 6:
        raise ValueError(f"{label} must have 6 values.")
    return np.asarray(data, dtype=float)
