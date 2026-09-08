"""Real Code_Aster qualification; never substitutes calculated result values."""
import os
import math
import json
from pathlib import Path
import unittest

import numpy as np

from tuba.solver.aster import CodeAsterSolver
from tuba.solver.code_aster_runtime import CodeAsterRuntimeConfig, run_code_aster_export


def run_reference(root, law='DIS_CONTACT', kn=1e10, kt=1e8, step=0.1, driver=False):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    template = Path(__file__).with_name('code_aster').joinpath('friction_reference.comm').read_text()
    for key, value in {'LAW': law, 'KN': kn, 'KT': kt, 'STEP': step, 'DRIVER': bool(driver)}.items():
        template = template.replace(f'__{key}__', str(value))
    (root / 'study.comm').write_text(template)
    (root / 'study.mail').write_text('''TITRE
Native contact beam reference
FINSF
COOR_3D
G 0. 0. 0.
P 0. 1. 0.
B -2. 1. 0.
FINSF
SEG2
C G P
E B P
FINSF
GROUP_MA
CONTACT C
FINSF
GROUP_MA
BEAM E
FINSF
GROUP_NO
GROUND G
FINSF
GROUP_NO
PIPE P
FINSF
GROUP_NO
BASE B
FINSF
FIN
''')
    CodeAsterSolver()._write_export(root)
    execution = run_code_aster_export(root / 'study.export', root,
        CodeAsterRuntimeConfig(exec_method='wsl', wsl_distro='Ubuntu', timeout_seconds=240))
    return CodeAsterSolver._parse_csv_table(root / 'study_effo.csv')



def table(root, name, *, point=None):
    rows = CodeAsterSolver._parse_csv_table(Path(root) / name)
    if point is not None:
        rows = [r for r in rows if int(r['POINT']) == point]
    return {round(float(r['INST']), 8): r for r in rows}


def assess_cycle(case, root, *, kn, kt, driver, law):
    forces = table(root, 'study_effo.csv', point=1)
    internal = table(root, 'study_sieq.csv', point=1)
    displacement = table(root, 'study_depl.csv')
    case.assertTrue(forces)
    case.assertEqual(set(forces), set(internal))
    case.assertEqual(set(forces), set(displacement))
    peak_bound_excess = 0.
    peak_penetration = 0.
    previous = None
    for time, row in sorted(forces.items()):
        n = -float(row['N'])
        force = np.array([float(row['VY']), float(row['VZ'])])
        case.assertTrue(np.all(np.isfinite(force)))
        case.assertGreaterEqual(n, -10.)
        excess = float(np.linalg.norm(force)) - 0.3*n
        peak_bound_excess = max(peak_bound_excess, excess)
        case.assertLessEqual(excess, 10.)
        peak_penetration = max(peak_penetration, -float(displacement[time]['DY']))
        if law in ('DIS_CONTACT', 'DIS_CHOC'):
            slip_keys = ('V3','V4') if law == 'DIS_CONTACT' else ('V5','V6')
            slip = np.array([float(internal[time][key]) for key in slip_keys])
            case.assertTrue(np.all(np.isfinite(slip)))
            if previous is not None and n > 1:
                delta = slip-previous
                # The local section force is opposite force on the pipe.
                case.assertLessEqual(-float(force @ delta), 1e-7)
            previous = slip
    case.assertLessEqual(peak_penetration, 1e-5*(1+1e-6))
    for time in (1.,2.,3.,4.,5.,7.,8.):
        case.assertAlmostEqual(-float(forces[time]['N']), 10000., delta=10.)
    case.assertAlmostEqual(float(forces[2.]['VY']), -1000., delta=10.)
    for time in (3.,5.,8.):
        case.assertAlmostEqual(np.hypot(float(forces[time]['VY']),float(forces[time]['VZ'])), 3000., delta=10.)
    case.assertLess(float(forces[3.]['VY']), 0.)
    case.assertGreater(float(forces[5.]['VY']), 0.)
    case.assertLess(abs(float(forces[6.]['N'])), 1.)
    case.assertLess(np.hypot(float(forces[6.]['VY']),float(forces[6.]['VZ'])),1.)
    if law == 'DIS_CHOC':
        for time,status in ((2.,0),(3.,1),(5.,1),(6.,2),(7.,0),(8.,1)):
            case.assertEqual(int(float(internal[time]['V4'])),status)
    peak_equilibrium = 0.
    reactions = CodeAsterSolver._parse_csv_table(Path(root)/'study_reac.csv')
    for time in forces:
        residual = np.sum([[float(r[k]) for k in ('DX','DY','DZ')] for r in reactions if round(float(r['INST']),8)==time],axis=0)
        peak_equilibrium=max(peak_equilibrium,float(np.linalg.norm(residual)))
    case.assertLess(peak_equilibrium,10.)
    beam_k = 2e11 * math.pi * (0.05715**2-(0.05715-.006)**2)/2
    series_k = beam_k*kt/(beam_k+kt)
    if driver:
        for time in forces:
            if not 1. <= time <= 3.:
                continue
            travel = (1000./series_k*(time-1.) if time<=2.
                      else 1000./series_k+(.001-1000./series_k)*(time-2.))
            reference_force = min(series_k*travel, 3000.)
            case.assertAlmostEqual(float(forces[time]['VY']), -reference_force, delta=10.)
            case.assertAlmostEqual(float(displacement[time]['DX']),travel-reference_force/beam_k,delta=1e-7)
        case.assertAlmostEqual(float(displacement[2.]['DX']), 1000./kt, delta=1000./kt*.01)
        case.assertAlmostEqual(float(displacement[3.]['DX']), .001-3000./beam_k, delta=1e-6)
        case.assertAlmostEqual(float(displacement[5.]['DX']), -.001+3000./beam_k, delta=1e-6)
        # Incremental elastic unloading, until the reverse Coulomb boundary.
        reference = min(3000., -3000.+series_k*.00001)
        case.assertAlmostEqual(float(forces[4.]['VY']), reference, delta=10.)
        if abs(reference)<2990:
            key='V3' if law=='DIS_CONTACT' else 'V5'
            case.assertAlmostEqual(float(internal[4.][key]),float(internal[3.][key]),delta=1e-8)
    return dict(law=law,driver=driver,kn=kn,kt=kt,peak_penetration=peak_penetration,
                max_coulomb_excess=peak_bound_excess,equilibrium_residual=peak_equilibrium,
                stick_force=float(forces[2.]['VY']), slide_force=float(forces[3.]['VY']),
                reversal_force=float(forces[4.]['VY']), reverse_slide_force=float(forces[5.]['VY']),
                slide_dx=float(displacement[3.]['DX']), breakaway_driver_displacement=3000/series_k,
                endpoints={str(t):[float(forces[t][k]) for k in ('N','VY','VZ')] for t in (1.,2.,3.,4.,5.,6.,7.,8.)})


@unittest.skipUnless(os.environ.get('TUBA_RUN_CODE_ASTER_INTEGRATION') == '1', 'requires real Code_Aster')
class NativeContactReference(unittest.TestCase):
    def test_native_contact_cycle(self):
        root = Path('.build/friction-reference')
        for law in ('DIS_CONTACT', 'DIS_CHOC'):
            with self.subTest(law=law):
                run_reference(root/law, law)
                summary=assess_cycle(self,root/law,kn=1e10,kt=1e8,driver=False,law=law)
                (root/law/'qualification.json').write_text(json.dumps(summary,indent=2))

    def test_elastic_driver_stiffness_and_step_sensitivity(self):
        root=Path('.build/friction-reference')
        records=[]
        for multiplier in (.1,1.,10.):
            previous=None
            for step in (.1,.05):
                case_root=root/f'choc-driver-{multiplier:g}-{step:g}'
                kn,kt=1e10*multiplier,1e8*multiplier
                run_reference(case_root,law='DIS_CHOC',kn=kn,kt=kt,step=step,driver=True)
                record=assess_cycle(self,case_root,kn=kn,kt=kt,driver=True,law='DIS_CHOC')
                record['step']=step
                if previous is not None:
                    changes=[abs(a-b) for t,values in previous['endpoints'].items() for a,b in zip(values,record['endpoints'][t])]
                    self.assertLess(max(changes),30.)
                    record['step_endpoint_difference']=max(changes)
                previous=record
                records.append(record)
                (case_root/'qualification.json').write_text(json.dumps(record,indent=2))
        (root/'choc-driver-qualification.json').write_text(json.dumps(records,indent=2))
        lines=['# Native contact diagnostic qualification', '',
               'Code_Aster 18.00.12; real WSL Ubuntu external execution. SI units. Selected law: DIS_CHOC (penalty contact).',
               'POU_D_T circular pipe OD114.3mm, WT6mm, L2m, E200GPa; beam base tangential travel imposed, pipe tangential displacement solved. Normal displacement fixes a measured 10 kN preload. This is not a force-controlled opening qualification.',
               '', 'Acceptance: force/reference within 1%; reaction-force equilibrium below 10 N (0.1%); penetration <=1e-5m; Coulomb excess <=10N; endpoint step sensitivity <=30N.', '',
               '| kn N/m | kt N/m | step | penetration m | stick N | slide N | reverse unload N | reverse slide N | equilibrium N |',
               '|---|---|---|---|---|---|---|---|---|']
        for r in records:
            lines.append('| '+' | '.join(f'{r[key]:.6g}' for key in ('kn','kt','step','peak_penetration','stick_force','slide_force','reversal_force','reverse_slide_force','equilibrium_residual'))+' |')
        lines+=['', 'DIS_CHOC native V4 labels stick=0, slide=1, detached=2; V5/V6 are tangential slip. The tests check native status against known phases and slip increments against friction work. DIS_CONTACT uses V3/V4 for slip instead; the two mappings must not be mixed.',
                'At the baseline stiffness, the closed elastic-driver reference is keq=kbeam*kt/(kbeam+kt); breakaway travel=3000/keq. Tests check 1000 N stick, 3000 N forward/reverse slide, and incremental unloading.']
        lines += ['', 'DIS_CONTACT also passed the prescribed-normal driver sweep (driver-qualification.json), but failed the force-loaded public opening pilot at both baseline and 0.1 stiffness, including CORDE. DIS_CHOC solved the public force-loaded cycle; this prescribed-normal diagnostic does not substitute for that independent production test.', '', '[Native variable mapping, R5.03.17 section 7.6](https://codeaster.gitlab.io/doc/docaster/manuals/man_r/r5/r5.03.17/Modelisation_des_chocs_et_du_frottement_DIS_CHOC.html). Installed Code_Aster18 catalog confirms ten internal variables.']
        (root/'qualification.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    unittest.main()
