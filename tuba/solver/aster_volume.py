"""Export native pipe-volume meshes as explicit Code_Aster 3D studies."""

from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path
from typing import Any, Iterable, NamedTuple

from tuba.analysis import AnalysisStudy
from tuba.analysis.provenance import (
    SolverInputIdentity,
    build_solver_input_identity,
)
from tuba.geometry.volume import VolumeGeometry, build_volume_geometry
from tuba.solver.compiler_contract import volume_contract, reject_fluid_contents
from tuba.meshing import build_pipe_volume_mesh
from tuba.meshing.policy import resolve_mesh_policy
from tuba.model import PipeSection, RectangularSection, TubaModel
from tuba.solver.aster_comm import _pipe_orientation_vector
from tuba.solver.code_aster_runtime import export_text, write_artifact_text
from tuba.solver.aster_loads import resolve_operation_field_groups
from tuba.solver.aster_sidecar import build_solver_name_map, dump_solver_sidecar, dump_study_manifest
from tuba.solver.modelisation import PipeModelization


class VolumeStudyInputs(NamedTuple):
    """What a pipe-volume export compiles, resolved without meshing or writing."""

    load_case_name: str
    load_case: Any
    element_ids: tuple[str, ...]
    line_elements: list
    compiler_inputs: dict[str, Any]
    solver_input_identity: SolverInputIdentity
    geometry: VolumeGeometry


def volume_study_inputs(
    model: TubaModel,
    load_case_name: str | None,
    *,
    element_ids: Iterable[str],
    max_element_size: float | None = None,
    element_order: int = 2,
    export_tensor_stress: bool = False,
) -> VolumeStudyInputs:
    """Resolve the solved case and fingerprint what the volume export compiles (spec decision 15).

    The fingerprint never reads the Gmsh mesh, so this meshes and writes nothing.
    """
    from tuba.solver.aster_contact import shoes

    shoes(model, PipeModelization.SOLID_3D)
    load_case_name, load_case = model.resolve_load_case(load_case_name)
    model.validate()
    reject_fluid_contents(load_case, "volume and mixed studies")
    if any(model.get_insulation(f"element:{element.id}") for element in model.elements):
        raise ValueError("Insulated pipe-volume studies are not supported; use the pipe beam/TUYAU solver so insulation weight is included.")
    ids = tuple(element_ids)
    line_elements = [element for element in model.elements if element.id not in ids]
    geometry = build_volume_geometry(model, ids)
    policy = resolve_mesh_policy(model,max_element_size=max_element_size,volume_geometry=geometry)
    contract = volume_contract(
        model,
        element_ids=ids,
        line_element_ids=[element.id for element in line_elements],
        element_order=element_order,
        max_element_size=policy._data["global_size_m"],
        export_tensor_stress=export_tensor_stress,
    )
    compiler_inputs = {**contract.compiler_inputs, "volume_geometry": geometry.to_dict()}
    from tuba.meshing.policy import has_mesh_policy
    if has_mesh_policy(model) or line_elements:
        compiler_inputs["mesh_policy"] = policy.to_dict()
    identity = build_solver_input_identity(
        model,
        load_case_name,
        compiler_id=contract.compiler_id,
        compiler_inputs=compiler_inputs,
    )
    return VolumeStudyInputs(
        load_case_name,
        load_case,
        ids,
        line_elements,
        compiler_inputs,
        identity,
        geometry,
    )


class PipeVolumeStudyExporter:
    SOLVER_NAME = "Code_Aster"

    def export_analysis_study(
        self,
        model: TubaModel,
        load_case_name: str | None,
        output_dir: str | Path,
        *,
        element_ids: Iterable[str],
        max_element_size: float | None = None,
        element_order: int = 2,
        export_tensor_stress: bool = False,
    ) -> AnalysisStudy:
        load_case_name, load_case, ids, line_elements, compiler_inputs, identity, geometry = volume_study_inputs(
            model,
            load_case_name,
            element_ids=element_ids,
            max_element_size=max_element_size,
            element_order=element_order,
            export_tensor_stress=export_tensor_stress,
        )
        mixed_analysis = bool(line_elements)
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        med_path = root / "study.med"
        comm_path = root / "study.comm"
        export_path = root / "study.export"
        manifest_path = root / "study_manifest.json"
        sidecar_path = root / "study_tuba_fem.json"
        _reject_unimplemented_loads(load_case, line_elements)
        pressure = _selected_pressure(model, load_case, ids)

        generated = build_pipe_volume_mesh(
            model,
            med_path,
            element_ids=ids,
            max_element_size=max_element_size,
            element_order=element_order,
            geometry=geometry,
            mesh_policy=resolve_mesh_policy(model,max_element_size=max_element_size,volume_geometry=geometry),
        )
        analysis_mesh = replace(generated.analysis_mesh, solver_input_identity=identity)
        name_map = build_solver_name_map(generated.groups)
        support_groups = _support_groups(model, generated.groups)
        couplings = _coupling_groups(model, generated.groups, ids)
        _write_comm(
            model,
            comm_path,
            name_map=name_map,
            pressure=pressure,
            support_groups=support_groups,
            couplings=couplings,
            line_elements=line_elements,
            nodal_forces=load_case.nodal_forces,
            node_groups={
                name: members[0]
                for name, members in generated.groups.items()
                if name.startswith("G_NODE_")
            },
            gravity=load_case.gravity,
            material_name=model.get_element(ids[0]).material,
            export_tensor_stress=export_tensor_stress,
        )
        _write_export(
            export_path,
            export_tensor_stress=export_tensor_stress,
            mixed_analysis=mixed_analysis,
        )
        dump_solver_sidecar(
            sidecar_path,
            solver_name=self.SOLVER_NAME,
            load_case=load_case_name,
            analysis_mesh_id=analysis_mesh.id,
            name_map=name_map,
            lineage={mapped: _group_lineage(raw) for raw, mapped in name_map.items()},
            solver_input_identity=identity,
        )

        metadata = {
            "project_name": model.project_name,
            "volume_analysis": True,
            "pipe_modelization": (
                "MIXED_1D_3D" if mixed_analysis else PipeModelization.SOLID_3D.value
            ),
            **({"mixed_analysis": True} if mixed_analysis else {}),
            "result_status": "pending_solver",
            "code_aster_solve_ready": True,
            "compiler_inputs": compiler_inputs,
            "gmsh_version": generated.gmsh_version,
            "mesh_settings": generated.settings,
            "tensor_stress_exported": bool(export_tensor_stress),
        }
        study = AnalysisStudy(
            id=f"pipe_volume_study:{load_case_name}",
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
            metadata=metadata,
            solver_input_identity=identity,
        )
        dump_study_manifest(manifest_path, study, analysis_mesh)
        return study


def _selected_pressure(model: TubaModel, load_case, element_ids: tuple[str, ...]) -> float:
    by_element = {element_id: float(load_case.internal_pressure) for element_id in element_ids}
    for field_element_ids, value in resolve_operation_field_groups(model, load_case, "pressure"):
        for element_id in set(field_element_ids) & set(element_ids):
            by_element[element_id] = float(value)
    values = set(by_element.values())
    if len(values) != 1:
        raise ValueError("A fused pipe-volume region requires one resolved internal pressure.")
    return values.pop()


def _support_groups(
    model: TubaModel,
    groups: dict[str, tuple[str, ...]],
) -> tuple[tuple[str, str], ...]:
    anchors: list[tuple[str, str]] = []
    for support in model.supports:
        if support.type != "anchor":
            raise ValueError("Pipe-volume studies currently support anchor boundary conditions only.")
        node_group = f"G_NODE_{support.node}"
        face_group = f"G_END_{support.node}"
        if node_group in groups:
            anchors.append((node_group, "node"))
        elif face_group in groups:
            anchors.append((face_group, "face"))
        else:
            raise ValueError(f"Anchor node {support.node!r} is not represented in the mixed mesh.")
    if not anchors:
        raise ValueError("Pipe-volume studies require at least one anchored terminal.")
    return tuple(dict.fromkeys(anchors))


def _coupling_groups(
    model: TubaModel,
    groups: dict[str, tuple[str, ...]],
    volume_element_ids: tuple[str, ...],
) -> tuple[tuple[str, str, tuple[float, float, float]], ...]:
    selected = set(volume_element_ids)
    line_elements = [element for element in model.elements if element.id not in selected]
    if not line_elements:
        return ()
    sections = {element.section for element in line_elements}
    materials = {element.material for element in line_elements}
    volume_materials = {model.get_element(element_id).material for element_id in selected}
    if len(sections) != 1 or len(materials | volume_materials) != 1:
        raise ValueError("Native mixed 1D/3D studies currently require one pipe section and material.")
    section = model.sections.get(next(iter(sections)))
    if not isinstance(section, PipeSection):
        raise ValueError("Native mixed 1D/3D studies require a circular PipeSection.")

    by_terminal: dict[str, list] = {}
    for element in line_elements:
        for node_id in (element.n1, element.n2):
            if f"G_END_{node_id}" in groups:
                by_terminal.setdefault(node_id, []).append(element)
    couplings = []
    for node_id, adjacent in by_terminal.items():
        if len(adjacent) != 1:
            raise ValueError(f"Volume terminal {node_id!r} must meet exactly one 1D continuation element.")
        element = adjacent[0]
        start = model.nodes[element.n1].coords
        end = model.nodes[element.n2].coords
        direction = tuple(float(end[index] - start[index]) for index in range(3))
        length = math.sqrt(sum(value * value for value in direction))
        axis = tuple(value / length for value in direction)
        couplings.append((f"G_END_{node_id}", f"G_NODE_{node_id}", axis))
    if not couplings:
        raise ValueError("Mixed 1D/3D studies require at least one pipe-to-solid terminal coupling.")
    return tuple(couplings)


def _reject_unimplemented_loads(load_case, line_elements: list) -> None:
    if any(field.quantity == "wind" for field in load_case.fields):
        raise ValueError("Pipe-volume wind loading is not implemented.")
    if any(field.quantity == "line_load" for field in load_case.fields):
        raise ValueError("Pipe-volume line loads are not implemented.")
    if load_case.nodal_forces:
        if not line_elements:
            raise ValueError(
                "Pipe-volume nodal forces act on the 1D TUYAU_3M remainder; this study is solid-only."
            )
        beam_nodes = {node for element in line_elements for node in (element.n1, element.n2)}
        off_pipe = sorted(force.node for force in load_case.nodal_forces if force.node not in beam_nodes)
        if off_pipe:
            raise ValueError(
                f"Pipe-volume nodal forces must act on nodes of the 1D pipe remainder; got {off_pipe!r}."
            )
    if abs(load_case.temperature - load_case.ref_temperature) > 1.0e-10:
        raise ValueError("Pipe-volume thermal loading is not implemented.")
    if any(field.quantity == "temperature" for field in load_case.fields):
        raise ValueError("Pipe-volume thermal fields are not implemented.")


def mixed_pipe_generatrices(model, line_elements):
    """One endpoint seed for each supported, oriented straight TUYAU chain."""
    # ponytail: collinear open chains; qualify bent/branched propagation before extending.
    pipes = {element.id: element for element in line_elements if element.type == "pipe_straight"}
    incident = {}
    for element in pipes.values():
        for node in (element.n1, element.n2):
            incident.setdefault(node, []).append(element.id)
    if any(len(ids) > 2 for ids in incident.values()):
        raise ValueError("Native mixed TUYAU generatrices do not support branching pipe chains.")
    unseen = set(pipes)
    rows = []
    for first_id in pipes:
        if first_id not in unseen:
            continue
        component = set()
        pending = [first_id]
        while pending:
            element_id = pending.pop()
            if element_id in component:
                continue
            component.add(element_id)
            element = pipes[element_id]
            pending.extend(other for node in (element.n1, element.n2) for other in incident[node] if other not in component)
        unseen.difference_update(component)
        nodes = {node for element_id in component for node in (pipes[element_id].n1, pipes[element_id].n2)}
        endpoints = [node for node in nodes if len(incident[node]) == 1]
        if len(endpoints) != 2:
            raise ValueError("Native mixed TUYAU generatrices require an open pipe chain without loops.")
        outgoing, incoming = {}, {}
        for element_id in component:
            element = pipes[element_id]
            if element.n1 in outgoing or element.n2 in incoming:
                raise ValueError("Native mixed TUYAU pipe chains must have consistent n1-to-n2 orientation.")
            outgoing[element.n1] = element_id
            incoming[element.n2] = element_id
        starts = [node for node in endpoints if node not in incoming]
        if len(starts) != 1:
            raise ValueError("Native mixed TUYAU pipe chains must have consistent n1-to-n2 orientation.")
        start = starts[0]
        ordered = []
        node = start
        while node in outgoing:
            element = pipes[outgoing[node]]
            ordered.append(element)
            node = element.n2
        if len(ordered) != len(component):
            raise ValueError("Native mixed TUYAU pipe chains must have consistent n1-to-n2 orientation.")
        axis = None
        for element in ordered:
            vector = model.nodes[element.n2].coords - model.nodes[element.n1].coords
            length = math.sqrt(float(sum(value * value for value in vector)))
            if length <= 1e-12:
                raise ValueError("Native mixed TUYAU pipe chains require nonzero element lengths.")
            direction = tuple(float(value) / length for value in vector)
            if axis is None:
                axis = direction
            elif math.dist(direction, axis) > 1e-8:
                raise ValueError("Native mixed TUYAU generatrices currently require collinear pipe chains.")
        rows.append({"element_ids": [element.id for element in ordered], "start_node": start,
                     "vector": list(_pipe_orientation_vector(model, ordered, []))})
    return rows


def mixed_load_inputs(model, load_case, line_elements, physical_regions):
    """Resolve supported mixed loads once for the compiler's auditable identity."""
    from tuba.physical import _fluid_density_by_element, _physical_properties_for_element
    from tuba.solver.aster_loads import resolve_region_temperature_groups, resolve_node_temperatures

    refused = sorted({field.quantity for field in load_case.fields} - {"temperature", "pressure", "fluid_density"})
    if refused:
        raise ValueError(f"Native mixed studies do not implement operation fields {refused!r}.")
    if any(field.quantity == "temperature" and field.profile != "uniform" for field in load_case.fields):
        raise ValueError("Native mixed temperature fields currently require a uniform profile; node temperatures can define interpolation.")
    if load_case.buckling is not None:
        raise ValueError("Native mixed buckling analysis is not supported.")
    temperature_fields = resolve_operation_field_groups(model, load_case, "temperature")
    region_temperatures = resolve_region_temperature_groups(model, load_case)
    temperatures = {element.id: float(load_case.temperature) for element in line_elements}
    for ids, temperature in temperature_fields:
        for element_id in ids:
            temperatures[element_id] = float(temperature)
    node_temperatures = resolve_node_temperatures(model, load_case)
    region_values = {region.mesh_group: float(load_case.temperature) for region in physical_regions}
    region_values.update({group: float(temperature) for groups, temperature in region_temperatures for group in groups})
    densities = _fluid_density_by_element(model, load_case)
    properties = {}
    pipe_generatrices = mixed_pipe_generatrices(model, line_elements)
    for element in line_elements:
        mat = model.materials[element.material]
        rho = float(mat.rho)
        if densities.get(element.id):
            physical = _physical_properties_for_element(model, element, densities[element.id])
            rho = physical.mass_kg_per_m / physical.metal_area_m2
        properties[element.id] = {"section": element.section, "material": element.material,
                                  "E": float(mat.E), "nu": float(mat.nu), "alpha": float(mat.alpha), "rho": rho}
    pipe_pressure = {e.id: float(load_case.internal_pressure) for e in line_elements if e.type == "pipe_straight"}
    pipe_pressure.update({element_id: float(value) for ids, value in resolve_operation_field_groups(model, load_case, "pressure") for element_id in ids})
    return {
        "line_properties": properties,
        "line_temperatures": temperatures,
        "region_temperatures": region_values,
        "node_temperatures": node_temperatures,
        "fluid_density": densities,
        "pipe_pressure": pipe_pressure,
        "pipe_generatrices": pipe_generatrices,
    }


def _write_mixed_temperature(lines, model, load_case, mesh, name_map, regions, line_elements, affe_entries):
    # Separate AFFE_VARC scopes preserve prescribed member temperatures at a
    # mechanical joint. A single global nodal field lets the last group written
    # silently change all neighbouring elements sharing that node.
    resolved = mixed_load_inputs(model, load_case, line_elements, regions)
    uniform = {}
    interpolated = []
    node_values = resolved["node_temperatures"]
    for region in regions:
        uniform.setdefault(resolved["region_temperatures"][region.mesh_group], []).append(region.mesh_group)
    for element in line_elements:
        temperature = resolved["line_temperatures"][element.id]
        group = f"G_LINE_{element.id}"
        if element.n1 not in node_values and element.n2 not in node_values:
            uniform.setdefault(temperature, []).append(group)
            continue
        if mesh is None:
            raise ValueError("Mixed node temperature interpolation requires the actual analysis mesh.")
        start, end = model.nodes[element.n1].coords, model.nodes[element.n2].coords
        axis = end - start
        length_squared = float(sum(value * value for value in axis))
        t0 = node_values.get(element.n1, temperature)
        t1 = node_values.get(element.n2, temperature)
        ids = dict.fromkeys(node for cell in mesh.groups[group] for node in mesh.elements[cell])
        rows = []
        for node in ids:
            fraction = float(sum((mesh.nodes[node][i] - start[i]) * axis[i] for i in range(3))) / length_squared
            rows.append((node, (1 - fraction) * t0 + fraction * t1))
        interpolated.append(([group], temperature, rows))
    partitions = [(groups, temperature, []) for temperature, groups in uniform.items()] + interpolated
    if not partitions:
        return
    assignments = []
    for index, (groups, temperature, rows) in enumerate(partitions):
        field = f"TF{index}"
        lines.extend([f"{field} = CREA_CHAMP(TYPE_CHAM='NOEU_TEMP_R', OPERATION='AFFE', MAILLAGE=MAIL, AFFE=(",
                      f"    _F(TOUT='OUI', NOM_CMP='TEMP', VALE={temperature:.12E}),"])
        for node_id, value in rows:
            lines.append(f"    _F(NOEUD='{node_id.removeprefix('VN')}', NOM_CMP='TEMP', VALE={value:.12E}),")
        lines.append("));")
        assignments.append(f"    _F(GROUP_MA={tuple(name_map[g] for g in groups)!r}, NOM_VARC='TEMP', CHAM_GD={field}, VALE_REF={float(load_case.ref_temperature):.12E}),")
    lines.extend(["CHMAT = AFFE_MATERIAU(MAILLAGE=MAIL, AFFE=(", *affe_entries, "), AFFE_VARC=(", *assignments, "));"])


def _write_comm(
    model: TubaModel,
    path: Path,
    *,
    name_map: dict[str, str],
    pressure: float,
    support_groups: tuple[tuple[str, str], ...],
    couplings: tuple[tuple[str, str, tuple[float, float, float]], ...],
    line_elements: list,
    nodal_forces: list,
    node_groups: dict[str, str],
    gravity: bool,
    material_name: str,
    export_tensor_stress: bool,
    solid_group: str | None = "G_SOLID_region_0",
    skin_groups_raw: tuple[str, ...] | None = None,
    pressure_groups_raw: tuple[str, ...] = ("G_INNER_region_0",),
    line_modelisation: str = "TUYAU_3M",
    modelisations: dict[str, str] | None = None,
    solid_regions: tuple = (),
    shell_regions: tuple = (),
    reference_regions: tuple = (),
    rigid_patch_groups: tuple[str, ...] = (),
    beam_stress: bool = False,
    load_case=None,
    mesh=None,
) -> None:
    material = model.materials[material_name]
    solid = name_map[solid_group] if solid_group is not None else None
    skin_groups = [
        mapped
        for raw, mapped in name_map.items()
        if (raw in skin_groups_raw if skin_groups_raw is not None else raw.startswith(("G_INNER_", "G_OUTER_", "G_END_")))
    ]
    skin_group_value = "(" + ", ".join(f"'{group}'" for group in skin_groups) + ",)"
    extended = modelisations is not None
    mixed = bool(line_elements or shell_regions or reference_regions)
    has_characteristics = mixed
    line_families = {element.id: ("POU_D_T" if element.type == "beam" else "TUYAU_3M")
                     if extended else line_modelisation for element in line_elements}
    pipe_elements = [e for e in line_elements if line_families[e.id] == "TUYAU_3M"]
    lines = ["DEBUT(PAR_LOT='NON');", "MAIL = LIRE_MAILLAGE(FORMAT='MED', UNITE=20);"]
    if skin_groups:
        volume_groups = tuple(name_map[r.mesh_group] for r in solid_regions) if solid_regions else (solid,)
        lines.extend(["MAIL = MODI_MAILLAGE(",
        "    reuse=MAIL,",
        "    MAILLAGE=MAIL,",
        "    ORIE_PEAU_3D=_F(",
        f"        GROUP_MA={skin_group_value},",
        f"        GROUP_MA_VOLU={volume_groups!r},",
        "    ),",
        ");",
        ])
    if node_groups and not extended:
        lines.extend(["MAIL = DEFI_GROUP(", "    reuse=MAIL,", "    MAILLAGE=MAIL,", "    CREA_GROUP_NO=("])
        for raw_group, mesh_node_id in node_groups.items():
            lines.append(
                f"        _F(NOM='{name_map[raw_group]}', NOEUD='{mesh_node_id.removeprefix('VN')}'),"
            )
        lines.extend(["    ),", ");"])
    lines.extend(["MODELE = AFFE_MODELE(", "    MAILLAGE=MAIL,"])
    if extended:
        assignments = dict(modelisations)
        assignments.update({group: "3D" for group in skin_groups_raw or ()})
        lines.append("    AFFE=(")
        for group, family in assignments.items():
            lines.append(f"        _F(GROUP_MA='{name_map[group]}', PHENOMENE='MECANIQUE', MODELISATION='{family}'),")
        lines.append("    ),")
    elif mixed:
        solid_groups = "(" + ", ".join(f"'{group}'" for group in (solid, *skin_groups)) + ",)"
        lines.extend(
            [
                "    AFFE=(",
                f"        _F(GROUP_MA={solid_groups}, PHENOMENE='MECANIQUE', MODELISATION='3D'),",
                f"        _F(GROUP_MA='{name_map['G_TUBE']}', PHENOMENE='MECANIQUE', MODELISATION='{line_modelisation}'),",
                "    ),",
            ]
        )
    else:
        lines.extend(
            [
                "    AFFE=_F(",
                "        TOUT='OUI',",
                "        PHENOMENE='MECANIQUE',",
                "        MODELISATION='3D',",
                "    ),",
            ]
        )
    lines.extend(
        [
        ");",
        "MAT = DEFI_MATERIAU(",
        "    ELAS=_F(",
        f"        E={material.E:.12E},",
        f"        NU={material.nu:.12E},",
        f"        RHO={material.rho:.12E},",
        f"        ALPHA={material.alpha:.12E},",
        "    ),",
        ");",
        ]
    )
    affe_entries = ([f"        _F(GROUP_MA='{solid}', MATER=MAT),"] if solid else []) if extended else [
        "        _F(TOUT='OUI', MATER=MAT)," if mixed else f"        _F(GROUP_MA='{solid}', MATER=MAT),"]
    if extended:
        from tuba.physical import _fluid_density_by_element, _physical_properties_for_element

        densities = _fluid_density_by_element(model, load_case)
        rows = [(f"G_LINE_{element.id}", element.material, element) for element in line_elements]
        rows.extend((region.mesh_group, region.material, None) for region in shell_regions)
        rows.extend((region.mesh_group, region.material, None) for region in solid_regions if region.mesh_group != solid_group)
        for index, (group, material_id, element) in enumerate(rows):
            mat = model.materials[material_id]
            rho = mat.rho
            if element is not None and densities.get(element.id):
                props = _physical_properties_for_element(model, element, densities[element.id])
                rho = props.mass_kg_per_m / props.metal_area_m2
                lines.append(f"# Fluid contents mass for {element.id}: {props.fluid_mass_kg_per_m:.12E} kg/m")
            concept = f"MAT{index:05d}"
            if len(concept) > 8:
                raise ValueError("Mixed material assignments exceed Code_Aster's concept-name limit.")
            lines.append(f"{concept} = DEFI_MATERIAU(ELAS=_F(E={mat.E:.12E}, NU={mat.nu:.12E}, RHO={rho:.12E}, ALPHA={mat.alpha:.12E}));")
            affe_entries.append(f"        _F(GROUP_MA='{name_map[group]}', MATER={concept}),")
    lines.extend(["CHMAT = AFFE_MATERIAU(", "    MAILLAGE=MAIL,", "    AFFE=(", *affe_entries, "    ),", ");"])
    if has_characteristics:
        lines.extend(["CARA = AFFE_CARA_ELEM(", "    MODELE=MODELE,"])
    if line_elements:
        lines.append("    POUTRE=(")
        section_elements = line_elements if extended else line_elements[:1]
        for element in section_elements:
            section = model.sections[element.section]
            family = line_families[element.id]
            group = f"G_LINE_{element.id}" if extended else "G_TUBE"
            if isinstance(section, PipeSection):
                section_kind, section_keys = "CERCLE", ("R", "EP")
                section_values = (section.OD / 2.0, section.WT)
            elif family == "POU_D_T" and isinstance(section, RectangularSection):
                section_kind, section_keys = "RECTANGLE", ("HY", "HZ")
                section_values = (section.height_y, section.height_z)
                if section.thickness_y or section.thickness_z:
                    section_keys += ("EPY", "EPZ")
                    section_values += (section.thickness_y, section.thickness_z)
            else:
                raise ValueError("Mixed studies support circular pipe or rectangular beam sections.")
            lines.append(f"        _F(GROUP_MA='{name_map[group]}', SECTION='{section_kind}', CARA={section_keys!r}, VALE={section_values!r}),")
        lines.extend(["    ),", "    ORIENTATION=("])
        pipe_elements = [e for e in line_elements if line_families[e.id] == "TUYAU_3M"]
        generatrices = mixed_pipe_generatrices(model, pipe_elements) if extended else [
            {"start_node": element.n1, "vector": _pipe_orientation_vector(model, pipe_elements, [])}
            for element in pipe_elements]
        for generatrice in generatrices:
            orientation = generatrice["vector"]
            node_group = name_map["G_NODE_" + generatrice["start_node"]]
            lines.extend([
                "        _F(", f"            GROUP_NO='{node_group}',",
                "            CARA='GENE_TUYAU',",
                f"            VALE=({orientation[0]:.8E}, {orientation[1]:.8E}, {orientation[2]:.8E}),", "        ),",
            ])
        from tuba.geometry.section_mesh import beam_local_frame

        for element in (e for e in line_elements if line_families[e.id] == "POU_D_T"):
            _x, local_y, _z = beam_local_frame(model.nodes[element.n1].coords, model.nodes[element.n2].coords)
            vector = tuple(float(value) for value in local_y)
            lines.append(f"        _F(GROUP_MA='{name_map[f'G_LINE_{element.id}']}', CARA='VECT_Y', VALE={vector!r}),")
        lines.append("    ),")
    if shell_regions:
        lines.append("    COQUE=(")
        for region in shell_regions:
            lines.append(f"        _F(GROUP_MA='{name_map[region.mesh_group]}', EPAIS={float(region.metadata['thickness_m']):.12E}, COQUE_NCOU=1),")
        lines.append("    ),")
    if reference_regions:
        lines.append("    DISCRET=(")
        for region in reference_regions:
            lines.append(f"        _F(GROUP_MA='{name_map[region.mesh_group]}', REPERE='GLOBAL', CARA='K_TR_D_N', VALE=(0., 0., 0., 0., 0., 0.)),")
            lines.append(f"        _F(GROUP_MA='{name_map[region.mesh_group]}', REPERE='GLOBAL', CARA='M_TR_D_N', VALE=(0., 0., 0., 0., 0., 0., 0., 0., 0., 0.)),")
        lines.append("    ),")
    if has_characteristics:
        lines.append(");")
    if extended and load_case is not None:
        _write_mixed_temperature(lines, model, load_case, mesh, name_map,
                                 (*solid_regions, *shell_regions), line_elements, affe_entries)

    lines.extend(["BC = AFFE_CHAR_MECA(", "    MODELE=MODELE,", "    DDL_IMPO=("])
    if extended:
        from tuba.solver.aster_comm import _held_dofs
        for support in model.supports:
            if support.attached_to is not None:
                continue
            held = _held_dofs(support)
            motion = list(support.imposed_displacement or ())
            values = {dof: float(motion[index]) if index < len(motion) else 0.0
                      for index, dof in enumerate(("DX", "DY", "DZ", "DRX", "DRY", "DRZ")) if dof in held}
            if values:
                entries = ", ".join(f"{dof}={value:.12E}" for dof, value in values.items())
                if len(held) == 6 and support.node in {node for e in pipe_elements for node in (e.n1, e.n2)}:
                    entries += ", WO=0.0"
                lines.append(f"        _F(GROUP_NO='{name_map[f'G_NODE_{support.node}']}', {entries}),")
    for group, kind in support_groups:
        if extended and kind == "node":
            continue
        if kind == "node":
            warping = ", WO=0.0" if line_modelisation == "TUYAU_3M" else ""
            lines.append(f"        _F(GROUP_NO='{name_map[group]}', BLOCAGE=('DEPLACEMENT', 'ROTATION'){warping}),")
        else:
            lines.append(f"        _F(GROUP_MA='{name_map[group]}', DX=0.0, DY=0.0, DZ=0.0),")
    lines.append("    ),")
    if extended:
        from tuba.solver.aster_contact import attachment_equations
        attachment_rows = []
        def attachment_name(raw):
            return name_map[f"G_NODE_{raw.removeprefix('GN_')}"]
        for support in model.supports:
            if support.attached_to is not None:
                attachment_rows.extend(attachment_equations(model, support, f"GN_{support.node}", _held_dofs(support), attachment_name))
        if attachment_rows:
            lines.extend(["    LIAISON_DDL=(", *(f"        {row}," for row in attachment_rows), "    ),"])
        if rigid_patch_groups:
            # Patches on adjoining faces/edges may share physical nodes as well
            # as their reference. One rigid body per reference avoids duplicate
            # Lagrange equations for those intersections.
            references = {patch.metadata["mesh_node_group"]: patch.source_node.id
                          for patch in model.couplings.values() if patch.kind == "rigid_patch"}
            bodies = {}
            for group in rigid_patch_groups:
                bodies.setdefault(references.get(group, group), []).append(name_map[group])
            lines.append("    LIAISON_SOLIDE=(")
            for groups in bodies.values():
                value = groups[0] if len(groups) == 1 else tuple(groups)
                lines.append(f"        _F(GROUP_NO={value!r}),")
            lines.append("    ),")
    if couplings:
        lines.append("    LIAISON_ELEM=(")
        for coupling in couplings:
            face_group, node_group, axis = coupling[:3]
            option = coupling[3] if len(coupling) == 4 else ("3D_TUYAU" if line_modelisation == "TUYAU_3M" else "3D_POU")
            lines.extend(["        _F(", f"            OPTION='{option}',"])
            if option == "3D_TUYAU":
                lines.extend(["            CARA_ELEM=CARA,", f"            AXE_POUTRE=({axis[0]:.8E}, {axis[1]:.8E}, {axis[2]:.8E}),"])
            lines.extend([f"            GROUP_MA_1='{name_map[face_group]}',", f"            GROUP_NO_2='{name_map[node_group]}',", "        ),"])
        lines.append("    ),")
    lines.append(");")

    if nodal_forces:
        lines.extend(
            [
                "POINT_FORCE = AFFE_CHAR_MECA(",
                "    MODELE=MODELE,",
                "    FORCE_NODALE=(",
            ]
        )
        for force in nodal_forces:
            lines.append("        _F(")
            lines.append(f"            GROUP_NO='{name_map[f'G_NODE_{force.node}']}',")
            for name, value in zip(("FX", "FY", "FZ", "MX", "MY", "MZ"), force.components):
                lines.append(f"            {name}={float(value):.8E},")
            lines.append("        ),")
        lines.extend(["    ),", ");"])

    excitations = ["_F(CHARGE=BC)"]
    pipe_pressures = []
    if extended:
        pipe_pressures = resolve_operation_field_groups(model, load_case, "pressure")
        if not pipe_pressures:
            pipe_pressures = [([e.id for e in pipe_elements], pressure)]
        pipe_pressures = [(ids, value) for ids, value in pipe_pressures if ids and value != 0]
    if pressure != 0 and solid and not pressure_groups_raw:
        raise ValueError("STEP component pressure requires explicit pressure surface selections.")
    if (pressure != 0.0 and (not extended or pressure_groups_raw)) or pipe_pressures:
        pressure_groups = tuple(name_map[group] for group in pressure_groups_raw)
        pressure_group_value = repr(pressure_groups[0]) if len(pressure_groups) == 1 else repr(pressure_groups)
        lines.extend(
            [
                "PRESSURE = AFFE_CHAR_MECA(",
                "    MODELE=MODELE,",
            ]
        )
        if pressure != 0 and pressure_groups_raw:
            lines.extend(["    PRES_REP=_F(", f"        GROUP_MA={pressure_group_value},", f"        PRES={pressure:.12E},", "    ),"])
        if extended and pipe_pressures:
            if len(pipe_pressures) == 1:
                element_ids, value = pipe_pressures[0]
                lines.extend(["    FORCE_TUYAU=_F(", f"        GROUP_MA={tuple(name_map[f'G_LINE_{e}'] for e in element_ids)!r},", f"        PRES={value:.12E},", "    ),"])
            else:
                lines.append("    FORCE_TUYAU=(")
                for element_ids, value in pipe_pressures:
                    lines.append(f"        _F(GROUP_MA={tuple(name_map[f'G_LINE_{e}'] for e in element_ids)!r}, PRES={value:.12E}),")
                lines.append("    ),")
        elif not extended and mixed and line_modelisation == "TUYAU_3M":
            lines.extend(
                [
                    "    FORCE_TUYAU=_F(",
                    f"        GROUP_MA='{name_map['G_TUBE']}',",
                    f"        PRES={pressure:.12E},",
                    "    ),",
                ]
            )
        lines.append(");")
        excitations.append("_F(CHARGE=PRESSURE)")
    if gravity:
        lines.extend(
            [
                "GRAVITY = AFFE_CHAR_MECA(",
                "    MODELE=MODELE,",
                "    PESANTEUR=_F(GRAVITE=9.80665, DIRECTION=(0.0, 0.0, -1.0)),",
                ");",
            ]
        )
        excitations.append("_F(CHARGE=GRAVITY)")
    if nodal_forces:
        excitations.append("_F(CHARGE=POINT_FORCE)")
    lines.extend(["RESU = MECA_STATIQUE(", "    MODELE=MODELE,", "    CHAM_MATER=CHMAT,"])
    if mixed:
        lines.append("    CARA_ELEM=CARA,")
    if reference_regions:
        # Keep the exact double-Lagrange constraints for zero-stiffness carriers.
        lines.append("    SOLVEUR=_F(METHODE='MULT_FRONT', NPREC=8, STOP_SINGULIER='OUI'),")
    lines.extend(
        [
            f"    EXCIT=({', '.join(excitations)},),",
            ");",
            "RESU = CALC_CHAMP(",
            "    reuse=RESU,",
            "    RESULTAT=RESU,",
            (
                "    CONTRAINTE=('SIGM_ELGA', 'SIGM_ELNO', 'EFGE_ELNO', 'SIEF_ELNO'),"
                if mixed
                else "    CONTRAINTE=('SIGM_ELGA', 'SIGM_ELNO'),"
            ),
            "    CRITERES=('SIEQ_ELGA', 'SIEQ_ELNO'),",
            "    FORCE='REAC_NODA',",
            ");",
        ]
    )
    beam_groups = tuple(name_map[group] for group, family in (modelisations or {}).items() if family == "POU_D_T")
    if beam_stress:
        if not beam_groups:
            raise ValueError("Beam stress was requested for a study without POU_D_T groups.")
        # Frame members only: solids and TUYAU_3M cannot compute SIPO_ELNO.
        lines.extend(["RESU = CALC_CHAMP(", "    reuse=RESU,", "    RESULTAT=RESU,",
                      f"    GROUP_MA={beam_groups!r},", "    CONTRAINTE=('SIPO_ELNO',),", ");"])
    lines.extend(["IMPR_RESU(", "    FORMAT='MED',", "    UNITE=80,"])
    if mixed:
        lines.append(
            "    RESU=_F(RESULTAT=RESU, CARA_ELEM=CARA, "
            "NOM_CHAM=('DEPL', 'SIGM_ELNO', 'SIEQ_ELNO', 'EFGE_ELNO', 'REAC_NODA')),"
        )
    else:
        lines.append(
            "    RESU=_F(RESULTAT=RESU, NOM_CHAM=('DEPL', 'SIGM_ELNO', 'SIEQ_ELNO', 'REAC_NODA')),"
        )
    displacement_components = "('DX', 'DY', 'DZ', 'DRX', 'DRY', 'DRZ')" if mixed else "('DX', 'DY', 'DZ')"
    stress_components = "('VMIS',)" if mixed else "('VMIS', 'TRESCA')"
    lines.extend(
        [
            ");",
            "TAB_DEPL = CREA_TABLE(",
            "    RESU=_F(RESULTAT=RESU, NOM_CHAM='DEPL', TOUT='OUI',",
            f"            NOM_CMP={displacement_components}),",
            ");",
            "IMPR_TABLE(TABLE=TAB_DEPL, FORMAT='TABLEAU', UNITE=39, SEPARATEUR=',');",
            "TAB_REAC = CREA_TABLE(",
            "    RESU=_F(RESULTAT=RESU, NOM_CHAM='REAC_NODA', TOUT='OUI',",
            f"            NOM_CMP={displacement_components}),",
            ");",
            "IMPR_TABLE(TABLE=TAB_REAC, FORMAT='TABLEAU', UNITE=40, SEPARATEUR=',');",
            "TAB_SIEQ = CREA_TABLE(",
            "    RESU=_F(RESULTAT=RESU, NOM_CHAM='SIEQ_ELNO', TOUT='OUI',",
            f"            NOM_CMP={stress_components}),",
            ");",
            "IMPR_TABLE(TABLE=TAB_SIEQ, FORMAT='TABLEAU', UNITE=41, SEPARATEUR=',');",
        ]
    )
    if line_elements:
        line_groups = tuple(name_map[group] for group, family in (modelisations or {"G_TUBE": line_modelisation}).items() if family in {"TUYAU_3M", "POU_D_T"})
        lines.extend(
            [
                "TAB_EFFO = CREA_TABLE(",
                f"    RESU=_F(RESULTAT=RESU, NOM_CHAM='EFGE_ELNO', GROUP_MA={line_groups!r},",
                "            NOM_CMP=('N', 'VY', 'VZ', 'MT', 'MFY', 'MFZ')),",
                ");",
                "IMPR_TABLE(TABLE=TAB_EFFO, FORMAT='TABLEAU', UNITE=38, SEPARATEUR=',');",
            ]
        )
    if beam_stress:
        lines.extend(
            [
                "TAB_SIPO = CREA_TABLE(",
                f"    RESU=_F(RESULTAT=RESU, NOM_CHAM='SIPO_ELNO', GROUP_MA={beam_groups!r},",
                "            NOM_CMP=('SN', 'SMFY', 'SMFZ')),",
                ");",
                "IMPR_TABLE(TABLE=TAB_SIPO, FORMAT='TABLEAU', UNITE=43, SEPARATEUR=',');",
            ]
        )
    if export_tensor_stress:
        lines.extend(
            [
                "TAB_SIGM = CREA_TABLE(",
                "    RESU=_F(RESULTAT=RESU, NOM_CHAM='SIGM_ELNO', TOUT='OUI',",
                "            NOM_CMP=('SIXX', 'SIYY', 'SIZZ', 'SIXY', 'SIXZ', 'SIYZ')),",
                ");",
                "IMPR_TABLE(TABLE=TAB_SIGM, FORMAT='TABLEAU', UNITE=42, SEPARATEUR=',');",
            ]
        )
    lines.extend(
        [
            "FIN();",
        ]
    )
    write_artifact_text(path, "\n".join(lines) + "\n")


def _write_export(path: Path, *, export_tensor_stress: bool, mixed_analysis: bool, beam_stress: bool = False) -> None:
    files = [
        "P actions make_etude",
        "P version stable",
        "P nomjob study",
        "P mode interactif",
        "P ncpus 1",
        "A memjeveux 1024",
        "A tpmax 3600",
        "F comm study.comm D 1",
        "F mmed study.med D 20",
        "F mess study.mess R 6",
        "F rmed study.rmed R 80",
        "F depl study_depl.csv R 39",
        "F reac study_reac.csv R 40",
        "F sieq study_sieq.csv R 41",
    ]
    if mixed_analysis:
        files.append("F effo study_effo.csv R 38")
    if export_tensor_stress:
        files.append("F sigm study_sigm.csv R 42")
    if beam_stress:
        files.append("F sipo study_sipo.csv R 43")
    write_artifact_text(path, export_text(files) + "\n")


def _group_lineage(group_name: str) -> str:
    if group_name.startswith("G_END_"):
        return f"node:{group_name.removeprefix('G_END_')}"
    if group_name.startswith("G_NODE_"):
        return f"node:{group_name.removeprefix('G_NODE_')}"
    if group_name.startswith("G_TEE_"):
        return f"node:{group_name.removeprefix('G_TEE_')}"
    return f"group:{group_name}"
