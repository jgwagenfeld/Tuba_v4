"""MCP construction units: saved to model.py or units/, applied transactionally."""

from __future__ import annotations

from pathlib import Path

import pytest

from tuba.mcp.server import (
    apply_unit,
    get_active_model,
    init_session,
    inspect_model,
    run_model_code,
    save_unit,
)
from tuba.project import run_model_script
from tuba.project.script import same_model

POSTS = (
    "def posts(model, x0=0.0, n=2):\n"
    '    """Add *n* nodes from *x0* along X."""\n'
    "    for i in range(n):\n"
    "        model.add_node([x0 + float(i), 0.0, 0.0])\n"
)


def test_save_unit_enforces_construction_style(tmp_path: Path):
    model_file = tmp_path / "proj" / "model.py"
    init_session(project_name="Units", file_path=str(model_file), load_existing=False)
    before = model_file.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="docstring"):
        save_unit(name="nodoc", code="def build(model):\n    model.add_node([0.0, 0.0, 0.0])\n", where="model")
    with pytest.raises(ValueError, match="first parameter"):
        save_unit(name="nomodel", code='def build(notmodel):\n    """Docstring."""\n', where="model")
    with pytest.raises(ValueError, match="print"):
        save_unit(name="noisy", code='def build(model):\n    """Docstring."""\n    print("hi")\n', where="model")
    with pytest.raises(ValueError, match="bare .except"):
        save_unit(name="sneaky",
                  code='def build(model):\n    """Docstring."""\n    try:\n        pass\n    except:\n        pass\n',
                  where="model")
    assert model_file.read_text(encoding="utf-8") == before
    assert not (model_file.parent / "units").exists()


def test_save_unit_rejects_lint_dirty_code(tmp_path: Path):
    pytest.importorskip("ruff")
    model_file = tmp_path / "proj" / "model.py"
    init_session(project_name="Units", file_path=str(model_file), load_existing=False)
    with pytest.raises(ValueError, match="statically clean"):
        save_unit(name="dirty",
                  code='def build(model):\n    """Docstring."""\n    import os\n    model.add_node([0.0, 0.0, 0.0])\n',
                  where="model")


def test_save_unit_to_model_py_and_apply_it(tmp_path: Path):
    model_file = tmp_path / "proj" / "model.py"
    init_session(project_name="Units", file_path=str(model_file), load_existing=False)

    saved = save_unit(name="posts", code=POSTS, func="posts", where="model", params={"n": 1})
    assert saved == {"status": "saved", "ref": "posts", "where": "model", "dry_run": True}

    res = apply_unit("posts", {"x0": 4.0, "n": 2})
    assert res["status"] == "success" and res["added_nodes"] == 2 and res["invocations"] == 1

    text = model_file.read_text(encoding="utf-8")
    assert POSTS in text
    assert "assemble(model, 'posts', x0=4.0, n=2)" in text
    assert same_model(run_model_script(model_file)["model"], get_active_model())


def test_save_unit_to_units_package_and_apply_by_ref(tmp_path: Path):
    model_file = tmp_path / "proj" / "model.py"
    init_session(project_name="Units", file_path=str(model_file), load_existing=False)

    saved = save_unit(name="rack", code=POSTS.replace("def posts", "def posts"), func="posts",
                      where="units", params={"n": 1})
    assert saved["ref"] == "units.rack:posts"
    assert (model_file.parent / "units" / "rack.py").is_file()

    apply_unit("units.rack:posts", {"x0": 1.0, "n": 2})
    # run_model_code snippets import project units too.
    run_model_code("from units.rack import posts\nposts(model, x0=10.0, n=1)\n")
    assert len(inspect_model()["nodes"]) == 3


def test_save_unit_refuses_broken_code_and_saves_nothing(tmp_path: Path):
    model_file = tmp_path / "proj" / "model.py"
    init_session(project_name="Units", file_path=str(model_file), load_existing=False)
    before = model_file.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="does not parse"):
        save_unit(name="bad", code="def broken(:\n", where="model")
    with pytest.raises(ValueError, match="no callable"):
        save_unit(name="empty", code="VALUE = 1\n", where="units")
    with pytest.raises(ValueError, match="dry-run"):
        save_unit(name="boom", code='def build(model):\n    """Docstring."""\n    raise RuntimeError("nope")\n',
                  where="units", params={})
    assert model_file.read_text(encoding="utf-8") == before
    assert not (model_file.parent / "units").exists()


def test_save_unit_refuses_a_duplicate_def(tmp_path: Path):
    model_file = tmp_path / "proj" / "model.py"
    init_session(project_name="Units", file_path=str(model_file), load_existing=False)
    save_unit(name="posts", code=POSTS, func="posts", where="model")
    with pytest.raises(ValueError, match="already defines"):
        save_unit(name="posts", code=POSTS, func="posts", where="model")
    assert model_file.read_text(encoding="utf-8").count("def posts") == 1


def test_apply_unit_resolves_model_py_defs_from_snippets(tmp_path: Path):
    model_file = tmp_path / "proj" / "model.py"
    init_session(project_name="Units", file_path=str(model_file), load_existing=False)
    save_unit(name="posts", code=POSTS, func="posts", where="model")

    res = run_model_code("assemble(model, 'posts', x0=2.0, n=2)\n")
    assert res["added_nodes"] == 2
    text = model_file.read_text(encoding="utf-8")
    assert "assemble(model, 'posts', x0=2.0, n=2)" in text
    assert same_model(run_model_script(model_file)["model"], get_active_model())


def test_apply_unknown_unit_changes_nothing(tmp_path: Path):
    model_file = tmp_path / "proj" / "model.py"
    init_session(project_name="Units", file_path=str(model_file), load_existing=False)
    before = model_file.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="posts"):
        apply_unit("posts")
    with pytest.raises(ValueError, match="cannot be imported"):
        apply_unit("units.missing:build")
    assert model_file.read_text(encoding="utf-8") == before
    assert get_active_model().assembly_calls == []


def test_agent_creates_on_the_fly_unit_for_bespoke_framing(tmp_path: Path):
    model_file = tmp_path / "proj" / "model.py"
    init_session(project_name="CustomFraming", file_path=str(model_file), load_existing=False)

    from tuba.mcp.server import add_ibeam_section, add_material, check_clashes
    add_material(name="Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    add_ibeam_section(name="IPE100", profile_name="IPE100")

    # On-the-fly construction unit synthesized by the agent
    code = (
        "def custom_offset_bay(model, origin=(0.0, 0.0, -3.0), material='Steel', section='IPE100'):\n"
        '    """Synthesize an offset rack bay on the fly without core library bloat."""\n'
        "    from tuba.assemblies import RackRow\n"
        "    from tuba.patches import ModelTransaction\n"
        "    row = RackRow(\n"
        "        name_prefix='bespoke',\n"
        "        origin=tuple(origin),\n"
        "        material=material,\n"
        "        section=section,\n"
        "        direction='X',\n"
        "        bays=2,\n"
        "        bay_length=2.0,\n"
        "        width=2.0,\n"
        "        height=3.0,\n"
        "        levels=(2.75,),\n"
        "    )\n"
        "    ModelTransaction(model).apply(row.to_patch())\n"
    )

    save_res = save_unit(
        name="custom_bay",
        code=code,
        func="custom_offset_bay",
        where="units",
        params={"origin": [0.0, 0.0, -3.0]},
    )
    assert save_res["status"] == "saved"
    assert save_res["ref"] == "units.custom_bay:custom_offset_bay"

    apply_res = apply_unit("units.custom_bay:custom_offset_bay", {"origin": [2.0, 0.0, -3.0]})
    assert apply_res["status"] == "success"
    assert apply_res["clash_warnings"] == []

    # Verify clash check is clean
    clashes = check_clashes()
    assert clashes["passed"] is True
    assert clashes["counts"]["self"] == 0
    assert clashes["counts"]["obstacle"] == 0

    # Verify inspect_model tracks the assembly call
    inspection = inspect_model()
    assert len(inspection["assembly_calls"]) == 1
    assert inspection["assembly_calls"][0]["ref"] == "units.custom_bay:custom_offset_bay"
    assert inspection["assembly_calls"][0]["params"] == {"origin": [2.0, 0.0, -3.0]}

