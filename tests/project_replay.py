"""A solver port for tests that replays committed real Code_Aster evidence (spec Testing).

No result is made up. The replay answers an exported study with the committed run that attests exactly
its solver input, and the import re-hashes every attested file, so an export that drifted from that run
fails loudly.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts


class ReplaySolver:
    """Solve by copying the committed run whose attested solver input identity matches the study.

    *evidence_roots* are searched for ``study_execution.json``. *execution_method*, when given, relabels
    the copied attestation, so ``"docker"`` turns real results into an unverified run. ``solved`` lists
    the operations this solver was asked to solve.
    """

    def __init__(self, *evidence_roots: Path, execution_method: str | None = None) -> None:
        self.runs = [path.parent for root in evidence_roots for path in sorted(Path(root).rglob("study_execution.json"))]
        self.execution_method = execution_method
        self.solved: list[str] = []

    def solve_exported_study(self, model, study):
        work = Path(study.work_dir)
        identity = study.solver_input_identity.to_dict()
        for folder in self.runs:
            attestation = json.loads((folder / "study_execution.json").read_text(encoding="utf-8"))
            if attestation["solver_input_identity"] != identity:
                continue
            for name in attestation["artifacts"]:
                if not (work / name).exists():
                    shutil.copy2(folder / name, work / name)
            if self.execution_method is None:
                shutil.copy2(folder / "study_execution.json", work / "study_execution.json")
            else:
                attestation["execution_method"] = self.execution_method
                (work / "study_execution.json").write_text(json.dumps(attestation, indent=2, sort_keys=True), encoding="utf-8")
            self.solved.append(study.load_case)
            return import_code_aster_artifacts(model=model, work_dir=work, study=study)
        raise LookupError(f"No committed evidence attests solver input {identity['fingerprint']}.")
