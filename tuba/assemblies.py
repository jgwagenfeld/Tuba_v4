"""Reusable construction assemblies that generate model patches."""

from __future__ import annotations

from dataclasses import dataclass

from tuba.patches import AddElement, AddNode, AssignAttribute, CreateGroup, ModelPatch
from tuba.routing.types import Point3D


@dataclass(frozen=True)
class RackBay:
    name: str
    origin: Point3D
    length: float
    width: float
    height: float
    levels: tuple[float, ...]
    section: str
    material: str
    zone: str | None = None

    def to_patch(self) -> ModelPatch:
        if self.length <= 0.0 or self.width <= 0.0 or self.height <= 0.0:
            raise ValueError("RackBay dimensions must be positive.")
        z_values = sorted({0.0, self.height, *self.levels})
        for z in z_values:
            if z < 0.0 or z > self.height:
                raise ValueError(f"RackBay level {z!r} is outside rack height.")

        operations = []
        node_ids: list[str] = []
        element_ids: list[str] = []

        def node_name(ix: int, iy: int, iz: int) -> str:
            return f"{self.name}_n_{ix}_{iy}_{iz}"

        def point(ix: int, iy: int, z: float) -> Point3D:
            return (
                self.origin[0] + ix * self.length,
                self.origin[1] + iy * self.width,
                self.origin[2] + z,
            )

        for iz, z in enumerate(z_values):
            for ix in (0, 1):
                for iy in (0, 1):
                    local = node_name(ix, iy, iz)
                    node_ids.append(local)
                    operations.append(AddNode(local_id=local, coords=point(ix, iy, z), reuse_existing=False))

        def add_beam(local_id: str, n1: str, n2: str) -> None:
            element_ids.append(local_id)
            operations.append(
                AddElement(
                    local_id=local_id,
                    type="beam",
                    n1=n1,
                    n2=n2,
                    section=self.section,
                    material=self.material,
                    id_prefix=f"{self.name}_beam",
                )
            )

        beam_index = 0
        for iz in range(len(z_values) - 1):
            for ix in (0, 1):
                for iy in (0, 1):
                    add_beam(
                        f"{self.name}_col_{beam_index}",
                        node_name(ix, iy, iz),
                        node_name(ix, iy, iz + 1),
                    )
                    beam_index += 1

        for level_number, z in enumerate(self.levels, start=1):
            iz = z_values.index(z)
            for iy in (0, 1):
                add_beam(f"{self.name}_long_{level_number}_{iy}", node_name(0, iy, iz), node_name(1, iy, iz))
            for ix in (0, 1):
                add_beam(f"{self.name}_cross_{level_number}_{ix}", node_name(ix, 0, iz), node_name(ix, 1, iz))

        attachment_points = {}
        for level_number, z in enumerate(self.levels, start=1):
            iz = z_values.index(z)
            attachment_points[f"level_{level_number}_left"] = f"node:{node_name(0, 0, iz)}"
            attachment_points[f"level_{level_number}_right"] = f"node:{node_name(1, 0, iz)}"

        metadata = {
            "assembly_type": "rack_bay",
            "levels": list(self.levels),
            "attachment_points": attachment_points,
        }
        if self.zone is not None:
            metadata["zone"] = self.zone

        operations.append(
            CreateGroup(
                name=self.name,
                nodes=node_ids,
                elements=element_ids,
                metadata=metadata,
            )
        )
        if self.zone is not None:
            operations.append(AssignAttribute(target=f"group:{self.name}", key="rack.zone", value=self.zone))

        return ModelPatch(
            operations=operations,
            provenance={"assembly": self.name, "assembly_type": "rack_bay"},
        )
