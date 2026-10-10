import pytest

from tests.project_replay import ReplaySolver
from tests.test_search_run import RACK, author
from tuba.search.__main__ import main


def test_cli_run_inspect_export_and_invalid_candidate(tmp_path, capsys):
    project = author(tmp_path, values=(100.0,))
    run = tmp_path / "run"
    assert main(["run", str(project), "--run-dir", str(run)], solver=ReplaySolver(RACK / "evidence")) == 0
    assert main(["inspect", "--run-dir", str(run)]) == 0
    assert "selected" in capsys.readouterr().out
    assert main(["inspect", "--run-dir", str(run), "--candidate", "C0001"]) == 0
    assert "evidence.Operating" in capsys.readouterr().out
    assert main(["export", "--run-dir", str(run), "--output", str(tmp_path / "export")]) == 0
    assert main(["inspect", "--run-dir", str(run), "--candidate", "absent"]) == 2


def test_no_feasible_exit_is_distinct_from_runtime_blocker(tmp_path):
    project = author(tmp_path, values=(100.0,), budget=0)
    assert main(["run", str(project), "--run-dir", str(tmp_path / "budget")]) == 3
    (project / "search.py").write_text((project / "search.py").read_text().replace(", 1, 0)", ", 1, 1)"))
    class Unavailable:
        def solve_exported_study(self, model, study):
            raise RuntimeError("Code_Aster runtime unavailable")
    assert main(["run", str(project), "--run-dir", str(tmp_path / "runtime")], solver=Unavailable()) == 4


def test_missing_history_and_parser_error_are_invalid_input(tmp_path):
    assert main(["inspect", "--run-dir", str(tmp_path / "absent")]) == 2
    with pytest.raises(SystemExit) as error:
        main(["run"])
    assert error.value.code == 2
