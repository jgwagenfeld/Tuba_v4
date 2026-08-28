"""
tuba.builder — Cursor-based procedural DSL for piping geometry.

The PipingBuilder maintains a 3-D cursor (position + forward direction)
and translates high-level commands (run, bend, support) into nodes and
elements on the parent TubaModel.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, List, Optional

import numpy as np


def _rotate_about_axis(vector: np.ndarray, axis: np.ndarray, angle: float) -> np.ndarray:
    """Rotate *vector* with Rodrigues' formula."""
    axis = axis / np.linalg.norm(axis)
    return (
        vector * np.cos(angle)
        + np.cross(axis, vector) * np.sin(angle)
        + axis * np.dot(axis, vector) * (1.0 - np.cos(angle))
    )


class PipingBuilder:
    """Fluent builder that constructs piping geometry by advancing a cursor.

    Usage::

        with model.pipe(section="4inch_sch40", material="P265GH") as b:
            b.start([0, 0, 0], support="anchor")
            b.run(5.0)
            b.bend(radius=0.1524, angle=90, plane="XY")
            b.run(3.0)
            b.end([5, 3, 0], support="anchor")
    """

    def __init__(
        self,
        model,
        section_name: str,
        material_name: str,
        route_id: Optional[str] = None,
        station: float = 0.0,
    ):
        from tuba.model import TubaModel

        self.model: TubaModel = model
        self.section_name = section_name
        self.material_name = material_name
        self.route_id = route_id
        self.station = float(station)

        self.cursor: np.ndarray = np.zeros(3)
        self.direction: np.ndarray = np.array([1.0, 0.0, 0.0])
        self.up_vector: np.ndarray = np.array([0.0, 0.0, 1.0])

        self.last_node_id: Optional[str] = None

        # Re-evaluable record of every geometry command, for regeneration.
        self.steps: List["BuildStep"] = []

    def _record(self, op: str, **params: Any) -> None:
        """Record one command so the run can be re-emitted from :attr:`recipe`."""
        self.steps.append(BuildStep(op=op, params=params))

    @property
    def recipe(self) -> "PipeRunRecipe":
        """Retained, re-evaluable description of everything built so far.

        Replay it with :meth:`PipeRunRecipe.build` on a fresh model, optionally
        after tweaking a step (:meth:`PipeRunRecipe.with_step_params`), to
        regenerate the geometry with changed lengths/angles.
        """
        return PipeRunRecipe(
            section=self.section_name,
            material=self.material_name,
            steps=list(self.steps),
            up_vector=tuple(float(x) for x in self.up_vector),
            route_id=self.route_id,
        )

    # -- Geometry commands ---------------------------------------------------

    def start(
        self,
        point: List[float],
        support: Optional[str] = None,
    ) -> "PipingBuilder":
        """Set the initial cursor position and create the starting node."""
        self._record("start", point=[float(x) for x in point], support=support)
        self.cursor = np.asarray(point, dtype=float)
        
        # Reuse an existing node at this coordinate to enable branching.
        existing_nid = self.model.find_node_by_point(self.cursor, tol=1e-5)
        if existing_nid is not None:
            self.last_node_id = existing_nid
        else:
            self.last_node_id = self.model.add_node(self.cursor)

        if support:
            self.model.add_support(self.last_node_id, support)
        return self

    def run(self, length: float) -> "PipingBuilder":
        """Extend a straight pipe segment of *length* [m] in the current direction."""
        self._record("run", length=length)
        target = self.cursor + self.direction * length
        node_id = self.model.add_node(target)
        elem_id = self.model.next_element_id("pipe_str")
        station_start = self.station
        station_end = station_start + abs(float(length))

        self.model.add_element(
            id=elem_id,
            type="pipe_straight",
            n1=self.last_node_id,
            n2=node_id,
            section=self.section_name,
            material=self.material_name,
            route_id=self.route_id,
            station_start=station_start,
            station_end=station_end,
        )
        self.cursor = target
        self.station = station_end
        self.last_node_id = node_id
        return self

    def bend(
        self,
        radius: float,
        angle: float,
        plane: str = "XY",
    ) -> "PipingBuilder":
        """Insert an elbow/bend and rotate the forward direction.

        Parameters
        ----------
        radius : float
            Bend radius [m].
        angle : float
            Rotation angle [degrees].  Positive = counter-clockwise when
            looking down the rotation axis.
        plane : str
            Plane in which the bend occurs: ``"XY"``, ``"XZ"``, or ``"YZ"``.
        """
        self._record("bend", radius=radius, angle=angle, plane=plane)
        return self._bend_with_axis(
            radius=radius,
            angle=angle,
            axis=self._axis_for_plane(plane),
            mode="bend",
        )

    def bend_in_plane(
        self,
        radius: float,
        angle: float,
        normal: List[float],
    ) -> "PipingBuilder":
        """Insert a bend whose plane is defined by its normal vector."""
        normal_values = [float(value) for value in normal]
        self._record("bend_in_plane", radius=radius, angle=angle, normal=normal_values)
        return self._bend_with_axis(
            radius=radius,
            angle=angle,
            axis=np.asarray(normal_values, dtype=float),
            mode="bend_in_plane",
        )

    def bend_by_orientation(
        self,
        radius: float,
        angle: float,
        axis: List[float],
    ) -> "PipingBuilder":
        """Insert a bend by rotating the current direction around *axis*."""
        axis_values = [float(value) for value in axis]
        self._record("bend_by_orientation", radius=radius, angle=angle, axis=axis_values)
        return self._bend_with_axis(
            radius=radius,
            angle=angle,
            axis=np.asarray(axis_values, dtype=float),
            mode="bend_by_orientation",
        )

    def bend_to(
        self,
        point: List[float],
        radius: float,
        plane_normal: Optional[List[float]] = None,
    ) -> "PipingBuilder":
        """Insert a circular bend ending at *point* with explicit geometry."""
        point_values = [float(value) for value in point]
        normal_values = None if plane_normal is None else [float(value) for value in plane_normal]
        self._record("bend_to", point=point_values, radius=radius, plane_normal=normal_values)

        from tuba.model import make_bend_geometry

        target = np.asarray(point_values, dtype=float)
        chord = target - self.cursor
        chord_len = float(np.linalg.norm(chord))
        if chord_len <= 1e-12:
            raise ValueError("bend_to target must differ from the current cursor.")
        if chord_len > 2.0 * float(radius) + 1e-9:
            raise ValueError("bend_to target is too far away for the requested bend radius.")
        if plane_normal is None:
            if abs(chord_len - 2.0 * float(radius)) <= 1e-9:
                raise ValueError("180-degree bend_to requires an explicit plane_normal.")
            normal = np.cross(self.direction, chord)
            if np.linalg.norm(normal) <= 1e-12:
                normal = np.cross(self.up_vector, chord)
            if np.linalg.norm(normal) <= 1e-12:
                raise ValueError("bend_to requires a plane_normal for this target direction.")
        else:
            normal = np.asarray(plane_normal, dtype=float)

        angle = math.degrees(2.0 * math.asin(min(1.0, chord_len / (2.0 * float(radius)))))
        provisional_end = np.cross(normal, target - self.cursor)
        if np.linalg.norm(provisional_end) <= 1e-12:
            provisional_end = chord
        geometry = make_bend_geometry(
            start=self.cursor,
            end=target,
            radius=radius,
            angle=angle,
            normal=normal,
            start_tangent=self.direction,
            end_tangent=provisional_end,
            generation_mode="bend_to",
        )

        station_start = self.station
        station_end = station_start + float(radius) * math.radians(abs(geometry.angle))
        exit_node_id = self.model.add_node(target)
        elem_id = self.model.next_element_id("pipe_bend")
        self.model.add_element(
            id=elem_id,
            type="pipe_bend",
            n1=self.last_node_id,
            n2=exit_node_id,
            section=self.section_name,
            material=self.material_name,
            bend_radius=float(radius),
            bend_angle=float(geometry.angle),
            bend_geometry=geometry,
            route_id=self.route_id,
            station_start=station_start,
            station_end=station_end,
        )
        self.direction = np.asarray(geometry.end_tangent, dtype=float)
        self.cursor = target
        self.station = station_end
        self.last_node_id = exit_node_id
        return self

    def _bend_with_axis(
        self,
        *,
        radius: float,
        angle: float,
        axis: np.ndarray,
        mode: str,
    ) -> "PipingBuilder":
        if np.linalg.norm(axis) <= 1e-12:
            raise ValueError("Bend axis must be non-zero.")
        axis = axis / np.linalg.norm(axis)
        theta = np.radians(angle)
        new_direction = _rotate_about_axis(self.direction, axis, theta)
        new_direction /= np.linalg.norm(new_direction)

        tangent_len = radius * abs(np.tan(theta / 2.0))
        bend_entry = self.cursor + self.direction * tangent_len
        bend_exit = bend_entry + new_direction * tangent_len

        from tuba.model import make_bend_geometry

        geometry = make_bend_geometry(
            start=self.cursor,
            end=bend_exit,
            radius=radius,
            angle=angle,
            normal=axis,
            start_tangent=self.direction,
            end_tangent=new_direction,
            generation_mode=mode,
        )
        station_start = self.station
        station_end = station_start + float(radius) * abs(theta)
        exit_node_id = self.model.add_node(bend_exit)
        elem_id = self.model.next_element_id("pipe_bend")
        self.model.add_element(
            id=elem_id,
            type="pipe_bend",
            n1=self.last_node_id,
            n2=exit_node_id,
            section=self.section_name,
            material=self.material_name,
            bend_radius=radius,
            bend_angle=angle,
            bend_geometry=geometry,
            route_id=self.route_id,
            station_start=station_start,
            station_end=station_end,
        )
        self.direction = new_direction
        self.cursor = bend_exit
        self.station = station_end
        self.last_node_id = exit_node_id
        return self

    def _axis_for_plane(self, plane: str) -> np.ndarray:
        if plane == "XY":
            return self.up_vector.copy()
        if plane == "XZ":
            axis = np.cross(self.direction, self.up_vector)
            norm = np.linalg.norm(axis)
            if norm < 1e-12:
                return np.array([0.0, 1.0, 0.0])
            return axis / norm
        return self.direction.copy()

    def add_support(
        self,
        type: str,
        direction: Optional[List[float]] = None,
        stiffness: Optional[float] = None,
        stiffness_matrix: Optional[List[float]] = None,
        blocked_dof: Optional[List[Any]] = None,
        mass: float = 0.0,
        friction_coefficient: float = 0.0,
    ) -> "PipingBuilder":
        """Attach a support to the last created node."""
        if type == "spring" and stiffness is not None and stiffness_matrix is None and direction is None:
            raise ValueError(
                "Spring supports require a direction with scalar stiffness, "
                "or use stiffness_matrix=[Kx, Ky, Kz, Krx, Kry, Krz]. "
                "For v2-style springs, call spring(x=..., y=..., z=..., rx=..., ry=..., rz=...)."
            )
        self._record(
            "add_support",
            type=type,
            direction=(None if direction is None else [float(x) for x in direction]),
            stiffness=stiffness,
            stiffness_matrix=stiffness_matrix,
            blocked_dof=blocked_dof,
            mass=mass,
            friction_coefficient=friction_coefficient,
        )
        self.model.add_support(
            self.last_node_id,
            type,
            direction=direction,
            stiffness=stiffness,
            stiffness_matrix=stiffness_matrix,
            blocked_dof=blocked_dof,
            mass=mass,
            friction_coefficient=friction_coefficient,
        )
        return self

    def spring(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        rx: float = 0.0,
        ry: float = 0.0,
        rz: float = 0.0,
        reference: str = "global",
    ) -> "PipingBuilder":
        """Attach a v2-style six-DOF spring to the last created node."""
        if reference != "global":
            raise ValueError("Spring reference must be 'global'; local spring references are not implemented in v4.")
        return self.add_support(
            type="spring",
            stiffness_matrix=[x, y, z, rx, ry, rz],
        )

    def run_element(self, length: float, element_type: str = "pipe_straight", twist_angle: float = 0.0) -> "PipingBuilder":
        """Extend a segment of *length* [m] in the current direction with a specific element type."""
        self._record("run_element", length=length, element_type=element_type, twist_angle=twist_angle)
        target = self.cursor + self.direction * length
        node_id = self.model.add_node(target)

        prefix = "pipe_str"
        if element_type == "beam":
            prefix = "beam"
        elif element_type == "bar":
            prefix = "bar"
        elif element_type == "cable":
            prefix = "cable"

        elem_id = self.model.next_element_id(prefix)
        station_start = self.station
        station_end = station_start + abs(float(length))

        self.model.add_element(
            id=elem_id,
            type=element_type,
            n1=self.last_node_id,
            n2=node_id,
            section=self.section_name,
            material=self.material_name,
            twist_angle=twist_angle,
            route_id=self.route_id,
            station_start=station_start,
            station_end=station_end,
        )
        self.cursor = target
        self.station = station_end
        self.last_node_id = node_id
        return self

    def beam(self, length: float, twist_angle: float = 0.0) -> "PipingBuilder":
        """Add a beam element of *length* [m] in the current direction."""
        return self.run_element(length, "beam", twist_angle)

    def bar(self, length: float) -> "PipingBuilder":
        """Add a bar element of *length* [m] in the current direction."""
        return self.run_element(length, "bar")

    def cable(self, length: float) -> "PipingBuilder":
        """Add a cable element of *length* [m] in the current direction."""
        return self.run_element(length, "cable")


    def end(
        self,
        point: Optional[List[float]] = None,
        support: Optional[str] = None,
    ) -> "PipingBuilder":
        """Terminate the piping run.

        If *point* is given and differs from the current cursor, a final
        straight segment is inserted to connect to that point.
        """
        self._record("end", point=(None if point is None else [float(x) for x in point]), support=support)
        if point is not None:
            target = np.asarray(point, dtype=float)
            dist = np.linalg.norm(target - self.cursor)
            if dist > 1e-6:
                # Insert a closing straight run
                node_id = self.model.add_node(target)
                elem_id = self.model.next_element_id("pipe_str")
                self.model.add_element(
                    id=elem_id,
                    type="pipe_straight",
                    n1=self.last_node_id,
                    n2=node_id,
                    section=self.section_name,
                    material=self.material_name,
                    route_id=self.route_id,
                    station_start=self.station,
                    station_end=self.station + dist,
                )
                self.cursor = target
                self.station += dist
                self.last_node_id = node_id

        if support:
            self.model.add_support(self.last_node_id, support)
        return self

    def set_direction(self, direction: List[float]) -> "PipingBuilder":
        """Override the current forward direction vector."""
        self._record("set_direction", direction=[float(x) for x in direction])
        d = np.asarray(direction, dtype=float)
        self.direction = d / np.linalg.norm(d)
        return self


# ---------------------------------------------------------------------------
# Re-evaluable pipe-run recipe (geometry regeneration)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BuildStep:
    """One recorded :class:`PipingBuilder` command: the method name + kwargs."""

    op: str
    params: dict

    def to_dict(self) -> dict:
        return {"op": self.op, "params": dict(self.params)}

    @classmethod
    def from_dict(cls, data: dict) -> "BuildStep":
        return cls(op=data["op"], params=dict(data.get("params", {})))


@dataclass(frozen=True)
class BuiltRun:
    """Ids created by replaying a :class:`PipeRunRecipe` onto a model."""

    node_ids: List[str]
    element_ids: List[str]


@dataclass
class PipeRunRecipe:
    """Retained, re-evaluable description of a pipe run.

    Capture it from a builder (``builder.recipe``), then :meth:`build` it onto a
    model. Because it replays the same DSL commands, tweaking a step and
    rebuilding regenerates the geometry — change a run length or bend angle and
    re-emit onto a fresh model::

        with model.pipe("DN100", "steel") as b:
            b.start([0, 0, 0]).run(2.0).bend(radius=0.15, angle=90).run(3.0).end()
        recipe = b.recipe

        longer = recipe.with_step_params(1, length=5.0)   # step 1 = first run
        longer.build(fresh_model)                          # regenerated geometry

    The recipe is JSON-serializable (:meth:`to_dict` / :meth:`from_dict`), so a
    parametric run can be persisted and regenerated later.
    """

    section: str
    material: str
    steps: List[BuildStep] = field(default_factory=list)
    up_vector: tuple = (0.0, 0.0, 1.0)
    route_id: Optional[str] = None

    def build(self, model) -> BuiltRun:
        """Replay the recorded commands onto *model*; return the ids created.

        Created ids are found by diffing the model's nodes/elements before and
        after replay, so the same recipe can be re-emitted onto any model.
        """
        nodes_before = set(model.nodes)
        elements_before = {elem.id for elem in model.elements}

        builder = PipingBuilder(
            model=model,
            section_name=self.section,
            material_name=self.material,
            route_id=self.route_id,
        )
        builder.up_vector = np.asarray(self.up_vector, dtype=float)
        for step in self.steps:
            getattr(builder, step.op)(**step.params)

        new_nodes = [nid for nid in model.nodes if nid not in nodes_before]
        new_elements = [elem.id for elem in model.elements if elem.id not in elements_before]
        return BuiltRun(node_ids=new_nodes, element_ids=new_elements)

    def with_step_params(self, index: int, **params: Any) -> "PipeRunRecipe":
        """Return a copy with *params* merged into the step at *index*.

        This is the regeneration hook: tweak one command's parameters (e.g. a
        run ``length`` or bend ``angle``) and :meth:`build` the result.
        """
        steps = list(self.steps)
        old = steps[index]
        steps[index] = BuildStep(op=old.op, params={**old.params, **params})
        return PipeRunRecipe(
            section=self.section,
            material=self.material,
            steps=steps,
            up_vector=self.up_vector,
            route_id=self.route_id,
        )

    def to_dict(self) -> dict:
        return {
            "section": self.section,
            "material": self.material,
            "up_vector": [float(x) for x in self.up_vector],
            **({"route_id": self.route_id} if self.route_id is not None else {}),
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PipeRunRecipe":
        return cls(
            section=data["section"],
            material=data["material"],
            steps=[BuildStep.from_dict(step) for step in data.get("steps", [])],
            up_vector=tuple(data.get("up_vector", (0.0, 0.0, 1.0))),
            route_id=data.get("route_id"),
        )
