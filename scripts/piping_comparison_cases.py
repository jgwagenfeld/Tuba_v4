"""Versioned thermal research cases, returned as independent requirement records."""

from copy import deepcopy

from scripts.benchmark_llm_piping import CASE as FIRST_CASE

DEFAULT_CASE_ID = 'thermal-guided-design-v1'
CASE_IDS = (DEFAULT_CASE_ID, 'thermal-guided-hot-v1', 'thermal-guided-compact-v1')


def get_case(case_id=DEFAULT_CASE_ID):
    if case_id not in CASE_IDS:
        raise ValueError(f'Unknown piping comparison case: {case_id!r}')
    case = deepcopy(FIRST_CASE)
    case.update(id=case_id, support_policy={
        'max_guides': 4, 'directions': [[0., 1., 0.], [0., 0., 1.]],
        'placement': 'Distinct interior nodes; ideal bilateral ground guides only.'})
    case['solver_options']['timeout_seconds'] = 600
    if case_id == 'thermal-guided-hot-v1':
        case['operation']['temperature'] = 300.
    elif case_id == 'thermal-guided-compact-v1':
        case['centerline_bounds_m'][1][1] = 1.2
        case['force_limit_N'] = 8000.
    return case
