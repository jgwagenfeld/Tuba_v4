"""An Analysis run's Evidence inside a review bundle (spec decision 14).

A run is staged into ``artifacts/<operation>/``, the folder its own attested operation names, so a bundle
can be read back from the attestation it carries rather than from the path a caller happened to pick.
Reading it back is validating it: :func:`read_staged_runs` joins every provenance file role to the
attestation covering that run's folder, and refuses the bundle when one of them does not belong there.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path, PureWindowsPath
import shutil
from typing import Any, Literal

from tuba.analysis.provenance import SolverInputIdentity, require_matching_solver_input_identities
from tuba.analysis.run import AnalysisRun
from tuba.solver.code_aster_runtime import execution_trust, load_code_aster_execution_attestation

ARTIFACTS = "artifacts"
_UNSAFE = frozenset('<>:"/\\|?*')
# Windows device names, alone or before an extension: no folder can take one.
_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", *(f"{port}{digit}" for port in ("COM", "LPT") for digit in "0123456789¹²³")}
)


def operation_folder_name(operation: str) -> str:
    """*operation* as one folder name, refusing a name Windows or Linux would not take.

    The rule is what both accept: no separator or reserved character, no control character, no trailing
    space or dot, no Windows device name, and no more than 255 UTF-8 bytes (Linux's limit).
    """
    if (
        not operation
        or operation[-1] in " ."
        or any(character in _UNSAFE or ord(character) < 32 for character in operation)
        or operation.split(".")[0].upper() in _RESERVED
        or len(operation.encode("utf-8")) > 255
    ):
        raise ValueError(f"Operation {operation!r} cannot name a folder.")
    return operation


def stage_runs(runs: Mapping[str, AnalysisRun], bundle_root: str | Path) -> dict[str, AnalysisRun]:
    """Copy each operation's attested Code_Aster evidence into ``<bundle_root>/artifacts/<operation>/``.

    *runs* maps an operation name to the Analysis run solved for it. The staged runs come back carrying
    bundle-relative POSIX references, with ``work_dir`` cleared.
    """
    root = Path(bundle_root).resolve()
    claimed: dict[str, str] = {}
    for operation in runs:
        folder = operation_folder_name(operation)
        # Two operations differing only in case share one folder on Windows.
        if (previous := claimed.setdefault(folder.casefold(), operation)) != operation:
            raise ValueError(f"Operations {previous!r} and {operation!r} claim one bundle folder.")
    return {operation: _stage_run(run, root, operation) for operation, run in runs.items()}


def _stage_run(artifact: AnalysisRun, bundle_root: Path, operation: str) -> AnalysisRun:
    """Copy one run's attested Code_Aster evidence into the folder its operation names."""
    destination = bundle_root / ARTIFACTS / operation_folder_name(operation)
    staged: dict[Path, str] = {}
    basename_sources: dict[str, Path] = {}
    portable_sources: dict[str, str] = {}
    evidence_root = _evidence_root(artifact.study.work_dir)
    if evidence_root is None:
        raise ValueError("Official Code_Aster evidence staging requires a solve attestation directory.")
    attestation = load_code_aster_execution_attestation(evidence_root)
    recorded_attestation = artifact.result_state.metadata.get("solve_attestation")
    if attestation is None or recorded_attestation != attestation:
        raise ValueError("Official Code_Aster evidence staging requires the validated solve attestation.")
    attestation_identity = SolverInputIdentity.from_dict(attestation["solver_input_identity"])
    if attestation_identity.load_case != operation:
        raise ValueError(
            f"Run staged as operation {operation!r} is attested for {attestation_identity.load_case!r}."
        )
    for context, identity in (
        ("study", artifact.study.solver_input_identity),
        ("analysis mesh", None if artifact.analysis_mesh is None else artifact.analysis_mesh.solver_input_identity),
        ("result state", artifact.result_state.solver_input_identity),
    ):
        if identity is None:
            raise ValueError(f"Official Code_Aster evidence staging requires a {context} identity.")
        require_matching_solver_input_identities(
            attestation_identity,
            identity,
            context=f"solve attestation and staged {context}",
        )
    for state in artifact.result_states:
        if state.metadata.get("solve_attestation") != attestation:
            raise ValueError("Official Code_Aster history staging requires the validated solve attestation.")
        require_matching_solver_input_identities(
            attestation_identity, state.solver_input_identity,
            context="solve attestation and staged history state",
        )
    attested = attestation["artifacts"]

    def stage_files(files: dict[str, str]) -> tuple[dict[str, str], dict[str, str], dict[str, int]]:
        portable: dict[str, str] = {}
        hashes: dict[str, str] = {}
        sizes: dict[str, int] = {}
        for role, value in files.items():
            basename = PureWindowsPath(value).name
            if basename not in attested and basename != "study_execution.json":
                continue
            source = _artifact_source(value, evidence_root=evidence_root)
            basename = source.name
            previous = basename_sources.setdefault(basename, source)
            if previous != source:
                raise ValueError(f"Artifact basename collision for {basename!r}.")
            relative = staged.get(source)
            if relative is None:
                destination.mkdir(parents=True, exist_ok=True)
                target = destination / basename
                shutil.copy2(source, target)
                relative = target.relative_to(bundle_root).as_posix()
                staged[source] = relative
            portable[role] = relative
            portable_sources[str(value)] = relative
            portable_sources[str(source)] = relative
            portable_sources[source.as_posix()] = relative
            if basename == "study_execution.json":
                hashes[role] = _sha256(source)
                sizes[role] = source.stat().st_size
            else:
                observed = attested[basename]
                hashes[role] = str(observed["sha256"])
                sizes[role] = int(observed["size_bytes"])
        return portable, hashes, sizes

    study_files, study_hashes, study_sizes = stage_files(artifact.study.input_files)
    mesh_files, _mesh_hashes, _mesh_sizes = stage_files(
        artifact.analysis_mesh.files if artifact.analysis_mesh is not None else {}
    )
    result_files, result_hashes, result_sizes = stage_files(artifact.result_state.files)
    history_files = [stage_files(state.files) for state in artifact.result_states]
    staged_names = {Path(relative).name for relative in staged.values()}
    required_names = {*attested, "study_execution.json"}
    missing = sorted(required_names - staged_names)
    if missing:
        raise ValueError(
            "Official Code_Aster evidence staging requires all attested payloads and the execution envelope; "
            f"missing file mappings for: {', '.join(missing)}."
        )
    if load_code_aster_execution_attestation(destination) != attestation:
        raise ValueError("Staged Code_Aster execution attestation does not match its source envelope.")
    study = replace(
        artifact.study,
        work_dir=None,
        input_files=study_files,
        metadata={
            **artifact.study.metadata,
            **_portable_metadata(artifact.study.metadata, portable_sources),
            "file_sha256": study_hashes,
            "file_sizes": study_sizes,
        },
    )
    mesh = (
        replace(artifact.analysis_mesh, files=mesh_files)
        if artifact.analysis_mesh is not None
        else None
    )
    result_state = replace(
        artifact.result_state,
        files=result_files,
        metadata={
            **artifact.result_state.metadata,
            **_portable_metadata(artifact.result_state.metadata, portable_sources),
            "file_sha256": result_hashes,
            "file_sizes": result_sizes,
        },
    )
    result_states = tuple(
        replace(
            state,
            files=files,
            metadata={
                **_portable_metadata(state.metadata, portable_sources),
                "file_sha256": hashes,
                "file_sizes": sizes,
            },
        )
        for state, (files, hashes, sizes) in zip(artifact.result_states, history_files)
    )
    return replace(
        artifact, study=study, analysis_mesh=mesh,
        result_state=result_states[-1] if result_states else result_state,
        result_states=result_states,
    )


@dataclass(frozen=True)
class StagedRun:
    """One Analysis run's staged Evidence, as the attestation covering its folder describes it.

    A caller reads the run rather than re-deriving it from the review document that points at it.
    """

    root: Path                           # the bundle holding this run
    operation: str                       # the attested load case; also the folder name
    folder: str                          # "artifacts/<operation>", bundle-relative POSIX
    identity: SolverInputIdentity        # from the attestation, never from review.json
    trust: Literal["verified", "unverified"]
    modelization: str | None             # compiler_inputs.pipe_modelization, when the study names one
    contact: bool                        # the attested inventory carries the contact rows
    inventory: tuple[str, ...]           # attested basenames, sorted
    files: Mapping[str, str]             # role -> bundle-relative POSIX path, every one attested

    def path(self, role: str) -> Path:
        """*role*'s staged file, absolute; ``KeyError`` for a role this run does not carry."""
        return self.root / self.files[role]


def read_staged_runs(bundle_root: str | Path) -> tuple[StagedRun, ...]:
    """Every run staged in this bundle, ordered by operation; reading is validating.

    A bundle without a review document holds no runs, which is the right answer for a model review and
    a mesh review. Every other bundle is refused unless each run's file roles land on the evidence its
    own attestation covers.
    """
    root = Path(bundle_root).resolve()
    review = root / "review.json"
    if not review.is_file():
        return ()
    groups = _records_by_identity(json.loads(review.read_text(encoding="utf-8")))
    return tuple(sorted((_read_run(root, group) for group in groups), key=lambda run: run.operation))


def _records_by_identity(review: Mapping[str, Any]) -> list[list[Mapping[str, Any]]]:
    """Group a review's provenance records into runs, one group per solver input identity."""
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for record in review.get("provenance", ()):
        metadata = record.get("metadata") if isinstance(record, Mapping) else None
        identity = metadata.get("solver_input_identity") if isinstance(metadata, Mapping) else None
        if not isinstance(identity, Mapping):
            name = record.get("id") if isinstance(record, Mapping) else None
            raise ValueError(f"Provenance record {name!r} carries no solver input identity.")
        # Only the grouping reads this identity; every run's own identity comes from its attestation.
        groups.setdefault(json.dumps(identity, sort_keys=True), []).append(record)
    return list(groups.values())


def _read_run(root: Path, group: Sequence[Mapping[str, Any]]) -> StagedRun:
    """Read one run back from the folder its execution envelope names, validating as it goes."""
    records = {record.get("kind"): record for record in group}
    # A name for the refusals below only; the attestation decides the operation.
    case = group[0].get("load_case")
    missing = [kind for kind in ("study", "analysis_mesh", "result_state") if kind not in records]
    if missing:
        raise ValueError(f"Staged run {case!r} is missing its {', '.join(missing)} provenance record.")
    envelope = records["result_state"].get("files", {}).get("execution")
    if not isinstance(envelope, str):
        raise ValueError(f"Staged run {case!r} carries no 'execution' envelope naming its evidence folder.")
    folder = _artifact_source(envelope, evidence_root=root).parent
    if root not in folder.parents:
        raise ValueError(f"Staged run {case!r} names an execution envelope outside its bundle: {envelope!r}.")
    folder_uri = folder.relative_to(root).as_posix()
    # Loading re-hashes every attested file, so one flipped byte is refused here.
    attestation = load_code_aster_execution_attestation(folder)
    if attestation is None:
        raise ValueError(f"Staged run {case!r} has no execution attestation in {folder_uri!r}.")
    identity = SolverInputIdentity.from_dict(attestation["solver_input_identity"])
    operation = identity.load_case
    if folder.name != operation:
        raise ValueError(f"Bundle folder {folder_uri!r} holds evidence attested for operation {operation!r}.")
    inventory = tuple(sorted(attestation["artifacts"]))
    attested = {*inventory, "study_execution.json"}
    for path in sorted(folder.iterdir()):
        if path.name not in attested:
            raise ValueError(
                f"Staged run {operation!r} carries {path.name!r}, which its attestation does not cover."
            )
    files: dict[str, str] = {}
    for record in group:
        for role, uri in record.get("files", {}).items():
            source = _artifact_source(uri, evidence_root=root)
            if source.parent != folder or source.name not in attested:
                raise ValueError(
                    f"Staged run {operation!r} role {role!r} names {uri!r}, "
                    "which its attestation does not cover."
                )
            files[role] = source.relative_to(root).as_posix()
    manifest = json.loads((folder / "study_manifest.json").read_text(encoding="utf-8"))
    return StagedRun(
        root=root,
        operation=operation,
        folder=folder_uri,
        identity=identity,
        trust=execution_trust(attestation),
        modelization=manifest["study"]["metadata"].get("compiler_inputs", {}).get("pipe_modelization"),
        contact="study_contact.json" in inventory,
        inventory=inventory,
        files=files,
    )


def _evidence_root(work_dir: str | None) -> Path | None:
    if work_dir is None:
        return None
    return Path(work_dir.replace("\\", "/")).resolve()


def _artifact_source(value: str, *, evidence_root: Path | None) -> Path:
    source = Path(value.replace("\\", "/"))
    if ".." in source.parts or ".." in PureWindowsPath(value).parts:
        raise ValueError(f"Artifact path must not traverse directories: {value!r}.")
    candidates = [source] if source.is_absolute() else [
        *( [evidence_root / source] if evidence_root is not None else [] ),
        source,
    ]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        if any(path.is_symlink() for path in _path_components(candidate)):
            raise ValueError(f"Artifact symlinks are not publishable: {value!r}.")
        return candidate.resolve()
    raise ValueError(f"Artifact file is missing: {value!r}.")


def _path_components(path: Path):
    current = path
    while True:
        yield current
        if current == current.parent:
            return
        current = current.parent


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _portable_metadata(value: Any, sources: Mapping[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _portable_metadata(item, sources) for key, item in value.items()}
    if isinstance(value, list):
        return [_portable_metadata(item, sources) for item in value]
    if isinstance(value, str):
        return sources.get(value, value)
    return value
