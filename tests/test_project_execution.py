"""Project functions and local units reload without foreign import mutations."""

import gc
from pathlib import Path
import sys
from types import ModuleType

import pytest

from tuba.project import load_project, run_model_script


def test_project_local_helpers_are_fresh_without_cwd_path_or_foreign_module_changes(tmp_path, monkeypatch):
    other = ModuleType("dimensions")
    other.LENGTH = 999
    monkeypatch.setitem(sys.modules, "dimensions", other)
    helper = tmp_path / "dimensions.py"
    helper.write_text("LENGTH = 2\n")
    script = tmp_path / "model.py"
    text = "from tuba import Model\nimport dimensions\nmodel = Model(str(dimensions.LENGTH))\n"
    script.write_text(text)
    cwd, path, modules = Path.cwd(), list(sys.path), dict(sys.modules)
    first = run_model_script(script)
    helper.write_text("LENGTH = 3\n")  # same size and timestamp resolution: never stale pycache
    second = run_model_script(script)
    assert (first["model"].project_name, second["model"].project_name) == ("2", "3")
    assert set(second["__tuba_project_dependencies__"]) == {script, helper}
    assert sys.modules["dimensions"] is other
    assert all(sys.modules.get(name) is module for name, module in modules.items())
    assert Path.cwd() == cwd and sys.path == path
    assert script.read_text() == text


def test_local_package_relative_import_and_recorded_unit_reload(tmp_path):
    package = tmp_path / "units"
    package.mkdir()
    (package / "__init__.py").write_text("")
    helper = package / "dimensions.py"
    helper.write_text("HEIGHT = 2\n")
    unit = package / "row.py"
    unit.write_text("from .dimensions import HEIGHT\n\ndef build(model):\n    return model.add_node([0, 0, HEIGHT])\n")
    script = tmp_path / "model.py"
    script.write_text("from tuba import Model\nfrom tuba.assemblies import assemble\nmodel=Model('Unit')\nassemble(model, 'units.row:build')\n")
    first = run_model_script(script)
    helper.write_text("HEIGHT = 4\n")
    second = run_model_script(script)
    assert first["model"].nodes["N0"].coords[2] == 2
    assert second["model"].nodes["N0"].coords[2] == 4
    assert second["model"].assembly_calls[0]["ref"] == "units.row:build"
    assert {script, helper, unit, package / "__init__.py"} == set(second["__tuba_project_dependencies__"])


def test_build_model_and_study_use_project_local_helpers(tmp_path):
    (tmp_path / "dimensions.py").write_text("NAME='Local'\n")
    (tmp_path / "model.py").write_text("from tuba import Model\ndef build_model():\n    from dimensions import NAME\n    return Model(NAME)\n")
    (tmp_path / "study.py").write_text("from dimensions import NAME\nLOAD_CASES=(NAME,)\n")
    project = load_project(tmp_path)
    assert project.run_model()["model"].project_name == "Local"
    assert project.load_study().LOAD_CASES == ("Local",)


def test_invalid_model_factory_runs_once(tmp_path):
    script = tmp_path / "model.py"
    script.write_text(
        "from pathlib import Path\ndef build_model():\n"
        "    with Path(__file__).with_suffix('.calls').open('a') as log:\n"
        "        log.write('called\\n')\n"
    )
    with pytest.raises(TypeError, match="must bind 'model'"):
        run_model_script(script)
    assert script.with_suffix(".calls").read_text() == "called\n"


def test_failed_helper_reports_dependencies_so_fix_can_be_watched(tmp_path):
    helper = tmp_path / "broken.py"
    helper.write_text("raise ValueError('bad helper')\n")
    script = tmp_path / "model.py"
    script.write_text("import broken\n")
    with pytest.raises(ValueError, match="bad helper") as error:
        run_model_script(script)
    assert set(error.value.__tuba_project_dependencies__) == {script, helper}


def test_relative_imports_of_private_root_children_are_fresh_and_tracked(tmp_path):
    dimensions = tmp_path / "dimensions.py"
    dimensions.write_text("LENGTH=2\n")
    helper = tmp_path / "helper.py"
    helper.write_text("from . import dimensions\nLENGTH=dimensions.LENGTH\n")
    package = tmp_path / "units"
    package.mkdir()
    nested = package / "nested.py"
    nested.write_text("from .. import dimensions\nLENGTH=dimensions.LENGTH\n")
    script = tmp_path / "model.py"
    script.write_text("from tuba import Model\nimport helper\nfrom units import nested\nmodel=Model(f'{helper.LENGTH}:{nested.LENGTH}')\n")
    first = run_model_script(script)
    dimensions.write_text("LENGTH=3\n")
    second = run_model_script(script)
    assert (first["model"].project_name, second["model"].project_name) == ("2:2", "3:3")
    assert set(second["__tuba_project_dependencies__"]) == {script, dimensions, helper, nested}


def test_helper_dataclasses_have_private_module_identity_and_cleanup(tmp_path, monkeypatch):
    from dataclasses import fields
    from typing import get_type_hints

    foreign = ModuleType("parameters")
    monkeypatch.setitem(sys.modules, "parameters", foreign)
    (tmp_path / "parameters.py").write_text(
        "from __future__ import annotations\nfrom dataclasses import dataclass\n"
        "from typing import ClassVar\n@dataclass\nclass Parameters:\n"
        "    label: ClassVar[str] = 'Dimensions'\n    height: float = 2\n"
    )
    script = tmp_path / "model.py"
    script.write_text("from tuba import Model\nfrom parameters import Parameters\nmodel=Model(str(Parameters().height))\n")
    before = set(sys.modules)
    namespace = run_model_script(script)
    cls = namespace["Parameters"]
    private = {name for name in set(sys.modules) - before if name.startswith("_tuba_project_")}
    assert cls.__module__ in private
    assert get_type_hints(cls)["height"] is float
    assert [field.name for field in fields(cls)] == ["height"]
    assert cls(3).height == 3
    assert sys.modules["parameters"] is foreign
    del namespace, cls
    gc.collect()
    assert not (private & set(sys.modules))


def test_entry_dataclass_annotations_resolve_without_replacing_main_module(tmp_path):
    from dataclasses import fields
    from typing import get_type_hints

    original_main = sys.modules["__main__"]
    (tmp_path / "__entry__.py").write_text("VALUE=10\n")
    script = tmp_path / "model.py"
    script.write_text(
        "from __future__ import annotations\nfrom dataclasses import dataclass\n"
        "from typing import ClassVar\nfrom tuba import Model\nimport __entry__\n@dataclass\nclass Parameters:\n"
        "    tag: ClassVar[str] = 'Entry'\n    height: float = 2\n"
        "if __name__ == '__main__':\n    model=Model(str(Parameters().height))\n"
    )
    namespace = run_model_script(script)
    cls = namespace["Parameters"]
    assert [field.name for field in fields(cls)] == ["height"]
    assert get_type_hints(cls)["height"] is float
    assert namespace["__name__"] == "__main__"
    assert namespace["model"].project_name == "2"
    assert sys.modules["__main__"] is original_main


def test_entry_and_helper_compile_do_not_inherit_framework_future_flags(tmp_path):
    (tmp_path / "helper.py").write_text("def height(value: float) -> float:\n    return value\n")
    script = tmp_path / "model.py"
    script.write_text("from tuba import Model\nfrom helper import height\ndef length(value: float) -> float:\n    return value\nmodel=Model('Annotations')\n")
    namespace = run_model_script(script)
    assert namespace["length"].__annotations__ == {"value": float, "return": float}
    assert namespace["height"].__annotations__ == {"value": float, "return": float}


def test_external_unit_mixed_records_link_to_each_authored_invocation(tmp_path):
    package = tmp_path / "units"
    package.mkdir()
    (package / "part.py").write_text(
        "def build(model, name, origin, material):\n"
        "    \"\"\"Build a named part at origin using the given material.\"\"\"\n"
        "    model.add_cad_asset(id=name+'_asset', source_path='geometry/part.step')\n"
        "    model.add_imported_component(id=name, asset='cad_asset:'+name+'_asset', name=name)\n"
        "    model.add_port(id=name+'_port', owner='component:'+name, kind='circular_face', position=origin, axis=[1,0,0], radius=.05)\n"
        "    reference=model.add_reference_point(name+'_reference', position=origin)\n"
        "    model.add_shell_panel(name+'_panel', polygon=[origin,[origin[0]+1,0,0],[origin[0],1,0]], thickness=.01, material=material)\n"
        "    model.add_rigid_patch(name+'_patch', reference=reference, shell=name+'_panel', vertices=[0])\n"
    )
    script = tmp_path / "model.py"
    script.write_text(
        "from tuba import Model\nfrom tuba.assemblies import assemble\nmodel=Model('Units')\n"
        "model.add_material('Steel', E=2.1e11, nu=.3)\n"
        "assemble(model,'units.part:build',name='left',origin=[0,0,0],material='Steel')\n"
        "assemble(model,'units.part:build',name='right',origin=[2,0,0],material='Steel')\n"
    )
    model = run_model_script(script)["model"]
    for collection in ("cad_assets", "imported_components", "analysis_regions", "ports", "mesh_groups", "couplings"):
        records = getattr(model, collection)
        assert records
        for identity, record in records.items():
            assert record.source_line == (5 if identity.startswith("left") else 6)
            assert "source_line" not in record.to_dict()
