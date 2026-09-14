from pathlib import Path

from tuba.model import IBeamSection
from tuba.project import load_project

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _run(project: str) -> dict:
    return load_project(EXAMPLES / project).run_model()


def test_support_rack_gallery_model_has_a_semantic_rack_and_supported_pipe():
    model = _run("support-rack-review")["model"]

    assert model.project_name == "SupportRackReview"
    assert model.groups["rack_A"]["metadata"]["assembly_type"] == "rack_bay"
    assert any(element.type == "beam" for element in model.elements)
    assert any(element.type.startswith("pipe") for element in model.elements)
    assert {support.type for support in model.supports} >= {"anchor", "rest"}


def test_support_rack_gallery_uses_ibeams_for_every_structural_member():
    model = _run("support-rack-review")["model"]

    beam_sections = {element.section for element in model.elements if element.type == "beam"}
    pipe_sections = {element.section for element in model.elements if element.type.startswith("pipe")}

    assert beam_sections == {"RackColumnIPE", "RackLongIPE", "RackCrossIPE"}
    assert all(isinstance(model.sections[name], IBeamSection) for name in beam_sections)
    assert pipe_sections == {"DN100"}


def test_autorouted_gallery_model_preserves_the_selected_route_for_review():
    namespace = _run("autorouted-expansion-loop")
    model, route_result = namespace["model"], namespace["route_result"]

    assert model.project_name == "HotLineExpansionLoop"
    assert route_result.selected is not None
    assert route_result.selected.metadata["route_family"] == "u_loop"
    assert all("solver" not in candidate.metadata for candidate in route_result.candidates)
    assert any(element.route_id == "HOT-EXP-100" for element in model.elements)
    assert sum(support.type == "anchor" for support in model.supports) == 2
