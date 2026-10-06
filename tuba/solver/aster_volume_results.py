"""Parse native Code_Aster solid, shell, line and reference-node tables."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Iterator

import numpy as np

from tuba.analysis import AnalysisMesh, AnalysisStudy
from tuba.model import TubaModel
from tuba.solver.base import ElementResult, FEAResults, NodeResult


def parse_volume_result_artifacts(
    model: TubaModel,
    work_dir: str | Path,
    analysis_mesh: AnalysisMesh,
    study: AnalysisStudy,
) -> FEAResults:
    root = Path(work_dir)
    results = FEAResults(solver_name="Code_Aster", load_case=study.load_case)
    results._model = model
    rmed_path = root / "study.rmed"
    if rmed_path.is_file():
        results.result_file = rmed_path

    six_dof_nodes = _six_dof_nodes(analysis_mesh)

    for row in _rows(root / "study_depl.csv"):
        node_id = _volume_node_id(row.get("NOEUD", ""))
        if node_id not in analysis_mesh.nodes:
            continue
        displacement = np.asarray(
            [
                *_components(row, ("DX", "DY", "DZ")),
                *(_components if node_id in six_dof_nodes else _optional_components)(row, ("DRX", "DRY", "DRZ")),
            ]
        )
        results.analysis_node_results[node_id] = NodeResult(
            node_id=node_id,
            displacement=displacement,
        )
        source = analysis_mesh.node_sources.get(node_id)
        if source is not None and source.source_ref.kind == "node":
            results.node_results[source.source_ref.id] = NodeResult(
                node_id=source.source_ref.id,
                displacement=displacement.copy(),
            )
    missing = sorted(set(analysis_mesh.nodes) - set(results.analysis_node_results))
    if missing:
        raise RuntimeError(
            f"Code_Aster volume output is missing displacement for {len(missing)} analysis nodes."
        )

    anchored_nodes = _anchored_volume_nodes(model, analysis_mesh, study)
    covered_reactions = set()
    for row in _rows(root / "study_reac.csv"):
        node_id = _volume_node_id(row.get("NOEUD", ""))
        node_result = results.analysis_node_results.get(node_id)
        if node_result is not None and node_id in anchored_nodes:
            reaction = np.asarray(
                [
                    *_components(row, ("DX", "DY", "DZ")),
                    *(_components if node_id in six_dof_nodes else _optional_components)(row, ("DRX", "DRY", "DRZ")),
                ]
            )
            node_result.reaction_force = reaction
            covered_reactions.add(node_id)
            source = analysis_mesh.node_sources.get(node_id)
            if source is not None and source.source_ref.kind == "node":
                results.node_results[source.source_ref.id].reaction_force = reaction.copy()
    if (study.metadata.get("step_component_analysis") or study.metadata.get("mixed_analysis")) and anchored_nodes - covered_reactions:
        raise RuntimeError("Code_Aster STEP output is missing reactions on restrained interface nodes.")

    surface_mesh = analysis_mesh.surface_mesh or {}
    surface_nodes = set(surface_mesh.get("node_ids", []))
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    volume_maximum = -math.inf
    shell_samples = []
    shell_nodes: dict[str, float] = {}
    shell_elements: dict[str, float] = {}
    shell_coverage: dict[tuple[str, str], set[int]] = {}
    volume_cells = {
        element_id for element_id, source in analysis_mesh.element_sources.items()
        if source.role == "volume_cell"
    }
    shell_cells = {
        element_id for element_id, source in analysis_mesh.element_sources.items()
        if source.role == "shell_cell"
    }
    shell_subpoints = _shell_layer_contract(analysis_mesh, study, shell_cells)
    # The rows this pass does not use - a mixed run's line elements - are kept for
    # the line parser. It used to read the whole table again (260 MB on the header
    # tower, all of it held in memory) for the few rows it needs.
    other_rows: list[dict[str, str]] = []
    for row in _rows(root / "study_sieq.csv"):
        element_label = row.get("MAILLE", "").strip()
        source = None
        if element_label:
            element_id = _analysis_element_id(element_label, analysis_mesh)
            source = analysis_mesh.element_sources.get(element_id)
            if source is None or source.role not in {"volume_cell", "shell_cell"}:
                other_rows.append(row)
                continue
        value = _finite(row, "VMIS")
        node_id = _volume_node_id(row.get("NOEUD", ""))
        if source is not None and source.role == "shell_cell":
            if node_id not in analysis_mesh.elements[element_id]:
                raise RuntimeError("Code_Aster shell stress node is outside its analysis cell.")
            subpoint = _shell_subpoint(row)
            shell_coverage.setdefault((element_id, node_id), set()).add(subpoint)
            shell_nodes[node_id] = max(shell_nodes.get(node_id, -math.inf), value)
            shell_elements[element_id] = max(shell_elements.get(element_id, -math.inf), value)
            shell_samples.append({
                "analysis_element_id": element_id, "node_id": node_id,
                "source_ref": str(source.source_ref), "subpoint_index": subpoint,
                "field": "SIEQ_ELNO", "component": "VMIS", "unit": "Pa", "value": value,
            })
            continue
        volume_maximum = max(volume_maximum, value)
        if node_id in surface_nodes:
            sums[node_id] = sums.get(node_id, 0.0) + value
            counts[node_id] = counts.get(node_id, 0) + 1
    if volume_cells and not math.isfinite(volume_maximum):
        raise RuntimeError("Code_Aster volume output contains no finite SIEQ_ELNO VMIS values.")
    results.volume_von_mises = {node_id: sums[node_id] / counts[node_id] for node_id in sums}
    missing_surface = sorted(surface_nodes - set(results.volume_von_mises))
    if missing_surface:
        raise RuntimeError(
            f"Code_Aster volume output is missing VMIS for {len(missing_surface)} surface nodes."
        )
    if shell_cells:
        incomplete = [
            (element_id, node_id)
            for element_id in shell_cells
            for node_id in analysis_mesh.elements[element_id]
            if shell_coverage.get((element_id, node_id), set()) != shell_subpoints
        ]
        if incomplete:
            raise RuntimeError(
                "Code_Aster shell output has incomplete or unexpected through-thickness VMIS samples "
                f"at {len(incomplete)} element-node locations."
            )
        results.metadata.update({
            "shell_von_mises": shell_nodes,
            "shell_element_von_mises": shell_elements,
            "shell_stress_samples": shell_samples,
            "shell_stress_basis": (
                "Code_Aster SIEQ_ELNO VMIS maximum across native through-thickness "
                "subpoints and adjacent shell cells; visualization only"
            ),
        })

    for element_id in study.metadata["compiler_inputs"]["element_ids"]:
        results.element_results[element_id] = ElementResult(
            element_id=element_id,
            forces_n1=np.full(6, np.nan),
            forces_n2=np.full(6, np.nan),
            max_von_mises=volume_maximum,
        )
    if study.metadata.get("mixed_analysis"):
        _parse_line_results(model, root, analysis_mesh, study, results, sieq_rows=other_rows)
    return results


def _six_dof_nodes(analysis_mesh: AnalysisMesh) -> set[str]:
    """Use actual modelisations, preserving old meshes' explicit source roles."""
    modelisations = {"TUYAU_3M", "POU_D_T", "POU_D_E", "DKT", "COQUE_3D", "DIS_TR"}
    cells = {
        element_id
        for group, modelisation in analysis_mesh.modelisations.items()
        if modelisation in modelisations
        for element_id in analysis_mesh.groups.get(group, ())
        if element_id in analysis_mesh.elements
    }
    cells.update(
        element_id for element_id, source in analysis_mesh.element_sources.items()
        if source.role in {"native_element", "shell_cell", "reference_carrier"}
    )
    return {node_id for element_id in cells for node_id in analysis_mesh.elements[element_id]}


def _shell_subpoint(row: dict[str, str]) -> int:
    value = _finite(row, "SOUS_POINT")
    if value < 1 or not value.is_integer():
        raise RuntimeError("Invalid Code_Aster shell through-thickness subpoint index.")
    return int(value)


def _shell_layer_contract(
    analysis_mesh: AnalysisMesh,
    study: AnalysisStudy,
    shell_cells: set[str],
) -> set[int]:
    """Require the compiled DKT layer contract verified against native output."""
    if not shell_cells:
        return set()
    owners = {
        analysis_mesh.element_sources[cell].source_ref.id
        for cell in shell_cells
    }
    layers = study.metadata.get("compiler_inputs", {}).get("shell_coque_ncou")
    if not isinstance(layers, dict) or set(layers) != owners:
        raise RuntimeError("Code_Aster shell COQUE_NCOU contract is missing or mismatches the analysis shell owners.")
    if any(type(count) is not int or count != 1 for count in layers.values()):
        raise RuntimeError("Code_Aster shell COQUE_NCOU contract requires the qualified integer value 1.")
    return {1, 2, 3}


def _anchored_volume_nodes(
    model: TubaModel,
    analysis_mesh: AnalysisMesh,
    study: AnalysisStudy,
) -> set[str]:
    selected_ids = set(study.metadata["compiler_inputs"]["element_ids"])
    anchor_ids = {
        support.node for support in model.supports
        if support.attached_to is None and "fixed" in support.restraint().states
    }
    anchored_nodes = {
        mesh_node_id
        for anchor_id in anchor_ids
        for mesh_node_id in analysis_mesh.groups.get(f"G_NODE_{anchor_id}", ())
    }
    anchored_nodes.update(
        node_id
        for group in (*study.metadata.get("fixed_face_groups", ()),
                      *study.metadata.get("fixed_node_groups", ()))
        for member in analysis_mesh.groups.get(group, ())
        for node_id in (analysis_mesh.elements[member] if member in analysis_mesh.elements else (member,))
        if node_id in analysis_mesh.nodes
    )
    # LIAISON_SOLIDE can carry support reactions on any physical patch node.
    # Follow connected patches through shared references/nodes so fanout is
    # complete; disconnected free patches carry internal transfer forces.
    while True:
        previous_count = len(anchored_nodes)
        for coupling in model.couplings.values():
            if coupling.kind != "rigid_patch":
                continue
            members = set(analysis_mesh.groups.get(coupling.metadata["mesh_node_group"], ()))
            if coupling.source_node.id not in anchor_ids and not members & anchored_nodes:
                continue
            reference_nodes = set(analysis_mesh.groups.get(f"G_NODE_{coupling.source_node.id}", ()))
            if (not reference_nodes or not reference_nodes < members
                    or not members <= analysis_mesh.nodes.keys()):
                raise RuntimeError("Code_Aster grounded rigid patch is missing its reference or physical analysis nodes.")
            anchored_nodes.update(members)
        if len(anchored_nodes) == previous_count:
            break
    planes: list[tuple[np.ndarray, np.ndarray, float]] = []
    for element_id in selected_ids:
        element = model.get_element(element_id)
        for anchor_id, other_id in ((element.n1, element.n2), (element.n2, element.n1)):
            if anchor_id not in anchor_ids:
                continue
            origin = np.asarray(model.nodes[anchor_id].coords, dtype=float)
            if element.type == "pipe_bend" and element.bend_geometry is not None:
                tangent = (
                    element.bend_geometry.start_tangent
                    if anchor_id == element.n1
                    else element.bend_geometry.end_tangent
                )
                inward = np.asarray(tangent, dtype=float) * (1.0 if anchor_id == element.n1 else -1.0)
                length = element.bend_geometry.radius * math.radians(element.bend_geometry.angle)
            else:
                inward = np.asarray(model.nodes[other_id].coords, dtype=float) - origin
                length = float(np.linalg.norm(inward))
            planes.append((origin, inward / np.linalg.norm(inward), max(length * 1.0e-7, 1.0e-9)))
    anchored_nodes.update(
        {
        node_id
        for node_id, coords in analysis_mesh.nodes.items()
        if any(
            abs(float(np.dot(np.asarray(coords, dtype=float) - origin, normal))) <= tolerance
            for origin, normal, tolerance in planes
        )
        }
    )
    return anchored_nodes


def _parse_line_results(
    model: TubaModel,
    root: Path,
    analysis_mesh: AnalysisMesh,
    study: AnalysisStudy,
    results: FEAResults,
    sieq_rows: list[dict[str, str]] | None = None,
) -> None:
    line_ids = set(study.metadata.get("compiler_inputs", {}).get("line_element_ids", ()))
    if not line_ids:
        return
    for element_id in line_ids:
        results.element_results[element_id] = ElementResult(
            element_id=element_id,
            forces_n1=np.full(6, np.nan),
            forces_n2=np.full(6, np.nan),
        )
    node_label_map: dict[str, str] = {}
    for mesh_node_id, source in analysis_mesh.node_sources.items():
        if not mesh_node_id.startswith("VN"):
            continue
        source_id = (
            source.source_ref.id if source.source_ref.kind == "node" else mesh_node_id
        )
        node_label_map[mesh_node_id] = source_id
        node_label_map[mesh_node_id.removeprefix("VN")] = source_id
    element_label_map = {
        label: source.source_ref.id
        for mesh_element_id, source in analysis_mesh.element_sources.items()
        if source.role == "native_element" and mesh_element_id.startswith("LM")
        for label in (mesh_element_id, mesh_element_id.removeprefix("LM"))
    }
    from tuba.solver import parse_tables
    covered = parse_tables.parse_effo_table(model, root, results, node_label_map, element_label_map)
    parse_tables.parse_sieq_table(model, root, results, node_label_map, element_label_map, rows=sieq_rows)
    if study.metadata.get("compiler_inputs", {}).get("beam_stress") == "SIPO_ELNO":
        parse_tables.parse_sipo_table(model, root, results, element_label_map)
    if study.metadata.get("step_component_analysis") or study.metadata.get("mixed_analysis"):
        required = {(e.id, node) for e in model.elements if e.id in line_ids for node in (e.n1, e.n2)}
        if required - covered:
            raise RuntimeError("Code_Aster STEP output is missing pipe/beam endpoint forces.")
        if any(e.type == "pipe_straight" and not math.isfinite(results.element_results[e.id].max_von_mises) for e in model.elements if e.id in line_ids):
            raise RuntimeError("Code_Aster STEP output is missing pipe stress values.")


def _rows(path: Path) -> Iterator[dict[str, str]]:
    if not path.is_file():
        raise RuntimeError(f"Code_Aster volume result table is missing: {path.name}.")
    with path.open(encoding="utf-8", errors="replace", newline="") as stream:
        data_lines = (
            line for line in stream if line.strip() and not line.lstrip().startswith("#")
        )
        yield from csv.DictReader(data_lines)


def _volume_node_id(label: str) -> str:
    label = label.strip()
    if label.startswith("VN") and label[2:].isdigit():
        return label
    try:
        return f"VN{int(label)}"
    except ValueError as exc:
        raise RuntimeError(f"Invalid Code_Aster volume node label {label!r}.") from exc


def _analysis_element_id(label: str, analysis_mesh: AnalysisMesh) -> str:
    label = label.strip()
    if label in analysis_mesh.elements:
        return label
    try:
        tag = int(label.strip())
    except ValueError as exc:
        raise RuntimeError(f"Invalid Code_Aster volume element label {label!r}.") from exc
    for prefix in ("VM", "LM", "SM", "RC", "VS"):
        candidate = f"{prefix}{tag}"
        if candidate in analysis_mesh.elements:
            return candidate
    for element_id, source in analysis_mesh.element_sources.items():
        if source.metadata.get("solver_element_tag") == tag:
            return element_id
    return f"VM{tag}"


def _components(row: dict[str, str], names: tuple[str, ...]) -> list[float]:
    return [_finite(row, name) for name in names]


def _optional_components(row: dict[str, str], names: tuple[str, ...]) -> list[float]:
    values = []
    for name in names:
        raw = row.get(name, "")
        values.append(_finite(row, name) if raw is not None and raw.strip() not in {"", "-"} else np.nan)
    return values


def _finite(row: dict[str, str], name: str) -> float:
    try:
        value = float(row.get(name, "").strip())
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid Code_Aster volume result component {name}={row.get(name)!r}.") from exc
    if not math.isfinite(value):
        raise RuntimeError(f"Non-finite Code_Aster volume result component {name}={value!r}.")
    return value
