"""tuba.solver.aster_comm — Code_Aster command file (.comm) generation.

Split out of tuba.solver.aster (behaviour-preserving). ``_CommWriterMixin`` is
mixed into ``CodeAsterSolver`` and keeps ``self`` access to mesh helpers.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np

from tuba.model import (
    BarSection,
    CableSection,
    IBeamSection,
    LoadCase,
    PipeSection,
    RectangularSection,
    TubaModel,
)
from tuba.solver.modelisation import (
    discrete_support_group,
    modelisation_assignments,
    needs_discrete_element,
)
from tuba.solver.aster_loads import (
    group_ma_value,
    has_pressure_load,
    has_temperature_load as has_thermal_load,
    has_wind_load,
    resolve_operation_field_groups,
    resolve_wind_field_groups,
    write_pressure_load,
    write_thermal_load,
    write_wind_load,
)

logger = logging.getLogger(__name__)


def _pipe_orientation_vector(model: TubaModel, pipe_straights: list, pipe_bends: list) -> tuple[float, float, float]:
    directions = []
    for elem in pipe_straights:
        directions.append(np.asarray(model.nodes[elem.n2].coords, dtype=float) - np.asarray(model.nodes[elem.n1].coords, dtype=float))
    for elem in pipe_bends:
        if elem.bend_geometry is not None:
            directions.append(np.asarray(elem.bend_geometry.start_tangent, dtype=float))
            directions.append(np.asarray(elem.bend_geometry.end_tangent, dtype=float))
        else:
            directions.append(np.asarray(model.nodes[elem.n2].coords, dtype=float) - np.asarray(model.nodes[elem.n1].coords, dtype=float))

    unit_directions = []
    for direction in directions:
        norm = float(np.linalg.norm(direction))
        if norm > 1e-12:
            unit_directions.append(direction / norm)

    if not unit_directions:
        return (0.0, 0.0, 1.0)

    candidates = [
        (0.0, 0.0, 1.0),
        (0.0, 1.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 1.0),
        (1.0, -1.0, 1.0),
        (1.0, 2.0, 3.0),
    ]
    for candidate in candidates:
        vector = np.asarray(candidate, dtype=float)
        vector_norm = float(np.linalg.norm(vector))
        if vector_norm <= 1e-12:
            continue
        unit_vector = vector / vector_norm
        if all(float(np.linalg.norm(np.cross(unit_vector, direction))) > 1e-8 for direction in unit_directions):
            return candidate

    for x in range(-3, 4):
        for y in range(-3, 4):
            for z in range(-3, 4):
                vector = np.asarray((float(x), float(y), float(z)), dtype=float)
                vector_norm = float(np.linalg.norm(vector))
                if vector_norm <= 1e-12:
                    continue
                unit_vector = vector / vector_norm
                if all(float(np.linalg.norm(np.cross(unit_vector, direction))) > 1e-8 for direction in unit_directions):
                    return (float(x), float(y), float(z))

    return (1.0, 2.0, 3.0)


class _CommWriterMixin:
    def _write_comm(
        self,
        model: TubaModel,
        load_case: LoadCase,
        path: Path,
        *,
        name_map: Callable[[str], str] | None = None,
    ) -> None:
        """Generate the Code_Aster command file for static piping analysis.

        Uses ``MODELISATION='TUYAU_3M'`` for pipe elements, ``'POU_D_T'`` for beams,
        ``'BARRE'`` for bars, and ``'CABLE'`` for cables.
        """
        pipe_straights = [e for e in model.elements if e.type == "pipe_straight"]
        pipe_bends = [e for e in model.elements if e.type == "pipe_bend"]
        beam_elems = [e for e in model.elements if e.type == "beam"]
        bar_elems = [e for e in model.elements if e.type == "bar"]
        cable_elems = [e for e in model.elements if e.type == "cable"]
        has_pipe_stress = bool(pipe_straights or pipe_bends)

        straight_elems = pipe_straights + beam_elems + bar_elems + cable_elems
        bend_elems = pipe_bends
        map_name = name_map or (lambda value: value)

        # Collect unique materials referenced by elements
        used_mat_names = sorted({e.material for e in model.elements})
        cable_mats = {e.material for e in model.elements if e.type == "cable"}

        # Collect unique sections
        used_sec_names = sorted({e.section for e in model.elements})

        # Check for POI1 requirements (discrete springs or masses)
        has_poi1 = any(needs_discrete_element(s) for s in model.supports)

        # Check if the model requires non-linear simulation (contact, friction, rests)
        is_nonlinear = any(s.type == "rest" or s.friction_coefficient > 0.0 for s in model.supports)

        comm: List[str] = []

        def w(text: str = "") -> None:
            """Append a line."""
            comm.append(text)

        # ==============================================================
        # DEBUT
        # ==============================================================
        w("DEBUT(PAR_LOT='NON');")
        w()

        # ==============================================================
        # LIRE_MAILLAGE / CREA_MAILLAGE
        # ==============================================================
        w("# ----- Read mesh -----")
        w("MAIL0 = LIRE_MAILLAGE(FORMAT='ASTER',")
        w("                      UNITE=20);")
        w()

        if has_poi1:
            w("# ----- Create POI1 elements for discrete springs/masses -----")
            w("MAIL = CREA_MAILLAGE(")
            w("    MAILLAGE=MAIL0,")
            w("    CREA_POI1=(")
            for s in model.supports:
                if needs_discrete_element(s):
                    w(f"        _F(NOM_GROUP_MA='{map_name(discrete_support_group(s.node))}', NOEUD='{map_name(s.node)}'),")
            w("    ),")
            w(");")
        else:
            w("MAIL = MAIL0;")
        w()

        # ==============================================================
        # AFFE_MODELE
        # ==============================================================
        w("# ----- Model definition -----")
        w("MODELE = AFFE_MODELE(")
        w("    MAILLAGE=MAIL,")
        w("    AFFE=(")
        for group_name, modelisation in modelisation_assignments(model).items():
            w("        _F(")
            w(f"            GROUP_MA='{map_name(group_name)}',")
            w("            PHENOMENE='MECANIQUE',")
            w(f"            MODELISATION='{modelisation}',")
            w("        ),")
        w("    ),")
        w(");")
        w()

        # ==============================================================
        # DEFI_MATERIAU
        # ==============================================================
        w("# ----- Material definitions -----")
        for mat_name in used_mat_names:
            mat = model.materials[mat_name]
            var = f"MAT_{mat_name.upper().replace(' ', '_').replace('-', '_')}"
            w(f"{var} = DEFI_MATERIAU(")
            w(f"    ELAS=_F(")
            w(f"        E={mat.E:.6E},")
            w(f"        NU={mat.nu:.6E},")
            w(f"        RHO={mat.rho:.6E},")
            w(f"        ALPHA={mat.alpha:.6E},")
            w(f"    ),")
            if mat_name in cable_mats:
                w(f"    CABLE=_F(EC_SUR_E=1.0),")
            w(f");")
            w()

        # ==============================================================
        # AFFE_MATERIAU
        # ==============================================================
        w("# ----- Material assignment -----")

        material_element_groups: Dict[str, List[str]] = {}
        for elem in model.elements:
            if elem.type == "pipe_bend":
                material_element_groups.setdefault(elem.material, []).extend(
                    f"{elem.id}_s{i}" for i in range(self._BEND_SEGMENTS)
                )
            else:
                material_element_groups.setdefault(elem.material, []).append(elem.id)

        delta_t = load_case.temperature - load_case.ref_temperature
        pressure_fields = resolve_operation_field_groups(model, load_case, "pressure")
        temperature_fields = resolve_operation_field_groups(model, load_case, "temperature")
        wind_fields = resolve_wind_field_groups(model, load_case)
        nodal_forces = list(getattr(load_case, "nodal_forces", []))
        has_pressure = has_pressure_load(load_case, pressure_fields)
        has_temperature = has_thermal_load(load_case, temperature_fields)
        has_wind = has_wind_load(wind_fields)
        has_nodal_forces = bool(nodal_forces)

        affe_entries: List[str] = []
        all_material_element_ids = {
            element_id
            for element_ids in material_element_groups.values()
            for element_id in element_ids
        }
        for mat_name, element_ids in material_element_groups.items():
            var = f"MAT_{mat_name.upper().replace(' ', '_').replace('-', '_')}"
            if set(element_ids) == all_material_element_ids:
                group_spec = "TOUT='OUI',"
            else:
                group_spec = f"GROUP_MA='{map_name(self._material_group_name(mat_name))}',"
            affe_entries.append(
                f"        _F(\n"
                f"            {group_spec}\n"
                f"            MATER={var},\n"
                f"        ),"
            )

        w("CHMAT = AFFE_MATERIAU(")
        w("    MAILLAGE=MAIL,")
        w("    AFFE=(")
        for entry in affe_entries:
            w(entry)
        w("    ),")
        w(");")
        w()

        # ==============================================================
        # AFFE_CARA_ELEM
        # ==============================================================
        w("# ----- Cross-section properties -----")
        w("CARA = AFFE_CARA_ELEM(")
        w("    MODELE=MODELE,")

        # POUTRE entries for pipes and beams
        poutre_entries: List[str] = []
        for sec_name in used_sec_names:
            sec = model.sections[sec_name]
            sec_straights = [e.id for e in straight_elems if e.section == sec_name and e.type in ("pipe_straight", "beam")]
            
            if sec_straights:
                section_group = f"'{map_name(self._section_group_name(sec_name))}'"
                
                if isinstance(sec, PipeSection) or isinstance(sec, BarSection):
                    r_ext = sec.OD / 2.0
                    ep = sec.WT
                    poutre_entries.append(
                        f"        _F(\n"
                        f"            GROUP_MA={section_group},\n"
                        f"            SECTION='CERCLE',\n"
                        f"            CARA=('R', 'EP'),\n"
                        f"            VALE=({r_ext:.8E}, {ep:.8E}),\n"
                        f"        ),"
                    )
                elif isinstance(sec, RectangularSection):
                    h_y = sec.height_y
                    h_z = sec.height_z
                    t_y = sec.thickness_y
                    t_z = sec.thickness_z
                    if t_y == 0.0 and t_z == 0.0:
                        poutre_entries.append(
                            f"        _F(\n"
                            f"            GROUP_MA={section_group},\n"
                            f"            SECTION='RECTANGLE',\n"
                            f"            CARA=('HY', 'HZ'),\n"
                            f"            VALE=({h_y:.8E}, {h_z:.8E}),\n"
                            f"        ),"
                        )
                    else:
                        poutre_entries.append(
                            f"        _F(\n"
                            f"            GROUP_MA={section_group},\n"
                            f"            SECTION='RECTANGLE',\n"
                            f"            CARA=('HY', 'HZ', 'EPY', 'EPZ'),\n"
                            f"            VALE=({h_y:.8E}, {h_z:.8E}, {t_y:.8E}, {t_z:.8E}),\n"
                            f"        ),"
                        )
                elif isinstance(sec, IBeamSection):
                    p = sec.properties
                    beamCaraStr = ['A','IY','IZ','AY','AZ','EY','EZ','JX','JG','IYR2','IZR2','RY','RZ','RT']
                    vals = [p.get(k, 0.0) for k in beamCaraStr]
                    poutre_entries.append(
                        f"        _F(\n"
                        f"            GROUP_MA={section_group},\n"
                        f"            SECTION='GENERALE',\n"
                        f"            CARA=({', '.join(repr(k) for k in beamCaraStr)}),\n"
                        f"            VALE=({', '.join(f'{v:.8E}' for v in vals)}),\n"
                        f"        ),"
                    )

        for elem in bend_elems:
            sec = model.sections[elem.section]
            r_ext = sec.OD / 2.0
            ep = sec.WT
            bend_group = f"'{map_name(elem.id)}'"
            poutre_entries.append(
                f"        _F(\n"
                f"            GROUP_MA={bend_group},\n"
                f"            SECTION='CERCLE',\n"
                f"            CARA=('R', 'EP'),\n"
                f"            VALE=({r_ext:.8E}, {ep:.8E}),\n"
                f"        ),"
            )
            poutre_entries.append(
                    f"        _F(\n"
                    f"            GROUP_MA={bend_group},\n"
                    f"            SECTION='COUDE',\n"
                    f"        ),"
            )

        if poutre_entries:
            w("    POUTRE=(")
            for entry in poutre_entries:
                w(entry)
            w("    ),")

        # BARRE entries
        barre_entries: List[str] = []
        for sec_name in used_sec_names:
            sec = model.sections[sec_name]
            sec_bars = [e.id for e in straight_elems if e.section == sec_name and e.type == "bar"]
            if sec_bars:
                group_list = ", ".join(f"'{map_name(eid)}'" for eid in sec_bars)
                grp = f"({group_list})" if len(sec_bars) > 1 else f"'{map_name(sec_bars[0])}'"
                r_ext = sec.OD / 2.0
                ep = sec.WT if hasattr(sec, "WT") else 0.0
                if ep == 0.0:
                    ep = r_ext  # Solid bar
                barre_entries.append(
                    f"        _F(\n"
                    f"            GROUP_MA={grp},\n"
                    f"            SECTION='CERCLE',\n"
                    f"            CARA=('R', 'EP'),\n"
                    f"            VALE=({r_ext:.8E}, {ep:.8E}),\n"
                    f"        ),"
                )
        if barre_entries:
            w("    BARRE=(")
            for entry in barre_entries:
                w(entry)
            w("    ),")

        # CABLE entries
        cable_entries: List[str] = []
        for sec_name in used_sec_names:
            sec = model.sections[sec_name]
            sec_cables = [e.id for e in straight_elems if e.section == sec_name and e.type == "cable"]
            if sec_cables:
                group_list = ", ".join(f"'{map_name(eid)}'" for eid in sec_cables)
                grp = f"({group_list})" if len(sec_cables) > 1 else f"'{map_name(sec_cables[0])}'"
                area = sec.area
                pret = sec.pretension
                cable_entries.append(
                    f"        _F(\n"
                    f"            GROUP_MA={grp},\n"
                    f"            SECTION={area:.8E},\n"
                    f"            N_INIT={pret:.8E},\n"
                    f"        ),"
                )
        if cable_entries:
            w("    CABLE=(")
            for entry in cable_entries:
                w(entry)
            w("    ),")

        # DISCRET entries for springs/masses
        discret_entries: List[str] = []
        for s in model.supports:
            if s.type == "spring" and (s.stiffness_matrix is not None or s.stiffness is not None):
                if s.stiffness_matrix:
                    k = s.stiffness_matrix
                else:
                    val = s.stiffness if s.stiffness is not None else 1.0e6
                    k = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                    if s.direction:
                        for idx, v in enumerate(s.direction):
                            if abs(v) > 1e-12:
                                k[idx] = val
                    else:
                        raise ValueError(
                            f"Spring support at node {s.node} uses scalar stiffness without direction. "
                            "Use stiffness_matrix=[Kx, Ky, Kz, Krx, Kry, Krz] or provide direction."
                        )
                discret_entries.append(
                    f"        _F(\n"
                    f"            GROUP_MA='{map_name(f'DIS_{s.node}')}',\n"
                    f"            REPERE='GLOBAL',\n"
                    f"            CARA='K_TR_D_N',\n"
                    f"            VALE=({k[0]:.8E}, {k[1]:.8E}, {k[2]:.8E}, {k[3]:.8E}, {k[4]:.8E}, {k[5]:.8E}),\n"
                    f"        ),"
                )
                if s.mass <= 0.0:
                    discret_entries.append(
                        f"        _F(\n"
                        f"            GROUP_MA='{map_name(f'DIS_{s.node}')}',\n"
                        f"            CARA='M_TR_D_N',\n"
                        f"            VALE=(0.00000000E+00, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),\n"
                        f"        ),"
                    )
            if s.mass > 0.0:
                discret_entries.append(
                    f"        _F(\n"
                    f"            GROUP_MA='{map_name(f'DIS_{s.node}')}',\n"
                    f"            CARA='M_TR_D_N',\n"
                    f"            VALE=({s.mass:.8E}, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),\n"
                    f"        ),"
                )
        if discret_entries:
            w("    DISCRET=(")
            for entry in discret_entries:
                w(entry)
            w("    ),")

        # Orientation
        orientation_entries: List[str] = []
        if pipe_straights or pipe_bends:
            orientation = _pipe_orientation_vector(model, pipe_straights, pipe_bends)
            orientation_entries.append(
                "        _F(\n"
                f"            GROUP_NO='{map_name('PipeOrientationNodes')}',\n"
                "            CARA='GENE_TUYAU',\n"
                f"            VALE=({orientation[0]:.8E}, {orientation[1]:.8E}, {orientation[2]:.8E}),\n"
                "        ),"
            )
        if beam_elems:
            for elem in beam_elems:
                angle = getattr(elem, "twist_angle", 0.0)
                orientation_entries.append(
                    f"        _F(\n"
                    f"            GROUP_MA='{map_name(elem.id)}',\n"
                    f"            CARA='ANGL_VRIL',\n"
                    f"            VALE={angle:.4f},\n"
                    f"        ),"
                )
        if orientation_entries:
            w("    ORIENTATION=(")
            for entry in orientation_entries:
                w(entry)
            w("    ),")

        w(");")
        w()


        # ==============================================================
        # AFFE_CHAR_MECA — supports
        # ==============================================================
        w("# ----- Boundary conditions -----")
        active_bcs = []
        pipe_nodes_with_warping = {
            node_id
            for elem in pipe_straights + pipe_bends
            for node_id in (elem.n1, elem.n2)
        }

        def append_pipe_warping_bc(lines: list[str], node_id: str) -> None:
            if node_id in pipe_nodes_with_warping:
                lines.append("        WO=0.0,")

        for i, sup in enumerate(model.supports):
            grp_name = map_name(f"GN_{sup.node}")
            char_name = f"BC_{i}"

            write_bc = False
            lines_bc = []

            if sup.blocked_dof is not None:
                dof_names = ["DX", "DY", "DZ", "DRX", "DRY", "DRZ"]
                blocked = []
                for idx, val in enumerate(sup.blocked_dof):
                    if val not in (False, 0, '0', 'x', 'X', None):
                        blocked.append(dof_names[idx])
                if blocked:
                    write_bc = True
                    lines_bc.append(f"{char_name} = AFFE_CHAR_MECA(")
                    lines_bc.append(f"    MODELE=MODELE,")
                    lines_bc.append(f"    DDL_IMPO=_F(")
                    lines_bc.append(f"        GROUP_NO='{grp_name}',")
                    for dof in blocked:
                        lines_bc.append(f"        {dof}=0.0,")
                    append_pipe_warping_bc(lines_bc, sup.node)
                    lines_bc.append(f"    ),")
                    lines_bc.append(f");")
            else:
                if sup.type == "anchor":
                    write_bc = True
                    lines_bc.append(f"{char_name} = AFFE_CHAR_MECA(")
                    lines_bc.append(f"    MODELE=MODELE,")
                    lines_bc.append(f"    DDL_IMPO=_F(")
                    lines_bc.append(f"        GROUP_NO='{grp_name}',")
                    lines_bc.append(f"        BLOCAGE=('DEPLACEMENT', 'ROTATION'),")
                    append_pipe_warping_bc(lines_bc, sup.node)
                    lines_bc.append(f"    ),")
                    lines_bc.append(f");")
                elif sup.type == "guide":
                    write_bc = True
                    lines_bc.append(f"{char_name} = AFFE_CHAR_MECA(")
                    lines_bc.append(f"    MODELE=MODELE,")
                    lines_bc.append(f"    DDL_IMPO=_F(")
                    lines_bc.append(f"        GROUP_NO='{grp_name}',")
                    if sup.direction:
                        dof_map = {0: "DX", 1: "DY", 2: "DZ"}
                        blocked = []
                        for idx, val in enumerate(sup.direction):
                            if abs(val) > 1e-12:
                                blocked.append(dof_map[idx])
                        for dof in blocked:
                            lines_bc.append(f"        {dof}=0.0,")
                    else:
                        lines_bc.append(f"        DX=0.0,")
                        lines_bc.append(f"        DY=0.0,")
                        lines_bc.append(f"        DZ=0.0,")
                    append_pipe_warping_bc(lines_bc, sup.node)
                    lines_bc.append(f"    ),")
                    lines_bc.append(f");")
                elif sup.type == "rest":
                    if is_nonlinear:
                        if sup.node not in pipe_nodes_with_warping:
                            continue
                        write_bc = True
                        lines_bc.append(f"{char_name} = AFFE_CHAR_MECA(")
                        lines_bc.append(f"    MODELE=MODELE,")
                        lines_bc.append(f"    DDL_IMPO=_F(")
                        lines_bc.append(f"        GROUP_NO='{grp_name}',")
                        append_pipe_warping_bc(lines_bc, sup.node)
                        lines_bc.append(f"    ),")
                        lines_bc.append(f");")
                        continue
                    write_bc = True
                    lines_bc.append(f"{char_name} = AFFE_CHAR_MECA(")
                    lines_bc.append(f"    MODELE=MODELE,")
                    lines_bc.append(f"    DDL_IMPO=_F(")
                    lines_bc.append(f"        GROUP_NO='{grp_name}',")
                    if sup.direction:
                        dof_map = {0: "DX", 1: "DY", 2: "DZ"}
                        for idx, val in enumerate(sup.direction):
                            if abs(val) > 1e-12:
                                lines_bc.append(f"        {dof_map[idx]}=0.0,")
                    else:
                        lines_bc.append(f"        DY=0.0,")
                    append_pipe_warping_bc(lines_bc, sup.node)
                    lines_bc.append(f"    ),")
                    lines_bc.append(f");")
                elif sup.type == "spring":
                    pass
                else:
                    write_bc = True
                    lines_bc.append(f"{char_name} = AFFE_CHAR_MECA(")
                    lines_bc.append(f"    MODELE=MODELE,")
                    lines_bc.append(f"    DDL_IMPO=_F(")
                    lines_bc.append(f"        GROUP_NO='{grp_name}',")
                    lines_bc.append(f"        DX=0.0,")
                    lines_bc.append(f"        DY=0.0,")
                    lines_bc.append(f"        DZ=0.0,")
                    append_pipe_warping_bc(lines_bc, sup.node)
                    lines_bc.append(f"    ),")
                    lines_bc.append(f");")

            if write_bc:
                for line in lines_bc:
                    w(line)
                w()
                active_bcs.append(char_name)

        # ==============================================================
        # AFFE_CHAR_MECA — gravity
        # ==============================================================
        if load_case.gravity:
            w("# ----- Gravity -----")
            w("GRAVITY = AFFE_CHAR_MECA(")
            w("    MODELE=MODELE,")
            w("    PESANTEUR=_F(")
            w("        GRAVITE=9.81,")
            w("        DIRECTION=(0.0, -1.0, 0.0),")
            w("    ),")
            w(");")
            w()

        # ==============================================================
        # AFFE_CHAR_MECA — pressure
        # ==============================================================
        if has_pressure:
            write_pressure_load(
                w,
                map_name=map_name,
                load_case=load_case,
                pressure_fields=pressure_fields,
            )

        # ==============================================================
        # AFFE_CHAR_MECA — wind on beam-modelized pipe
        # ==============================================================
        if has_wind:
            write_wind_load(
                w,
                map_name=map_name,
                wind_fields=wind_fields,
            )

        # ==============================================================
        # AFFE_CHAR_MECA - concentrated nodal forces
        # ==============================================================
        if has_nodal_forces:
            component_names = ("FX", "FY", "FZ", "MX", "MY", "MZ")
            w("# ----- Concentrated nodal forces -----")
            w("POINT_FORCE = AFFE_CHAR_MECA(")
            w("    MODELE=MODELE,")
            w("    FORCE_NODALE=(")
            for force in nodal_forces:
                w("        _F(")
                w(f"            GROUP_NO='{map_name(f'GN_{force.node}')}',")
                for name, value in zip(component_names, force.components):
                    w(f"            {name}={float(value):.8E},")
                w("        ),")
            w("    ),")
            w(");")
            w()

        # ==============================================================
        # Thermal load (uniform temperature field for expansion)
        # ==============================================================
        if has_temperature:
            write_thermal_load(
                w,
                map_name=map_name,
                load_case=load_case,
                temperature_fields=temperature_fields,
                affe_entries=affe_entries,
                is_nonlinear=is_nonlinear,
            )

        # ==============================================================
        # DEFI_CONTACT & Solve
        # ==============================================================
        if is_nonlinear:
            w("# ----- Unilateral contacts -----")
            w("UNIL_ZERO = DEFI_CONSTANTE(VALE=0.0);")
            w("UNIL_ONE = DEFI_CONSTANTE(VALE=1.0);")
            w()
            w("contact = DEFI_CONTACT(")
            w("    MODELE=MODELE,")
            w("    FORMULATION='LIAISON_UNIL',")
            w("    ZONE=(")
            for sup in model.supports:
                if sup.type == "rest":
                    grp_name = map_name(f"GN_{sup.node}")
                    cmp_name = "DY"
                    if sup.direction:
                        dof_map = {0: "DX", 1: "DY", 2: "DZ"}
                        for idx, val in enumerate(sup.direction):
                            if abs(val) > 1e-12:
                                cmp_name = dof_map[idx]
                                break
                    w(
                        f"        _F(GROUP_NO='{grp_name}', NOM_CMP='{cmp_name}', "
                        "COEF_IMPO=UNIL_ZERO, COEF_MULT=UNIL_ONE),"
                    )
            w("    ),")
            w(");")
            w()

        w("# ----- Solve -----")

        # Build EXCIT list
        excit_entries: List[str] = []
        for char_name in active_bcs:
            excit_entries.append(f"        _F(CHARGE={char_name}),")
        if load_case.gravity:
            excit_entries.append("        _F(CHARGE=GRAVITY),")
        if has_pressure:
            excit_entries.append("        _F(CHARGE=PRESSURE),")
        if has_wind:
            excit_entries.append("        _F(CHARGE=WIND),")
        if has_nodal_forces:
            excit_entries.append("        _F(CHARGE=POINT_FORCE),")

        if is_nonlinear:
            w("lst_inst = DEFI_LIST_REEL(VALE=(0.0, 1.0));")
            w("times = DEFI_LIST_INST(DEFI_LIST=_F(LIST_INST=lst_inst));")
            w()
            w("RESU = STAT_NON_LINE(")
            w("    MODELE=MODELE,")
            w("    CHAM_MATER=CHMAT,")
            w("    CARA_ELEM=CARA,")
            w("    EXCIT=(")
            for entry in excit_entries:
                w(entry)
            w("    ),")
            if cable_elems:
                elastic_groups: List[str] = []
                if pipe_straights or pipe_bends:
                    elastic_groups.append("AllPipes")
                if beam_elems:
                    elastic_groups.append("G_TUBE")
                if bar_elems:
                    elastic_groups.append("G_BAR")
                for support in model.supports:
                    if (support.type == "spring" and (support.stiffness_matrix is not None or support.stiffness is not None)) or support.mass > 0.0:
                        elastic_groups.append(f"DIS_{support.node}")
                w("    COMPORTEMENT=(")
                if elastic_groups:
                    w("        _F(")
                    w(f"            GROUP_MA={group_ma_value(elastic_groups, map_name)},")
                    w("            RELATION='ELAS',")
                    w("        ),")
                w("        _F(")
                w(f"            GROUP_MA='{map_name('G_CABLE')}',")
                w("            RELATION='CABLE',")
                w("            DEFORMATION='GROT_GDEP',")
                w("        ),")
                w("    ),")
            else:
                w("    COMPORTEMENT=_F(")
                w("        TOUT='OUI',")
                w("        RELATION='ELAS',")
                w("    ),")
            w("    INCREMENT=_F(")
            w("        LIST_INST=times,")
            w("    ),")
            w("    CONTACT=contact,")
            w("    METHODE='NEWTON',")
            w(");")
        else:
            w("RESU = MECA_STATIQUE(")
            w("    MODELE=MODELE,")
            w("    CHAM_MATER=CHMAT,")
            w("    CARA_ELEM=CARA,")
            w("    EXCIT=(")
            for entry in excit_entries:
                w(entry)
            w("    ),")
            w(");")
        w()

        # ==============================================================
        # CALC_CHAMP — derived fields
        # ==============================================================
        w("# ----- Derived fields -----")
        w("RESU = CALC_CHAMP(")
        w("    reuse=RESU,")
        w("    RESULTAT=RESU,")
        w("    CONTRAINTE=('EFGE_ELNO', 'SIEF_ELNO'),")
        if has_pipe_stress:
            w("    CRITERES=('SIEQ_ELGA', 'SIEQ_ELNO'),")
        w("    FORCE='FORC_NODA',")
        w(");")
        w()

        # ==============================================================
        # IMPR_RESU — MED output
        # ==============================================================
        w("# ----- Write MED results file -----")
        w("IMPR_RESU(")
        w("    FORMAT='MED',")
        w("    UNITE=80,")
        w("    RESU=_F(")
        w("        RESULTAT=RESU,")
        if has_pipe_stress:
            w("        CARA_ELEM=CARA,")
            w("        NOM_CHAM=('DEPL', 'SIEQ_ELGA', 'SIEQ_ELNO', 'EFGE_ELNO', 'FORC_NODA'),")
        else:
            w("        NOM_CHAM=('DEPL', 'EFGE_ELNO', 'FORC_NODA'),")
        w("    ),")
        w(");")
        w()

        # ==============================================================
        # CREA_TABLE + IMPR_TABLE — parseable text output
        # ==============================================================
        w("# ----- Text table for EFGE_ELNO -----")
        w("TAB_EFFO = CREA_TABLE(")
        w("    RESU=_F(")
        w("        RESULTAT=RESU,")
        w("        NOM_CHAM='EFGE_ELNO',")
        w("        TOUT='OUI',")
        w("        NOM_CMP=('N', 'VY', 'VZ', 'MT', 'MFY', 'MFZ'),")
        if is_nonlinear:
            w("        INST=1.0,")
        w("    ),")
        w(");")
        w()
        w("IMPR_TABLE(")
        w("    TABLE=TAB_EFFO,")
        w("    UNITE=38,")
        w("    FORMAT='TABLEAU',")
        w("    SEPARATEUR=',',")
        w(");")
        w()
        w("# ----- Text table for DEPL -----")
        w("TAB_DEPL = CREA_TABLE(")
        w("    RESU=_F(")
        w("        RESULTAT=RESU,")
        w("        NOM_CHAM='DEPL',")
        w("        TOUT='OUI',")
        w("        NOM_CMP=('DX', 'DY', 'DZ', 'DRX', 'DRY', 'DRZ'),")
        if is_nonlinear:
            w("        INST=1.0,")
        w("    ),")
        w(");")
        w()
        w("IMPR_TABLE(")
        w("    TABLE=TAB_DEPL,")
        w("    UNITE=39,")
        w("    FORMAT='TABLEAU',")
        w("    SEPARATEUR=',',")
        w(");")
        w()
        w("# ----- Text table for FORC_NODA -----")
        w("TAB_REAC = CREA_TABLE(")
        w("    RESU=_F(")
        w("        RESULTAT=RESU,")
        w("        NOM_CHAM='FORC_NODA',")
        w("        TOUT='OUI',")
        w("        NOM_CMP=('DX', 'DY', 'DZ', 'DRX', 'DRY', 'DRZ'),")
        if is_nonlinear:
            w("        INST=1.0,")
        w("    ),")
        w(");")
        w()
        w("IMPR_TABLE(")
        w("    TABLE=TAB_REAC,")
        w("    UNITE=40,")
        w("    FORMAT='TABLEAU',")
        w("    SEPARATEUR=',',")
        w(");")
        w()
        if has_pipe_stress:
            w("# ----- Text table for SIEQ_ELNO -----")
            w("TAB_SIEQ = CREA_TABLE(")
            w("    RESU=_F(")
            w("        RESULTAT=RESU,")
            w("        NOM_CHAM='SIEQ_ELNO',")
            w("        TOUT='OUI',")
            w("        NOM_CMP=('VMIS',),")
            if is_nonlinear:
                w("        INST=1.0,")
            w("    ),")
            w(");")
            w()
            w("IMPR_TABLE(")
            w("    TABLE=TAB_SIEQ,")
            w("    UNITE=41,")
            w("    FORMAT='TABLEAU',")
            w("    SEPARATEUR=',',")
            w(");")
            w()

        # ==============================================================
        # FIN
        # ==============================================================
        w("FIN();")

        path.write_text("\n".join(comm), encoding="utf-8")
        logger.info("Wrote command file: %s", path)
