"""Qualification must fail closed even when pytest exits zero after skipping."""

import ast
import importlib.util
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'check_code_aster_references.py'


def load_gate():
    assert SCRIPT.is_file(), 'The shared numerical qualification command is missing'
    spec = importlib.util.spec_from_file_location('reference_gate', SCRIPT)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    return gate


def test_required_references_do_not_force_a_platform_runtime():
    gate = load_gate()
    forced = []
    for filename in gate.REFERENCE_TESTS:
        tree = ast.parse((gate.ROOT / filename).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if keyword.arg in {'exec_method', 'wsl_distro'} and isinstance(keyword.value, ast.Constant):
                        if keyword.value.value not in {None, 'auto'}:
                            forced.append(f'{filename}:{node.lineno} {keyword.arg}={keyword.value.value!r}')
    assert not forced, '\n'.join(forced)


@pytest.mark.parametrize('xml', [
    '<testsuites/>',
    '<testsuites><testsuite tests="0"/></testsuites>',
    '<testsuite tests="1"><testcase><skipped/></testcase></testsuite>',
    '<testsuite tests="1"><testcase><failure/></testcase></testsuite>',
    '<testsuite tests="1"><testcase><error/></testcase></testsuite>',
    '<testsuite tests="1" skipped="1"><testcase/></testsuite>',
    '<testsuite tests="1" errors="1"><testcase/></testsuite>',
    '<testsuite tests="1" failures="1"><testcase/></testsuite>',
    '<testsuite tests="1" skipped="invalid"><testcase/></testsuite>',
    '<testsuites>',
    '<unrelated><testcase/></unrelated>',
])
def test_incomplete_or_failed_report_is_rejected(tmp_path, xml):
    gate = load_gate()
    report = tmp_path / 'results.xml'
    report.write_text(xml)
    with pytest.raises(ValueError):
        gate.passed_reference_count(report)


def test_nested_suites_count_each_actual_case_once(tmp_path):
    gate = load_gate()
    report = tmp_path / 'results.xml'
    report.write_text('''<testsuites tests="2"><testsuite tests="2" failures="0" errors="0" skipped="0">
        <testsuite tests="1"><testcase name="a"/></testsuite>
        <testsuite tests="1"><testcase name="b"/></testsuite>
    </testsuite></testsuites>''')
    assert gate.passed_reference_count(report) == 2


@pytest.mark.parametrize(('body', 'exit_code'), [
    ('assert True', 0),
    ('import pytest; pytest.skip("no solver")', 1),
    ('assert False', 1),
])
def test_command_runs_pytest_and_enforces_no_skips(tmp_path, monkeypatch, body, exit_code):
    gate = load_gate()
    monkeypatch.setattr(gate, 'ROOT', tmp_path)
    test_file = tmp_path / 'test_reference.py'
    test_file.write_text('def test_reference():\n    ' + body + '\n')
    monkeypatch.setattr(gate, 'REFERENCE_TESTS', (str(test_file),))
    # Filtering must not silently reduce a mandatory qualification run.
    monkeypatch.setenv('PYTEST_ADDOPTS', '-k nonexistent_reference')
    report = tmp_path / 'new' / 'results.xml'
    assert gate.main(['--report', str(report)]) == exit_code
    assert report.is_file()


def test_zero_collected_cases_is_a_failed_command(tmp_path, monkeypatch):
    gate = load_gate()
    monkeypatch.setattr(gate, 'ROOT', tmp_path)
    test_file = tmp_path / 'test_empty.py'
    test_file.write_text('# no references\n')
    monkeypatch.setattr(gate, 'REFERENCE_TESTS', (str(test_file),))
    assert gate.main(['--report', str(tmp_path / 'results.xml')]) != 0


@pytest.mark.parametrize('returncode', [0, 7])
def test_previous_report_cannot_hide_missing_new_report(tmp_path, monkeypatch, returncode):
    gate = load_gate()
    report = tmp_path / 'results.xml'
    report.write_text('<testsuite tests="1"><testcase/></testsuite>')

    def child_without_report(command, **kwargs):
        assert not report.exists()
        assert kwargs['env']['TUBA_RUN_CODE_ASTER_INTEGRATION'] == '1'
        assert kwargs['env']['TUBA_CODE_ASTER_EXEC_METHOD'] == 'wsl'
        return subprocess.CompletedProcess(command, returncode)

    monkeypatch.setenv('TUBA_CODE_ASTER_EXEC_METHOD', 'wsl')
    monkeypatch.setattr(gate.subprocess, 'run', child_without_report)
    assert gate.main(['--report', str(report)]) == (returncode or 1)


def test_failed_child_cannot_be_overruled_by_a_passing_report(tmp_path, monkeypatch):
    gate = load_gate()
    report = tmp_path / 'results.xml'

    def failing_child(command, **kwargs):
        report.write_text('<testsuite tests="1"><testcase/></testsuite>')
        return subprocess.CompletedProcess(command, 7)

    monkeypatch.setattr(gate.subprocess, 'run', failing_child)
    assert gate.main(['--report', str(report)]) == 7
