"""The studio opens a project folder, never a bare model file."""

from pathlib import Path

import pytest

from tuba import cli_studio


def test_the_studio_refuses_anything_but_a_project_folder(tmp_path: Path, capsys):
    model_json = tmp_path / "model.json"
    model_json.write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit) as exit_info:
        cli_studio.main([str(model_json), "--no-open"])

    assert exit_info.value.code == 2
    assert "project folder" in capsys.readouterr().err
