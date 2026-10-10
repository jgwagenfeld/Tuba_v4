from pathlib import Path
import textwrap

import pytest

from tests.project_replay import ReplaySolver
from tuba.project import load_project
from tuba.search.contracts import SearchDefinition
from tuba.search.history import History
from tuba.search.run import grid_parameters, load_search, run_search

RACK = Path(__file__).resolve().parents[1] / "examples/support-rack-review"


def author(tmp_path, *, values=(100.0, 101.0), budget=2, limit=None, options="{}", name="project"):
    root = tmp_path / name
    root.mkdir()
    original = (RACK / "model.py").read_text(encoding="utf-8")
    source = "def build_model(parameters):\n" + textwrap.indent(original, "    ")
    source += '\n    model.add_obstacle(id="equipment", type="cuboid", min_point=(0, parameters["y"], 0), max_point=(1, parameters["y"]+1, 1))\n    return model\n\nmodel = build_model({"y": 100.0})\n'
    (root / "model.py").write_text(source, encoding="utf-8")
    study = f'LOAD_CASES = ("Operating",)\nSOLVER_OPTIONS = {options}\n'
    if limit is not None:
        node = load_project(RACK).run_model()["model"].supports[0].node
        study += f'from tuba.search.contracts import CheckSpec\nSEARCH_CHECKS = (CheckSpec("anchor.force", "reaction_force", True, ("Operating",), ("node:{node}",), {limit!r}, "N", {{}}),)\n'
    (root / "study.py").write_text(study, encoding="utf-8")
    (root / "search.py").write_text('from tuba.search.contracts import SearchDefinition\n'
         f'SEARCH = SearchDefinition({{"y": {values!r}}}, ("pipe_length_m", "bend_count", "support_count"), {len(values)}, {budget})\n', encoding="utf-8")
    return root


def read(run):
    with History.open(run / "history.sqlite3", readonly=True) as h:
        return h.manifest(), h.events(), h.candidates()


def test_grid_order_is_stable_and_bounded():
    definition = SearchDefinition({"width_m": (2.0, 3.0), "depth_m": (0.8, 1.0)},
                                  ("pipe_length_m", "bend_count", "support_count"), 4, 8)
    assert grid_parameters(definition) == [{"depth_m": d, "width_m": w} for d in (0.8, 1.0) for w in (2.0, 3.0)]
    with pytest.raises(ValueError, match="candidate_limit"):
        grid_parameters(SearchDefinition(definition.parameter_grid, definition.objective_fields, 3, 8))


def test_run_reuses_exact_operations_and_selects_by_stable_objectives(tmp_path):
    project = author(tmp_path)
    before = {p.name: p.read_bytes() for p in project.iterdir()}
    replay = ReplaySolver(RACK / "evidence")
    run = tmp_path / "run"
    result = run_search(project, run, solver=replay)
    assert result["selected_candidate_id"] == "C0001"
    assert result["solver_calls"] == 1 and replay.solved == ["Operating"]
    _, events, candidates = read(run)
    assert len(candidates) == 2
    assert any(e["kind"] == "operation.reused" for e in events)
    assert [e["payload"]["outcome"] for e in events if e["kind"] == "candidate.decision"][-2:] == ["selected", "feasible_not_selected"]
    built = [e["payload"] for e in events if e["kind"] == "candidate.built"]
    assert built[0]["design_digest"] != built[1]["design_digest"]
    assert built[0]["solver_identities"] == built[1]["solver_identities"]
    assert {p.name: p.read_bytes() for p in project.iterdir()} == before
    assert run_search(project, run, resume=True, solver=replay)["solver_calls"] == 1


def test_duplicate_proposal_is_recorded_without_erasing_origin(tmp_path):
    project = author(tmp_path, values=(100.0, 100.0))
    run = tmp_path / "run"
    run_search(project, run, solver=ReplaySolver(RACK / "evidence"))
    _, events, candidates = read(run)
    assert len(candidates) == 2
    decision = next(e["payload"] for e in events if e["kind"] == "candidate.decision" and e["candidate_id"] == "C0002")
    assert decision["outcome"] == "duplicate"
    assert decision["comparison_ids"] == ["C0001"]


def test_budget_registers_all_proposals_and_defers_unexecuted(tmp_path):
    project = author(tmp_path, budget=0)
    run = tmp_path / "run"
    result = run_search(project, run, solver=ReplaySolver(RACK / "evidence"))
    assert result["selected_candidate_id"] is None and result["solver_calls"] == 0
    _, events, candidates = read(run)
    assert len(candidates) == 2
    assert all(e["payload"]["outcome"] == "deferred" for e in events if e["kind"] == "candidate.decision")


def test_failed_calls_count_and_cannot_be_reused(tmp_path):
    project = author(tmp_path, budget=1)
    run = tmp_path / "run"
    class Fail:
        def solve_exported_study(self, model, study):
            raise ValueError("solver failed")
    result = run_search(project, run, solver=Fail())
    assert result["solver_calls"] == 1 and result["selected_candidate_id"] is None
    outcomes = [e["payload"]["outcome"] for e in read(run)[1] if e["kind"] == "candidate.decision"]
    assert outcomes == ["evaluation_failed", "deferred"]


def test_resume_refuses_changed_source_and_parent_run_rechecks_new_policy(tmp_path):
    project = author(tmp_path, values=(100.0,), limit=1e9)
    old = tmp_path / "old"
    run_search(project, old, solver=ReplaySolver(RACK / "evidence"))
    study = project / "study.py"
    study.write_text(study.read_text().replace("1000000000.0", "0.0"))
    before = {p.relative_to(old): p.read_bytes() for p in old.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="source|configuration"):
        run_search(project, old, resume=True)
    assert before == {p.relative_to(old): p.read_bytes() for p in old.rglob("*") if p.is_file()}
    new = tmp_path / "new"
    result = run_search(project, new, parent_run_dir=old, solver=ReplaySolver(RACK / "evidence"))
    assert result["solver_calls"] == 0 and result["selected_candidate_id"] is None
    old_manifest, _, _ = read(old)
    new_manifest, events, _ = read(new)
    assert new_manifest["parent_run_id"] == old_manifest["run_id"]
    assert new_manifest["check_digest"] != old_manifest["check_digest"]
    assert any(e["kind"] == "candidate.decision" and e["payload"]["outcome"] == "rejected_constraint" for e in events)


def test_resume_preserves_interruption_and_uses_a_new_attempt(tmp_path):
    project = author(tmp_path, values=(100.0,))
    run = tmp_path / "run"
    class Cancel:
        def solve_exported_study(self, model, study):
            raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        run_search(project, run, solver=Cancel())
    result = run_search(project, run, resume=True, solver=ReplaySolver(RACK / "evidence"))
    assert result["selected_candidate_id"] == "C0001"
    attempts = [e["payload"]["attempt_id"] for e in read(run)[1] if e["kind"] == "evaluation.started"]
    assert len(set(attempts)) == 2


def test_resume_retries_runtime_blocked_candidate_without_erasing_failure(tmp_path):
    project = author(tmp_path, values=(100.0,), budget=2)
    run = tmp_path / "run"
    class Unavailable:
        def solve_exported_study(self, model, study):
            raise RuntimeError("Code_Aster runtime unavailable")
    blocked = run_search(project, run, solver=Unavailable())
    assert blocked["blocked"] and blocked["solver_calls"] == 1
    result = run_search(project, run, resume=True, solver=ReplaySolver(RACK / "evidence"))
    assert result["selected_candidate_id"] == "C0001" and result["solver_calls"] == 2
    events = read(run)[1]
    assert any(e["kind"] == "evaluation.failed" for e in events)
    attempts = [e["payload"]["attempt_id"] for e in events if e["kind"] == "evaluation.started"]
    assert len(set(attempts)) == 2


def test_missing_required_evaluator_cannot_be_selected(tmp_path):
    project = author(tmp_path, values=(100.0,))
    study = project / "study.py"
    study.write_text(study.read_text() + 'from tuba.search.contracts import CheckSpec\nSEARCH_CHECKS = (CheckSpec("code.required", "user_evaluator", True, ("Operating",), (), None, None, {}),)\n')
    result = run_search(project, tmp_path / "run", solver=ReplaySolver(RACK / "evidence"))
    assert result["selected_candidate_id"] is None


def test_source_paths_cannot_hold_the_run_archive(tmp_path):
    project = author(tmp_path)
    with pytest.raises(ValueError, match="outside"):
        run_search(project, project / "run")


def test_byte_budget_stops_and_reports_actual_retained_storage(tmp_path):
    project = author(tmp_path)
    search = project / "search.py"
    search.write_text(search.read_text().replace(", 2, 2)", ", 2, 2, max_artifact_bytes=1)"))
    result = run_search(project, tmp_path / "run")
    assert result["blocked"] and result["retained_bytes"] > 1 and result["free_bytes"] >= 0


@pytest.mark.parametrize("change", ["mesh", "support", "operation"])
def test_solver_input_changes_require_a_fresh_call(tmp_path, change):
    project = author(tmp_path, values=(100.0,))
    parent = tmp_path / "parent"
    run_search(project, parent, solver=ReplaySolver(RACK / "evidence"))
    if change == "mesh":
        path = project / "study.py"
        path.write_text(path.read_text().replace("SOLVER_OPTIONS = {}", 'SOLVER_OPTIONS = {"line_segments": 4}'))
    elif change == "support":
        path = project / "model.py"
        path.write_text(path.read_text().replace("    return model", '    model.supports[0].type = "rest"\n    return model'))
    else:
        path = project / "model.py"
        path.write_text(path.read_text().replace("    return model", '    model.define_load_case("Other", gravity=False)\n    return model'))
        path = project / "study.py"
        path.write_text(path.read_text().replace('("Operating",)', '("Other",)'))
    result = run_search(project, tmp_path / "new", parent_run_dir=parent, solver=ReplaySolver(RACK / "evidence"))
    assert result["solver_calls"] == 1
    assert result["selected_candidate_id"] is None


def test_reimport_failure_is_recorded_without_returning_cached_metrics(tmp_path, monkeypatch):
    project = author(tmp_path)
    import tuba.search.run as run_module
    def fail_import(**kwargs):
        raise ValueError("reimport failed")
    monkeypatch.setattr(run_module, "import_code_aster_artifacts", fail_import)
    root = tmp_path / "run"
    result = run_search(project, root, solver=ReplaySolver(RACK / "evidence"))
    assert result["selected_candidate_id"] == "C0001"
    outcomes = [e["payload"]["outcome"] for e in read(root)[1] if e["kind"] == "candidate.decision" and e["candidate_id"] == "C0002"]
    assert outcomes == ["evaluation_failed"]


def test_missing_objective_is_visible_and_never_selected(tmp_path, monkeypatch):
    project = author(tmp_path, values=(100.0,))
    import tuba.search.run as run_module
    def fail_objective(*args):
        raise ValueError("objective unavailable")
    monkeypatch.setattr(run_module, "objective_values", fail_objective)
    result = run_search(project, tmp_path / "run")
    assert result["selected_candidate_id"] is None and result["solver_calls"] == 0
    assert "objective unavailable" in str(read(tmp_path / "run")[1])


def test_benchmark_shoes_hold_lateral_and_vertical_motion():
    project = load_project(RACK.parent / "piping-search")
    loaded = load_search(project)
    model = loaded.build_candidate({"width_m": 2.4, "depth_m": 1.8, "guide_layout": "end_guides"})
    shoes = [support for support in model.supports if support.type == "custom"]
    assert len(shoes) == 2
    assert all(s.restraint().states[:3] == ("free", "fixed", "fixed") for s in shoes)
    assert len(loaded.settings.operations) == 2


@pytest.mark.parametrize("mode", ["deduplicate", "unrelated_identity"])
def test_cache_indexes_native_identity_before_reading_evidence(tmp_path, monkeypatch, mode):
    from tuba.project.freshness import expected_identity
    from tuba.search.artifacts import ArtifactStore
    from tuba.search.run import EvidenceCache
    project = author(tmp_path, values=(100.0,))
    root = tmp_path / "run"
    run_search(project, root, solver=ReplaySolver(RACK / "evidence"))
    archive = ArtifactStore(root)
    with History.open(root / "history.sqlite3", readonly=True) as history:
        cache = EvidenceCache(archive, history)
        cache.collect(archive, history)
        if mode == "deduplicate":
            cache.collect(archive, history)
            assert len(cache.entries) == 1
        else:
            model = load_project(project).run_model()["model"]
            identity = expected_identity(model, "Operating", solver_options={"line_segments": 4})
            reads = []
            original = archive.verify_inventory
            def verify(ref):
                reads.append(ref)
                return original(ref)
            monkeypatch.setattr(archive, "verify_inventory", verify)
            assert cache.find(identity) is None
            assert reads == []
