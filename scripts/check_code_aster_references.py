"""Run the mandatory numerical references; skips are not qualification evidence."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_TESTS = (
    'tests/test_code_aster_real_smoke.py',
    'tests/test_code_aster_beam_pipes.py',
    'tests/test_code_aster_supports.py',
    'tests/test_code_aster_line_loads.py',
    'tests/test_code_aster_node_temperatures.py',
    'tests/test_code_aster_pipe_volume_reference.py',
    'tests/test_code_aster_mixed_volume_reference.py',
    'tests/test_code_aster_tee_volume_reference.py',
    'tests/test_insulation_solver.py',
    'tests/test_code_aster_fluid_contents.py',
    'tests/integration/test_code_aster_friction.py',
)


def passed_reference_count(report: Path) -> int:
    """Return the number of passed cases, rejecting absent or incomplete evidence."""
    try:
        root = ET.parse(report).getroot()
    except (OSError, ET.ParseError) as exc:
        raise ValueError(f'Cannot read qualification report {report}: {exc}') from exc
    if root.tag not in {'testsuites', 'testsuite'}:
        raise ValueError('Qualification report must be JUnit testsuites or testsuite.')
    cases = list(root.iter('testcase'))
    if not cases:
        raise ValueError('Qualification report contains no test cases.')
    if any(node.tag in {'failure', 'error', 'skipped'} for node in root.iter()):
        raise ValueError('Qualification requires every reference to pass; failures, errors and skips are forbidden.')
    # Inspect aggregate verdicts too, but count only actual cases so nested suites
    # cannot double-count successful references or conceal a reported error.
    for suite in root.iter():
        if suite.tag in {'testsuites', 'testsuite'}:
            for verdict in ('failures', 'errors', 'skipped'):
                if int(suite.get(verdict, '0')) != 0:
                    raise ValueError(f'Qualification report has nonzero {verdict}.')
    return len(cases)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path,
                        default=ROOT / '.build' / 'qualification' / 'code-aster-references.xml')
    args = parser.parse_args(argv)
    report = args.report.resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    report.unlink(missing_ok=True)
    env = dict(os.environ, TUBA_RUN_CODE_ASTER_INTEGRATION='1')
    # This is a mandatory fixed selection, never a user's filtered quick run.
    env.pop('PYTEST_ADDOPTS', None)
    command = [sys.executable, '-m', 'pytest', *REFERENCE_TESTS, '-q', '--tb=short',
               '-o', 'addopts=', f'--junitxml={report}']
    completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
    if completed.returncode:
        return completed.returncode
    try:
        count = passed_reference_count(report)
    except ValueError as exc:
        print(f'Code_Aster qualification failed: {exc}', file=sys.stderr)
        return 1
    print(f'Code_Aster qualification: {count} references passed, no skips. Report: {report}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
