"""Native point-contact compilation for fixed-frame beam piping shoes."""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np

from tuba.solver.modelisation import PipeModelization


@dataclass(frozen=True)
class Shoe:
    support: object
    group: str
    ground: str
    normal: tuple
    tangent: tuple
    kn: float
    kt: float


def shoes(model, formulation):
    result = []
    ids = set()
    authored_names = (set(model.nodes) | {e.id for e in model.elements}
                      | set(model.groups) | set(model.materials) | set(model.sections))
    for index, support in enumerate(model.supports):
        support.__post_init__()
        if support.id is not None and support.id in ids:
            raise ValueError(f'Duplicate support id: {support.id}')
        ids.add(support.id)
        if support.friction_coefficient and (support.type != 'rest' or formulation != PipeModelization.POU_D_T):
            raise ValueError('Native friction requires a rest support and pipe_modelization=POU_D_T.')
        if support.type != 'rest' or formulation != PipeModelization.POU_D_T:
            if support.gap != 0 or support.normal_stiffness is not None or support.tangential_stiffness is not None:
                raise ValueError('Contact gap/stiffness parameters require a rest support and pipe_modelization=POU_D_T.')
            continue
        if not isinstance(support.id, str) or not support.id.strip():
            raise ValueError('Native shoes require persistent nonempty support IDs.')
        group, ground = f'CONTACT_{index}', f'GROUND_{index}'
        collisions = authored_names.intersection((group, ground))
        if collisions:
            raise ValueError(f'Native contact helper names collide with authored names: {sorted(collisions)}.')
        if support.blocked_dof is not None:
            raise ValueError('Native shoe blocked_dof overrides are not supported.')
        if support.imposed_displacement is not None:
            raise ValueError('Native shoe support movement is not implemented.')
        if any(s is not support and s.node == support.node and s.type not in ('rest', 'spring') for s in model.supports):
            raise ValueError(f'Contact at {support.node} overlaps another displacement restraint.')
        n = np.asarray(support.direction or (0., 0., 1.), dtype=float)
        n /= np.linalg.norm(n)
        axis = np.eye(3)[int(np.argmin(np.abs(n)))]
        tangent = axis - n * np.dot(axis, n)
        tangent /= np.linalg.norm(tangent)
        # Penalty stiffnesses; exposed individually for numerical sensitivity checks.
        result.append(Shoe(support, group, ground, tuple(map(float, n)), tuple(map(float, tangent)),
                           support.normal_stiffness or 1e10, support.tangential_stiffness or 1e8))
    if result and any(s.imposed_displacement is not None for s in model.supports):
        raise ValueError("Native contact paths do not support prescribed support movement.")
    if result and any(s.type == "spring" or s.mass > 0 for s in model.supports):
        raise ValueError("Native shoes with discrete springs or support masses are not yet qualified.")
    return result


def validate_path(model, load_case, load_path):
    names = tuple(load_path) if load_path is not None else (load_case.name,)
    if not names or any(not isinstance(name, str) or name not in model.load_cases for name in names):
        raise ValueError('load_path must contain existing load-case names.')
    cases = [model.load_cases[name] for name in names]
    reference = cases[0].ref_temperature
    if not np.isfinite(reference):
        raise ValueError("Load-path reference temperature must be finite.")
    for case in cases:
        if not np.isfinite(case.temperature) or case.ref_temperature != reference:
            raise ValueError('Load-path temperatures must be finite with one reference temperature.')
        if case.internal_pressure or case.fields:
            raise ValueError('Native contact load paths currently support uniform temperature, gravity and nodal forces only.')
        for force in case.nodal_forces:
            if not np.all(np.isfinite(force.components)):
                raise ValueError('Load-path nodal forces and moments must be finite.')
    return names, cases


def write_contact_solve(w, model, load_case, load_path, specs, map_name, affe_entries, active_bcs, step):
    """Emit a single stateful nonlinear evolution, including thermal history."""
    names, cases = validate_path(model, load_case, load_path)
    if not math.isfinite(step) or not 0 < step <= 1:
        raise ValueError('load_step must be finite and in (0, 1].')
    # An explicit unloaded reference precedes all authored endpoints.
    times = tuple(float(i) for i in range(len(cases) + 1))
    def function(name, values):
        w(f"{name} = DEFI_FONCTION(NOM_PARA='INST', ABSCISSE={times!r}, ORDONNEE={tuple(values)!r})")
    function('GRAMP', [0.] + [float(c.gravity) for c in cases])
    w("GRAVITY = AFFE_CHAR_MECA(MODELE=MODELE, PESANTEUR=_F(GRAVITE=9.81,DIRECTION=(0.,0.,-1.)))")
    entries = [f'_F(CHARGE={bc})' for bc in active_bcs] + ['_F(CHARGE=GRAVITY,FONC_MULT=GRAMP)']
    for i, spec in enumerate(specs):
        w(f"GROUND{i} = AFFE_CHAR_MECA(MODELE=MODELE, DDL_IMPO=_F(GROUP_NO='{map_name(spec.ground)}',DX=0.,DY=0.,DZ=0.))")
        entries.append(f'_F(CHARGE=GROUND{i})')
    node_ids = sorted({force.node for case in cases for force in case.nodal_forces})
    for ni, node_id in enumerate(node_ids):
        for component, key in enumerate(('FX','FY','FZ','MX','MY','MZ')):
            values = [0.] + [sum(float(f.components[component])
                                  for f in case.nodal_forces if f.node == node_id) for case in cases]
            if not any(values):
                continue
            name = f'F{ni}_{component}'
            function(name, values)
            w(f"L{ni}_{component} = AFFE_CHAR_MECA(MODELE=MODELE, FORCE_NODALE=_F(GROUP_NO='{map_name('GN_'+node_id)}',{key}=1.))")
            entries.append(f'_F(CHARGE=L{ni}_{component},FONC_MULT={name})')
    temperatures = [cases[0].ref_temperature] + [c.temperature for c in cases]
    w('TFIELDS = []')
    for temperature in temperatures:
        w(f"TFIELDS.append(CREA_CHAMP(TYPE_CHAM='NOEU_TEMP_R',OPERATION='AFFE',MAILLAGE=MAIL,AFFE=_F(TOUT='OUI',NOM_CMP='TEMP',VALE={temperature!r})))")
    w(f"THERM = CREA_RESU(OPERATION='AFFE',TYPE_RESU='EVOL_THER',NOM_CHAM='TEMP',AFFE=tuple(_F(CHAM_GD=f,INST=t) for f,t in zip(TFIELDS,{times!r})))")
    w('CHMAT = AFFE_MATERIAU(MAILLAGE=MAIL,AFFE=(')
    for entry in affe_entries:
        w(entry)
    w(f"), AFFE_VARC=_F(TOUT='OUI',NOM_VARC='TEMP',EVOL=THERM,VALE_REF={cases[0].ref_temperature!r}))")
    elastic_groups = [name for name in ('AllPipes','G_TUBE','G_BAR')
                      if (name == 'AllPipes' and any(e.type.startswith('pipe_') for e in model.elements))
                      or (name == 'G_TUBE' and any(e.type == 'beam' for e in model.elements))
                      or (name == 'G_BAR' and any(e.type == 'bar' for e in model.elements))]
    elastic_groups.extend(f'DIS_{s.node}' for s in model.supports if s.type == 'spring' or s.mass > 0.)
    elastic_groups = tuple(map_name(x) for x in dict.fromkeys(elastic_groups))
    intervals = tuple(_ for _ in range(1, len(cases)+1))
    w("lst_inst = DEFI_LIST_REEL(DEBUT=0., INTERVALLE=(")
    for end in intervals:
        w(f'_F(JUSQU_A={float(end)!r},NOMBRE={math.ceil(1/step)}),')
    w('))')
    w("times = DEFI_LIST_INST(DEFI_LIST=_F(LIST_INST=lst_inst),ECHEC=_F(EVENEMENT='ERREUR',SUBD_METHODE='MANUEL',SUBD_PAS=4,SUBD_NIVEAU=8))")
    w('RESU = STAT_NON_LINE(MODELE=MODELE,CHAM_MATER=CHMAT,CARA_ELEM=CARA,')
    w('EXCIT=(' + ','.join(entries) + ',), COMPORTEMENT=(')
    w(f"_F(GROUP_MA={elastic_groups!r},RELATION='ELAS'),")
    for spec in specs:
        w(f"_F(GROUP_MA='{map_name(spec.group)}',RELATION='DIS_CHOC',RESI_INTE=1e-9),")
    w("),INCREMENT=_F(LIST_INST=times),NEWTON=_F(MATRICE='TANGENTE',REAC_ITER=1),CONVERGENCE=_F(RESI_GLOB_RELA=1e-8,ITER_GLOB_MAXI=50))")


def write_contact_tables(w, specs, map_name):
    """Solver-side JSON preserves exact support identifiers and all increments."""
    w('import json')
    w('contact_rows = []')
    for spec in specs:
        w(f"CT = CREA_TABLE(RESU=_F(RESULTAT=RESU,GROUP_MA='{map_name(spec.group)}',NOM_CHAM='SIEF_ELGA',TOUT_CMP='OUI'))")
        w('forces = CT.EXTR_TABLE().values()')
        w(f"VT = CREA_TABLE(RESU=_F(RESULTAT=RESU,GROUP_MA='{map_name(spec.group)}',NOM_CHAM='VARI_ELGA',TOUT_CMP='OUI'))")
        w('variables = VT.EXTR_TABLE().values()')
        w("if not all(f'V{i}' in variables for i in range(1,11)): raise RuntimeError('Native friction requires the qualified ten-variable DIS_CHOC layout.')")
        w('iv = {float(t): i for i,t in enumerate(variables["INST"]) if variables["POINT"][i] == 1}')
        w('for i,t in enumerate(forces["INST"]):')
        w('    if forces["POINT"][i] != 1: continue')
        w('    j = iv[float(t)]')
        w(f'    contact_rows.append(dict(support_id={spec.support.id!r},instant=float(t),N=forces["N"][i],VY=forces["VY"][i],VZ=forces["VZ"][i],slip_y=variables["V5"][j],slip_z=variables["V6"][j],status=variables["V4"][j]))')
    w("with open('fort.42','w') as stream: json.dump(contact_rows,stream,allow_nan=False)")
