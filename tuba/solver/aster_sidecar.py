"""Code_Aster sidecar helpers for traceable Tuba solver exports."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.provenance import (
    CODE_ASTER_COMPILER_ID,
    MIXED_CODE_ASTER_COMPILER_ID,
    SolverInputIdentity,
    require_matching_solver_input_identities,
    validate_solver_input_identity,
)
from tuba.analysis.study import AnalysisStudy


MAX_ASTER_NAME_LEN = 24


class SolverNameMap:
    def __init__(self, mapping: dict[str, str] | None = None):
        self.mapping = dict(mapping or {})

    def __call__(self, name: str) -> str:
        return self.mapping.get(name, name)


def _hashed_solver_name(name: str, *, max_length: int, used: set[str]) -> str:
    if max_length < 2:
        raise ValueError("max_length must allow at least a prefix and one digest character.")
    prefix = "G_" if max_length >= 10 else "G"
    digest_chars = max_length - len(prefix)
    attempt = 0
    while True:
        seed = name if attempt == 0 else f"{name}:{attempt}"
        digest = hashlib.sha1(seed.encode("utf-8")).hexdigest().upper()
        mapped = f"{prefix}{digest[:digest_chars]}"
        if mapped not in used:
            return mapped
        attempt += 1


def build_solver_name_map(names: Iterable[str], *, max_length: int = MAX_ASTER_NAME_LEN) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for name in names:
        if len(name) <= max_length and name not in used:
            mapped = name
        else:
            mapped = _hashed_solver_name(name, max_length=max_length, used=used)
        mapping[name] = mapped
        used.add(mapped)
    return mapping


def dump_solver_sidecar(
    path: str | Path,
    *,
    solver_name: str,
    load_case: str,
    analysis_mesh_id: str,
    name_map: dict[str, str],
    lineage: dict[str, str],
    mixed_analysis: dict | None = None,
    solver_input_identity: SolverInputIdentity | None = None,
) -> None:
    payload = {
        "schema_version": 1,
        "solver_name": solver_name,
        "load_case": load_case,
        "analysis_mesh_id": analysis_mesh_id,
        "name_map": dict(sorted(name_map.items())),
        "lineage": dict(sorted(lineage.items())),
    }
    if mixed_analysis is not None:
        payload["mixed_analysis"] = mixed_analysis
    if solver_input_identity is not None:
        payload["solver_input_identity"] = solver_input_identity.to_dict()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_and_validate_artifact_chain(
    model: Any,
    work_dir: str | Path,
    *,
    study: AnalysisStudy | None = None,
    requested_load_case: str | None = None,
) -> tuple[AnalysisStudy, AnalysisStudy | None, AnalysisMesh | None, dict[str, Any] | None]:
    """Load and validate Code_Aster lineage before any sidecar mapping is trusted."""
    root = Path(work_dir)
    manifest_study, analysis_mesh = _load_manifest_records(root)
    loaded_study = study or manifest_study
    if loaded_study is None:
        raise FileNotFoundError(
            f"Code_Aster artifact parsing requires {root / 'study_manifest.json'}; "
            "refusing to synthesize solver lineage."
        )
    if requested_load_case is not None and requested_load_case != loaded_study.load_case:
        raise ValueError(
            f"Requested Code_Aster load case {requested_load_case!r} does not match "
            f"artifact study load case {loaded_study.load_case!r}."
        )

    sidecar, sidecar_identity = _load_sidecar(root)
    compiler_id = (
        MIXED_CODE_ASTER_COMPILER_ID
        if loaded_study.metadata.get("mixed_analysis")
        else CODE_ASTER_COMPILER_ID
    )
    _validate_artifact_identities(
        model=model,
        study=loaded_study,
        manifest_study=manifest_study,
        analysis_mesh=analysis_mesh,
        sidecar=sidecar,
        sidecar_identity=sidecar_identity,
        compiler_id=compiler_id,
    )
    return loaded_study, manifest_study, analysis_mesh, sidecar


def _load_manifest_records(work_dir: Path) -> tuple[AnalysisStudy | None, AnalysisMesh | None]:
    manifest_path = work_dir / "study_manifest.json"
    if not manifest_path.exists():
        return None, None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return AnalysisStudy.from_dict(manifest["study"]), AnalysisMesh.from_dict(manifest["analysis_mesh"])
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid Code_Aster study manifest {manifest_path}: {exc}") from exc


def _load_sidecar(work_dir: Path) -> tuple[dict[str, Any] | None, SolverInputIdentity | None]:
    sidecar_path = work_dir / "study_tuba_fem.json"
    if not sidecar_path.exists():
        return None, None
    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        identity_data = sidecar.get("solver_input_identity")
        identity = SolverInputIdentity.from_dict(identity_data) if identity_data is not None else None
        return sidecar, identity
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid Code_Aster sidecar {sidecar_path}: {exc}") from exc


def _validate_artifact_identities(
    *,
    model: Any,
    study: AnalysisStudy,
    manifest_study: AnalysisStudy | None,
    analysis_mesh: AnalysisMesh | None,
    sidecar: dict[str, Any] | None,
    sidecar_identity: SolverInputIdentity | None,
    compiler_id: str,
) -> None:
    identities: list[tuple[str, SolverInputIdentity | None]] = [
        (f"Code_Aster study {study.id!r}", study.solver_input_identity),
    ]
    if manifest_study is not None:
        if manifest_study.load_case != study.load_case:
            raise ValueError(
                f"Code_Aster manifest study load case {manifest_study.load_case!r} does not "
                f"match imported study load case {study.load_case!r}."
            )
        if manifest_study.mesh_id != study.mesh_id:
            raise ValueError(
                f"Code_Aster manifest study mesh {manifest_study.mesh_id!r} does not "
                f"match imported study mesh {study.mesh_id!r}."
            )
        identities.append(("Code_Aster manifest study", manifest_study.solver_input_identity))
    if analysis_mesh is not None:
        if analysis_mesh.id != study.mesh_id:
            raise ValueError(
                f"Code_Aster manifest analysis mesh {analysis_mesh.id!r} does not "
                f"match imported study mesh {study.mesh_id!r}."
            )
        identities.append(("Code_Aster manifest analysis mesh", analysis_mesh.solver_input_identity))
    if sidecar is not None:
        if sidecar.get("load_case") != study.load_case:
            raise ValueError(
                f"Code_Aster sidecar load case {sidecar.get('load_case')!r} does not "
                f"match imported study load case {study.load_case!r}."
            )
        if sidecar.get("analysis_mesh_id") != study.mesh_id:
            raise ValueError(
                f"Code_Aster sidecar mesh {sidecar.get('analysis_mesh_id')!r} does not "
                f"match imported study mesh {study.mesh_id!r}."
            )
        if sidecar_identity is None and any(identity is not None for _context, identity in identities):
            raise ValueError(
                "Code_Aster sidecar is missing a solver input identity alongside an "
                "identity-bearing study or manifest; refusing to trust its name_map."
            )
        identities.append(("Code_Aster sidecar", sidecar_identity))

    for context, identity in identities:
        validate_solver_input_identity(
            model,
            identity,
            context=context,
            expected_load_case=study.load_case,
            expected_compiler_id=compiler_id,
        )
    for index, (left_context, left_identity) in enumerate(identities):
        for right_context, right_identity in identities[index + 1 :]:
            require_matching_solver_input_identities(
                left_identity,
                right_identity,
                context=f"{left_context} and {right_context}",
            )
