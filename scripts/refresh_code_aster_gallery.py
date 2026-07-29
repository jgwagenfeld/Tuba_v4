"""Refresh the canonical gallery with a real, attested Code_Aster solve."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from examples.code_aster_artifact_review import build_model
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.solver.aster import CodeAsterSolver


_REQUIRED_RESULT_FILES = (
    "study.rmed",
    "study_depl.csv",
    "study_effo.csv",
    "study_reac.csv",
    "study_sieq.csv",
    "study_execution.json",
)


def refresh_gallery(output: str | Path) -> Any:
    """Export, solve, import, and verify one canonical operating gallery."""
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    model = build_model()
    solver = CodeAsterSolver(work_dir=output_path)
    study = solver.export_analysis_study(model, "Operating", output_path)
    solver.solve_exported_study(model, study)
    artifact = import_code_aster_artifacts(model=model, work_dir=output_path, study=study)
    _validate_gallery_artifact_chain(output_path, artifact)
    return artifact


def _validate_gallery_artifact_chain(output: Path, artifact: Any) -> None:
    for filename in _REQUIRED_RESULT_FILES:
        if not (output / filename).is_file():
            raise ValueError(f"Canonical Code_Aster gallery is missing required artifact {filename}.")

    identities = (
        artifact.study.solver_input_identity,
        None if artifact.analysis_mesh is None else artifact.analysis_mesh.solver_input_identity,
        artifact.result_state.solver_input_identity,
    )
    fingerprints = [_fingerprint(identity) for identity in identities]
    if any(fingerprint is None for fingerprint in fingerprints) or len(set(fingerprints)) != 1:
        raise ValueError("Canonical Code_Aster gallery requires one matching non-null solver input identity.")

    attestation = artifact.result_state.metadata.get("solve_attestation")
    if not isinstance(attestation, dict):
        raise ValueError("Canonical Code_Aster gallery requires a validated solve attestation.")
    if not isinstance(attestation.get("solver_version"), str) or not attestation["solver_version"]:
        raise ValueError("Canonical Code_Aster gallery attestation requires solver_version.")
    if attestation.get("execution_method") != "wsl":
        raise ValueError("Canonical Code_Aster gallery attestation execution_method must be wsl.")
    if attestation.get("solver_name") != "Code_Aster":
        raise ValueError("Canonical Code_Aster gallery attestation must name Code_Aster.")
    if not isinstance(attestation.get("solved_at"), str) or not attestation["solved_at"]:
        raise ValueError("Canonical Code_Aster gallery attestation requires solved_at.")
    if _fingerprint_from_attestation(attestation) != fingerprints[0]:
        raise ValueError("Canonical Code_Aster gallery attestation identity does not match the imported artifacts.")


def _fingerprint(identity: Any) -> str | None:
    fingerprint = getattr(identity, "fingerprint", None)
    return fingerprint if isinstance(fingerprint, str) and fingerprint else None


def _fingerprint_from_attestation(attestation: dict[str, Any]) -> str | None:
    identity = attestation.get("solver_input_identity")
    fingerprint = identity.get("fingerprint") if isinstance(identity, dict) else None
    return fingerprint if isinstance(fingerprint, str) and fingerprint else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Canonical Code_Aster gallery directory")
    args = parser.parse_args()
    artifact = refresh_gallery(args.output)
    attestation = artifact.result_state.metadata["solve_attestation"]
    print(
        f"Refreshed Code_Aster gallery at {args.output} "
        f"({attestation['execution_method']} Code_Aster {attestation['solver_version']}, "
        f"{attestation['solved_at']})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
