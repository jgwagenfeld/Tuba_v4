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
from tuba.geometry.junctions import classify_tee_junction
from tuba.model import BendGeometry, PipeSection, TubaModel, sample_bend_geometry
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
    bend_geometry: BendGeometry | None = None


@dataclass(frozen=True)
class _PipeSelection:
    pipes: tuple[_StraightSelection, ...]
    tee_node: str | None = None


def build_pipe_volume_mesh(
    model: TubaModel,
    output_path: str | Path,
    *,
    element_ids: Iterable[str],
    max_element_size: float,
    element_order: int = 2,
) -> GeneratedPipeVolumeMesh:
    """Mesh one straight pipe, one bend, or one explicit three-run tee."""
    selection = _preflight(model, element_ids, max_element_size, element_order)
    output = Path(output_path)
    temporary = output.with_name(f".{output.stem}-{uuid4().hex}.tmp.med")
    owned_session = not bool(gmsh.isInitialized())
    previous_model = gmsh.model.getCurrent() if not owned_session else ""
    created_model = f"tuba_pipe_volume_{uuid4().hex}"
    option_names = (
        "General.Terminal",
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
        gmsh.option.setNumber("General.Terminal", 0)
        if selection.tee_node is None:
            selected_pipe = selection.pipes[0]
            volume_tags, surface_groups = (
                _build_bend_geometry(selected_pipe)
                if selected_pipe.bend_geometry is not None
                else _build_straight_geometry(selected_pipe)
            )
        else:
            volume_tags, surface_groups = _build_tee_geometry(model, selection)
        raw_entities: dict[str, tuple[int, tuple[int, ...]]] = {
            "G_SOLID_region_0": (3, volume_tags),
            **{name: (2, tags) for name, tags in surface_groups.items()},
        }
        if selection.tee_node is not None:
            raw_entities[f"G_TEE_{selection.tee_node}"] = (3, volume_tags)
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
) -> _PipeSelection:
    ids = tuple(element_ids)
    if element_order != 2:
        raise ValueError("Native pipe volume meshes require element_order=2.")
    if not math.isfinite(max_element_size) or max_element_size <= 0.0:
        raise ValueError("max_element_size must be positive and finite.")
    if len(ids) not in {1, 3} or len(set(ids)) != len(ids):
        raise ValueError("Select one pipe_straight or the three unique runs of one explicit tee.")
    pipes: list[_StraightSelection] = []
    materials: set[str] = set()
    for element_id in ids:
        element = model.get_element(element_id)
        if element is None:
            raise ValueError(f"Unknown selected element {element_id!r}.")
        if element.type not in {"pipe_straight", "pipe_bend"} or (len(ids) == 3 and element.type != "pipe_straight"):
            raise ValueError(
                f"Selected element {element.id!r} must be an isolated pipe_bend or pipe_straight, "
                f"got {element.type!r}."
            )
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
        bend_geometry = element.bend_geometry if element.type == "pipe_bend" else None
        if element.type == "pipe_bend":
            if not isinstance(bend_geometry, BendGeometry):
                raise ValueError(f"Selected bend {element.id!r} requires explicit bend_geometry.")
            if not math.isfinite(bend_geometry.radius) or bend_geometry.radius <= section.OD / 2.0:
                raise ValueError(f"Selected bend {element.id!r} radius must exceed the pipe outer radius.")
            if not math.isfinite(bend_geometry.angle) or not 0.0 < bend_geometry.angle < 360.0:
                raise ValueError(f"Selected bend {element.id!r} angle must be between 0 and 360 degrees.")
            sampled_end = sample_bend_geometry(start, bend_geometry, n_segments=1)[-1]
            if not np.allclose(sampled_end, end, rtol=0.0, atol=max(bend_geometry.radius * 1e-7, 1e-9)):
                raise ValueError(f"Selected bend {element.id!r} geometry does not end at node {element.n2!r}.")
        materials.add(element.material)
        pipes.append(_StraightSelection(element.id, element.n1, element.n2, start, direction, section, bend_geometry))
    if len(materials) != 1:
        raise ValueError("A native pipe volume region must use one material.")
    if len(pipes) == 1:
        return _PipeSelection(tuple(pipes))

    common_nodes = set.intersection(*({pipe.n1, pipe.n2} for pipe in pipes))
    if len(common_nodes) != 1:
        raise ValueError("The three selected pipe_straight elements must share one junction node.")
    tee_node = common_nodes.pop()
    if tee_node not in model.tees:
        raise ValueError(f"Junction {tee_node!r} must have an explicit tee definition.")
    junction = classify_tee_junction(model, tee_node, element_ids=ids)
    pipe_by_id = {pipe.element_id: pipe for pipe in pipes}
    headers = [pipe_by_id[element_id].section for element_id in junction.header_element_ids]
    if not math.isclose(headers[0].OD, headers[1].OD) or not math.isclose(headers[0].WT, headers[1].WT):
        raise ValueError("The two tee header runs must use matching pipe dimensions.")
    branch = pipe_by_id[junction.branch_element_id].section
    if branch.OD > headers[0].OD:
        raise ValueError("The tee branch OD cannot exceed the header OD.")
    return _PipeSelection(tuple(pipes), tee_node)


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


def _build_bend_geometry(
    selection: _StraightSelection,
) -> tuple[tuple[int, ...], dict[str, tuple[int, ...]]]:
    geometry = selection.bend_geometry
    assert geometry is not None
    center = np.asarray(geometry.center, dtype=float)
    normal = np.asarray(geometry.normal, dtype=float)
    normal /= np.linalg.norm(normal)
    tangent = np.asarray(geometry.start_tangent, dtype=float)
    tangent /= np.linalg.norm(tangent)
    radial = selection.start - center
    radial /= np.linalg.norm(radial)
    outer = gmsh.model.occ.addDisk(
        *selection.start.tolist(),
        selection.section.OD / 2.0,
        selection.section.OD / 2.0,
        zAxis=tangent.tolist(),
        xAxis=radial.tolist(),
    )
    inner = gmsh.model.occ.addDisk(
        *selection.start.tolist(),
        selection.section.ID / 2.0,
        selection.section.ID / 2.0,
        zAxis=tangent.tolist(),
        xAxis=radial.tolist(),
    )
    annulus, _lineage = gmsh.model.occ.cut([(2, outer)], [(2, inner)], removeObject=True, removeTool=True)
    swept = gmsh.model.occ.revolve(
        annulus,
        *center.tolist(),
        *normal.tolist(),
        math.radians(geometry.angle),
    )
    gmsh.model.occ.synchronize()
    volumes = tuple(tag for dimension, tag in swept if dimension == 3)
    if len(volumes) != 1:
        raise RuntimeError(f"Expected one pipe-bend wall volume, got {len(volumes)}.")

    boundary = gmsh.model.getBoundary([(3, tag) for tag in volumes], oriented=False, recursive=False)
    surface_tags = tuple(sorted({tag for dimension, tag in boundary if dimension == 2}))
    end_tolerance = max(geometry.radius * math.radians(geometry.angle) * 1e-7, 1e-9)
    ends: dict[str, list[int]] = {selection.n1: [], selection.n2: []}
    curved: list[int] = []
    for tag in surface_tags:
        surface_center = np.asarray(gmsh.model.occ.getCenterOfMass(2, tag), dtype=float)
        if np.linalg.norm(surface_center - selection.start) <= end_tolerance:
            ends[selection.n1].append(tag)
        elif np.linalg.norm(surface_center - (selection.start + selection.direction)) <= end_tolerance:
            ends[selection.n2].append(tag)
        else:
            curved.append(tag)
    if any(len(tags) != 1 for tags in ends.values()) or len(curved) != 2:
        raise RuntimeError("Could not classify the pipe-bend end, inner, and outer surfaces.")
    inner_tag, outer_tag = sorted(curved, key=lambda tag: gmsh.model.occ.getMass(2, tag))
    return volumes, {
        "G_INNER_region_0": (inner_tag,),
        "G_OUTER_region_0": (outer_tag,),
        f"G_END_{selection.n1}": tuple(ends[selection.n1]),
        f"G_END_{selection.n2}": tuple(ends[selection.n2]),
    }


def _build_tee_geometry(
    model: TubaModel,
    selection: _PipeSelection,
) -> tuple[tuple[int, ...], dict[str, tuple[int, ...]]]:
    assert selection.tee_node is not None
    junction = np.asarray(model.nodes[selection.tee_node].coords, dtype=float)
    axes: list[tuple[np.ndarray, np.ndarray, PipeSection]] = []
    terminals: dict[str, np.ndarray] = {}
    pipe_by_id = {pipe.element_id: pipe for pipe in selection.pipes}
    for pipe in selection.pipes:
        terminal_node = pipe.n2 if pipe.n1 == selection.tee_node else pipe.n1
        terminal = np.asarray(model.nodes[terminal_node].coords, dtype=float)
        direction = terminal - junction
        axes.append((junction, direction / np.linalg.norm(direction), pipe.section))
        terminals[terminal_node] = terminal

    classified = classify_tee_junction(model, selection.tee_node, element_ids=[*pipe_by_id])
    header_pipes = [pipe_by_id[element_id] for element_id in classified.header_element_ids]
    header_ends = [
        np.asarray(
            model.nodes[pipe.n2 if pipe.n1 == selection.tee_node else pipe.n1].coords,
            dtype=float,
        )
        for pipe in header_pipes
    ]
    header_direction = header_ends[1] - header_ends[0]
    header_section = header_pipes[0].section
    branch_pipe = pipe_by_id[classified.branch_element_id]
    branch_node = branch_pipe.n2 if branch_pipe.n1 == selection.tee_node else branch_pipe.n1
    branch_direction = np.asarray(model.nodes[branch_node].coords, dtype=float) - junction
    outer_cylinders = [
        (3, gmsh.model.occ.addCylinder(*header_ends[0].tolist(), *header_direction.tolist(), header_section.OD / 2.0)),
        (3, gmsh.model.occ.addCylinder(*junction.tolist(), *branch_direction.tolist(), branch_pipe.section.OD / 2.0)),
    ]
    inner_cylinders = [
        (3, gmsh.model.occ.addCylinder(*header_ends[0].tolist(), *header_direction.tolist(), header_section.ID / 2.0)),
        (3, gmsh.model.occ.addCylinder(*junction.tolist(), *branch_direction.tolist(), branch_pipe.section.ID / 2.0)),
    ]

    outer, _outer_lineage = gmsh.model.occ.fuse(
        [outer_cylinders[0]], outer_cylinders[1:], removeObject=True, removeTool=True
    )
    inner, _inner_lineage = gmsh.model.occ.fuse(
        [inner_cylinders[0]], inner_cylinders[1:], removeObject=True, removeTool=True
    )
    wall, _wall_lineage = gmsh.model.occ.cut(outer, inner, removeObject=True, removeTool=True)
    gmsh.model.occ.synchronize()
    volumes = tuple(tag for dimension, tag in wall if dimension == 3)
    if len(volumes) != 1:
        raise RuntimeError(f"Expected one conformal tee-wall volume, got {len(volumes)}.")

    boundary = gmsh.model.getBoundary([(3, tag) for tag in volumes], oriented=False, recursive=False)
    surface_tags = tuple(sorted({tag for dimension, tag in boundary if dimension == 2}))
    end_tolerance = max(max(np.linalg.norm(point - junction) for point in terminals.values()) * 1e-7, 1e-9)
    ends: dict[str, list[int]] = {node_id: [] for node_id in terminals}
    curved: list[int] = []
    for tag in surface_tags:
        center = np.asarray(gmsh.model.occ.getCenterOfMass(2, tag), dtype=float)
        end_node = next(
            (node_id for node_id, point in terminals.items() if np.linalg.norm(center - point) <= end_tolerance),
            None,
        )
        if end_node is None:
            curved.append(tag)
        else:
            ends[end_node].append(tag)
    if any(len(tags) != 1 for tags in ends.values()):
        raise RuntimeError("Could not classify every tee terminal face exactly once.")

    inner_surfaces: list[int] = []
    outer_surfaces: list[int] = []
    for tag in curved:
        points = _surface_sample_points(tag)
        inner_error = _radius_error(points, axes, inner=True)
        outer_error = _radius_error(points, axes, inner=False)
        (inner_surfaces if inner_error < outer_error else outer_surfaces).append(tag)
    if not inner_surfaces or not outer_surfaces or set(inner_surfaces) & set(outer_surfaces):
        raise RuntimeError("Could not classify disjoint tee inner and outer surfaces.")
    return volumes, {
        "G_INNER_region_0": tuple(inner_surfaces),
        "G_OUTER_region_0": tuple(outer_surfaces),
        **{f"G_END_{node_id}": tuple(tags) for node_id, tags in ends.items()},
    }


def _surface_sample_points(tag: int) -> tuple[np.ndarray, ...]:
    lower, upper = gmsh.model.getParametrizationBounds(2, tag)
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    points: list[np.ndarray] = []
    for u_fraction in (0.2, 0.5, 0.8):
        for v_fraction in (0.2, 0.5, 0.8):
            parameters = lower + (upper - lower) * np.asarray((u_fraction, v_fraction))
            point = np.asarray(gmsh.model.getValue(2, tag, parameters.tolist()), dtype=float)
            if point.size == 3 and np.isfinite(point).all():
                points.append(point)
    if not points:
        raise RuntimeError(f"Could not sample tee surface {tag}.")
    return tuple(points)


def _radius_error(
    points: tuple[np.ndarray, ...],
    axes: list[tuple[np.ndarray, np.ndarray, PipeSection]],
    *,
    inner: bool,
) -> float:
    errors = []
    for point in points:
        candidates = []
        for origin, unit_axis, section in axes:
            offset = point - origin
            radial_distance = float(np.linalg.norm(offset - np.dot(offset, unit_axis) * unit_axis))
            radius = section.ID / 2.0 if inner else section.OD / 2.0
            candidates.append(abs(radial_distance - radius))
        errors.append(min(candidates))
    return float(np.mean(errors))


def _readback(
    model: TubaModel,
    selection: _PipeSelection,
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
    source_ref = EntityRef("element", selection.pipes[0].element_id)
    nodes = {f"VN{tag}": value for tag, value in coordinates_by_tag.items()}
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
                mesh_id = f"VM{int(element_tag)}"
                start = index * node_count
                elements[mesh_id] = tuple(f"VN{int(tag)}" for tag in element_nodes[start : start + node_count])
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

    groups: dict[str, tuple[str, ...]] = {
        raw_name: tuple(elements)
        for raw_name, (dimension, _entity_tags) in raw_entities.items()
        if dimension == 3
    }
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
                    mesh_ids.append(f"VS{int(element_tag)}")
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
        solver_name="Code_Aster",
        nodes=nodes,
        elements=elements,
        groups=groups,
        node_sources=node_sources,
        element_sources=element_sources,
        files={"med": str(output)},
        modelisations={"G_SOLID_region_0": "3D"},
        surface_mesh={
            "vertices": vertices,
            "faces": faces,
            "node_ids": [f"VN{tag}" for tag in skin_tags],
        },
    )
    return analysis_mesh, groups, vertices, faces
