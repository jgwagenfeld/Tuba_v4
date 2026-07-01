"""tuba.solver.aster_comm — Code_Aster command file (.comm) generation.

Split out of tuba.solver.aster (behaviour-preserving). ``_CommWriterMixin`` is
mixed into ``CodeAsterSolver`` and keeps ``self`` access to mesh helpers.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from tuba.model import (
    BarSection,
    CableSection,
    IBeamSection,
    LoadCase,
    PipeSection,
    RectangularSection,
    TubaModel,
)

logger = logging.getLogger(__name__)


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

        straight_elems = pipe_straights + beam_elems + bar_elems + cable_elems
        bend_elems = pipe_bends
        map_name = name_map or (lambda value: value)

        # Collect unique materials referenced by elements
        used_mat_names = sorted({e.material for e in model.elements})
        cable_mats = {e.material for e in model.elements if e.type == "cable"}

        # Collect unique sections
        used_sec_names = sorted({e.section for e in model.elements})

        # Check for POI1 requirements (discrete springs or masses)
        has_springs = any(s.stiffness_matrix is not None or s.stiffness is not None for s in model.supports if s.type == "spring")
        has_masses = any(s.mass > 0.0 for s in model.supports)
        has_poi1 = has_springs or has_masses

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
                if (s.type == "spring" and (s.stiffness_matrix is not None or s.stiffness is not None)) or s.mass > 0.0:
                    w(f"        _F(NOM_GROUP_MA='{map_name(f'DIS_{s.node}')}', NOEUD='{map_name(s.node)}'),")
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
        if pipe_straights or pipe_bends:
            w("        _F(")
            w(f"            GROUP_MA='{map_name('AllPipes')}',")
            w("            PHENOMENE='MECANIQUE',")
            w("            MODELISATION='TUYAU_3M',")
            w("        ),")
        if beam_elems:
            w("        _F(")
            w(f"            GROUP_MA='{map_name('G_TUBE')}',")
            w("            PHENOMENE='MECANIQUE',")
            w("            MODELISATION='POU_D_T',")
            w("        ),")
        if bar_elems:
            w("        _F(")
            w(f"            GROUP_MA='{map_name('G_BAR')}',")
            w("            PHENOMENE='MECANIQUE',")
            w("            MODELISATION='BARRE',")
            w("        ),")
        if cable_elems:
            w("        _F(")
            w(f"            GROUP_MA='{map_name('G_CABLE')}',")
            w("            PHENOMENE='MECANIQUE',")
            w("            MODELISATION='CABLE',")
            w("        ),")
        for s in model.supports:
            if (s.type == "spring" and (s.stiffness_matrix is not None or s.stiffness is not None)) or s.mass > 0.0:
                w("        _F(")
                w(f"            GROUP_MA='{map_name(f'DIS_{s.node}')}',")
                w("            PHENOMENE='MECANIQUE',")
                w("            MODELISATION='DIS_TR',")
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
            orientation_entries.append(
                "        _F(\n"
                f"            GROUP_NO='{map_name('PipeOrientationNodes')}',\n"
                "            CARA='GENE_TUYAU',\n"
                "            VALE=(0.0, 0.0, 1.0),\n"
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
        if load_case.internal_pressure > 0.0:
            w("# ----- Internal pressure -----")
            w("PRESSURE = AFFE_CHAR_MECA(")
            w("    MODELE=MODELE,")
            w("    FORCE_TUYAU=_F(")
            w(f"        GROUP_MA='{map_name('AllPipes')}',")
            w(f"        PRES={load_case.internal_pressure:.6E},")
            w("    ),")
            w(");")
            w()

        # ==============================================================
        # Thermal load (uniform temperature field for expansion)
        # ==============================================================
        if abs(delta_t) > 1e-10:
            w("# ----- Thermal expansion -----")
            if is_nonlinear:
                w("TEMP_REF_FIELD = CREA_CHAMP(")
                w("    TYPE_CHAM='NOEU_TEMP_R',")
                w("    OPERATION='AFFE',")
                w("    MAILLAGE=MAIL,")
                w("    AFFE=_F(")
                w("        TOUT='OUI',")
                w("        NOM_CMP='TEMP',")
                w(f"        VALE={load_case.ref_temperature:.6E},")
                w("    ),")
                w(");")
                w()
                w("TEMP_HOT_FIELD = CREA_CHAMP(")
                w("    TYPE_CHAM='NOEU_TEMP_R',")
                w("    OPERATION='AFFE',")
                w("    MAILLAGE=MAIL,")
                w("    AFFE=_F(")
                w("        TOUT='OUI',")
                w("        NOM_CMP='TEMP',")
                w(f"        VALE={load_case.temperature:.6E},")
                w("    ),")
                w(");")
                w()
                w("TEMP_EVOL = CREA_RESU(")
                w("    OPERATION='AFFE',")
                w("    TYPE_RESU='EVOL_THER',")
                w("    NOM_CHAM='TEMP',")
                w("    AFFE=(")
                w("        _F(CHAM_GD=TEMP_REF_FIELD, INST=0.0),")
                w("        _F(CHAM_GD=TEMP_HOT_FIELD, INST=1.0),")
                w("    ),")
                w(");")
                w()
            else:
                w("TEMP_FIELD = CREA_CHAMP(")
                w("    TYPE_CHAM='NOEU_TEMP_R',")
                w("    OPERATION='AFFE',")
                w("    MAILLAGE=MAIL,")
                w("    AFFE=_F(")
                w("        TOUT='OUI',")
                w("        NOM_CMP='TEMP',")
                w(f"        VALE={load_case.temperature:.6E},")
                w("    ),")
                w(");")
                w()

            # Rebuild CHMAT with thermal reference
            w("CHMAT = AFFE_MATERIAU(")
            w("    MAILLAGE=MAIL,")
            w("    AFFE=(")
            for entry in affe_entries:
                w(entry)
            w("    ),")
            w("    AFFE_VARC=_F(")
            w("        TOUT='OUI',")
            w("        NOM_VARC='TEMP',")
            if is_nonlinear:
                w("        EVOL=TEMP_EVOL,")
                w("        NOM_CHAM='TEMP',")
            else:
                w("        CHAM_GD=TEMP_FIELD,")
            w(f"        VALE_REF={load_case.ref_temperature:.6E},")
            w("    ),")
            w(");")
            w()

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
        if load_case.internal_pressure > 0.0:
            excit_entries.append("        _F(CHARGE=PRESSURE),")

        def group_ma_value(group_names: List[str]) -> str:
            mapped = [map_name(group_name) for group_name in group_names]
            if len(mapped) == 1:
                return f"'{mapped[0]}'"
            return "(" + ", ".join(f"'{group_name}'" for group_name in mapped) + ",)"

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
                    w(f"            GROUP_MA={group_ma_value(elastic_groups)},")
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
        w("    CRITERES=('SIEQ_ELNO',),")
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
        w("        NOM_CHAM=('DEPL', 'SIEQ_ELNO', 'EFGE_ELNO', 'FORC_NODA'),")
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
