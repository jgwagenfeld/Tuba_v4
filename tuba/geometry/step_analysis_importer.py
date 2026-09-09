"""STEP analysis importer for reviewable port candidate metadata."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from tuba.meshing._gmsh import gmsh_model
from tuba.model import TubaModel

try:
    import gmsh  # type: ignore
except ImportError:  # pragma: no cover - exercised via test monkey-patch
    gmsh = None


class StepImportError(RuntimeError):
    """Import error used when StepAnalysisImporter prerequisites are unavailable."""


class StepAnalysisImporter:
    """Import STEP files for mixed-analysis review metadata."""

    def import_component(
        self,
        model: TubaModel,
        file_path: str | Path,
        *,
        id: str,
        asset_id: str = "cad_asset_0",
        role: str = "equipment",
        unit_scale_to_m: float = 1.0,
    ) -> Any:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"STEP file not found: {path}")

        if gmsh is None:
            raise StepImportError("gmsh is required to import STEP files for mixed analysis.")

        with gmsh_model(gmsh, f"tuba_step_{id}"):
            imported = gmsh.model.occ.importShapes(str(path))
            gmsh.model.occ.synchronize()

            ports = self._detect_port_candidates(imported)
            digest = self._compute_digest(path)
            return self.record_component_from_metadata(
                model,
                source_path=path,
                component_id=id,
                asset_id=asset_id,
                role=role,
                unit_scale_to_m=unit_scale_to_m,
                content_digest=digest,
                ports=ports,
            )

    def record_component_from_metadata(
        self,
        model: TubaModel,
        *,
        source_path: str | Path,
        component_id: str,
        asset_id: str,
        role: str = "equipment",
        source_format: str = "STEP",
        unit_scale_to_m: float = 1.0,
        placement: dict[str, Any] | None = None,
        content_digest: str | None = None,
        importer: str = "gmsh-occ",
        metadata: dict[str, Any] | None = None,
        ports: list[dict[str, Any]] | None = None,
    ) -> Any:
        port_payloads = [self._normalize_port_candidate(port) for port in ports or []]
        model.add_cad_asset(
            id=asset_id,
            source_path=str(source_path),
            source_format=source_format.upper(),
            unit_scale_to_m=unit_scale_to_m,
            placement=placement
            or {
                "origin": [0.0, 0.0, 0.0],
                "rotation": [1.0, 0.0, 0.0, 0.0],
            },
            content_digest=content_digest,
            importer=importer,
            metadata=dict(metadata or {}),
        )

        component = model.add_imported_component(
            id=component_id,
            asset=f"cad_asset:{asset_id}",
            name=component_id,
            role=role,
            status="review",
        )

        for candidate in port_payloads:
            model.add_port(
                id=str(candidate.get("id", f"port_candidate_{len(model.ports)}")),
                owner=f"component:{component_id}",
                kind=candidate.get("kind", "circular_face"),
                position=candidate["position"],
                axis=candidate.get("axis", [1.0, 0.0, 0.0]),
                radius=float(candidate["radius"]),
                face_group=candidate.get("face_group"),
                edge_group=candidate.get("edge_group"),
                status=candidate.get("status", "detected"),
                metadata=dict(candidate.get("metadata", {})),
            )

        return component

    def _detect_port_candidates(self, imported: list[tuple[int, int]] | None) -> list[dict[str, Any]]:
        if gmsh is None:
            return []
        if not imported:
            return []

        candidates: list[dict[str, Any]] = []
        seen_face_tags: set[int] = set()

        for entity in imported:
            try:
                dim, tag = entity
            except (TypeError, ValueError):
                continue
            if dim != 3:
                continue
            try:
                faces = gmsh.model.getBoundary([(dim, tag)], oriented=False, recursive=False)
            except Exception:
                continue
            try:
                solid_center = gmsh.model.occ.getCenterOfMass(dim, tag)
            except Exception:
                solid_center = None

            for boundary_dim, raw_face_tag in faces:
                face_tag = abs(int(raw_face_tag))
                if boundary_dim != 2 or face_tag in seen_face_tags:
                    continue
                # A pipe lands on a flat face. On a curved one the bounding box
                # is not a radius - on a cylinder lateral it is half the face
                # length - and a normal sampled at the parametric midpoint is an
                # arbitrary point on the surface. A confident wrong number is
                # worse than no candidate.
                try:
                    if gmsh.model.getType(boundary_dim, face_tag) != "Plane":
                        continue
                except Exception:
                    continue
                try:
                    x_min, y_min, z_min, x_max, y_max, z_max = gmsh.model.getBoundingBox(
                        boundary_dim,
                        face_tag,
                    )
                except Exception:
                    continue

                seen_face_tags.add(face_tag)
                radius = max(x_max - x_min, y_max - y_min, z_max - z_min) / 2.0
                if radius <= 0.0:
                    radius = 1e-6
                position = [
                    (x_min + x_max) / 2.0,
                    (y_min + y_max) / 2.0,
                    (z_min + z_max) / 2.0,
                ]

                index = len(candidates)
                candidates.append(
                    {
                        "id": f"port_candidate_{index}",
                        "kind": "circular_face",
                        "position": position,
                        "axis": self._outward_face_axis(face_tag, position, solid_center),
                        "radius": float(radius),
                        "face_group": f"G_PORT_CANDIDATE_{index}",
                        "metadata": {"gmsh_face_tag": face_tag},
                    }
                )

        return candidates

    @staticmethod
    def _outward_face_axis(
        face_tag: int,
        face_center: list[float],
        solid_center: Any,
    ) -> list[float]:
        """The face normal, flipped to point away from the solid it bounds.

        OCC orients a face however the modelling history left it, so the raw
        normal's sign says nothing about which side the material is on. A port
        axis has to point away from the equipment and back down the pipe.
        """
        default = [1.0, 0.0, 0.0]
        if gmsh is None:
            return default
        try:
            parametric_min, parametric_max = gmsh.model.getParametrizationBounds(2, face_tag)
            u = (float(parametric_min[0]) + float(parametric_max[0])) / 2.0
            v = (float(parametric_min[1]) + float(parametric_max[1])) / 2.0
            normal = [float(value) for value in gmsh.model.getNormal(face_tag, [u, v])]
        except Exception:
            return default
        length = sum(value * value for value in normal) ** 0.5
        if length <= 1e-12:
            return default
        normal = [value / length for value in normal]
        if solid_center is None:
            return normal
        # ponytail: centroid heuristic; use a ray cast if a concave solid ever
        # puts its centre of mass on the wrong side of one of its own faces.
        outward = [float(face_center[index]) - float(solid_center[index]) for index in range(3)]
        if sum(a * b for a, b in zip(normal, outward)) < 0.0:
            normal = [-value for value in normal]
        return normal

    @staticmethod
    def _normalize_port_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(candidate, dict):
            raise StepImportError("Port candidate must be a mapping.")
        if "position" not in candidate:
            raise StepImportError("Port candidate is missing required field 'position'.")
        if "radius" not in candidate:
            raise StepImportError("Port candidate is missing required field 'radius'.")
        return dict(candidate)

    @staticmethod
    def _compute_digest(path: Path) -> str:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return f"sha256:{digest}"
