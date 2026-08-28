"""Mixed MED-backed Code_Aster study export."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from tuba.analysis import AnalysisMesh, AnalysisStudy, MeshElementSource, MeshNodeSource
from tuba.analysis.provenance import MIXED_CODE_ASTER_COMPILER_ID, build_solver_input_identity
from tuba.meshing._gmsh import gmsh_model
from tuba.model import TubaModel
from tuba.refs import EntityRef
from tuba.solver.aster_sidecar import build_solver_name_map, dump_solver_sidecar, dump_study_manifest


class MixedCodeAsterStudyExporter:
    SOLVER_NAME = "Code_Aster"
    SUPPORTED_LINE_ELEMENT_TYPES = {"pipe_straight", "pipe_bend", "beam"}
    STEP_SUFFIXES = {".step", ".stp"}
    RESULT_STATUS = "export_only"
    RUNTIME_BLOCKER = (
        "Mixed Code_Aster export is a diagnostic handoff, not a solve-ready "
        "study. The 3D STEP mesh groups, pipe-to-solid coupling, material/load "
        "commands, and result-table extraction still need real Code_Aster "
        "validation before execution is enabled."
    )

    def export_analysis_study(
        self,
        model: TubaModel,
        load_case_name: str,
        output_dir: str | Path,
    ) -> AnalysisStudy:
        load_case_name, _ = model.resolve_load_case(load_case_name)

        model.validate()
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)

        med_path = root / "study.med"
        comm_path = root / "study.comm"
        export_path = root / "study.export"
        manifest_path = root / "study_manifest.json"
        sidecar_path = root / "study_tuba_fem.json"

        name_map = self._group_name_map(model)
        self._write_med(model, med_path)
        analysis_mesh = self._build_analysis_mesh(model, med_path)
        solver_input_identity = build_solver_input_identity(
            model,
            load_case_name,
            compiler_id=MIXED_CODE_ASTER_COMPILER_ID,
        )
        analysis_mesh = replace(analysis_mesh, solver_input_identity=solver_input_identity)
        self._write_comm(model, load_case_name, comm_path, name_map=name_map)
        self._write_export(root, export_path)

        dump_solver_sidecar(
            sidecar_path,
            solver_name=self.SOLVER_NAME,
            load_case=load_case_name,
            analysis_mesh_id=analysis_mesh.id,
            name_map=name_map,
            lineage=self._build_lineage(model, name_map),
            mixed_analysis=self._mixed_payload(model),
            solver_input_identity=solver_input_identity,
        )

        study = AnalysisStudy(
            id=f"mixed_analysis_study:{load_case_name}",
            model_revision=int(getattr(model, "revision", 0)),
            solver_name=self.SOLVER_NAME,
            load_case=load_case_name,
            work_dir=str(root),
            input_files={
                "med": str(med_path),
                "comm": str(comm_path),
                "export": str(export_path),
                "manifest": str(manifest_path),
                "sidecar": str(sidecar_path),
            },
            mesh_id=analysis_mesh.id,
            metadata={
                "project_name": model.project_name,
                "mixed_analysis": True,
                "result_status": self.RESULT_STATUS,
                "code_aster_solve_ready": False,
                "runtime_blocker": self.RUNTIME_BLOCKER,
            },
            solver_input_identity=solver_input_identity,
        )
        dump_study_manifest(manifest_path, study, analysis_mesh)
        return study

    def _write_med(self, model: TubaModel, path: Path) -> None:
        if self._has_existing_step_assets(model):
            self._write_med_with_gmsh(model, path)
        else:
            self._write_med_with_meshio(model, path)

    def _has_existing_step_assets(self, model: TubaModel) -> bool:
        return bool(self._existing_step_assets(model))

    def _existing_step_assets(self, model: TubaModel) -> list[Any]:
        return [
            asset
            for asset in model.cad_assets.values()
            if asset.source_format.upper() in {"STEP", "STP"}
            and Path(asset.source_path).suffix.lower() in self.STEP_SUFFIXES
            and Path(asset.source_path).exists()
        ]

    def _write_med_with_gmsh(self, model: TubaModel, path: Path) -> None:
        try:
            import gmsh
        except ImportError as exc:
            raise RuntimeError("gmsh is required to write MED studies from STEP assets.") from exc

        name_map = self._group_name_map(model)
        try:
            with gmsh_model(gmsh, "tuba_mixed"):
                volume_tags_by_asset: dict[str, list[int]] = {}
                known_volume_tags: set[int] = set()
                for asset in self._existing_step_assets(model):
                    source = Path(asset.source_path)
                    gmsh.model.occ.importShapes(str(source))
                    gmsh.model.occ.synchronize()
                    current_volume_tags = {tag for _, tag in gmsh.model.getEntities(3)}
                    volume_tags_by_asset[asset.id] = sorted(current_volume_tags - known_volume_tags)
                    known_volume_tags = current_volume_tags

                volume_tags = sorted(known_volume_tags)
                for region in model.analysis_regions.values():
                    region_volume_tags = self._region_volume_tags(model, region, volume_tags_by_asset, volume_tags)
                    if region.role == "solid_3d" and region_volume_tags:
                        gmsh.model.addPhysicalGroup(
                            3,
                            region_volume_tags,
                            name=name_map[region.mesh_group],
                        )

                pipe_line_tags = []
                for element in self._line_elements_for_med(model):
                    n1 = model.nodes[element.n1].coords
                    n2 = model.nodes[element.n2].coords
                    p1 = gmsh.model.geo.addPoint(float(n1[0]), float(n1[1]), float(n1[2]), 1.0)
                    p2 = gmsh.model.geo.addPoint(float(n2[0]), float(n2[1]), float(n2[2]), 1.0)
                    pipe_line_tags.append(gmsh.model.geo.addLine(p1, p2))
                gmsh.model.geo.synchronize()
                if pipe_line_tags:
                    gmsh.model.addPhysicalGroup(1, pipe_line_tags, name=name_map["G_TUBE"])

                for port in model.ports.values():
                    face_tag = port.metadata.get("gmsh_face_tag")
                    if port.face_group and isinstance(face_tag, int):
                        gmsh.model.addPhysicalGroup(2, [face_tag], name=name_map[port.face_group])

                gmsh.model.mesh.generate(3)
                gmsh.write(str(path))
        except Exception as exc:
            raise RuntimeError(f"Failed to write Gmsh MED mesh {path}: {exc}") from exc
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"Gmsh MED writer produced an empty file: {path}")

    def _region_volume_tags(
        self,
        model: TubaModel,
        region: Any,
        volume_tags_by_asset: dict[str, list[int]],
        fallback_volume_tags: list[int],
    ) -> list[int]:
        metadata_tags = region.metadata.get("gmsh_volume_tags")
        if isinstance(metadata_tags, (list, tuple)) and all(isinstance(tag, int) for tag in metadata_tags):
            return list(metadata_tags)
        if region.owner.kind == "component" and region.owner.id in model.imported_components:
            component = model.imported_components[region.owner.id]
            if component.asset.kind == "cad_asset":
                return volume_tags_by_asset.get(component.asset.id, fallback_volume_tags)
        return fallback_volume_tags

    def _write_med_with_meshio(self, model: TubaModel, path: Path) -> None:
        try:
            import meshio
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("meshio and numpy are required to write mixed MED studies.") from exc

        name_map = self._group_name_map(model)
        point_ids = list(model.nodes.keys())
        points = np.array([model.nodes[node_id].coords for node_id in point_ids], dtype=float)
        point_index = {node_id: index for index, node_id in enumerate(point_ids)}
        line_cells = [
            [point_index[element.n1], point_index[element.n2]]
            for element in self._line_elements_for_med(model)
        ]

        cells = []
        cell_sets: dict[str, list[Any]] = {}
        if line_cells:
            cells.append(("line", np.array(line_cells, dtype=int)))
            cell_count = len(line_cells)
            cell_sets[name_map["G_TUBE"]] = [np.arange(cell_count, dtype=int)]
            for region in model.analysis_regions.values():
                cell_sets[name_map[region.mesh_group]] = [np.array([], dtype=int)]
            for port in model.ports.values():
                if port.face_group:
                    cell_sets[name_map[port.face_group]] = [np.array([], dtype=int)]

        mesh = meshio.Mesh(points=points, cells=cells, cell_sets=cell_sets)
        try:
            meshio.write(path, mesh, file_format="med")
        except Exception as exc:
            raise RuntimeError(f"Failed to write MED mesh {path}: {exc}") from exc
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"MED writer produced an empty file: {path}")

    def _build_analysis_mesh(self, model: TubaModel, med_path: Path) -> AnalysisMesh:
        nodes = {
            node_id: tuple(float(value) for value in node.coords)
            for node_id, node in model.nodes.items()
        }
        elements = {
            element.id: (element.n1, element.n2)
            for element in self._line_elements_for_med(model)
        }
        groups: dict[str, tuple[str, ...]] = {
            "G_TUBE": tuple(elements.keys()),
        }
        node_sources = {
            node_id: MeshNodeSource(
                node_id=node_id,
                source_ref=EntityRef("node", node_id),
                role="native_node",
            )
            for node_id in nodes
        }
        element_sources = {
            element_id: MeshElementSource(
                element_id=element_id,
                source_ref=EntityRef("element", element_id),
                role="native_element",
            )
            for element_id in elements
        }
        for region in model.analysis_regions.values():
            groups[region.mesh_group] = tuple()
        for port in model.ports.values():
            if port.face_group:
                groups[port.face_group] = tuple()

        return AnalysisMesh(
            id="analysis_mesh:mixed",
            model_revision=int(getattr(model, "revision", 0)),
            solver_name=self.SOLVER_NAME,
            nodes=nodes,
            elements=elements,
            groups=groups,
            node_sources=node_sources,
            element_sources=element_sources,
            files={"med": str(med_path)},
            modelisations=self._modelisation_assignments(model),
        )

    @staticmethod
    def _modelisation_assignments(model: TubaModel) -> dict[str, str]:
        """``GROUP_MA`` -> ``MODELISATION`` for the mixed 1D/3D study.

        Single source for AFFE_MODELE emission and AnalysisMesh metadata. Note
        this differs from the pure-piping path in tuba.solver.modelisation:
        here ``G_TUBE`` is the TUYAU shell-beam region, not a POU_D_T beam.
        """
        assignments = {"G_TUBE": "TUYAU_3M"}
        for region in model.analysis_regions.values():
            assignments[region.mesh_group] = region.code_aster_modelisation
        return assignments

    def _write_comm(
        self,
        model: TubaModel,
        load_case_name: str,
        path: Path,
        *,
        name_map: dict[str, str],
    ) -> None:
        lines = [
            "DEBUT()",
            "MAIL0 = LIRE_MAILLAGE(FORMAT='MED', UNITE=20)",
            "MODELE = AFFE_MODELE(",
            "    MAILLAGE=MAIL0,",
            "    AFFE=(",
        ]
        for group_name, modelisation in self._modelisation_assignments(model).items():
            lines.append(
                "        _F("
                f"GROUP_MA=('{name_map[group_name]}',), "
                "PHENOMENE='MECANIQUE', "
                f"MODELISATION='{modelisation}'"
                "),"
            )
        lines.extend(["    ),", ")"])
        lines.extend(
            [
                "CHAR = AFFE_CHAR_MECA(",
                "    MODELE=MODELE,",
                "    LIAISON_ELEM=(",
            ]
        )
        for coupling in model.couplings.values():
            port = model.ports[coupling.target.id]
            lines.extend(
                [
                    "        _F(",
                    f"            OPTION='{coupling.code_aster_option}',",
                    f"            GROUP_MA_1='{name_map[port.face_group]}',",
                    f"            GROUP_NO_2='{coupling.source_node.id}',",
                    "        ),",
                ]
            )
        lines.extend(["    ),", ")", "FIN()"])
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_export(self, root: Path, path: Path) -> None:
        path.write_text(
            "\n".join(
                [
                    "P actions make_etude",
                    "P memjob 1024",
                    "P time_limit 60",
                    "F comm study.comm D 1",
                    "F mmed study.med D 20",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def _build_lineage(self, model: TubaModel, name_map: dict[str, str]) -> dict[str, str]:
        lineage = {name_map["G_TUBE"]: "group:G_TUBE"}
        for region in model.analysis_regions.values():
            lineage[name_map[region.mesh_group]] = f"analysis_region:{region.id}"
        for port in model.ports.values():
            if port.face_group:
                lineage[name_map[port.face_group]] = f"port:{port.id}"
        return lineage

    def _group_name_map(self, model: TubaModel) -> dict[str, str]:
        return build_solver_name_map(self._group_names(model))

    def _group_names(self, model: TubaModel) -> list[str]:
        names = ["G_TUBE"]
        names.extend(region.mesh_group for region in model.analysis_regions.values())
        names.extend(port.face_group for port in model.ports.values() if port.face_group)
        return list(dict.fromkeys(names))

    def _line_elements_for_med(self, model: TubaModel) -> list[Any]:
        unsupported = [
            element
            for element in model.elements
            if element.type not in self.SUPPORTED_LINE_ELEMENT_TYPES
        ]
        if unsupported:
            details = ", ".join(f"{element.id}:{element.type}" for element in unsupported)
            raise ValueError(
                "mixed MED export does not support these structural element types yet: "
                f"{details}"
            )
        return list(model.elements)

    def _mixed_payload(self, model: TubaModel) -> dict[str, Any]:
        return {
            "result_status": self.RESULT_STATUS,
            "code_aster_solve_ready": False,
            "runtime_blocker": self.RUNTIME_BLOCKER,
            "cad_assets": {key: value.to_dict() for key, value in model.cad_assets.items()},
            "components": {key: value.to_dict() for key, value in model.imported_components.items()},
            "analysis_regions": {key: value.to_dict() for key, value in model.analysis_regions.items()},
            "ports": {key: value.to_dict() for key, value in model.ports.items()},
            "couplings": {key: value.to_dict() for key, value in model.couplings.items()},
        }


def load_mixed_sidecar_diagnostics(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    mixed = payload.get("mixed_analysis", {})
    if not isinstance(mixed, dict) or not mixed:
        raise ValueError("Sidecar does not contain mixed_analysis diagnostics.")
    refs: list[str] = []
    refs.extend(f"cad_asset:{key}" for key in mixed.get("cad_assets", {}))
    refs.extend(f"component:{key}" for key in mixed.get("components", {}))
    refs.extend(f"analysis_region:{key}" for key in mixed.get("analysis_regions", {}))
    refs.extend(f"port:{key}" for key in mixed.get("ports", {}))
    refs.extend(f"coupling:{key}" for key in mixed.get("couplings", {}))
    return {
        "result_status": mixed.get("result_status", "export_only"),
        "code_aster_solve_ready": bool(mixed.get("code_aster_solve_ready", False)),
        "runtime_blocker": mixed.get("runtime_blocker"),
        "refs": refs,
        "lineage": dict(payload.get("lineage", {})),
        "analysis_mesh_id": payload.get("analysis_mesh_id"),
    }
