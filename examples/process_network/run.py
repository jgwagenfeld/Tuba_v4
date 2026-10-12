"""Retain bounded proposals evaluated by pandapipes and Code_Aster.

python -m examples.process_network.run --output D:/tuba-runs/Tuba_v4/new-circuit
Optional --proposals takes JSON edits from a person or LLM. No generated code
is executed and this example does not claim a controlled LLM benchmark.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import uuid

from tuba.project.study import StudySettings
from tuba.process.dexpi import MAX_XML_BYTES, import_dexpi_segment
from tuba.process.modelica import OpenModelicaBackend
from tuba.process.pandapipes import PandapipesBackend
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

DEXPI_PROPOSALS = [
    {"id": "dexpi-base", "parent_ids": [], "parameters": {"size": "larger", "offset_m": 1.0},
     "intent": "Evaluate the imported DN80 connection with an authored water-study route"},
    {"id": "dexpi-longer", "parent_ids": ["dexpi-base"], "parameters": {"size": "larger", "offset_m": 3.0},
     "intent": "Change physical routing while preserving imported DN80 connectivity"},
]
DEXPI_ASSUMPTIONS = {
    "boundary_conditions": "Cut at the two imported nozzles: prescribe 10 kg/s at 333.15 K and 300000 Pa absolute outlet pressure. Pump and heat-exchanger behavior and equipment loads are not modeled.",
    "physical_layout": "Authored L-101 offset route and two anchors; drawing coordinates are not physical positions. DN80 demonstration section OD=0.0889 m, WT=0.00549 m, illustrative steel and roughness=0.000046 m; piping class qualification is outside this study.",
    "fluid_service": "Explicit demonstration substitution: use constant-property water for the imported fluid code, including MNb in the reference. This does not reproduce the reference plant's original service.",
}
REFERENCE_XML_SHA256 = "acd39c74292aef3f6f00581fc78b05814acf2318815abd28c14ebefba12fdd94"
REFERENCE_ATTRIBUTION = (
    "DEXPI Initiative, DEXPI Specification 2.0.1 reference P&ID, unmodified. "
    "CC BY 4.0: https://creativecommons.org/licenses/by/4.0/ . Source: "
    "https://gitlab.com/dexpi/Specification/-/blob/eef0f0c6e8edfe84582e7a45d109c396bdc544f8/src/documentation/_static/reference_pid.xml"
)


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


def run(output, *, omc=None, proposals=None, dexpi=None, segment=None, backend=None):
    backend_name = backend or ("openmodelica" if omc is not None else "pandapipes")
    if backend_name not in {"pandapipes", "openmodelica"}:
        raise ValueError("backend must be pandapipes or openmodelica")
    if backend_name == "pandapipes" and omc is not None:
        raise ValueError("omc is only valid with the openmodelica backend")
    if (dexpi is None) != (segment is None):
        raise ValueError("Supply both dexpi XML and segment ID, or neither")
    imported = None
    if dexpi is not None:
        with Path(dexpi).open("rb") as stream:
            source_xml = stream.read(MAX_XML_BYTES + 1)
        attribution = REFERENCE_ATTRIBUTION if hashlib.sha256(source_xml).hexdigest() == REFERENCE_XML_SHA256 else None
        imported = import_dexpi_segment(source_xml, segment_id=segment, route_id="L-101",
            roughness_m=4.6e-5, bend_loss_coefficient=0.2,
            bend_loss_source="Demo assumption: excess zeta per authored bend",
            study_assumptions=DEXPI_ASSUMPTIONS, source_attribution=attribution)
        source_data = imported.to_dict()["source_data"]
        tags = source_data[segment]["tags"]
        if tags.get("NominalDiameterRepresentation", {}).get("value") != "DN 80":
            raise ValueError("This example requires an imported DN 80 segment; author other sections explicitly")
        expected_dn = {"NominalDiameterRepresentation": "DN 80",
                       "NominalDiameterNumericalValueRepresentation": "80",
                       "NominalDiameterTypeRepresentation": "DN"}
        for ident, source in source_data.items():
            for tag, expected in expected_dn.items():
                if tag in source["tags"] and source["tags"][tag]["value"] != expected:
                    raise ValueError(f"Conflicting DN80 metadata: {ident}.{tag}")
    if proposals is None:
        proposals = DEXPI_PROPOSALS if imported is not None else DEFAULT_PROPOSALS
    if not isinstance(proposals, list) or not 1 <= len(proposals) <= 10:
        raise ValueError("Supply one to ten bounded proposal records")
    candidates = [Candidate.from_dict(record) for record in proposals]
    seen, models = set(), []
    for candidate in candidates:
        if candidate.id in seen or not set(candidate.parent_ids) <= seen:
            raise ValueError("Proposal IDs must be unique and parents must precede children")
        seen.add(candidate.id)
        if imported is not None and candidate.parameters.get("size") != "larger":
            raise ValueError("The imported DN80 example permits only size='larger'; changing P&ID nominal size requires a declared design revision")
        models.append(build_model(candidate.parameters))
    bounds = [process_inputs(model, network=imported.network if imported else None) for model in models]
    root = Path(output).absolute()
    no_links(root)
    if root.exists():
        raise FileExistsError("Choose a new output directory to retain prior attempts")
    if root.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError("Generated results must be outside the source checkout")
    archive = ArtifactStore(root)
    source_ref = archive.capture_files(Path(__file__).parent, ("model.py", "run.py"))
    settings = StudySettings(("WaterOperating",), {"pipe_modelization": "TUYAU_3M"}, None)
    base_bound = bounds[0]
    base_checks = (*hydraulic_check_specs(base_bound), *structural_checks(models[0], settings.operations[0]))
    manifest = {
        "schema": "tuba.search.history.v1", "run_id": "R" + uuid.uuid4().hex,
        "source_manifest_ref": source_ref, "source_digest": archive.read_inventory(source_ref)["digest"],
        "check_digest": digest([spec.to_dict() for spec in base_checks]),
        "settings": {"operations": settings.operations, "solver_options": settings.solver_options, "volume_export": None},
        "check_specs": [spec.to_dict() for spec in base_checks],
        "definition": {"policy": "bounded supplied proposals", "proposal_limit": 10,
                       "hydraulic_backend": backend_name,
                       "process_source": "DEXPI 2.0.1 selected segment" if imported else "authored graph"},
        "scope": "Steady serial water; pressure/temperature/contents loads. Demo losses and limits; no piping-code compliance or flow-induced-stress qualification.",
    }
    rows = []
    hydraulic_backend = PandapipesBackend() if backend_name == "pandapipes" else OpenModelicaBackend(omc=omc)
    with History.create(archive.path("history.sqlite3"), manifest) as history:
        for candidate, model, bound in zip(candidates, models, bounds, strict=True):
            history.record_candidate(candidate)
            evaluation, decision = evaluate_process_candidate(candidate, model, bound,
                backend=hydraulic_backend, archive=archive, history=history, settings=settings,
                structural_checks=structural_checks(model, settings.operations[0]),
                wall_temperature_model=WALL_TEMPERATURE_MODEL, process_import=imported)
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
    parser.add_argument("--backend", choices=("pandapipes", "openmodelica"),
                        help="Default: pandapipes; supplying --omc selects openmodelica")
    parser.add_argument("--proposals", type=Path)
    parser.add_argument("--dexpi", type=Path, help="DEXPI 2.0.1 XML containing a supported DN80 pipe segment")
    parser.add_argument("--segment", help="Exact source PipingNetworkSegment ID; requires --dexpi")
    args = parser.parse_args()
    proposals = json.loads(args.proposals.read_text(encoding="utf-8")) if args.proposals else None
    print(run(args.output, omc=args.omc, proposals=proposals, dexpi=args.dexpi, segment=args.segment,
              backend=args.backend))


if __name__ == "__main__":
    main()
