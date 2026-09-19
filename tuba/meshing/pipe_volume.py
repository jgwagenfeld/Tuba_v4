"""Quadratic hexahedral Gmsh meshes for explicitly selected pipe geometry."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

import gmsh
import numpy as np

from tuba.analysis.mesh import AnalysisMesh, MeshElementSource, MeshNodeSource
from tuba.geometry.volume import VolumeGeometry, build_volume_geometry
from tuba.meshing._gmsh import gmsh_model
from tuba.model import TubaModel
from tuba.refs import EntityRef
from tuba.solver.aster_sidecar import build_solver_name_map


@dataclass(frozen=True)
class GeneratedPipeVolumeMesh:
    analysis_mesh: AnalysisMesh
    groups: dict[str, tuple[str, ...]]
    surface_vertices: tuple[tuple[float, float, float], ...]
    surface_faces: tuple[tuple[int, ...], ...]
    gmsh_version: str
    settings: dict[str, Any]
    med_path: Path
    geometry: VolumeGeometry


def build_pipe_volume_mesh(
    model: TubaModel,
    output_path: str | Path,
    *,
    element_ids: Iterable[str],
    max_element_size: float,
    element_order: int = 2,
    geometry: VolumeGeometry | None = None,
) -> GeneratedPipeVolumeMesh:
    """Mesh one straight pipe, one bend, or one explicit three-run tee.

    The wall solid comes from :func:`tuba.geometry.volume.build_volume_geometry`;
    pass an already-derived *geometry* to mesh exactly the record the caller
    fingerprinted, rather than a second derivation of the same selection.
    """
    if geometry is None:
        geometry = build_volume_geometry(model, element_ids)
    _require_mesh_settings(geometry, max_element_size, element_order)
    line_elements = _remaining_line_elements(model, geometry)
    output = Path(output_path)
    temporary = output.with_name(f".{output.stem}-{uuid4().hex}.tmp.med")
    try:
        with gmsh_model(
            gmsh,
            "tuba_pipe_volume",
            initialize_args=["-noenv"],
            options={
                "General.Terminal": 0,
                "Mesh.MeshSizeMin": max_element_size * 2.0,
                "Mesh.MeshSizeMax": max_element_size * 2.0,
                "Mesh.MeshSizeFromCurvature": 20,
                "Mesh.ElementOrder": element_order,
                "Mesh.SecondOrderIncomplete": 1,
                "Mesh.SubdivisionAlgorithm": 2,
            },
        ):
            if geometry.kind == "bend":
                volume_tags, surface_groups = _build_bend_geometry(geometry)
            elif geometry.kind == "tee":
                volume_tags, surface_groups = _build_tee_geometry(geometry)
            else:
                volume_tags, surface_groups = _build_straight_geometry(geometry)
            line_entities: dict[str, int] = {}
            node_entities: dict[str, int] = {}
            for element in line_elements:
                for node_id in (element.n1, element.n2):
                    if node_id not in node_entities:
                        node_entities[node_id] = gmsh.model.occ.addPoint(*model.nodes[node_id].coords)
                line_entities[element.id] = gmsh.model.occ.addLine(
                    node_entities[element.n1],
                    node_entities[element.n2],
                )
            gmsh.model.occ.synchronize()
            raw_entities: dict[str, tuple[int, tuple[int, ...]]] = {
                "G_SOLID_region_0": (3, volume_tags),
                **{name: (2, tags) for name, tags in surface_groups.items()},
            }
            if geometry.tee_node is not None:
                raw_entities[f"G_TEE_{geometry.tee_node}"] = (3, volume_tags)
            if line_entities:
                raw_entities["G_TUBE"] = (1, tuple(line_entities.values()))
            name_map = build_solver_name_map(
                [*raw_entities, *(f"G_NODE_{node_id}" for node_id in node_entities)]
            )
            for raw_name, (dimension, tags) in raw_entities.items():
                physical = gmsh.model.addPhysicalGroup(dimension, list(tags))
                gmsh.model.setPhysicalName(dimension, physical, name_map[raw_name])

            gmsh.model.mesh.generate(3)
            gmsh.model.mesh.setOrder(element_order)
            output.parent.mkdir(parents=True, exist_ok=True)
            gmsh.write(str(temporary))
            if not temporary.is_file() or temporary.stat().st_size == 0:
                raise RuntimeError("Gmsh did not write a non-empty MED mesh.")

            analysis_mesh, groups, vertices, faces = _readback(
                model,
                geometry,
                output,
                raw_entities,
                line_entities=line_entities,
                node_entities=node_entities,
            )
            temporary.replace(output)
            return GeneratedPipeVolumeMesh(
                analysis_mesh=analysis_mesh,
                groups=groups,
                surface_vertices=vertices,
                surface_faces=faces,
                gmsh_version=str(gmsh.__version__),
                settings={
                    "element_family": "HEXA20",
                    "element_order": element_order,
                    "max_element_size": max_element_size,
                    **({"line_element_family": "SEG3"} if line_entities else {}),
                },
                med_path=output,
                geometry=geometry,
            )
    finally:
        temporary.unlink(missing_ok=True)


def _require_mesh_settings(
    geometry: VolumeGeometry,
    max_element_size: float,
    element_order: int,
) -> None:
    """Reject mesh settings the geometry cannot carry, before anything is built."""
    if element_order != 2:
        raise ValueError("Native pipe volume meshes require element_order=2.")
    if not math.isfinite(max_element_size) or max_element_size <= 0.0:
        raise ValueError("max_element_size must be positive and finite.")
    if max_element_size > geometry.wall_thickness_m / 2.0:
        raise ValueError("max_element_size must provide at least two elements through the pipe wall.")


def _remaining_line_elements(model: TubaModel, geometry: VolumeGeometry) -> list[Any]:
    selected_ids = set(geometry.element_ids)
    remaining = [element for element in model.elements if element.id not in selected_ids]
    unsupported = [element for element in remaining if element.type != "pipe_straight"]
    if unsupported:
        details = ", ".join(f"{element.id}:{element.type}" for element in unsupported)
        raise ValueError(
            "Native mixed 1D/3D studies currently require straight TUYAU_3M continuation elements; "
            f"unsupported remaining elements: {details}."
        )
    return remaining


def _build_straight_geometry(
    geometry: VolumeGeometry,
) -> tuple[tuple[int, ...], dict[str, tuple[int, ...]]]:
    outer = geometry.outer[0]
    inner = geometry.inner[0]
    outer_tag = gmsh.model.occ.addCylinder(*outer.start, *outer.axis, outer.radius)
    inner_tag = gmsh.model.occ.addCylinder(*inner.start, *inner.axis, inner.radius)
    wall, _lineage = gmsh.model.occ.cut([(3, outer_tag)], [(3, inner_tag)], removeObject=True, removeTool=True)
    gmsh.model.occ.synchronize()
    volumes = tuple(tag for dimension, tag in wall if dimension == 3)
    if len(volumes) != 1:
        raise RuntimeError(f"Expected one pipe-wall volume, got {len(volumes)}.")
    ends, curved = _classify_faces(volumes, geometry)
    if any(len(tags) != 1 for tags in ends.values()) or len(curved) != 2:
        raise RuntimeError("Could not classify the pipe end, inner, and outer surfaces.")
    inner_tag, outer_tag = sorted(curved, key=lambda tag: gmsh.model.occ.getMass(2, tag))
    return volumes, {
        "G_INNER_region_0": (inner_tag,),
        "G_OUTER_region_0": (outer_tag,),
        **{f"G_END_{node_id}": tuple(tags) for node_id, tags in ends.items()},
    }


def _build_bend_geometry(
    geometry: VolumeGeometry,
) -> tuple[tuple[int, ...], dict[str, tuple[int, ...]]]:
    annulus = geometry.swept_annulus
    assert annulus is not None
    outer = gmsh.model.occ.addDisk(
        *annulus.start,
        annulus.outer_radius,
        annulus.outer_radius,
        zAxis=list(annulus.tangent),
        xAxis=list(annulus.radial),
    )
    inner = gmsh.model.occ.addDisk(
        *annulus.start,
        annulus.inner_radius,
        annulus.inner_radius,
        zAxis=list(annulus.tangent),
        xAxis=list(annulus.radial),
    )
    profile, _lineage = gmsh.model.occ.cut([(2, outer)], [(2, inner)], removeObject=True, removeTool=True)
    swept = gmsh.model.occ.revolve(
        profile,
        *annulus.center,
        *annulus.normal,
        math.radians(annulus.angle_deg),
    )
    gmsh.model.occ.synchronize()
    volumes = tuple(tag for dimension, tag in swept if dimension == 3)
    if len(volumes) != 1:
        raise RuntimeError(f"Expected one pipe-bend wall volume, got {len(volumes)}.")
    ends, curved = _classify_faces(volumes, geometry)
    if any(len(tags) != 1 for tags in ends.values()) or len(curved) != 2:
        raise RuntimeError("Could not classify the pipe-bend end, inner, and outer surfaces.")
    inner_tag, outer_tag = sorted(curved, key=lambda tag: gmsh.model.occ.getMass(2, tag))
    return volumes, {
        "G_INNER_region_0": (inner_tag,),
        "G_OUTER_region_0": (outer_tag,),
        **{f"G_END_{node_id}": tuple(tags) for node_id, tags in ends.items()},
    }


def _build_tee_geometry(
    geometry: VolumeGeometry,
) -> tuple[tuple[int, ...], dict[str, tuple[int, ...]]]:
    outer_cylinders = [
        (3, gmsh.model.occ.addCylinder(*solid.start, *solid.axis, solid.radius)) for solid in geometry.outer
    ]
    inner_cylinders = [
        (3, gmsh.model.occ.addCylinder(*solid.start, *solid.axis, solid.radius)) for solid in geometry.inner
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
    ends, curved = _classify_faces(volumes, geometry)
    if any(len(tags) != 1 for tags in ends.values()):
        raise RuntimeError("Could not classify every tee terminal face exactly once.")

    inner_surfaces: list[int] = []
    outer_surfaces: list[int] = []
    for tag in curved:
        points = _surface_sample_points(tag)
        inner_error = _radius_error(points, geometry.inner)
        outer_error = _radius_error(points, geometry.outer)
        (inner_surfaces if inner_error < outer_error else outer_surfaces).append(tag)
    if not inner_surfaces or not outer_surfaces or set(inner_surfaces) & set(outer_surfaces):
        raise RuntimeError("Could not classify disjoint tee inner and outer surfaces.")
    return volumes, {
        "G_INNER_region_0": tuple(inner_surfaces),
        "G_OUTER_region_0": tuple(outer_surfaces),
        **{f"G_END_{node_id}": tuple(tags) for node_id, tags in ends.items()},
    }


def _classify_faces(
    volume_tags: tuple[int, ...],
    geometry: VolumeGeometry,
) -> tuple[dict[str, list[int]], list[int]]:
    """Split a wall solid's boundary into one face per terminal plus the curved faces."""
    boundary = gmsh.model.getBoundary([(3, tag) for tag in volume_tags], oriented=False, recursive=False)
    surface_tags = tuple(sorted({tag for dimension, tag in boundary if dimension == 2}))
    terminal_points = [np.asarray(terminal.point, dtype=float) for terminal in geometry.terminals]
    end_tolerance = max(
        max(float(np.linalg.norm(point - other)) for other in terminal_points)
        for point in terminal_points
    ) * 1e-7
    ends: dict[str, list[int]] = {terminal.node_id: [] for terminal in geometry.terminals}
    curved: list[int] = []
    for tag in surface_tags:
        center = np.asarray(gmsh.model.occ.getCenterOfMass(2, tag), dtype=float)
        end_node = next(
            (
                terminal.node_id
                for terminal, point in zip(geometry.terminals, terminal_points)
                if np.linalg.norm(center - point) <= end_tolerance
            ),
            None,
        )
        if end_node is None:
            curved.append(tag)
        else:
            ends[end_node].append(tag)
    return ends, curved


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
    solids: tuple[Any, ...],
) -> float:
    errors = []
    for point in points:
        candidates = []
        for solid in solids:
            origin = np.asarray(solid.start, dtype=float)
            unit_axis = np.asarray(solid.unit_axis, dtype=float)
            offset = point - origin
            radial_distance = float(np.linalg.norm(offset - np.dot(offset, unit_axis) * unit_axis))
            candidates.append(abs(radial_distance - solid.radius))
        errors.append(min(candidates))
    return float(np.mean(errors))


def _readback(
    model: TubaModel,
    geometry: VolumeGeometry,
    output: Path,
    raw_entities: dict[str, tuple[int, tuple[int, ...]]],
    *,
    line_entities: dict[str, int],
    node_entities: dict[str, int],
) -> tuple[
    AnalysisMesh,
    dict[str, tuple[str, ...]],
    tuple[tuple[float, float, float], ...],
    tuple[tuple[int, ...], ...],
]:
    node_tags, coordinates, _parameters = gmsh.model.mesh.getNodes()
    if not np.isfinite(coordinates).all():
        raise RuntimeError("Gmsh generated non-finite node coordinates.")
    coordinates_by_tag = {
        int(tag): tuple(float(value) for value in coordinates[index * 3 : index * 3 + 3])
        for index, tag in enumerate(node_tags)
    }
    source_ref = (
        EntityRef("node", geometry.tee_node)
        if geometry.tee_node is not None
        else EntityRef("element", geometry.element_ids[0])
    )
    source_metadata = (
        {"source_element_refs": [f"element:{element_id}" for element_id in geometry.element_ids]}
        if geometry.tee_node is not None
        else {}
    )
    nodes = {f"VN{tag}": value for tag, value in coordinates_by_tag.items()}
    node_sources = {
        node_id: MeshNodeSource(
            node_id=node_id,
            source_ref=source_ref,
            role="volume_node",
            metadata=source_metadata,
        )
        for node_id in nodes
    }

    elements: dict[str, tuple[str, ...]] = {}
    element_sources: dict[str, MeshElementSource] = {}
    volume_mesh_tags: list[int] = []
    for volume_tag in raw_entities["G_SOLID_region_0"][1]:
        types, element_tag_blocks, node_tag_blocks = gmsh.model.mesh.getElements(3, volume_tag)
        for element_type, element_tags, element_nodes in zip(types, element_tag_blocks, node_tag_blocks):
            _name, dimension, order, node_count, _local, primary_count = gmsh.model.mesh.getElementProperties(
                element_type
            )
            if dimension != 3 or order != 2 or node_count != 20 or primary_count != 8:
                continue
            for index, element_tag in enumerate(element_tags):
                mesh_id = f"VM{int(element_tag)}"
                start = index * node_count
                elements[mesh_id] = tuple(f"VN{int(tag)}" for tag in element_nodes[start : start + node_count])
                element_sources[mesh_id] = MeshElementSource(
                    element_id=mesh_id,
                    source_ref=source_ref,
                    role="volume_cell",
                    metadata=source_metadata,
                )
                volume_mesh_tags.append(int(element_tag))
    if not volume_mesh_tags:
        raise RuntimeError("Gmsh generated no quadratic hexahedral volume cells.")
    qualities = np.asarray(gmsh.model.mesh.getElementQualities(volume_mesh_tags, "minSJ"), dtype=float)
    if not qualities.size or not np.isfinite(qualities).all() or float(qualities.min()) <= 0.0:
        raise RuntimeError("Gmsh generated an invalid quadratic hexahedral cell.")
    _require_connected_volume(elements)

    line_mesh_ids: list[str] = []
    for source_element_id, entity_tag in line_entities.items():
        types, element_tag_blocks, node_tag_blocks = gmsh.model.mesh.getElements(1, entity_tag)
        for element_type, element_tags, element_nodes in zip(types, element_tag_blocks, node_tag_blocks):
            _name, dimension, order, node_count, _local, primary_count = gmsh.model.mesh.getElementProperties(
                element_type
            )
            if dimension != 1 or order != 2 or node_count != 3 or primary_count != 2:
                continue
            for index, element_tag in enumerate(element_tags):
                mesh_id = f"LM{int(element_tag)}"
                start = index * node_count
                line_node_ids = tuple(
                    f"VN{int(tag)}" for tag in element_nodes[start : start + node_count]
                )
                elements[mesh_id] = line_node_ids
                element_sources[mesh_id] = MeshElementSource(
                    element_id=mesh_id,
                    source_ref=EntityRef("element", source_element_id),
                    role="native_element",
                )
                line_mesh_ids.append(mesh_id)
                for node_id in line_node_ids:
                    node_sources[node_id] = MeshNodeSource(
                        node_id=node_id,
                        source_ref=EntityRef("element", source_element_id),
                        role="generated_element_node",
                    )
    if line_entities and not line_mesh_ids:
        raise RuntimeError("Gmsh generated no quadratic line elements for the mixed pipe region.")

    native_node_ids: dict[str, str] = {}
    for model_node_id, entity_tag in node_entities.items():
        entity_node_tags, _coordinates, _parameters = gmsh.model.mesh.getNodes(0, entity_tag)
        if len(entity_node_tags) != 1:
            raise RuntimeError(f"Gmsh generated no unique node for mixed endpoint {model_node_id!r}.")
        mesh_node_id = f"VN{int(entity_node_tags[0])}"
        native_node_ids[model_node_id] = mesh_node_id
        node_sources[mesh_node_id] = MeshNodeSource(
            node_id=mesh_node_id,
            source_ref=EntityRef("node", model_node_id),
            role="native_node",
        )

    groups: dict[str, tuple[str, ...]] = {
        raw_name: tuple(elements)
        for raw_name, (dimension, _entity_tags) in raw_entities.items()
        if dimension == 3
    }
    if line_mesh_ids:
        groups["G_TUBE"] = tuple(line_mesh_ids)
        groups.update(
            {
                f"G_NODE_{model_node_id}": (mesh_node_id,)
                for model_node_id, mesh_node_id in native_node_ids.items()
            }
        )
    surface_quad_nodes: list[tuple[int, int, int, int]] = []
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
                if cell_dimension != 2 or primary_count != 4:
                    continue
                for index, element_tag in enumerate(element_tags):
                    tags = tuple(int(tag) for tag in element_nodes[index * node_count : index * node_count + 4])
                    mesh_ids.append(f"VS{int(element_tag)}")
                    surface_quad_nodes.append(tags)
        groups[raw_name] = tuple(mesh_ids)
        if not groups[raw_name]:
            raise RuntimeError(f"Gmsh generated an empty physical group {raw_name!r}.")

    skin_tags = tuple(dict.fromkeys(tag for face in surface_quad_nodes for tag in face))
    skin_indices = {tag: index for index, tag in enumerate(skin_tags)}
    vertices = tuple(coordinates_by_tag[tag] for tag in skin_tags)
    faces = tuple(tuple(skin_indices[tag] for tag in face) for face in surface_quad_nodes)
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
        modelisations={
            "G_SOLID_region_0": "3D",
            **({"G_TUBE": "TUYAU_3M"} if line_mesh_ids else {}),
        },
        surface_mesh={
            "vertices": vertices,
            "faces": faces,
            "node_ids": [f"VN{tag}" for tag in skin_tags],
        },
        geometry_ref=geometry.id,
    )
    return analysis_mesh, groups, vertices, faces


def _require_connected_volume(elements: dict[str, tuple[str, ...]]) -> None:
    neighbours = {element_id: set() for element_id in elements}
    face_owner: dict[frozenset[str], str] = {}
    for element_id, node_ids in elements.items():
        corners = node_ids[:8]
        for indices in (
            (0, 1, 2, 3),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        ):
            face = frozenset(corners[index] for index in indices)
            owner = face_owner.setdefault(face, element_id)
            if owner != element_id:
                neighbours[element_id].add(owner)
                neighbours[owner].add(element_id)
    visited: set[str] = set()
    pending = [next(iter(elements))]
    while pending:
        element_id = pending.pop()
        if element_id in visited:
            continue
        visited.add(element_id)
        pending.extend(neighbours[element_id] - visited)
    if len(visited) != len(elements):
        raise RuntimeError("Gmsh generated a disconnected volume mesh.")
