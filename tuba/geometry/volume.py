"""The solid geometry a pipe-volume study discretises.

One record, one builder: :func:`build_volume_geometry` is the only place that
decides what wall solid a selected set of pipe elements forms. The Gmsh mesher
translates this record into OCC operations, the solver-input fingerprint hashes
it, and the scene reads its terminals and provenance. Nothing downstream
re-derives the geometry for itself.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np

from tuba.canonical import canonical_digest
from tuba.geometry.junctions import classify_tee_junction
from tuba.model import BendGeometry, PipeSection, TubaModel, sample_bend_geometry

Vector = tuple[float, float, float]

#: Terminal roles in a tee; a single run's ends are plain ``run`` terminals.
TERMINAL_ROLES = ("run", "header", "branch")

VOLUME_GEOMETRY_KINDS = ("straight", "bend", "tee")


def _vector(values: Iterable[float]) -> Vector:
    return tuple(float(value) for value in values)


def _normalized(values: Iterable[float]) -> Vector:
    vector = np.asarray(tuple(values), dtype=float)
    length = float(np.linalg.norm(vector))
    if length <= 0.0:
        raise ValueError("Geometry vectors must be non-zero.")
    return _vector(vector / length)


@dataclass(frozen=True)
class CylinderSolid:
    """A finite circular cylinder envelope: one run's outer wall or bore."""

    start: Vector
    axis: Vector
    radius: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.radius) or self.radius <= 0.0:
            raise ValueError("CylinderSolid radius must be positive and finite.")
        if not np.isfinite(np.asarray(self.axis, dtype=float)).all():
            raise ValueError("CylinderSolid axis must be finite.")
        if float(np.linalg.norm(np.asarray(self.axis, dtype=float))) <= 0.0:
            raise ValueError("CylinderSolid axis must be non-zero.")

    @property
    def unit_axis(self) -> Vector:
        return _normalized(self.axis)

    @property
    def length_m(self) -> float:
        return float(np.linalg.norm(np.asarray(self.axis, dtype=float)))

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "cylinder", "start": list(self.start), "axis": list(self.axis), "radius": self.radius}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CylinderSolid":
        return cls(start=_vector(data["start"]), axis=_vector(data["axis"]), radius=float(data["radius"]))


@dataclass(frozen=True)
class SweptAnnulusSolid:
    """A pipe-bend wall: an annulus of *outer_radius*/*inner_radius* swept about *normal*."""

    start: Vector
    tangent: Vector
    radial: Vector
    center: Vector
    normal: Vector
    angle_deg: float
    outer_radius: float
    inner_radius: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.angle_deg) or not 0.0 < self.angle_deg < 360.0:
            raise ValueError("SweptAnnulusSolid angle_deg must be between 0 and 360 degrees.")
        if not math.isfinite(self.outer_radius) or not math.isfinite(self.inner_radius):
            raise ValueError("SweptAnnulusSolid radii must be finite.")
        if self.inner_radius <= 0.0 or self.outer_radius <= self.inner_radius:
            raise ValueError("SweptAnnulusSolid requires a positive bore inside a larger outer radius.")

    @property
    def wall_thickness_m(self) -> float:
        return self.outer_radius - self.inner_radius

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "swept_annulus",
            "start": list(self.start),
            "tangent": list(self.tangent),
            "radial": list(self.radial),
            "center": list(self.center),
            "normal": list(self.normal),
            "angle_deg": self.angle_deg,
            "outer_radius": self.outer_radius,
            "inner_radius": self.inner_radius,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SweptAnnulusSolid":
        return cls(
            start=_vector(data["start"]),
            tangent=_vector(data["tangent"]),
            radial=_vector(data["radial"]),
            center=_vector(data["center"]),
            normal=_vector(data["normal"]),
            angle_deg=float(data["angle_deg"]),
            outer_radius=float(data["outer_radius"]),
            inner_radius=float(data["inner_radius"]),
        )


@dataclass(frozen=True)
class VolumeTerminal:
    """An open end of the wall solid: the node it lands on and the run's role."""

    node_id: str
    element_id: str
    point: Vector
    role: str

    def __post_init__(self) -> None:
        if not self.node_id or not self.element_id:
            raise ValueError("VolumeTerminal node_id and element_id must not be empty.")
        if self.role not in TERMINAL_ROLES:
            raise ValueError(f"VolumeTerminal role must be one of {TERMINAL_ROLES}, got {self.role!r}.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "element_id": self.element_id,
            "point": list(self.point),
            "role": self.role,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VolumeTerminal":
        return cls(
            node_id=str(data["node_id"]),
            element_id=str(data["element_id"]),
            point=_vector(data["point"]),
            role=str(data["role"]),
        )


@dataclass(frozen=True)
class VolumeGeometry:
    """The wall solid a pipe-volume selection forms, independent of any mesher.

    ``outer`` cylinders are fused and then the fused ``inner`` cylinders are cut
    from them; a bend is one ``swept_annulus`` instead. ``fingerprint`` is the
    canonical digest of that definition, so the mesh, the solver-input identity,
    and the scene all pin the same solid.
    """

    id: str
    fingerprint: str
    kind: str
    element_ids: tuple[str, ...]
    material: str
    outer: tuple[CylinderSolid, ...]
    inner: tuple[CylinderSolid, ...]
    swept_annulus: SweptAnnulusSolid | None
    terminals: tuple[VolumeTerminal, ...]
    tee_node: str | None = None
    header_element_ids: tuple[str, ...] = ()
    branch_element_id: str | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.fingerprint:
            raise ValueError("VolumeGeometry id and fingerprint must not be empty.")
        if self.kind not in VOLUME_GEOMETRY_KINDS:
            raise ValueError(f"VolumeGeometry kind must be one of {VOLUME_GEOMETRY_KINDS}, got {self.kind!r}.")
        if not self.element_ids:
            raise ValueError("VolumeGeometry must name at least one element.")
        if not self.terminals:
            raise ValueError("VolumeGeometry must carry at least one terminal.")
        if self.kind == "bend":
            if self.swept_annulus is None or self.outer or self.inner:
                raise ValueError("A bend VolumeGeometry is one swept annulus and no cylinders.")
        elif self.kind == "straight":
            if self.swept_annulus is not None or len(self.outer) != 1 or len(self.inner) != 1:
                raise ValueError("A straight VolumeGeometry is one outer and one inner cylinder.")
        elif self.kind == "tee":
            if self.swept_annulus is not None or len(self.outer) != 2 or len(self.inner) != 2:
                raise ValueError("A tee VolumeGeometry is a header and branch outer/inner cylinder pair.")
            if self.tee_node is None or not self.header_element_ids or self.branch_element_id is None:
                raise ValueError("A tee VolumeGeometry must name its junction, header runs, and branch run.")

    @property
    def wall_thickness_m(self) -> float:
        """The thinnest wall in the region, the one the mesh element size is checked against."""
        if self.swept_annulus is not None:
            return self.swept_annulus.wall_thickness_m
        return min(outer.radius - inner.radius for outer, inner in zip(self.outer, self.inner))

    def definition(self) -> dict[str, Any]:
        """The geometry definition the fingerprint hashes; identity fields stay out."""
        return {
            "kind": self.kind,
            "element_ids": list(self.element_ids),
            "material": self.material,
            "outer": [solid.to_dict() for solid in self.outer],
            "inner": [solid.to_dict() for solid in self.inner],
            "swept_annulus": self.swept_annulus.to_dict() if self.swept_annulus is not None else None,
            "terminals": [terminal.to_dict() for terminal in self.terminals],
            "tee_node": self.tee_node,
            "header_element_ids": list(self.header_element_ids),
            "branch_element_id": self.branch_element_id,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "fingerprint": self.fingerprint, **self.definition()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VolumeGeometry":
        return cls(
            id=str(data["id"]),
            fingerprint=str(data["fingerprint"]),
            kind=str(data["kind"]),
            element_ids=tuple(str(value) for value in data["element_ids"]),
            material=str(data["material"]),
            outer=tuple(CylinderSolid.from_dict(item) for item in data.get("outer", ())),
            inner=tuple(CylinderSolid.from_dict(item) for item in data.get("inner", ())),
            swept_annulus=(
                SweptAnnulusSolid.from_dict(data["swept_annulus"])
                if data.get("swept_annulus") is not None
                else None
            ),
            terminals=tuple(VolumeTerminal.from_dict(item) for item in data["terminals"]),
            tee_node=data.get("tee_node"),
            header_element_ids=tuple(str(value) for value in data.get("header_element_ids", ())),
            branch_element_id=data.get("branch_element_id"),
        )


@dataclass(frozen=True)
class _Run:
    element_id: str
    n1: str
    n2: str
    start: Vector
    end: Vector
    section: PipeSection
    material: str
    bend_geometry: BendGeometry | None

    def terminal_point(self, node_id: str) -> Vector:
        return self.start if node_id == self.n1 else self.end

    def terminal_node(self, junction: str) -> str:
        return self.n2 if self.n1 == junction else self.n1


def build_volume_geometry(
    model: TubaModel,
    element_ids: Iterable[str],
) -> VolumeGeometry:
    """Derive the wall solid for one straight pipe, one bend, or one explicit tee.

    This owns every geometry decision the mesher used to make inline: selection
    validation, run directions, the tee header/branch classification, and the
    outer/inner envelope dimensions.
    """
    ids = tuple(element_ids)
    if len(ids) not in {1, 3} or len(set(ids)) != len(ids):
        raise ValueError("Select one pipe_straight or the three unique runs of one explicit tee.")
    runs = [_selected_run(model, element_id, single=len(ids) == 1) for element_id in ids]
    materials = {run.material for run in runs}
    if len(materials) != 1:
        raise ValueError("A native pipe volume region must use one material.")
    if len(runs) == 1:
        return _single_run_geometry(runs[0])
    return _tee_geometry(model, runs)


def _selected_run(model: TubaModel, element_id: str, *, single: bool) -> _Run:
    element = model.get_element(element_id)
    if element is None:
        raise ValueError(f"Unknown selected element {element_id!r}.")
    if element.type not in {"pipe_straight", "pipe_bend"} or (not single and element.type != "pipe_straight"):
        raise ValueError(
            f"Selected element {element.id!r} must be an isolated pipe_bend or pipe_straight, "
            f"got {element.type!r}."
        )
    section = model.sections.get(element.section)
    if not isinstance(section, PipeSection):
        raise ValueError(f"Selected element {element.id!r} must use a circular PipeSection.")
    if section.ID <= 0.0 or section.WT <= 0.0:
        raise ValueError(f"Pipe section {section.name!r} must have positive bore and wall thickness.")
    if element.material not in model.materials:
        raise ValueError(f"Selected element {element.id!r} references missing material {element.material!r}.")
    start = _vector(model.nodes[element.n1].coords)
    end = _vector(model.nodes[element.n2].coords)
    direction = np.asarray(end, dtype=float) - np.asarray(start, dtype=float)
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
    return _Run(element.id, element.n1, element.n2, start, end, section, element.material, bend_geometry)


def _single_run_geometry(run: _Run) -> VolumeGeometry:
    if run.bend_geometry is not None:
        annulus = _bend_annulus(run)
        return _assemble(
            kind="bend",
            runs=(run,),
            outer=(),
            inner=(),
            swept_annulus=annulus,
            terminals=(
                VolumeTerminal(run.n1, run.element_id, run.start, "run"),
                VolumeTerminal(run.n2, run.element_id, run.end, "run"),
            ),
        )
    outer = CylinderSolid(run.start, _vector(np.asarray(run.end) - np.asarray(run.start)), run.section.OD / 2.0)
    inner = CylinderSolid(run.start, outer.axis, run.section.ID / 2.0)
    return _assemble(
        kind="straight",
        runs=(run,),
        outer=(outer,),
        inner=(inner,),
        swept_annulus=None,
        terminals=(
            VolumeTerminal(run.n1, run.element_id, run.start, "run"),
            VolumeTerminal(run.n2, run.element_id, run.end, "run"),
        ),
    )


def _bend_annulus(run: _Run) -> SweptAnnulusSolid:
    geometry = run.bend_geometry
    assert geometry is not None
    start = np.asarray(run.start, dtype=float)
    center = np.asarray(geometry.center, dtype=float)
    return SweptAnnulusSolid(
        start=run.start,
        tangent=_normalized(geometry.start_tangent),
        radial=_normalized(start - center),
        center=_vector(center),
        normal=_normalized(geometry.normal),
        angle_deg=float(geometry.angle),
        outer_radius=run.section.OD / 2.0,
        inner_radius=run.section.ID / 2.0,
    )


def _tee_geometry(model: TubaModel, runs: list[_Run]) -> VolumeGeometry:
    ids = tuple(sorted(run.element_id for run in runs))
    common_nodes = set.intersection(*({run.n1, run.n2} for run in runs))
    if len(common_nodes) != 1:
        raise ValueError("The three selected pipe_straight elements must share one junction node.")
    tee_node = common_nodes.pop()
    if tee_node not in model.tees:
        raise ValueError(f"Junction {tee_node!r} must have an explicit tee definition.")
    classified = classify_tee_junction(model, tee_node, element_ids=ids)
    by_id = {run.element_id: run for run in runs}
    header_runs = [by_id[element_id] for element_id in classified.header_element_ids]
    if not math.isclose(header_runs[0].section.OD, header_runs[1].section.OD) or not math.isclose(
        header_runs[0].section.WT, header_runs[1].section.WT
    ):
        raise ValueError("The two tee header runs must use matching pipe dimensions.")
    branch_run = by_id[classified.branch_element_id]
    if branch_run.section.OD > header_runs[0].section.OD:
        raise ValueError("The tee branch OD cannot exceed the header OD.")

    junction = np.asarray(model.nodes[tee_node].coords, dtype=float)
    header_ends = [
        np.asarray(run.terminal_point(run.terminal_node(tee_node)), dtype=float) for run in header_runs
    ]
    header_axis = _vector(header_ends[1] - header_ends[0])
    branch_end = np.asarray(
        branch_run.terminal_point(branch_run.terminal_node(tee_node)), dtype=float
    )
    branch_axis = _vector(branch_end - junction)
    outer = (
        CylinderSolid(_vector(header_ends[0]), header_axis, header_runs[0].section.OD / 2.0),
        CylinderSolid(_vector(junction), branch_axis, branch_run.section.OD / 2.0),
    )
    inner = (
        CylinderSolid(outer[0].start, outer[0].axis, header_runs[0].section.ID / 2.0),
        CylinderSolid(outer[1].start, outer[1].axis, branch_run.section.ID / 2.0),
    )
    terminals = tuple(
        VolumeTerminal(
            node_id=run.terminal_node(tee_node),
            element_id=run.element_id,
            point=run.terminal_point(run.terminal_node(tee_node)),
            role=("header" if run.element_id in classified.header_element_ids else "branch"),
        )
        for run in (header_runs[0], header_runs[1], branch_run)
    )
    return _assemble(
        kind="tee",
        runs=tuple(sorted(runs, key=lambda run: run.element_id)),
        outer=outer,
        inner=inner,
        swept_annulus=None,
        terminals=terminals,
        tee_node=tee_node,
        header_element_ids=tuple(classified.header_element_ids),
        branch_element_id=classified.branch_element_id,
    )


def _assemble(
    *,
    kind: str,
    runs: tuple[_Run, ...],
    outer: tuple[CylinderSolid, ...],
    inner: tuple[CylinderSolid, ...],
    swept_annulus: SweptAnnulusSolid | None,
    terminals: tuple[VolumeTerminal, ...],
    tee_node: str | None = None,
    header_element_ids: tuple[str, ...] = (),
    branch_element_id: str | None = None,
) -> VolumeGeometry:
    definition = {
        "kind": kind,
        "element_ids": sorted(run.element_id for run in runs),
        "material": runs[0].material,
        "outer": [solid.to_dict() for solid in outer],
        "inner": [solid.to_dict() for solid in inner],
        "swept_annulus": swept_annulus.to_dict() if swept_annulus is not None else None,
        "terminals": [terminal.to_dict() for terminal in terminals],
        "tee_node": tee_node,
        "header_element_ids": list(header_element_ids),
        "branch_element_id": branch_element_id,
    }
    fingerprint = canonical_digest(definition)
    return VolumeGeometry(
        id=f"volume_geometry:{fingerprint[:16]}",
        fingerprint=fingerprint,
        kind=kind,
        element_ids=tuple(definition["element_ids"]),
        material=runs[0].material,
        outer=outer,
        inner=inner,
        swept_annulus=swept_annulus,
        terminals=terminals,
        tee_node=tee_node,
        header_element_ids=header_element_ids,
        branch_element_id=branch_element_id,
    )
