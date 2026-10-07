"""Mixed MED-backed Code_Aster study export."""

from __future__ import annotations

import json
import hashlib
import math
from dataclasses import replace
from pathlib import Path
from typing import Any, NamedTuple

from tuba.analysis import AnalysisMesh, AnalysisStudy, MeshElementSource, MeshNodeSource
from tuba.analysis.provenance import build_solver_input_identity
from tuba.meshing._gmsh import gmsh_model
from tuba.model import TubaModel
from tuba.refs import EntityRef
from tuba.solver.aster_sidecar import build_solver_name_map, dump_solver_sidecar, dump_study_manifest
from tuba.solver.code_aster_runtime import write_artifact_text
from tuba.solver.compiler_contract import BEAM_STRESS_OPTION, mixed_contract, reject_fluid_contents


class StepStudyInputs(NamedTuple):
    """The STEP compiler's validated inputs, resolved without generating a mesh."""

    load_case_name: str
    load_case: Any
    compiler_inputs: dict[str, Any]
    solver_input_identity: Any
    region: Any
    line_elements: list
    line_modelisation: str
    supports: list
    fixed_face_groups: list
    couplings: list
    pressure: float
    comm_context: dict[str, Any]


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
        *,
        max_element_size: float | None = None,
    ) -> AnalysisStudy:
        if max_element_size is not None or self._has_native_step_request(model):
            return self._export_step_study(model, load_case_name, output_dir, max_element_size=max_element_size)
        inputs = self.analysis_study_inputs(model, load_case_name)
        load_case_name = inputs.load_case_name
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
        solver_input_identity = inputs.solver_input_identity
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
                "compiler_inputs": inputs.compiler_inputs,
                "result_status": self.RESULT_STATUS,
                "code_aster_solve_ready": False,
                "runtime_blocker": self.RUNTIME_BLOCKER,
            },
            solver_input_identity=solver_input_identity,
        )
        dump_study_manifest(manifest_path, study, analysis_mesh)
        return study

    @staticmethod
    def _has_native_step_request(model: TubaModel) -> bool:
        return any(region.role in {"shell_2d", "reference"} for region in model.analysis_regions.values()) or any(
            asset.metadata.get("analysis_import_version") or "mesh_size" in asset.metadata
            for asset in model.cad_assets.values()
        ) or any("face_selector" in port.metadata for port in model.ports.values())

    def analysis_study_inputs(self, model, load_case_name, *, max_element_size=None):
        """Resolve the identity of the same native or diagnostic export, without meshing."""
        if max_element_size is not None or self._has_native_step_request(model):
            return self.step_study_inputs(model, load_case_name, max_element_size=max_element_size)
        from tuba.solver.aster import StudyInputs
        from tuba.solver.aster_contact import shoes
        from tuba.solver.modelisation import PipeModelization

        shoes(model, PipeModelization.SOLID_3D)
        load_case_name, load_case = model.resolve_load_case(load_case_name)
        model.validate()
        reject_fluid_contents(load_case, "mixed/CAD studies")
        contract = mixed_contract(model)
        identity = build_solver_input_identity(
            model, load_case_name, compiler_id=contract.compiler_id,
            compiler_inputs=contract.compiler_inputs,
        )
        return StudyInputs(load_case_name, load_case, contract.compiler_inputs, identity)

    def step_study_inputs(self, model, load_case_name, *, max_element_size=None):
        """Validate and fingerprint native solid/shell/line mechanics without meshing."""
        from tuba.meshing.step_component import step_mesh_size
        from tuba.model import PipeSection, RectangularSection
        from tuba.solver.aster_comm import _held_dofs
        from tuba.solver.aster_volume import mixed_load_inputs

        model.validate()
        load_case_name, load_case = model.resolve_load_case(load_case_name)
        solids = tuple(r for r in model.analysis_regions.values() if r.role == "solid_3d")
        shells = tuple(r for r in model.analysis_regions.values() if r.role == "shell_2d")
        references = tuple(r for r in model.analysis_regions.values() if r.role == "reference")
        if not solids and not shells:
            raise ValueError("Native mixed studies require an explicit solid_3d or shell_2d region.")
        if len(solids) + len(shells) + len(references) != len(model.analysis_regions):
            raise ValueError("Native mixed studies only support solid_3d, shell_2d and reference regions.")
        mesh_sizes = {}
        for region in (*solids, *shells, *references):
            if region.status not in {"reviewed", "confirmed"}:
                raise ValueError("Review all analysis regions before solving.")
            if region.role == "solid_3d":
                component = model.imported_components[region.owner.id]
                if region.owner.kind != "component" or region.code_aster_modelisation != "3D" or component.asset.kind != "cad_asset":
                    raise ValueError("STEP solids require a component-owned region using 3D and a CAD asset.")
                if component.status not in {"reviewed", "confirmed"}:
                    raise ValueError("Review the imported component before solving.")
                asset = model.cad_assets[component.asset.id]
                source = Path(asset.source_path)
                if asset.source_format.upper() not in {"STEP", "STP"} or source.suffix.lower() not in self.STEP_SUFFIXES:
                    raise ValueError("Solved imported solids require a STEP file.")
                if not source.is_file():
                    raise ValueError(f"STEP source is unavailable: {source}")
                if asset.content_digest != "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest():
                    raise ValueError("STEP source changed since import; reimport and review its interfaces.")
                mesh_sizes[region.id] = step_mesh_size(model, region, max_element_size)
            elif region.role == "shell_2d":
                if region.code_aster_modelisation != "DKT" or region.element_order != 1:
                    raise ValueError("Native mixed shells require first-order DKT triangles.")
                mesh_sizes[region.id] = step_mesh_size(model, region, max_element_size)
            elif region.code_aster_modelisation != "DIS_TR" or region.owner.kind != "node":
                raise ValueError("Reference carriers require node-owned DIS_TR regions.")
        from tuba.meshing.policy import has_mesh_policy, has_legacy_refinements, resolve_mesh_policy
        resolved_policy = resolve_mesh_policy(model,max_element_size=max_element_size) if has_mesh_policy(model) or has_legacy_refinements(model) else None
        if resolved_policy is not None:
            mesh_sizes = {region.id:resolved_policy.base_size(str(region.owner)) for region in (*solids,*shells)}
        line_elements = list(model.elements)
        if any(e.type not in {"pipe_straight", "beam"} for e in line_elements):
            raise ValueError("Native mixed studies support straight TUYAU pipes and POU_D_T beams.")
        line_families = {e.id: "POU_D_T" if e.type == "beam" else "TUYAU_3M" for e in line_elements}
        families = set(line_families.values())
        line_modelisation = next(iter(families)) if len(families) == 1 else ("MIXED" if families else "TUYAU_3M")
        for element in line_elements:
            section = model.sections[element.section]
            if not isinstance(section, (PipeSection, RectangularSection)) or (element.type == "pipe_straight" and not isinstance(section, PipeSection)):
                raise ValueError("Native mixed studies support circular pipes or circular/rectangular frames.")
            if element.twist_angle:
                raise ValueError("Native mixed beam section twist is not supported.")
            if model.get_insulation(f"element:{element.id}"):
                raise ValueError("Native mixed insulation loads are not supported.")
        resolved_loads = mixed_load_inputs(model, load_case, line_elements, (*solids, *shells))
        physical_nodes = {n for e in line_elements for n in (e.n1, e.n2)} | {r.owner.id for r in references}
        physical_nodes |= {node_id for node_id, node in model.nodes.items()
                           if any(math.dist(node.coords, point) <= 1e-8 for shell in shells for point in shell.metadata["polygon_m"])}
        requested_nodes = {force.node for force in load_case.nodal_forces}
        requested_nodes |= {n for support in model.supports for n in (support.node, support.attached_to) if n is not None}
        requested_nodes |= {n for coupling in model.couplings.values() if coupling.kind == "rigid_patch"
                            for n in coupling.metadata.get("nodes", [])}
        if requested_nodes - physical_nodes:
            raise ValueError(f"Mixed loads and supports require line nodes, shell corners or declared reference carriers; got {sorted(requested_nodes - physical_nodes)!r}.")

        supports = []
        anchored_nodes = set()
        for support in model.supports:
            support.__post_init__()
            if (support.type in {"rest", "spring", "hanger"} or support.stiffness is not None
                    or support.stiffness_matrix is not None or support.mass != 0
                    or support.friction_coefficient != 0 or support.gap != 0
                    or support.normal_stiffness is not None or support.tangential_stiffness is not None):
                raise ValueError("Native mixed studies currently support bilateral masks and node attachments without contact, springs or masses.")
            held = _held_dofs(support)
            if support.imposed_displacement is not None:
                values = support.imposed_displacement
                if len(values) not in {3, 6} or not all(math.isfinite(float(value)) for value in values):
                    raise ValueError("Mixed imposed displacement must contain three or six finite components.")
                for dof, value in zip(("DX", "DY", "DZ", "DRX", "DRY", "DRZ"), values):
                    if float(value) != 0 and dof not in held:
                        raise ValueError(f"Mixed imposed displacement sets free DOF {dof!r} at {support.node!r}.")
            supports.append((f"G_NODE_{support.node}", "node"))
            if support.attached_to is not None:
                supports.append((f"G_NODE_{support.attached_to}", "node"))
            elif held:
                anchored_nodes.add(support.node)
        supports = list(dict.fromkeys(supports))
        fixed_face_groups = []
        solid_by_owner = {r.owner: r for r in solids}
        for region in solids:
            for port_id in region.metadata.get("fixed_interfaces", []):
                port = model.ports.get(str(port_id).removeprefix("port:"))
                if port is None or port.status != "confirmed" or port.owner != region.owner or not port.face_group:
                    raise ValueError(f"Fixed interface {port_id!r} must be a confirmed component face.")
                if port.face_group not in fixed_face_groups:
                    supports.append((port.face_group, "face"))
                    fixed_face_groups.append(port.face_group)
        if not anchored_nodes and not fixed_face_groups:
            raise ValueError("Native mixed study requires a held ground support or named fixed interface.")
        couplings, rigid_patches = [], []
        coupled_nodes, coupled_faces = set(), set()
        reference_nodes = {r.owner.id for r in references}
        for coupling in model.couplings.values():
            if coupling.kind == "rigid_patch":
                if coupling.code_aster_keyword != "LIAISON_SOLIDE" or coupling.code_aster_option != "RIGID_PATCH" or coupling.source_node.id not in reference_nodes:
                    raise ValueError("Rigid patches require LIAISON_SOLIDE and a declared six-DOF reference carrier.")
                rigid_patches.append(coupling.metadata.get("mesh_node_group", f"G_{coupling.id}_PATCH"))
                coupled_nodes.add(coupling.source_node.id)
                continue
            if coupling.kind != "pipe_to_solid_port" or coupling.code_aster_keyword != "LIAISON_ELEM":
                raise ValueError(f"Unsupported native mixed coupling {coupling.kind!r}.")
            element = model.get_element(coupling.source.id)
            expected_option = "3D_TUYAU" if line_families[element.id] == "TUYAU_3M" else "3D_POU"
            if coupling.code_aster_option != expected_option:
                raise ValueError("STEP coupling must match its source line modelization (3D_TUYAU or 3D_POU).")
            node_id = coupling.source_node.id
            port = model.ports[coupling.target.id]
            if port.status != "confirmed" or port.owner not in solid_by_owner or not port.face_group or node_id not in {element.n1, element.n2}:
                raise ValueError("STEP coupling requires a confirmed solid face and a source element endpoint.")
            if node_id in coupled_nodes or sum(node_id in {e.n1, e.n2} for e in line_elements) != 1:
                raise ValueError("Each STEP cut interface must meet exactly one continuation endpoint.")
            if port.face_group in fixed_face_groups or port.face_group in coupled_faces:
                raise ValueError("STEP interface must not be both fixed and coupled, or coupled more than once.")
            offset = model.nodes[node_id].coords - port.position
            tolerance = max(1e-8, port.radius * 1e-5)
            if float(sum(v * v for v in offset)) ** 0.5 > tolerance:
                raise ValueError(f"Line endpoint {node_id!r} must coincide with interface {port.id!r}.")
            other_id = element.n2 if node_id == element.n1 else element.n1
            direction = model.nodes[other_id].coords - model.nodes[node_id].coords
            length = float(sum(v * v for v in direction)) ** 0.5
            axis = tuple(float(v / length) for v in direction)
            if sum(a * b for a, b in zip(axis, port.axis)) < 1 - 1e-6:
                raise ValueError("STEP continuation must leave the interface along its outward axis.")
            if expected_option == "3D_TUYAU":
                region = solid_by_owner[port.owner]
                asset = model.cad_assets[model.imported_components[region.owner.id].asset.id]
                section = model.sections[element.section]
                selector = port.metadata.get("face_selector", {})
                inner = float(selector.get("inner_radius", 0)) * asset.unit_scale_to_m
                if selector.get("shape") != "annular_face" or abs(port.radius - section.OD / 2) > tolerance or abs(inner - (section.OD / 2 - section.WT)) > tolerance:
                    raise ValueError("3D_TUYAU requires an annular cut face matching the pipe outer and inner radii.")
            couplings.append((port.face_group, f"G_NODE_{node_id}", axis, expected_option))
            coupled_nodes.add(node_id)
            coupled_faces.add(port.face_group)
        connected = set(coupled_nodes) | anchored_nodes
        while True:
            expanded = connected | {n for e in line_elements if e.n1 in connected or e.n2 in connected for n in (e.n1, e.n2)}
            expanded |= {n for support in model.supports if support.attached_to is not None
                         and (support.node in connected or support.attached_to in connected)
                         for n in (support.node, support.attached_to)}
            expanded |= {n for patch in model.couplings.values()
                         if patch.kind == "rigid_patch" and patch.metadata.get("selection") == "nodes"
                         and (patch.source_node.id in connected or any(node in connected for node in patch.metadata["nodes"]))
                         for n in (patch.source_node.id, *patch.metadata["nodes"])}
            if expanded == connected:
                break
            connected = expanded
        if {n for e in line_elements for n in (e.n1, e.n2)} - connected:
            raise ValueError("Every native mixed line component must connect to an interface, rigid patch or ground restraint.")
        pressure = float(load_case.internal_pressure)
        if pressure and not solids and not any(e.type == "pipe_straight" for e in line_elements):
            raise ValueError("Native mixed internal pressure requires a solid pressure surface or a TUYAU pipe; shells and frames do not carry internal pressure.")
        if pressure and any(not region.metadata.get("pressure_surfaces") for region in solids):
            raise ValueError("STEP pressure requires explicit pressure surface selections for each solid region.")
        region = solids[0] if solids else None
        size = mesh_sizes[region.id] if region is not None else (next(iter(mesh_sizes.values())) if len(mesh_sizes) == 1 else None)
        contract = mixed_contract(model)
        compiler_inputs = {
            **contract.compiler_inputs, "element_ids": [],
            **({"component_id": region.owner.id} if len(solids) == 1 else {}),
            "max_element_size": size, "region_mesh_sizes": mesh_sizes,
            "step_mesher": "tetra10-tri3-seg3-seg2-poi1-v6",
            "mixed_mechanics_version": "solid-shell-line-reference-v2",
            "line_modelisation": line_modelisation, "line_modelisations": line_families,
            "region_modelisations": {r.mesh_group: r.code_aster_modelisation for r in model.analysis_regions.values()},
            "shell_coque_ncou": {r.id: 1 for r in shells},
            **({"solver_policy": {"method": "MULT_FRONT", "nprec": 8, "stop_singulier": "OUI"}}
               if references else {}),
            "pipe_generatrices": resolved_loads["pipe_generatrices"],
            "rigid_patch_groups": rigid_patches, "resolved_loads": resolved_loads,
            **({"beam_stress": BEAM_STRESS_OPTION} if any(e.type == "beam" for e in line_elements) else {}),
        }
        if resolved_policy is not None:
            compiler_inputs["mesh_policy"] = resolved_policy.to_dict()
        from tuba.solver.compiler_contract import compiler_id_for
        compiler_id = compiler_id_for({"volume_analysis": True, "mixed_analysis": True})
        identity = build_solver_input_identity(model, load_case_name, compiler_id=compiler_id, compiler_inputs=compiler_inputs)
        return StepStudyInputs(
            load_case_name, load_case, compiler_inputs, identity, region,
            line_elements, line_modelisation, supports, fixed_face_groups, couplings, pressure,
            {"solid_regions": solids, "shell_regions": shells, "reference_regions": references,
             "rigid_patch_groups": tuple(rigid_patches)},
        )

    def _export_step_study(self, model, load_case_name, output_dir, *, max_element_size):
        """Compile the resolved STEP inputs through the native 3D/line compiler."""
        from tuba.meshing.step_component import build_step_component_mesh
        from tuba.meshing.policy import resolve_mesh_policy
        from tuba.solver.aster_volume import _write_comm, _write_export

        (
            load_case_name, load_case, compiler_inputs, identity, region,
            line_elements, line_modelisation, supports, fixed_face_groups, couplings, pressure, comm_context,
        ) = self.step_study_inputs(model, load_case_name, max_element_size=max_element_size)
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        generated = build_step_component_mesh(
            model, root / "study.med",
            max_element_size=max_element_size,
            mesh_policy=resolve_mesh_policy(model,max_element_size=max_element_size),
        )
        for group, _kind in supports:
            if group not in generated.groups:
                raise ValueError(f"STEP anchor {group!r} is not represented in the analysis mesh.")
        mesh = replace(generated.analysis_mesh, solver_input_identity=identity)
        name_map = build_solver_name_map(generated.groups)
        solids = comm_context["solid_regions"]
        shells = comm_context["shell_regions"]
        for group in comm_context["rigid_patch_groups"]:
            if group not in generated.groups:
                raise ValueError(f"Rigid patch {group!r} is not represented in the analysis mesh.")
        _write_comm(
            model, root / "study.comm", name_map=name_map, pressure=pressure,
            support_groups=tuple(supports), couplings=tuple(couplings),
            line_elements=line_elements, nodal_forces=load_case.nodal_forces,
            node_groups={name: members[0] for name, members in generated.groups.items() if name.startswith("G_NODE_")},
            gravity=load_case.gravity, material_name=(solids or shells)[0].material,
            export_tensor_stress=False, solid_group=region.mesh_group if region is not None else None,
            skin_groups_raw=tuple(f"G_SKIN_{r.id}" for r in solids),
            pressure_groups_raw=tuple(f"G_PRESSURE_{r.id}" for r in solids if r.metadata.get("pressure_surfaces")),
            line_modelisation=line_modelisation,
            modelisations=mesh.modelisations, load_case=load_case, mesh=mesh,
            beam_stress="beam_stress" in compiler_inputs, **comm_context,
        )
        _write_export(root / "study.export", export_tensor_stress=False, mixed_analysis=bool(line_elements),
                      beam_stress="beam_stress" in compiler_inputs)
        result_status = "pending_solver"
        payload = {
            **self._mixed_payload(model), "result_status": result_status,
            "code_aster_solve_ready": True, "runtime_blocker": None,
            "qualification_status": "qualified",
        }
        dump_solver_sidecar(
            root / "study_tuba_fem.json", solver_name=self.SOLVER_NAME,
            load_case=load_case_name, analysis_mesh_id=mesh.id,
            name_map=name_map, lineage=self._build_lineage(model, name_map),
            mixed_analysis=payload, solver_input_identity=identity,
        )
        study = AnalysisStudy(
            id=f"step_analysis_study:{load_case_name}",
            model_revision=int(getattr(model, "revision", 0)),
            solver_name=self.SOLVER_NAME, load_case=load_case_name, work_dir=str(root),
            input_files={key: str(root / filename) for key, filename in {
                "med": "study.med", "comm": "study.comm", "export": "study.export",
                "manifest": "study_manifest.json", "sidecar": "study_tuba_fem.json",
            }.items()},
            mesh_id=mesh.id,
            metadata={
                "project_name": model.project_name, "volume_analysis": True,
                "mixed_analysis": True, "step_component_analysis": True,
                "solid_analysis": bool(solids), "shell_analysis": bool(shells),
                "region_modelisations": {r.mesh_group: r.code_aster_modelisation for r in model.analysis_regions.values()},
                "line_force_exported": bool(line_elements),
                "result_status": result_status, "code_aster_solve_ready": True,
                "runtime_blocker": None,
                "qualification_status": "qualified", "compiler_inputs": compiler_inputs,
                "tensor_stress_exported": False,
                "fixed_face_groups": fixed_face_groups,
                "gmsh_version": generated.gmsh_version, "mesh_settings": generated.settings,
            },
            solver_input_identity=identity,
        )
        dump_study_manifest(root / "study_manifest.json", study, mesh)
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
        from tuba.geometry._native_worker import read_source, run_native
        source_digests = []
        for asset in self._existing_step_assets(model):
            source_digests.append((str(Path(asset.source_path).resolve()), hashlib.sha256(read_source(asset.source_path)).hexdigest()))
        run_native("legacy_step_mesh", json.dumps(model.to_dict(), allow_nan=False, separators=(",", ":")).encode("utf-8"),
                   output_path=str(Path(path).resolve()), source_digests=source_digests)

    def _write_med_with_gmsh_native(self, model: TubaModel, path: Path) -> None:
        try:
            import gmsh
        except ImportError as exc:
            raise RuntimeError("gmsh is required to write MED studies from STEP assets.") from exc

        name_map = self._group_name_map(model)
        from tuba.geometry._native_worker import MAX_CAD_ENTITIES, MAX_OUTPUT_BYTES, NativeImportError, read_source
        from tuba.meshing.step_component import _check_mesh_budget
        try:
            with gmsh_model(gmsh, "tuba_mixed"):
                volume_tags_by_asset: dict[str, list[int]] = {}
                known_volume_tags: set[int] = set()
                for asset in self._existing_step_assets(model):
                    source = Path(asset.source_path)
                    read_source(source)
                    gmsh.model.occ.importShapes(str(source))
                    gmsh.model.occ.synchronize()
                    if len(gmsh.model.getEntities()) > MAX_CAD_ENTITIES:
                        raise NativeImportError("Legacy STEP CAD entity budget exceeded before meshing.")
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
                _check_mesh_budget()
                gmsh.write(str(path))
        except Exception as exc:
            raise RuntimeError(f"Failed to write Gmsh MED mesh {path}: {exc}") from exc
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"Gmsh MED writer produced an empty file: {path}")
        if path.stat().st_size > MAX_OUTPUT_BYTES:
            raise NativeImportError("Native MED mesh exceeds 64 MiB.")

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
        write_artifact_text(path, "\n".join(lines) + "\n")

    def _write_export(self, root: Path, path: Path) -> None:
        write_artifact_text(
            path,
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
        )

    def _build_lineage(self, model: TubaModel, name_map: dict[str, str]) -> dict[str, str]:
        lineage = {name_map["G_TUBE"]: "group:G_TUBE"} if "G_TUBE" in name_map else {}
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
