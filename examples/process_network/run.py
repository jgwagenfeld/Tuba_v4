"""Retain bounded proposals evaluated by real OpenModelica and Code_Aster.

python -m examples.process_network.run --output D:/tuba-runs/Tuba_v4/new-circuit
Optional --proposals takes JSON edits from a person or LLM. No generated code
is executed and this example does not claim a controlled LLM benchmark.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import uuid

from tuba.project.study import StudySettings
from tuba.process.modelica import OpenModelicaBackend
from tuba.process.structural import WALL_TEMPERATURE_MODEL
from tuba.process.workflow import evaluate_process_candidate, hydraulic_check_specs
from tuba.search.artifacts import ArtifactStore, atomic_json, no_links
from tuba.search.contracts import Candidate, CheckSpec
from tuba.search.history import History
from tuba.search.replay import write_search_replay
from tuba.search.run import digest, storage_report

from .model import build_model, process_inputs

DEFAULT_PROPOSALS = [
    {"id": "small-bore", "parent_ids": [], "parameters": {"size": "small", "offset_m": 1.0},
     "intent": "Test smaller bore for required 10 kg/s delivery and 3 m/s limit"},
    {"id": "larger-bore", "parent_ids": ["small-bore"], "parameters": {"size": "larger", "offset_m": 1.0},
     "intent": "Increase bore with unchanged process connectivity and endpoint positions"},
    {"id": "longer-offset", "parent_ids": ["larger-bore"], "parameters": {"size": "larger", "offset_m": 3.0},
     "intent": "Measure pressure-loss and flexibility effects of a longer offset"},
]


def structural_checks(model, operation):
    """Illustrative envelope checks, not a piping-standard assessment."""
    return (
        CheckSpec("cold.model", "cold_model", True, (), (), None, None, {}),
        CheckSpec("cold.clearance", "cold_clearance", True, (), (), None, None, {"clearance_m": 0.01}),
        CheckSpec(f"evidence.{operation}", "evidence_verified", True, (operation,), (), None, None, {}),
        CheckSpec("supports.force", "reaction_force", True, (operation,),
                  tuple(f"node:{support.node}" for support in model.supports), 20_000.0, "N", {}),
        CheckSpec("pipe.displacement", "displacement", True, (operation,),
                  tuple(f"node:{node}" for node in model.nodes), 0.05, "m", {}),
        CheckSpec("operating.clearance", "operating_clearance", True, (operation,), (), None, None,
                  {"clearance_m": 0.01, "envelope_type": "bare"}),
    )


def run(output, *, omc=None, proposals=None):
    proposals = DEFAULT_PROPOSALS if proposals is None else proposals
    if not isinstance(proposals, list) or not 1 <= len(proposals) <= 10:
        raise ValueError("Supply one to ten bounded proposal records")
    candidates = [Candidate.from_dict(record) for record in proposals]
    seen, models = set(), []
    for candidate in candidates:
        if candidate.id in seen or not set(candidate.parent_ids) <= seen:
            raise ValueError("Proposal IDs must be unique and parents must precede children")
        seen.add(candidate.id)
        models.append(build_model(candidate.parameters))
    root = Path(output).absolute()
    no_links(root)
    if root.exists():
        raise FileExistsError("Choose a new output directory to retain prior attempts")
    if root.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError("Generated results must be outside the source checkout")
    archive = ArtifactStore(root)
    source_ref = archive.capture_files(Path(__file__).parent, ("model.py", "run.py"))
    settings = StudySettings(("WaterOperating",), {"pipe_modelization": "TUYAU_3M"}, None)
    base_bound = process_inputs(models[0])
    base_checks = (*hydraulic_check_specs(base_bound), *structural_checks(models[0], settings.operations[0]))
    manifest = {
        "schema": "tuba.search.history.v1", "run_id": "R" + uuid.uuid4().hex,
        "source_manifest_ref": source_ref, "source_digest": archive.read_inventory(source_ref)["digest"],
        "check_digest": digest([spec.to_dict() for spec in base_checks]),
        "settings": {"operations": settings.operations, "solver_options": settings.solver_options, "volume_export": None},
        "check_specs": [spec.to_dict() for spec in base_checks],
        "definition": {"policy": "bounded supplied proposals", "proposal_limit": 10},
        "scope": "Steady serial water; pressure/temperature/contents loads. Demo losses and limits; no piping-code compliance or flow-induced-stress qualification.",
    }
    rows, backend = [], OpenModelicaBackend(omc=omc)
    with History.create(archive.path("history.sqlite3"), manifest) as history:
        for candidate, model in zip(candidates, models, strict=True):
            history.record_candidate(candidate)
            bound = process_inputs(model)
            evaluation, decision = evaluate_process_candidate(candidate, model, bound,
                backend=backend, archive=archive, history=history, settings=settings,
                structural_checks=structural_checks(model, settings.operations[0]),
                wall_temperature_model=WALL_TEMPERATURE_MODEL)
            rows.append({"candidate_id": candidate.id, "decision": decision.to_dict(),
                         "evaluation": evaluation.to_dict()})
            print(f"{candidate.id}: {decision.outcome}", flush=True)
            if evaluation.error_kind:
                break
        summary = {"candidates": rows, **storage_report(archive)}
        history.append("run.completed", {"candidate_count": len(rows),
                       "blocked": any(row["evaluation"]["error_kind"] for row in rows)})
    atomic_json(root / "summary.json", summary)
    write_search_replay(root, root / "replay")
    if any(row["evaluation"]["error_kind"] for row in rows):
        raise RuntimeError(f"Coupled evaluation failed; retained diagnostics in {root}")
    return root / "replay" / "search_replay.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--omc", type=Path)
    parser.add_argument("--proposals", type=Path)
    args = parser.parse_args()
    proposals = json.loads(args.proposals.read_text(encoding="utf-8")) if args.proposals else None
    print(run(args.output, omc=args.omc, proposals=proposals))


if __name__ == "__main__":
    main()
