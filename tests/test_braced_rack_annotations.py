"""Rack labels follow solved quantities, never remembered example numbers."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from tuba.project import load_project


PROJECT = Path(__file__).resolve().parents[1] / "examples" / "braced-rack-thermal-split"


def test_rack_labels_follow_results_and_require_finite_evidence():
    project = load_project(PROJECT)
    namespace = project.run_model()
    study = project.load_study()
    model = namespace["model"]
    shoe = next(s for s in model.supports if s.type == "rest" and s.attached_to)
    foot = next(s.node for s in model.supports if s.type == "anchor" and not s.attached_to)
    result = SimpleNamespace(
        node_displacements={node: [0.0] * 6 for node in model.nodes},
        node_reactions={node: [0.0] * 3 + [float("nan")] * 3 for node in model.nodes},
    )
    for scale in (1, 2):
        result.node_displacements[shoe.attached_to][0] = 0.002 * scale
        result.node_displacements[shoe.node][0] = 0.012 * scale
        result.node_reactions[foot][:3] = [3000.0 * scale, 4000.0 * scale, 0.0]
        scene = SimpleNamespace(objects=[], geometry_assets=[], layers=[])
        study._add_rack_labels(scene, namespace, result)
        labels = {obj.id: obj.name for obj in scene.objects}
        assert labels["label:label-rack-growth"] == f"Rack max |DX|: {2 * scale:.1f} mm"
        assert labels["label:label-pipe-slide"] == f"Max pipe/shoe relative |DX|: {10 * scale:.1f} mm"
        assert labels["label:label-braced-foot"] == f"Max end-bay ground reaction |F|: {5 * scale:.1f} kN"
    del result.node_displacements[shoe.attached_to]
    with pytest.raises(ValueError, match="Missing Code_Aster DX"):
        study._add_rack_labels(None, namespace, result)
    result.node_displacements[shoe.attached_to] = [float("nan")] * 6
    with pytest.raises(ValueError, match="Non-finite Code_Aster DX"):
        study._add_rack_labels(None, namespace, result)
    result.node_displacements[shoe.attached_to] = [0.0] * 6
    del result.node_reactions[foot]
    with pytest.raises(ValueError, match="Missing Code_Aster reaction FX/FY/FZ"):
        study._add_rack_labels(None, namespace, result)
    result.node_reactions[foot] = [0.0, float("nan"), 0.0]
    with pytest.raises(ValueError, match="Non-finite Code_Aster reaction FX/FY/FZ"):
        study._add_rack_labels(None, namespace, result)


def test_supplied_run_keeps_import_provenance_without_importing_twice(tmp_path, monkeypatch):
    from examples import code_aster_artifact_review as pipeline

    namespace = load_project(PROJECT).run_model()
    model = namespace["model"]
    evidence = PROJECT / "evidence" / "Operating"
    run = pipeline.solve_or_import(model, "Operating", tmp_path / "solver", artifact_dir=evidence)

    def duplicate_import(**kwargs):
        raise AssertionError("The supplied Code_Aster run must not be imported again.")

    monkeypatch.setattr(pipeline, "import_code_aster_artifacts", duplicate_import)
    for artifact_dir, expected in ((evidence, "provided_real_code_aster_artifacts"), (None, "solved_in_this_run")):
        # Fresh solve and evidence import return the same kind of run; its caller records which path supplied it.
        summary = pipeline.run_example(tmp_path / expected, model=model, run=run, artifact_dir=artifact_dir)
        assert summary["artifact_provenance"] == expected
