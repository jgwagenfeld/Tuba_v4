"""Quadratic Gmsh volume meshes for explicitly selected pipe geometry."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

import gmsh
import numpy as np

from tuba.analysis.mesh import AnalysisMesh, MeshElementSource, MeshNodeSource
from tuba.model import PipeSection, TubaModel
from tuba.refs import EntityRef
from tuba.solver.aster_sidecar import build_solver_name_map


@dataclass(frozen=True)
class GeneratedPipeVolumeMesh:
    analysis_mesh: AnalysisMesh
    groups: dict[str, tuple[str, ...]]
    surface_vertices: tuple[tuple[float, float, float], ...]
    surface_faces: tuple[tuple[int, int, int], ...]
    gmsh_version: str
    settings: dict[str, Any]
    med_path: Path


@dataclass(frozen=True)
class _StraightSelection:
    element_id: str
    n1: str
    n2: str
    start: np.ndarray
    direction: np.ndarray
    section: PipeSection


def build_pipe_volume_mesh(
    model: TubaModel,
    output_path: str | Path,
    *,
    element_ids: Iterable[str],
    max_element_size: float,
    element_order: int = 2,
) -> GeneratedPipeVolumeMesh:
    """Mesh one selected straight hollow pipe as quadratic tetrahedra."""
    selection = _preflight(model, element_ids, max_element_size, element_order)
    output = Path(output_path)
    temporary = output.with_name(f".{output.stem}-{uuid4().hex}.tmp.med")
    owned_session = not bool(gmsh.isInitialized())
    previous_model = gmsh.model.getCurrent() if not owned_session else ""
    created_model = f"tuba_pipe_volume_{uuid4().hex}"
    option_names = (
        "Mesh.MeshSizeMin",
        "Mesh.MeshSizeMax",
        "Mesh.MeshSizeFromCurvature",
        "Mesh.ElementOrder",
    )
    previous_options = (
        {name: gmsh.option.getNumber(name) for name in option_names}
        if not owned_session
        else {}
    )

    try:
        if owned_session:
            gmsh.initialize()
        gmsh.model.add(created_model)
        volume_tags, surface_groups = _build_straight_geometry(selection)
        raw_entities: dict[str, tuple[int, tuple[int, ...]]] = {
            "G_SOLID_region_0": (3, volume_tags),
            **{name: (2, tags) for name, tags in surface_groups.items()},
        }
        name_map = build_solver_name_map(raw_entities)
        for raw_name, (dimension, tags) in raw_entities.items():
            physical = gmsh.model.addPhysicalGroup(dimension, list(tags))
            gmsh.model.setPhysicalName(dimension, physical, name_map[raw_name])

        gmsh.option.setNumber("Mesh.MeshSizeMin", max_element_size)
        gmsh.option.setNumber("Mesh.MeshSizeMax", max_element_size)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 20)
        gmsh.option.setNumber("Mesh.ElementOrder", element_order)
        gmsh.model.mesh.generate(3)
        gmsh.model.mesh.setOrder(element_order)

        output.parent.mkdir(parents=True, exist_ok=True)
        gmsh.write(str(temporary))
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise RuntimeError("Gmsh did not write a non-empty MED mesh.")

        analysis_mesh, groups, vertices, faces = _readback(
            model,
            selection,
            output,
            raw_entities,
        )
        temporary.replace(output)
        return GeneratedPipeVolumeMesh(
            analysis_mesh=analysis_mesh,
            groups=groups,
            surface_vertices=vertices,
            surface_faces=faces,
            gmsh_version=str(gmsh.__version__),
            settings={"element_order": element_order, "max_element_size": max_element_size},
            med_path=output,
        )
    finally:
        temporary.unlink(missing_ok=True)
        if gmsh.isInitialized():
            try:
                gmsh.model.setCurrent(created_model)
                gmsh.model.remove()
            except Exception:
                pass
            if owned_session:
                gmsh.finalize()
            else:
                for name, value in previous_options.items():
                    gmsh.option.setNumber(name, value)
                if previous_model:
                    gmsh.model.setCurrent(previous_model)


def _preflight(
    model: TubaModel,
    element_ids: Iterable[str],
    max_element_size: float,
    element_order: int,
) -> _StraightSelection:
    ids = tuple(element_ids)
    if element_order != 2:
        raise ValueError("Native pipe volume meshes require element_order=2.")
    if not math.isfinite(max_element_size) or max_element_size <= 0.0:
        raise ValueError("max_element_size must be positive and finite.")
    if len(ids) != 1:
        raise ValueError("The current native volume mesher requires one selected pipe_straight element.")
    element = model.get_element(ids[0])
    if element is None:
        raise ValueError(f"Unknown selected element {ids[0]!r}.")
    if element.type != "pipe_straight":
        raise ValueError(f"Selected element {element.id!r} must be pipe_straight, got {element.type!r}.")
    section = model.sections.get(element.section)
    if not isinstance(section, PipeSection):
        raise ValueError(f"Selected element {element.id!r} must use a circular PipeSection.")
    if section.ID <= 0.0 or section.WT <= 0.0:
        raise ValueError(f"Pipe section {section.name!r} must have positive bore and wall thickness.")
    if max_element_size > section.WT / 2.0:
        raise ValueError("max_element_size must provide at least two elements through the pipe wall.")
    if element.material not in model.materials:
        raise ValueError(f"Selected element {element.id!r} references missing material {element.material!r}.")
    start = np.asarray(model.nodes[element.n1].coords, dtype=float)
    end = np.asarray(model.nodes[element.n2].coords, dtype=float)
    direction = end - start
    if not np.isfinite(direction).all() or float(np.linalg.norm(direction)) <= 0.0:
        raise ValueError(f"Selected element {element.id!r} must have non-zero finite length.")
    return _StraightSelection(element.id, element.n1, element.n2, start, direction, section)


def _build_straight_geometry(
    selection: _StraightSelection,
) -> tuple[tuple[int, ...], dict[str, tuple[int, ...]]]:
    start = selection.start.tolist()
    direction = selection.direction.tolist()
    outer = gmsh.model.occ.addCylinder(*start, *direction, selection.section.OD / 2.0)
    inner = gmsh.model.occ.addCylinder(*start, *direction, selection.section.ID / 2.0)
    wall, _lineage = gmsh.model.occ.cut([(3, outer)], [(3, inner)], removeObject=True, removeTool=True)
    gmsh.model.occ.synchronize()
    volumes = tuple(tag for dimension, tag in wall if dimension == 3)
    if len(volumes) != 1:
        raise RuntimeError(f"Expected one pipe-wall volume, got {len(volumes)}.")

    boundary = gmsh.model.getBoundary([(3, tag) for tag in volumes], oriented=False, recursive=False)
    surface_tags = tuple(sorted({tag for dimension, tag in boundary if dimension == 2}))
    length_squared = float(np.dot(selection.direction, selection.direction))
    end_tolerance = max(math.sqrt(length_squared) * 1e-7, 1e-9)
    ends: dict[str, list[int]] = {selection.n1: [], selection.n2: []}
    curved: list[int] = []
    for tag in surface_tags:
        center = np.asarray(gmsh.model.occ.getCenterOfMass(2, tag), dtype=float)
        station = float(np.dot(center - selection.start, selection.direction) / length_squared)
        if abs(station) * math.sqrt(length_squared) <= end_tolerance:
            ends[selection.n1].append(tag)
        elif abs(station - 1.0) * math.sqrt(length_squared) <= end_tolerance:
            ends[selection.n2].append(tag)
        else:
            curved.append(tag)
    if any(len(tags) != 1 for tags in ends.values()) or len(curved) != 2:
        raise RuntimeError("Could not classify the pipe end, inner, and outer surfaces.")
    inner_tag, outer_tag = sorted(curved, key=lambda tag: gmsh.model.occ.getMass(2, tag))
    return volumes, {
        "G_INNER_region_0": (inner_tag,),
        "G_OUTER_region_0": (outer_tag,),
        f"G_END_{selection.n1}": tuple(ends[selection.n1]),
        f"G_END_{selection.n2}": tuple(ends[selection.n2]),
    }


def _readback(
    model: TubaModel,
    selection: _StraightSelection,
    output: Path,
    raw_entities: dict[str, tuple[int, tuple[int, ...]]],
) -> tuple[
    AnalysisMesh,
    dict[str, tuple[str, ...]],
    tuple[tuple[float, float, float], ...],
    tuple[tuple[int, int, int], ...],
]:
    node_tags, coordinates, _parameters = gmsh.model.mesh.getNodes()
    coordinates_by_tag = {
        int(tag): tuple(float(value) for value in coordinates[index * 3 : index * 3 + 3])
        for index, tag in enumerate(node_tags)
    }
    source_ref = EntityRef("element", selection.element_id)
    nodes = {f"N{tag}": value for tag, value in coordinates_by_tag.items()}
    node_sources = {
        node_id: MeshNodeSource(node_id=node_id, source_ref=source_ref, role="volume_node")
        for node_id in nodes
    }

    elements: dict[str, tuple[str, ...]] = {}
    element_sources: dict[str, MeshElementSource] = {}
    volume_mesh_tags: list[int] = []
    for volume_tag in raw_entities["G_SOLID_region_0"][1]:
        types, element_tag_blocks, node_tag_blocks = gmsh.model.mesh.getElements(3, volume_tag)
        for element_type, element_tags, element_nodes in zip(types, element_tag_blocks, node_tag_blocks):
            _name, dimension, order, node_count, _local, _primary_count = gmsh.model.mesh.getElementProperties(
                element_type
            )
            if dimension != 3 or order != 2 or node_count != 10:
                continue
            for index, element_tag in enumerate(element_tags):
                mesh_id = f"M{int(element_tag)}"
                start = index * node_count
                elements[mesh_id] = tuple(f"N{int(tag)}" for tag in element_nodes[start : start + node_count])
                element_sources[mesh_id] = MeshElementSource(
                    element_id=mesh_id,
                    source_ref=source_ref,
                    role="volume_cell",
                )
                volume_mesh_tags.append(int(element_tag))
    if not volume_mesh_tags:
        raise RuntimeError("Gmsh generated no quadratic tetrahedral volume cells.")
    qualities = np.asarray(gmsh.model.mesh.getElementQualities(volume_mesh_tags, "minSJ"), dtype=float)
    if not qualities.size or not np.isfinite(qualities).all() or float(qualities.min()) <= 0.0:
        raise RuntimeError("Gmsh generated an invalid quadratic tetrahedral cell.")

    groups: dict[str, tuple[str, ...]] = {"G_SOLID_region_0": tuple(elements)}
    surface_triangle_nodes: list[tuple[int, int, int]] = []
    for raw_name, (dimension, entity_tags) in raw_entities.items():
        if dimension != 2:
            continue
        mesh_ids: list[str] = []
        for entity_tag in entity_tags:
            types, element_tag_blocks, node_tag_blocks = gmsh.model.mesh.getElements(2, entity_tag)
            for element_type, element_tags, element_nodes in zip(types, element_tag_blocks, node_tag_blocks):
                _name, cell_dimension, _order, node_count, _local, primary_count = (
                    gmsh.model.mesh.getElementProperties(element_type)
                )
                if cell_dimension != 2 or primary_count != 3:
                    continue
                for index, element_tag in enumerate(element_tags):
                    tags = tuple(int(tag) for tag in element_nodes[index * node_count : index * node_count + 3])
                    mesh_ids.append(f"S{int(element_tag)}")
                    surface_triangle_nodes.append(tags)
        groups[raw_name] = tuple(mesh_ids)
        if not groups[raw_name]:
            raise RuntimeError(f"Gmsh generated an empty physical group {raw_name!r}.")

    skin_tags = tuple(dict.fromkeys(tag for face in surface_triangle_nodes for tag in face))
    skin_indices = {tag: index for index, tag in enumerate(skin_tags)}
    vertices = tuple(coordinates_by_tag[tag] for tag in skin_tags)
    faces = tuple(tuple(skin_indices[tag] for tag in face) for face in surface_triangle_nodes)
    analysis_mesh = AnalysisMesh(
        id=f"pipe-volume-{uuid4().hex}",
        model_revision=int(getattr(model, "revision", 0)),
        solver_name="code_aster",
        nodes=nodes,
        elements=elements,
        groups=groups,
        node_sources=node_sources,
        element_sources=element_sources,
        files={"med": str(output)},
        modelisations={"G_SOLID_region_0": "3D"},
    )
    return analysis_mesh, groups, vertices, faces
