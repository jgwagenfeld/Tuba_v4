"""Mixed MED-backed Code_Aster study export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tuba.analysis import AnalysisMesh, AnalysisStudy, MeshElementSource, MeshNodeSource
from tuba.model import TubaModel
from tuba.refs import EntityRef
from tuba.solver.aster_sidecar import build_solver_name_map, dump_solver_sidecar


class MixedCodeAsterStudyExporter:
    SOLVER_NAME = "Code_Aster"
    SUPPORTED_LINE_ELEMENT_TYPES = {"pipe_straight", "pipe_bend", "beam"}

    def export_analysis_study(
        self,
        model: TubaModel,
        load_case_name: str,
        output_dir: str | Path,
    ) -> AnalysisStudy:
        if load_case_name not in model.load_cases:
            raise ValueError(f"Load case {load_case_name!r} not found.")

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
            metadata={"project_name": model.project_name, "mixed_analysis": True},
        )
        manifest = {
            "study": study.to_dict(),
            "analysis_mesh": analysis_mesh.to_dict(),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        return study

    def _write_med(self, model: TubaModel, path: Path) -> None:
        self._write_med_with_meshio(model, path)

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
        )

    def _write_comm(
        self,
        model: TubaModel,
        load_case_name: str,
        path: Path,
        *,
        name_map: dict[str, str],
    ) -> None:
        _ = model.load_cases[load_case_name]
        lines = [
            "DEBUT()",
            "MAIL0 = LIRE_MAILLAGE(FORMAT='MED', UNITE=20)",
            "MODELE = AFFE_MODELE(",
            "    MAILLAGE=MAIL0,",
            "    AFFE=(",
            f"        _F(GROUP_MA=('{name_map['G_TUBE']}',), PHENOMENE='MECANIQUE', MODELISATION='TUYAU_3M'),",
        ]
        for region in model.analysis_regions.values():
            lines.append(
                "        _F("
                f"GROUP_MA=('{name_map[region.mesh_group]}',), "
                "PHENOMENE='MECANIQUE', "
                f"MODELISATION='{region.code_aster_modelisation}'"
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
            "cad_assets": {key: value.to_dict() for key, value in model.cad_assets.items()},
            "components": {key: value.to_dict() for key, value in model.imported_components.items()},
            "analysis_regions": {key: value.to_dict() for key, value in model.analysis_regions.items()},
            "ports": {key: value.to_dict() for key, value in model.ports.items()},
            "couplings": {key: value.to_dict() for key, value in model.couplings.items()},
        }
