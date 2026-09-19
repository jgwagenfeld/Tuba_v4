"""run_model_code: the script stays the basis, execution is nondestructive."""

from __future__ import annotations

from pathlib import Path

import pytest

from tuba.mcp.server import (
    build_pipe_run,
    get_active_model,
    init_session,
    inspect_model,
    run_model_code,
)
from tuba.project.script import same_model


def _fresh(model_file: Path):
    return init_session(project_name="Code Run", file_path=str(model_file), load_existing=False)


def test_a_loop_builds_what_unrolled_steps_build(tmp_path: Path):
    first = tmp_path / "a" / "model.py"
    _fresh(first)
    build_pipe_run(
        section="DN100_SCH40",
        material="P265GH",
        steps=[
            {"op": "start", "point": [0.0, 0.0, 0.0], "support": "anchor"},
            {"op": "run", "length": 2.0},
            {"op": "run", "length": 2.0},
            {"op": "end", "support": "anchor"},
        ],
    )
    reference = get_active_model()

    second = tmp_path / "b" / "model.py"
    _fresh(second)
    res = run_model_code(
        "with model.pipe(section='DN100_SCH40', material='P265GH') as builder:\n"
        "    builder.start([0.0, 0.0, 0.0], support='anchor')\n"
        "    for _ in range(2):\n"
        "        builder.run(2.0)\n"
        "    builder.end(support='anchor')\n"
    )
    assert res["status"] == "success"
    assert res["added_nodes"] == 3
    assert same_model(get_active_model(), reference)
    # The persisted script is still unrolled: one record per line.
    assert "for _ in range" not in second.read_text(encoding="utf-8")


def test_code_may_import_tuba_and_loop_over_specs(tmp_path: Path):
    model_file = tmp_path / "demo" / "model.py"
    _fresh(model_file)
    run_model_code(
        "for name, od in [('DN50', 0.0603), ('DN65', 0.0761)]:\n"
        "    model.add_pipe_section(name, OD=od, WT=0.00391)\n"
    )
    assert {"DN50", "DN65"} <= set(inspect_model()["sections"])


def test_failing_code_changes_neither_session_nor_script(tmp_path: Path):
    model_file = tmp_path / "demo" / "model.py"
    _fresh(model_file)
    before_text = model_file.read_text(encoding="utf-8")
    with pytest.raises(RuntimeError, match="unchanged"):
        run_model_code("model.add_pipe_section('DN50', OD=0.0603, WT=0.00391)\nundefined_name\n")
    assert inspect_model()["sections"] == ["DN100_SCH40", "DN150_SCH40", "DN200_SCH40"]
    assert model_file.read_text(encoding="utf-8") == before_text


def test_rebinding_model_to_something_else_is_refused(tmp_path: Path):
    model_file = tmp_path / "demo" / "model.py"
    _fresh(model_file)
    with pytest.raises(RuntimeError, match="TubaModel"):
        run_model_code("model = 'not a model'\n")
    assert inspect_model()["nodes"] == {}


def test_an_outside_edit_is_never_overwritten(tmp_path: Path):
    model_file = tmp_path / "demo" / "model.py"
    _fresh(model_file)
    edited = model_file.read_text(encoding="utf-8") + "\n# edited in the studio\n"
    model_file.write_text(edited, encoding="utf-8")
    with pytest.raises(RuntimeError, match="init_session"):
        run_model_code("model.add_pipe_section('DN50', OD=0.0603, WT=0.00391)\n")
    assert model_file.read_text(encoding="utf-8") == edited
    assert "DN50" not in inspect_model()["sections"]
