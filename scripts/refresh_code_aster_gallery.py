"""Refresh the canonical gallery with a real, attested Code_Aster solve."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from examples.code_aster_artifact_review import (
    build_autorouted_expansion_model,
    build_model,
    build_support_rack_model,
)
from examples.code_aster_tee_volume_review import (
    TEE_VOLUME_ELEMENT_IDS,
    TEE_VOLUME_MAX_ELEMENT_SIZE,
    build_tee_volume_model,
)
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.solver.aster import CodeAsterSolver


_SOLVER_OUTPUT_FILES = (
    "study.mess",
    "study.rmed",
    "study_depl.csv",
    "study_effo.csv",
    "study_reac.csv",
    "study_sieq.csv",
    "study_execution.json",
)
_VOLUME_SOLVER_OUTPUT_FILES = (
    "study.mess",
    "study.rmed",
    "study_depl.csv",
    "study_reac.csv",
    "study_sieq.csv",
    "study_execution.json",
)


def build_gallery_model(gallery: str, scratch_root: str | Path) -> tuple[Any, str]:
    if gallery == "code-aster-review":
        return build_model(), "Operating"
    if gallery == "support-rack-review":
        return build_support_rack_model(), "Operating"
    if gallery == "autorouted-expansion-loop":
        model, _route_result = build_autorouted_expansion_model(Path(scratch_root) / "routing")
        return model, "Hot"
    if gallery == "pipe-tee-volume-review":
        return build_tee_volume_model(), "Operating"
    raise ValueError(f"Unknown official engineering gallery {gallery!r}.")


def refresh_gallery(output: str | Path, *, gallery: str = "code-aster-review") -> Any:
    """Export, solve, import, and verify one canonical operating gallery."""
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="tuba-gallery-routing-") as scratch:
        model, load_case = build_gallery_model(gallery, scratch)
    solver = CodeAsterSolver(work_dir=output_path)
    study = (
        solver.export_volume_study(
            model,
            load_case,
            output_path,
            element_ids=TEE_VOLUME_ELEMENT_IDS,
            max_element_size=TEE_VOLUME_MAX_ELEMENT_SIZE,
            export_tensor_stress=False,
        )
        if gallery == "pipe-tee-volume-review"
        else solver.export_analysis_study(model, load_case, output_path)
    )
    for filename in {*_SOLVER_OUTPUT_FILES, *_VOLUME_SOLVER_OUTPUT_FILES, "study_sigm.csv"}:
        (output_path / filename).unlink(missing_ok=True)
    solver.solve_exported_study(model, study)
    artifact = import_code_aster_artifacts(model=model, work_dir=output_path, study=study)
    _validate_gallery_artifact_chain(output_path, artifact)
    return artifact


def _validate_gallery_artifact_chain(output: Path, artifact: Any) -> None:
    required_outputs = (
        _VOLUME_SOLVER_OUTPUT_FILES
        if getattr(artifact.study, "metadata", {}).get("volume_analysis")
        else _SOLVER_OUTPUT_FILES
    )
    for filename in required_outputs:
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
    parser.add_argument(
        "--gallery",
        choices=(
            "autorouted-expansion-loop",
            "code-aster-review",
            "pipe-tee-volume-review",
            "support-rack-review",
        ),
        default="code-aster-review",
    )
    args = parser.parse_args()
    artifact = refresh_gallery(args.output, gallery=args.gallery)
    attestation = artifact.result_state.metadata["solve_attestation"]
    print(
        f"Refreshed Code_Aster gallery at {args.output} "
        f"({attestation['execution_method']} Code_Aster {attestation['solver_version']}, "
        f"{attestation['solved_at']})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
