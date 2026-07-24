# tuba/geometry/collision.py
"""
tuba.geometry.collision — 3D Collision checking for piping layouts and obstacles.
"""

from __future__ import annotations

from typing import List, Dict, Any, Tuple, Optional
import numpy as np

from tuba.model import TubaModel, Element
from tuba.physical import physical_properties_for_element


def _quaternion_matrix(quaternion) -> np.ndarray:
    """Return a rotation matrix for a ``[w, x, y, z]`` quaternion."""
    w, x, y, z = np.asarray(quaternion, dtype=float)
    norm = np.linalg.norm([w, x, y, z])
    if norm <= 1e-12:
        raise ValueError("Obstacle orientation quaternion must be non-zero.")
    w, x, y, z = (value / norm for value in (w, x, y, z))
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def _load_trimesh():
    try:
        import trimesh
    except ImportError as exc:
        raise ImportError("trimesh is required for collision checking.") from exc
    return trimesh


def create_cylinder_mesh(p1: np.ndarray, p2: np.ndarray, radius: float) -> Optional[Any]:
    """Helper to create a Trimesh cylinder connecting p1 and p2 with a given radius."""
    trimesh = _load_trimesh()

    v = p2 - p1
    height = np.linalg.norm(v)
    if height < 1e-9:
        return None

    # Create default cylinder along Z-axis centered at origin
    cylinder = trimesh.creation.cylinder(radius=radius, height=height)

    # Calculate midpoint translation
    midpoint = (p1 + p2) / 2.0

    # Calculate rotation matrix from Z-axis [0, 0, 1] to target vector v
    z_axis = np.array([0.0, 0.0, 1.0])
    v_norm = v / height

    cross_prod = np.cross(z_axis, v_norm)
    dot_prod = np.dot(z_axis, v_norm)

    if np.linalg.norm(cross_prod) < 1e-9:
        if dot_prod < 0:
            # 180 degree rotation around X-axis
            rotation = trimesh.transformations.rotation_matrix(np.pi, [1.0, 0.0, 0.0])
        else:
            rotation = np.eye(4)
    else:
        angle = np.arccos(np.clip(dot_prod, -1.0, 1.0))
        axis = cross_prod / np.linalg.norm(cross_prod)
        rotation = trimesh.transformations.rotation_matrix(angle, axis)

    transform = rotation
    transform[:3, 3] = midpoint
    cylinder.apply_transform(transform)

    return cylinder


class PipingCollisionChecker:
    """Checks for 3D geometric collisions between the piping model elements and obstacles."""

    def __init__(self, model: TubaModel):
        self._trimesh = _load_trimesh()
        self.model = model
        self.manager = self._trimesh.collision.CollisionManager()
        self._load_obstacles()

    def _load_obstacles(self):
        """Build and load trimesh representations of all obstacles in the model."""
        trimesh = self._trimesh
        importer = None

        for idx, obs in enumerate(self.model.obstacles):
            obs_type = obs.get("type")
            obs_id = obs.get("id", f"obstacle_{idx}")

            if obs_type == "cuboid":
                min_pt = np.array(obs["min_point"])
                max_pt = np.array(obs["max_point"])
                extents = max_pt - min_pt
                center = (min_pt + max_pt) / 2.0
                transform = np.eye(4)
                transform[:3, 3] = center
                mesh = trimesh.creation.box(extents=extents, transform=transform)
                self.manager.add_object(obs_id, mesh)

            elif obs_type == "cylinder":
                min_pt = np.array(obs["min_point"])
                max_pt = np.array(obs["max_point"])
                explicit_radius = obs.get("radius")
                if explicit_radius is None:
                    radius = np.linalg.norm(max_pt[:2] - min_pt[:2]) / 2.0
                    if radius < 1e-3:
                        raise ValueError(
                            f"Cylinder obstacle {obs_id!r} requires an explicit radius "
                            "or nonzero XY extent between min_point and max_point."
                        )
                else:
                    radius = float(explicit_radius)
                mesh = create_cylinder_mesh(min_pt, max_pt, radius)
                if mesh is not None:
                    self.manager.add_object(obs_id, mesh)

            elif obs_type == "mesh":
                file_path = obs.get("file_path")
                if not file_path:
                    continue
                
                # Lazy initialize importer
                if importer is None:
                    from tuba.geometry.importer import StepGeometryImporter

                    importer = StepGeometryImporter()

                # Import mesh from STEP/STL file
                mesh = importer.import_step(file_path)

                # Apply transform (position + quaternion orientation)
                pos = obs.get("position", [0.0, 0.0, 0.0])
                q = obs.get("orientation", [1.0, 0.0, 0.0, 0.0]) # [qw, qx, qy, qz]
                
                rot = _quaternion_matrix(q)

                transform = np.eye(4)
                transform[:3, :3] = rot
                transform[:3, 3] = pos
                mesh.apply_transform(transform)

                self.manager.add_object(obs_id, mesh)

    def check_collisions(self) -> List[str]:
        """Check each element in the model against all obstacles.

        Returns
        -------
        List[str]
            A list of element IDs that are in collision.
        """
        colliding_elements = []

        for elem in self.model.elements:
            radius = physical_properties_for_element(self.model, elem).effective_radius_m

            p1 = self.model.nodes[elem.n1].coords
            p2 = self.model.nodes[elem.n2].coords

            # Model bend elements as straight cylinders between their start/end
            # nodes for conservative collision checking.
            pipe_mesh = create_cylinder_mesh(p1, p2, radius)
            if pipe_mesh is None:
                continue

            # Check if this cylinder collides with any of the loaded obstacles
            in_collision = self.manager.in_collision_single(pipe_mesh)
            if in_collision:
                colliding_elements.append(elem.id)

        return colliding_elements

    def check_deformed_collisions(self, results: FEAResults) -> List[str]:
        """Check each element in the model in its deformed (operating) state
        against all obstacles.

        Returns
        -------
        List[str]
            A list of element IDs that are in collision when deformed.
        """
        from tuba.solver.base import FEAResults

        colliding_elements = []

        for elem in self.model.elements:
            radius = physical_properties_for_element(self.model, elem).effective_radius_m

            p1_cold = self.model.nodes[elem.n1].coords
            p2_cold = self.model.nodes[elem.n2].coords

            if elem.n1 not in results.node_results or elem.n2 not in results.node_results:
                raise ValueError(
                    f"Missing displacement results for element {elem.id!r}; "
                    "deformed collision checking requires both end-node displacements."
                )
            disp1 = results.get_displacement(elem.n1)[:3]
            disp2 = results.get_displacement(elem.n2)[:3]

            p1_deformed = p1_cold + disp1
            p2_deformed = p2_cold + disp2

            # Build deformed cylinder
            pipe_mesh = create_cylinder_mesh(p1_deformed, p2_deformed, radius)
            if pipe_mesh is None:
                continue

            in_collision = self.manager.in_collision_single(pipe_mesh)
            if in_collision:
                colliding_elements.append(elem.id)

        return colliding_elements
