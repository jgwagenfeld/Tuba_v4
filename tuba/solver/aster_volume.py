"""Export native pipe-volume meshes as explicit Code_Aster 3D studies."""

from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path
from typing import Iterable

from tuba.analysis import AnalysisStudy
from tuba.analysis.provenance import (
    MIXED_CODE_ASTER_COMPILER_ID,
    VOLUME_CODE_ASTER_COMPILER_ID,
    build_solver_input_identity,
)
from tuba.meshing import build_pipe_volume_mesh
from tuba.model import PipeSection, TubaModel
from tuba.solver.aster_comm import _pipe_orientation_vector
from tuba.solver.aster_loads import resolve_operation_field_groups
from tuba.solver.aster_sidecar import build_solver_name_map, dump_solver_sidecar, dump_study_manifest
from tuba.solver.modelisation import PipeModelization


class PipeVolumeStudyExporter:
    SOLVER_NAME = "Code_Aster"

    def export_analysis_study(
        self,
        model: TubaModel,
        load_case_name: str | None,
        output_dir: str | Path,
        *,
        element_ids: Iterable[str],
        max_element_size: float,
        element_order: int = 2,
        export_tensor_stress: bool = True,
    ) -> AnalysisStudy:
        load_case_name, load_case = model.resolve_load_case(load_case_name)
        model.validate()
        ids = tuple(element_ids)
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        med_path = root / "study.med"
        comm_path = root / "study.comm"
        export_path = root / "study.export"
        manifest_path = root / "study_manifest.json"
        sidecar_path = root / "study_tuba_fem.json"
        _reject_unimplemented_loads(load_case)
        pressure = _selected_pressure(model, load_case, ids)

        generated = build_pipe_volume_mesh(
            model,
            med_path,
            element_ids=ids,
            max_element_size=max_element_size,
            element_order=element_order,
        )
        line_elements = [element for element in model.elements if element.id not in ids]
        mixed_analysis = bool(line_elements)
        compiler_inputs = {
            "element_ids": sorted(ids),
            **({"line_element_ids": sorted(element.id for element in line_elements)} if mixed_analysis else {}),
            "element_order": element_order,
            "max_element_size": float(max_element_size),
            "export_tensor_stress": bool(export_tensor_stress),
        }
        identity = build_solver_input_identity(
            model,
            load_case_name,
            compiler_id=(MIXED_CODE_ASTER_COMPILER_ID if mixed_analysis else VOLUME_CODE_ASTER_COMPILER_ID),
            compiler_inputs=compiler_inputs,
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


def _reject_unimplemented_loads(load_case) -> None:
    if load_case.nodal_forces:
        raise ValueError("Pipe-volume nodal-force coupling is not implemented.")
    if abs(load_case.temperature - load_case.ref_temperature) > 1.0e-10:
        raise ValueError("Pipe-volume thermal loading is not implemented.")
    if any(field.quantity == "temperature" for field in load_case.fields):
        raise ValueError("Pipe-volume thermal fields are not implemented.")


def _write_comm(
    model: TubaModel,
    path: Path,
    *,
    name_map: dict[str, str],
    pressure: float,
    support_groups: tuple[tuple[str, str], ...],
    couplings: tuple[tuple[str, str, tuple[float, float, float]], ...],
    line_elements: list,
    node_groups: dict[str, str],
    gravity: bool,
    material_name: str,
    export_tensor_stress: bool,
) -> None:
    material = model.materials[material_name]
    solid = name_map["G_SOLID_region_0"]
    inner = name_map["G_INNER_region_0"]
    skin_groups = [
        mapped
        for raw, mapped in name_map.items()
        if raw.startswith(("G_INNER_", "G_OUTER_", "G_END_"))
    ]
    skin_group_value = "(" + ", ".join(f"'{group}'" for group in skin_groups) + ",)"
    mixed = bool(line_elements)
    lines = [
        "DEBUT(PAR_LOT='NON');",
        "MAIL = LIRE_MAILLAGE(FORMAT='MED', UNITE=20);",
        "MAIL = MODI_MAILLAGE(",
        "    reuse=MAIL,",
        "    MAILLAGE=MAIL,",
        "    ORIE_PEAU_3D=_F(",
        f"        GROUP_MA={skin_group_value},",
        f"        GROUP_MA_VOLU=('{solid}',),",
        "    ),",
        ");",
    ]
    if mixed:
        lines.extend(["MAIL = DEFI_GROUP(", "    reuse=MAIL,", "    MAILLAGE=MAIL,", "    CREA_GROUP_NO=("])
        for raw_group, mesh_node_id in node_groups.items():
            lines.append(
                f"        _F(NOM='{name_map[raw_group]}', NOEUD='{mesh_node_id.removeprefix('VN')}'),"
            )
        lines.extend(["    ),", ");"])
    lines.extend(["MODELE = AFFE_MODELE(", "    MAILLAGE=MAIL,"])
    if mixed:
        solid_groups = "(" + ", ".join(f"'{group}'" for group in (solid, *skin_groups)) + ",)"
        lines.extend(
            [
                "    AFFE=(",
                f"        _F(GROUP_MA={solid_groups}, PHENOMENE='MECANIQUE', MODELISATION='3D'),",
                f"        _F(GROUP_MA='{name_map['G_TUBE']}', PHENOMENE='MECANIQUE', MODELISATION='TUYAU_3M'),",
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
        "CHMAT = AFFE_MATERIAU(",
        "    MAILLAGE=MAIL,",
        ("    AFFE=_F(TOUT='OUI', MATER=MAT)," if mixed else f"    AFFE=_F(GROUP_MA='{solid}', MATER=MAT),"),
        ");",
        ]
    )
    if mixed:
        section = model.sections[line_elements[0].section]
        assert isinstance(section, PipeSection)
        orientation = _pipe_orientation_vector(model, line_elements, [])
        lines.extend(
            [
                "CARA = AFFE_CARA_ELEM(",
                "    MODELE=MODELE,",
                "    POUTRE=_F(",
                f"        GROUP_MA='{name_map['G_TUBE']}',",
                "        SECTION='CERCLE',",
                "        CARA=('R', 'EP'),",
                f"        VALE=({section.OD / 2.0:.8E}, {section.WT:.8E}),",
                "    ),",
                "    ORIENTATION=(",
            ]
        )
        for element in line_elements:
            lines.extend(
                [
                    "        _F(",
                    f"            GROUP_NO='{name_map[f'G_NODE_{element.n1}']}',",
                    "            CARA='GENE_TUYAU',",
                    f"            VALE=({orientation[0]:.8E}, {orientation[1]:.8E}, {orientation[2]:.8E}),",
                    "        ),",
                ]
            )
        lines.extend(["    ),", ");"])

    lines.extend(["BC = AFFE_CHAR_MECA(", "    MODELE=MODELE,", "    DDL_IMPO=("])
    for group, kind in support_groups:
        if kind == "node":
            lines.append(
                f"        _F(GROUP_NO='{name_map[group]}', BLOCAGE=('DEPLACEMENT', 'ROTATION'), WO=0.0),"
            )
        else:
            lines.append(f"        _F(GROUP_MA='{name_map[group]}', DX=0.0, DY=0.0, DZ=0.0),")
    lines.append("    ),")
    if mixed:
        lines.append("    LIAISON_ELEM=(")
        for face_group, node_group, axis in couplings:
            lines.extend(
                [
                    "        _F(",
                    "            OPTION='3D_TUYAU',",
                    "            CARA_ELEM=CARA,",
                    f"            AXE_POUTRE=({axis[0]:.8E}, {axis[1]:.8E}, {axis[2]:.8E}),",
                    f"            GROUP_MA_1='{name_map[face_group]}',",
                    f"            GROUP_NO_2='{name_map[node_group]}',",
                    "        ),",
                ]
            )
        lines.append("    ),")
    lines.append(");")

    excitations = ["_F(CHARGE=BC)"]
    if pressure != 0.0:
        lines.extend(
            [
                "PRESSURE = AFFE_CHAR_MECA(",
                "    MODELE=MODELE,",
                "    PRES_REP=_F(",
                f"        GROUP_MA='{inner}',",
                f"        PRES={pressure:.12E},",
                "    ),",
            ]
        )
        if mixed:
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
    lines.extend(["RESU = MECA_STATIQUE(", "    MODELE=MODELE,", "    CHAM_MATER=CHMAT,"])
    if mixed:
        lines.append("    CARA_ELEM=CARA,")
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
            "    FORCE='FORC_NODA',",
            ");",
            "IMPR_RESU(",
            "    FORMAT='MED',",
            "    UNITE=80,",
        ]
    )
    if mixed:
        lines.append(
            "    RESU=_F(RESULTAT=RESU, CARA_ELEM=CARA, "
            "NOM_CHAM=('DEPL', 'SIGM_ELNO', 'SIEQ_ELNO', 'EFGE_ELNO', 'FORC_NODA')),"
        )
    else:
        lines.append(
            "    RESU=_F(RESULTAT=RESU, NOM_CHAM=('DEPL', 'SIGM_ELNO', 'SIEQ_ELNO', 'FORC_NODA')),"
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
            "    RESU=_F(RESULTAT=RESU, NOM_CHAM='FORC_NODA', TOUT='OUI',",
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
    if mixed:
        lines.extend(
            [
                "TAB_EFFO = CREA_TABLE(",
                "    RESU=_F(RESULTAT=RESU, NOM_CHAM='EFGE_ELNO', TOUT='OUI',",
                "            NOM_CMP=('N', 'VY', 'VZ', 'MT', 'MFY', 'MFZ')),",
                ");",
                "IMPR_TABLE(TABLE=TAB_EFFO, FORMAT='TABLEAU', UNITE=38, SEPARATEUR=',');",
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
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_export(path: Path, *, export_tensor_stress: bool, mixed_analysis: bool) -> None:
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
    path.write_text(
        "\n".join(files) + "\n",
        encoding="utf-8",
    )


def _group_lineage(group_name: str) -> str:
    if group_name.startswith("G_END_"):
        return f"node:{group_name.removeprefix('G_END_')}"
    if group_name.startswith("G_NODE_"):
        return f"node:{group_name.removeprefix('G_NODE_')}"
    if group_name.startswith("G_TEE_"):
        return f"node:{group_name.removeprefix('G_TEE_')}"
    return f"group:{group_name}"
