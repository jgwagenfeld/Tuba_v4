from examples import code_aster_artifact_review as gallery


def test_support_rack_gallery_model_has_a_semantic_rack_and_supported_pipe():
    builder = getattr(gallery, "build_support_rack_model", None)
    assert callable(builder)

    model = builder()

    assert model.project_name == "SupportRackReview"
    assert model.groups["rack_A"]["metadata"]["assembly_type"] == "rack_bay"
    assert any(element.type == "beam" for element in model.elements)
    assert any(element.type.startswith("pipe") for element in model.elements)
    assert {support.type for support in model.supports} >= {"anchor", "rest"}


def test_autorouted_gallery_model_preserves_the_selected_route_for_review(tmp_path):
    builder = getattr(gallery, "build_autorouted_expansion_model", None)
    assert callable(builder)

    model, route_result = builder(tmp_path)

    assert model.project_name == "HotLineExpansionLoop"
    assert route_result.selected is not None
    assert route_result.selected.metadata["route_family"] == "u_loop"
    assert all("solver" not in candidate.metadata for candidate in route_result.candidates)
    assert any(element.route_id == "HOT-EXP-100" for element in model.elements)
    assert sum(support.type == "anchor" for support in model.supports) == 2
