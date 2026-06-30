"""
tuba.builder — Cursor-based procedural DSL for piping geometry.

The PipingBuilder maintains a 3-D cursor (position + forward direction)
and translates high-level commands (run, bend, support) into nodes and
elements on the parent TubaModel.
"""

from __future__ import annotations

from typing import Any, List, Optional

import numpy as np
from scipy.spatial.transform import Rotation


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

    def __init__(self, model, section_name: str, material_name: str):
        from tuba.model import TubaModel

        self.model: TubaModel = model
        self.section_name = section_name
        self.material_name = material_name

        self.cursor: np.ndarray = np.zeros(3)
        self.direction: np.ndarray = np.array([1.0, 0.0, 0.0])
        self.up_vector: np.ndarray = np.array([0.0, 0.0, 1.0])

        self.last_node_id: Optional[str] = None

    # -- Geometry commands ---------------------------------------------------

    def start(
        self,
        point: List[float],
        support: Optional[str] = None,
    ) -> "PipingBuilder":
        """Set the initial cursor position and create the starting node."""
        self.cursor = np.asarray(point, dtype=float)
        
        # Check if a node already exists at this coordinate to enable branching
        existing_nid = None
        for nid, node in self.model.nodes.items():
            if np.allclose(node.coords, self.cursor, atol=1e-5):
                existing_nid = nid
                break
                
        if existing_nid is not None:
            self.last_node_id = existing_nid
        else:
            self.last_node_id = self.model.add_node(self.cursor)

        if support:
            self.model.add_support(self.last_node_id, support)
        return self

    def run(self, length: float) -> "PipingBuilder":
        """Extend a straight pipe segment of *length* [m] in the current direction."""
        target = self.cursor + self.direction * length
        node_id = self.model.add_node(target)
        elem_id = self.model.next_element_id("pipe_str")

        self.model.add_element(
            id=elem_id,
            type="pipe_straight",
            n1=self.last_node_id,
            n2=node_id,
            section=self.section_name,
            material=self.material_name,
        )
        self.cursor = target
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
        # Determine rotation axis
        if plane == "XY":
            axis = self.up_vector.copy()
        elif plane == "XZ":
            axis = np.cross(self.direction, self.up_vector)
            norm = np.linalg.norm(axis)
            if norm < 1e-12:
                axis = np.array([0.0, 1.0, 0.0])
            else:
                axis /= norm
        else:  # YZ or arbitrary
            axis = self.direction.copy()

        theta = np.radians(angle)
        rot = Rotation.from_rotvec(axis * theta)
        new_direction = rot.apply(self.direction)
        new_direction /= np.linalg.norm(new_direction)  # normalise

        # Tangent length from bend geometry
        tangent_len = radius * abs(np.tan(theta / 2.0))

        # Bend entry → exit: advance by tangent in old dir, then tangent in new dir
        bend_entry = self.cursor + self.direction * tangent_len
        bend_exit = bend_entry + new_direction * tangent_len

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
        )

        self.direction = new_direction
        self.cursor = bend_exit
        self.last_node_id = exit_node_id
        return self

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

    def Spring(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        rx: float = 0.0,
        ry: float = 0.0,
        rz: float = 0.0,
        reference: str = "global",
    ) -> "PipingBuilder":
        """Compatibility alias matching the v2 command name."""
        return self.spring(x=x, y=y, z=z, rx=rx, ry=ry, rz=rz, reference=reference)

    def run_element(self, length: float, element_type: str = "pipe_straight", twist_angle: float = 0.0) -> "PipingBuilder":
        """Extend a segment of *length* [m] in the current direction with a specific element type."""
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

        self.model.add_element(
            id=elem_id,
            type=element_type,
            n1=self.last_node_id,
            n2=node_id,
            section=self.section_name,
            material=self.material_name,
            twist_angle=twist_angle,
        )
        self.cursor = target
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
                )
                self.cursor = target
                self.last_node_id = node_id

        if support:
            self.model.add_support(self.last_node_id, support)
        return self

    def set_direction(self, direction: List[float]) -> "PipingBuilder":
        """Override the current forward direction vector."""
        d = np.asarray(direction, dtype=float)
        self.direction = d / np.linalg.norm(d)
        return self
