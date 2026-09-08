"""Read native contact histories; no solver fields are inferred from animation."""
from __future__ import annotations

import json
import math
import numpy as np

from tuba.solver.aster_contact import shoes
from tuba.solver.base import ContactResult


def read_contact_history(model, root, study, parser):
    inputs = study.metadata.get('compiler_inputs', {})
    if inputs.get('contact_law') != 'DIS_CHOC':
        raise ValueError('Unsupported native contact law in result metadata.')
    specs = shoes(model, inputs['pipe_modelization'])
    rows = json.loads((root / 'study_contact.json').read_text())
    if not isinstance(rows, list) or not rows or not specs:
        raise ValueError('Native contact history must contain solved support records.')
    indexed = {}
    support_ids = {s.support.id for s in specs}
    keys = ('instant','N','VY','VZ','slip_y','slip_z','status')
    for row in rows:
        if not isinstance(row, dict) or row.get('support_id') not in support_ids:
            raise ValueError('Unknown support in native contact history.')
        if any(k not in row or not isinstance(row[k], (int,float)) or isinstance(row[k], bool) or not math.isfinite(row[k]) for k in keys):
            raise ValueError('Missing or nonfinite native contact result.')
        key = (float(row['instant']), row['support_id'])
        if key in indexed:
            raise ValueError('Duplicate native contact increment/support record.')
        indexed[key] = row
    instants = sorted({key[0] for key in indexed})
    path = inputs['load_path']
    if instants[0] != 0 or abs(instants[-1] - len(path)) > 1e-10:
        raise ValueError('Native contact history is incomplete at the load-path endpoints.')
    for endpoint in range(len(path)+1):
        if not any(abs(t-endpoint) < 1e-10 for t in instants):
            raise ValueError('Native contact history is missing an authored load stage.')
    displacement_times = {float(r['INST']) for r in parser._parse_csv_table(root/'study_depl.csv')}
    if len(displacement_times) != len(instants) or any(not any(abs(t-d)<1e-10 for d in displacement_times) for t in instants):
        raise ValueError('Contact and displacement histories have different increments.')
    history = []
    for instant in instants:
        results = parser._parse_results(model,root,instant=instant)
        results.load_case = study.load_case
        if any(results.node_results[s.node].reaction_force is None for s in model.supports):
            raise ValueError('Missing native support reaction at a converged increment.')
        stage_index = max(0, min(len(path), math.ceil(instant-1e-10)))
        results.metadata.update(pseudo_time=instant, stage_index=stage_index,
            stage_label='Reference' if instant == 0 else path[stage_index-1],
            run_id=study.solver_input_identity.fingerprint, formulation='POU_D_T / DIS_CHOC',
            convergence_status='converged', contact_status_tolerances={'force_N':1.,'relative_force':.001,'slip_m':1e-9,'gap_m':1e-9},
            contact_variable_mapping={'N':'local compression negative','V4':'0 sticking, 1 sliding, 2 open','V5':'local y slip','V6':'local z slip'},
            source='Code_Aster study_contact.json')
        for spec in specs:
            row = indexed.get((instant,spec.support.id))
            if row is None:
                raise ValueError('Missing support at a converged contact increment.')
            normal = np.array(spec.normal)
            t1 = np.array(spec.tangent)
            t2 = np.cross(normal,t1)
            displacement = results.node_results[spec.support.node].displacement[:3]
            normal_force = -float(row['N'])
            tangential_force = -(row['VY']*t1 + row['VZ']*t2)
            slip = row['slip_y']*t1 + row['slip_z']*t2
            gap = spec.support.gap + float(np.dot(displacement,normal))
            limit = spec.support.friction_coefficient * max(0.,normal_force)
            ft = float(np.linalg.norm(tangential_force))
            tolerance = max(1., .001*max(abs(normal_force),limit))
            if gap > 1e-9 and normal_force > tolerance:
                raise ValueError('Separated native contact has a nonzero normal force.')
            if normal_force < -tolerance or ft > limit + tolerance:
                raise ValueError('Native contact result violates the normal/Coulomb force bounds.')
            if row['status'] not in (0, 1, 2):
                raise ValueError('Unknown native DIS_CHOC contact status.')
            status = {0: 'sticking', 1: 'sliding', 2: 'open'}[row['status']]
            source = 'solver'
            results.metadata.setdefault('native_contact_status', {})[spec.support.id] = row['status']
            if instant == 0 and gap > 1e-9 and abs(normal_force) <= tolerance and ft <= tolerance:
                status, source = 'open', 'derived'
                results.metadata.setdefault('contact_status_basis', {})[spec.support.id] = 'Unloaded reference: positive authored/solved gap and zero contact force; native variables initially zero.'
            if spec.support.friction_coefficient == 0:
                # Code_Aster 18 DIS_CHOC symmetric LOCAL branch retains V4=2
                # after reseating. Report normal opening from solved gap/force;
                # a closed frictionless shoe has no stick/slip classification.
                status = 'open' if gap > 1e-9 and abs(normal_force) <= tolerance else 'indeterminate'
                source = 'derived'
                results.metadata.setdefault('contact_status_basis', {})[spec.support.id] = (
                    'Frictionless: open from solved gap/normal force; closed has no stick/slip classification. Native V4 retained separately.')
            if status == 'open' and (abs(normal_force) > tolerance or ft > tolerance):
                raise ValueError('Open native contact has nonzero contact force.')
            results.contact_results[spec.support.id] = ContactResult(
                support_id=spec.support.id,node_id=spec.support.node,status=status,normal=spec.normal,
                normal_force=normal_force,tangential_force=tuple(tangential_force),gap=gap,
                relative_displacement=tuple(displacement),slip=tuple(slip),friction_limit=limit,
                utilization=ft/limit if limit > 1e-9 and status != 'open' else None,status_source=source)
        # The true nodal reaction at the shared shoe node excludes its connector.
        # Publish the isolated support force on the pipe as its reaction instead.
        for node_id in {spec.support.node for spec in specs}:
            reaction = np.zeros(6)
            for contact in results.contact_results.values():
                if contact.node_id == node_id:
                    reaction[:3] += contact.normal_force*np.array(contact.normal) + contact.tangential_force
            results.node_results[node_id].reaction_force = reaction
        history.append(results)
    return history
