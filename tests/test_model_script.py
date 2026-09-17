"""A generated model script rebuilds its model exactly and links every element and support to its own line."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from tuba import Model
from tuba.builder import BuildStep, PipeRunRecipe
from tuba.model import TubaModel
from tuba.patches import ModelPatch, ModelTransaction
from tuba.project import load_project, run_model_script
from tuba.project.script import GENERATED_HEADER, generate_model_script, is_generated, same_model
from tuba.project.script import AuthoredModelScript, ModelScriptChanged, write_model_script

EXAMPLES = sorted(
    folder
    for folder in (Path(__file__).resolve().parents[1] / "examples").iterdir()
    if (folder / "model.py").is_file()
)

_BUILDER = """from tuba import Model

model = Model("ScriptLink")
model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
model.define_load_case("Operating", gravity=True, pressure=1.5e6, temperature=150.0)
with model.pipe(section="DN100", material="Steel") as builder:
    builder.start([0.0, 0.0, 0.0], support="anchor")
    builder.run(4.0)
    builder.bend(radius=0.3, angle=90.0, plane="XY")
    builder.add_support(type="guide")
    builder.run(2.0)
    builder.end(support="anchor")
"""


def _rebuild(text: str) -> TubaModel:
    namespace: dict = {"__name__": "generated_model_check"}
    exec(compile(text, "model.py", "exec"), namespace)
    return namespace["model"]


def _block(*steps: str, section: str = "DN100", material: str = "Steel", route: str | None = None) -> str:
    route_argument = "" if route is None else f", route={route!r}"
    head = f"with model.pipe(section={section!r}, material={material!r}{route_argument}) as builder:"
    return "\n".join([head, *(f"    builder.{step}" for step in steps)])


def _sections_model(name: str) -> TubaModel:
    model = Model(name)
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    return model


@pytest.mark.parametrize("folder", EXAMPLES, ids=lambda folder: folder.name)
def test_a_generated_script_rebuilds_each_example_project(folder: Path):
    model = load_project(folder).run_model()["model"]
    text = generate_model_script(model)

    assert is_generated(text)
    assert same_model(model, _rebuild(text))


def test_a_generated_script_keeps_awkward_names_and_numbers():
    backslash = chr(92)
    model = Model("Edge \"double\" 'single' ''' \u00dcmlaut " + backslash + "path")
    model.add_material(
        "St\u00e4hl \"X\"", E=2.1e11, nu=0.3, rho=7850, alpha=float("nan"), allowable_stress={20: 1.37e8, 150.5: 1.2e8}
    )
    model.add_pipe_section("DN100 'sch40'", OD=np.float64(0.1143), WT=0.00602)
    first = model.add_node((0, 0, 0))
    second = model.add_node([1.0, -0.0, 0.0])
    model.add_element(
        id="pipe \"a\"", type="pipe_straight", n1=first, n2=second,
        section="DN100 'sch40'", material="St\u00e4hl \"X\"", route_id="\u30eb\u30fc\u30c8-1",
    )
    model.add_support(node=first, type="anchor", direction=(0.0, 0.0, 1.0))
    model.define_load_case("Hot \"1\"", temperature=120)
    model.add_obstacle(id="tray", type="cuboid", min_point=(0, 0, 0), max_point=(1, 1, 1))
    model.add_obstacle(id="far", type="cuboid", min_point=(float("-inf"), 0.0, 0.0), max_point=(float("inf"), 1.0, 1.0))

    assert same_model(model, _rebuild(generate_model_script(model)))


def test_a_generated_script_keeps_groups_specs_attributes_operations_and_placements():
    from tuba.assemblies import RackBay
    from tuba.patches import ModelTransaction
    from tuba.placements import PlacementAssignment, PlacementFrame

    model = Model(project_name="Semantic records")
    model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    model.add_rectangular_section("RackSec", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
    model.add_insulation_spec("mw_50", material="mineral_wool", thickness_m=0.05, density_kg_m3=100.0, cost_per_m=20.0)
    rack = RackBay(
        name="rack_A", origin=(0.0, -0.5, 0.0), length=4.0, width=1.0, height=3.0, levels=(1.5, 3.0),
        section="RackSec", material="Steel", zone="north",
    )
    ModelTransaction(model).apply(rack.to_patch())
    with model.pipe(section="DN100", material="Steel") as pipe:
        pipe.start([0.0, 0.0, 1.5], support="anchor")
        pipe.run(4.0)
        pipe.end(support="rest")
    created = [element.id for element in model.elements if element.section == "DN100"]
    model.groups["line_A"] = {"name": "line_A", "elements": created, "fragment": "shoe"}
    model.assign_insulation("group:line_A", "mw_50")
    node = model.elements[-1].n2
    model.define_tee(node, type="reinforced_tee", pad_thickness=0.01)
    model.add_obstacle(id="vessel", type="mesh", file_path="vessel.stl", position=[1.0, 2.0, 3.0])
    model.add_placement_frame(
        PlacementFrame(id="skid_frame", origin=(1.0, 2.0, 0.0), frame_type="skid", metadata={"tag": "S-1"})
    )
    model.assign_placement(
        PlacementAssignment(target=f"element:{created[0]}", frame="placement_frame:skid_frame", source="test")
    )
    model.specs["paint"] = {"epoxy": {"microns": 250, "colour": "RAL 7035"}}
    model.assign_attribute(f"element:{created[0]}", "paint", "epoxy", source="test", metadata={"coats": 2})
    hot = model.define_operation(
        "Hot", pressure=1.0e6, temperature=150.0, metadata={"source": "test"},
        fields=[{"quantity": "temperature", "value": 180, "group": "line_A"}],
    )
    hot.add_nodal_force(node, [0.0, 0.0, -100.0])
    model.define_load_case("Cold", temperature=20.0).add_nodal_force(node, force=[1.0, 2.0, 3.0], moment=[0.0, 0.0, 4.0])

    assert same_model(model, _rebuild(generate_model_script(model)))


def test_a_generated_script_keeps_an_empty_insulation_spec_map():
    data = Model("Empty insulation").to_dict()
    data["specs"] = {"insulation": {}}
    model = TubaModel.from_dict(data)

    assert same_model(model, _rebuild(generate_model_script(model)))


def test_a_generated_script_keeps_a_numpy_boolean():
    model = Model("Numpy boolean")
    model.add_obstacle(id="box", type="cuboid", min_point=(0.0, 0.0, 0.0), max_point=(1.0, 1.0, 1.0))
    model.assign_attribute("obstacle:box", "movable", np.bool_(True))

    assert same_model(model, _rebuild(generate_model_script(model)))


def test_a_pipe_block_is_written_as_the_steps_that_built_it():
    namespace: dict = {"__name__": "generated_model_check"}
    exec(compile(_BUILDER, "authored.py", "exec"), namespace)
    model = namespace["model"]

    text = generate_model_script(model)

    assert _block(
        "start([0.0, 0.0, 0.0], support='anchor')",
        "run(4.0)",
        "bend(radius=0.3, angle=90.0, axis=[0.0, 0.0, 1.0])",
        "add_support(type='guide')",
        "run(2.0)",
        "end(support='anchor')",
    ) in text
    assert "model.add_node(" not in text and "model.add_element(" not in text
    assert same_model(model, _rebuild(text))
    single_calls = generate_model_script(model, pipe_runs=False)
    assert "with model.pipe(" not in single_calls
    assert same_model(model, _rebuild(single_calls))


def test_beams_and_cables_are_written_under_their_own_names():
    model = _sections_model("Members")
    model.add_ibeam_section("IPE100", "IPE100")
    model.add_cable_section("Guy", radius=0.006, pretension=500.0)
    with model.pipe(section="IPE100", material="Steel") as builder:
        builder.start([0.0, 0.0, 0.0]).beam(1.5, twist_angle=45.0)
    with model.pipe(section="Guy", material="Steel", route="G-1") as builder:
        builder.start([0.0, 0.0, 1.0])
        builder.set_direction([1.0, 0.0, -1.0])
        builder.cable(2.0)

    text = generate_model_script(model)

    assert _block("start([0.0, 0.0, 0.0])", "beam(1.5, twist_angle=45.0)", section="IPE100") in text
    assert _block(
        "start([0.0, 0.0, 1.0])", "set_direction([1.0, 0.0, -1.0])", "cable(2.0)", section="Guy", route="G-1"
    ) in text
    assert same_model(model, _rebuild(text))


def test_a_negative_zero_twist_is_written_rather_than_taken_for_the_default():
    model = _sections_model("Negative zero")
    model.add_ibeam_section("IPE100", "IPE100")
    with model.pipe(section="IPE100", material="Steel") as builder:
        builder.start([0.0, 0.0, 0.0]).beam(1.5, twist_angle=-0.0)

    assert _block("start([0.0, 0.0, 0.0])", "beam(1.5, twist_angle=-0.0)", section="IPE100") in generate_model_script(model)


def test_records_added_between_two_runs_stay_single_calls_in_creation_order():
    model = _line_model()
    patch = ModelPatch.from_dict(
        {
            "operations": [
                {"op": "add_node", "local_id": "far", "coords": [2.0, 3.0, 0.0]},
                {
                    "op": "add_element", "local_id": "link", "type": "pipe_straight",
                    "n1": "N1", "n2": "far", "section": "DN100", "material": "Steel",
                },
            ],
            "provenance": {"source": "test"},
        }
    )
    ModelTransaction(model).apply(patch, validate=False)
    with model.pipe(section="DN100", material="Steel") as builder:
        builder.start([2.0, 3.0, 0.0])  # snaps onto the patch's node
        builder.run(1.0)

    text = generate_model_script(model)
    lines = text.splitlines()
    first, second = [index for index, line in enumerate(lines) if line.startswith("with model.pipe(")]
    link = next(index for index, line in enumerate(lines) if line.startswith("model.add_element(id='pipe_str_1'"))

    assert first < lines.index("model.add_node([2.0, 3.0, 0.0])") < link < second
    assert same_model(model, _rebuild(text))


def test_a_model_call_inside_a_block_is_written_after_it():
    model = _sections_model("Foreign call")
    with model.pipe(section="DN100", material="Steel") as builder:
        builder.start([0.0, 0.0, 0.0])
        builder.run(2.0)
        model.add_support(node=builder.last_node_id, type="anchor")
        builder.run(1.0)

    text = generate_model_script(model)

    support = "model.add_support(node='N1', type='anchor', id='support_0')"
    assert _block("start([0.0, 0.0, 0.0])", "run(2.0)", "run(1.0)") + "\n" + support in text
    assert same_model(model, _rebuild(text))


def test_a_run_whose_records_are_interleaved_is_written_as_single_calls():
    model = _sections_model("Interleaved")
    with model.pipe(section="DN100", material="Steel") as builder:
        builder.start([0.0, 0.0, 0.0])
        builder.run(1.0)
        model.add_node([5.0, 5.0, 5.0])  # takes N2 between the run's own nodes
        builder.run(1.0)

    text = generate_model_script(model)

    assert "with model.pipe(" not in text
    assert same_model(model, _rebuild(text))


def test_a_run_with_its_own_up_vector_is_written_as_single_calls():
    model = _sections_model("Up vector")
    with model.pipe(section="DN100", material="Steel") as builder:
        builder.up_vector = np.array([0.0, 1.0, 0.0])
        builder.start([0.0, 0.0, 0.0])
        builder.run(1.0)
        builder.bend(radius=0.3, angle=90.0, plane="XY")

    text = generate_model_script(model)

    assert "with model.pipe(" not in text
    assert same_model(model, _rebuild(text))


def test_generated_elements_link_to_their_steps_and_supports_to_their_points(tmp_path: Path):
    namespace: dict = {"__name__": "__main__"}
    exec(compile(_BUILDER, "authored.py", "exec"), namespace)
    script = tmp_path / "model.py"
    script.write_text(generate_model_script(namespace["model"]), encoding="utf-8", newline="")

    rebuilt = run_model_script(script)["model"]
    lines = script.read_text(encoding="utf-8").splitlines()

    def step(record) -> str:
        return lines[record.source_line - 1].strip()

    assert {element.id: step(element) for element in rebuilt.elements} == {
        "pipe_str_0": "builder.run(4.0)",
        "pipe_bend_0": "builder.bend(radius=0.3, angle=90.0, axis=[0.0, 0.0, 1.0])",
        "pipe_str_1": "builder.run(2.0)",
    }
    assert {support.id: step(rebuilt.nodes[support.node]) for support in rebuilt.supports} == {
        "support_0": "builder.start([0.0, 0.0, 0.0], support='anchor')",
        "support_1": "builder.bend(radius=0.3, angle=90.0, axis=[0.0, 0.0, 1.0])",
        "support_2": "builder.run(2.0)",
    }


def test_a_byte_order_mark_does_not_hide_the_header():
    assert is_generated("\ufeff" + GENERATED_HEADER + "\n")
    assert not is_generated('from tuba import Model\n\nmodel = Model("Hand written")\n')


def test_node_ids_outside_the_add_node_sequence_are_refused():
    data = Model("Custom ids").to_dict()
    data["nodes"] = {"inlet": [0.0, 0.0, 0.0]}

    with pytest.raises(ValueError, match="N0"):
        generate_model_script(TubaModel.from_dict(data))


def test_out_of_order_node_ids_are_refused():
    data = Model("Swapped ids").to_dict()
    data["nodes"] = {"N1": [0.0, 0.0, 0.0], "N0": [1.0, 0.0, 0.0]}

    with pytest.raises(ValueError, match="N0"):
        generate_model_script(TubaModel.from_dict(data))


def test_a_value_without_an_exact_literal_is_refused():
    model = Model("Array bounds")
    model.add_obstacle(id="box", type="cuboid", min_point=np.array([0.0, 0.0, 0.0]), max_point=(1.0, 1.0, 1.0))

    with pytest.raises(TypeError, match="ndarray"):
        generate_model_script(model)


def _line_model() -> TubaModel:
    model = Model("Line")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    with model.pipe(section="DN100", material="Steel") as builder:
        builder.start([0.0, 0.0, 0.0], support="anchor")
        builder.run(2.0)
        builder.end(support="anchor")
    return model


def test_writing_a_new_script_writes_lf_text_that_rebuilds_the_model(tmp_path: Path):
    target = tmp_path / "project" / "model.py"
    model = _line_model()

    text = write_model_script(target, model, last_text=None)

    assert target.read_bytes() == text.encode("utf-8")
    assert b"\r\n" not in target.read_bytes()
    assert same_model(model, run_model_script(target)["model"])


def test_writing_refuses_a_script_that_changed_since_it_was_written(tmp_path: Path):
    target = tmp_path / "model.py"
    model = _line_model()
    text = write_model_script(target, model, last_text=None)
    assert write_model_script(target, model, last_text=text) == text
    edited = text + "# edited in the studio\n"
    target.write_text(edited, encoding="utf-8", newline="")

    with pytest.raises(ModelScriptChanged):
        write_model_script(target, model, last_text=text)
    assert target.read_text(encoding="utf-8") == edited


def test_writing_refuses_an_edit_saved_while_the_script_is_proved(tmp_path: Path, monkeypatch):
    import tuba.project.script as script_module

    target = tmp_path / "model.py"
    model = _line_model()
    text = write_model_script(target, model, last_text=None)
    edited = text + "# saved in the studio during the proof\n"
    real_same_model = script_module.same_model

    def save_then_compare(first: TubaModel, second: TubaModel) -> bool:
        target.write_text(edited, encoding="utf-8", newline="")
        return real_same_model(first, second)

    monkeypatch.setattr(script_module, "same_model", save_then_compare)

    with pytest.raises(ModelScriptChanged):
        write_model_script(target, model, last_text=text)
    assert target.read_text(encoding="utf-8") == edited


def test_writing_refuses_an_authored_script(tmp_path: Path):
    target = tmp_path / "model.py"
    authored = 'from tuba import Model\n\nmodel = Model("Hand written")\n'
    target.write_text(authored, encoding="utf-8")

    with pytest.raises(AuthoredModelScript):
        write_model_script(target, _line_model(), last_text=None)
    assert target.read_text(encoding="utf-8") == authored


def test_writing_refuses_a_script_that_does_not_rebuild_the_model(tmp_path: Path, monkeypatch):
    import tuba.project.script as script_module

    monkeypatch.setattr(
        script_module,
        "generate_model_script",
        lambda model, **_options: GENERATED_HEADER + "\nfrom tuba.model import TubaModel\nmodel = TubaModel(project_name='Other')\n",
    )
    target = tmp_path / "project" / "model.py"

    with pytest.raises(ValueError, match="does not rebuild"):
        write_model_script(target, _line_model(), last_text=None)
    assert not target.parent.exists()


def test_writing_falls_back_to_single_calls_when_the_blocks_do_not_rebuild_the_model(tmp_path: Path):
    target = tmp_path / "model.py"
    model = _line_model()
    model.pipe_runs[0].recipe.steps[1] = BuildStep(op="run", params={"length": 3.0})  # no longer what built N1

    text = write_model_script(target, model, last_text=None)

    assert "with model.pipe(" not in text
    assert same_model(model, run_model_script(target)["model"])


def test_a_run_built_from_integer_steps_keeps_its_block(tmp_path: Path):
    model = _sections_model("Integer steps")
    recipe = PipeRunRecipe(
        section="DN100",
        material="Steel",
        steps=[  # JSON numbers as an agent sends them to build_pipe_run
            BuildStep(op="start", params={"point": [0, 0, 0], "support": "anchor"}),
            BuildStep(op="run", params={"length": 2}),
            BuildStep(op="bend", params={"radius": 1, "angle": 90, "plane": "XY"}),
            BuildStep(op="add_support", params={"type": "guide", "direction": [0, 1, 0]}),
            BuildStep(op="run", params={"length": 3}),
        ],
    )
    recipe.build(model)
    target = tmp_path / "model.py"

    text = write_model_script(target, model, last_text=None)

    assert "with model.pipe(" in text
    assert "builder.add_support(type='guide', direction=[0, 1, 0])" in text
    assert same_model(model, run_model_script(target)["model"])
