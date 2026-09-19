"""Evidence folders: where a project's solved operations live, how a solve lands there, and whether one
may be reused.

Spec decision 10: one folder per operation, ``<project>/evidence/<operation>/``. Decision 12: a solve
promotes its files first and ``study_execution.json`` last; nothing moves before every staged
attestation passes its integrity check, and an interrupted promotion leaves operations unsolved, never
falsely attested. This module owns the one verdict over a folder: intact and verified, unverified,
damaged, or missing, and whether its attested solver input identity still matches the model and study.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from tuba.analysis.provenance import SolverInputIdentity
from tuba.analysis.staged_run import operation_folder_name
from tuba.solver.code_aster_runtime import execution_trust, load_code_aster_execution_attestation

EVIDENCE = "evidence"
ATTESTATION = "study_execution.json"


def evidence_dir(project_root: str | Path, operation: str) -> Path:
    """``<project>/evidence/<operation>/``, refusing an operation name that cannot be one folder name.

    An evidence folder is named by its operation under the same rule a bundle's staged run is, so what
    one refuses the other refuses too.
    """
    try:
        operation_folder_name(operation)
    except ValueError:
        raise ValueError(f"Operation {operation!r} cannot name an evidence folder.") from None
    return Path(project_root) / EVIDENCE / operation


def study_artifact_dir(project_root: str | Path, operations: Sequence[str]) -> Path:
    """The folder a study's ``build_review`` imports the project's evidence from.

    A single-operation study imports its operation's folder, and a study of several imports the evidence
    folder holding one folder per operation, as today's studies set ``ARTIFACT_DIR``.
    """
    if len(operations) == 1:
        return evidence_dir(project_root, operations[0])
    return Path(project_root) / EVIDENCE


def promote_evidence(moves: Mapping[Path, Path]) -> None:
    """Move solved operations from their staging folders (keys) into their evidence folders (values).

    Every staged attestation is integrity-checked before anything moves, so one bad operation promotes
    none. Then the old attestations go, the attested files move in, every other file in an evidence
    folder is removed, and the new attestations land last. A folder is evidence only while it has an
    attestation: an interruption leaves operations unsolved, never new files under an old attestation.
    """
    inventories = {}
    for staged in moves:
        attestation = load_code_aster_execution_attestation(staged)
        if attestation is None:
            raise ValueError(f"{staged} holds no solve attestation to promote.")
        inventories[staged] = tuple(attestation["artifacts"])
    for target in moves.values():
        target.mkdir(parents=True, exist_ok=True)
        (target / ATTESTATION).unlink(missing_ok=True)
    for staged, target in moves.items():
        for name in inventories[staged]:
            os.replace(staged / name, target / name)
        for path in target.iterdir():
            if path.is_file() and path.name not in inventories[staged]:
                path.unlink()
    # ponytail: the attestations land one after another, so an interruption between two leaves the
    # later operations unsolved; a journal would make the set atomic if that ever matters.
    for staged, target in moves.items():
        os.replace(staged / ATTESTATION, target / ATTESTATION)


EvidenceStatus = Literal["verified", "unverified", "damaged", "missing"]


@dataclass(frozen=True)
class EvidenceState:
    """What an evidence folder holds, loaded once: presence, integrity, trust, and the attestation.

    ``status`` is ``verified``, ``unverified`` (a Docker solve), ``damaged`` (the attestation
    failed its integrity check), or ``missing`` (no attestation). ``reason`` says why, in words
    an engineer can act on; ``attestation`` is the validated payload when one was read.
    """

    status: EvidenceStatus
    trust: str
    reason: str
    attestation: dict[str, Any] | None


@dataclass(frozen=True)
class EvidenceVerdict:
    """Evidence judged against the solver input identity the model and study would compile now."""

    state: EvidenceState
    identity_matches: bool

    @property
    def reusable(self) -> bool:
        """Whether a solve may reuse this folder instead of solving the operation again."""
        return self.state.status == "verified" and self.identity_matches


def evidence_state(folder: str | Path) -> EvidenceState:
    """Load *folder*'s attestation once and classify it.

    Reading the attestation integrity-checks every attested artifact, so this is the expensive
    half of the verdict; it is memoized by the folder's file signature because the studio asks
    on every poll while a solve asks once per operation.
    """
    root = Path(folder)
    try:
        attestation = _cached_attestation(root)
    except (OSError, ValueError) as exc:
        return EvidenceState("damaged", "unverified", str(exc), None)
    if attestation is None:
        return EvidenceState("missing", "unverified", f"{root / ATTESTATION} does not exist.", None)
    trust = execution_trust(attestation)
    if trust != "verified":
        return EvidenceState(
            "unverified", trust, "the solve ran through Docker, so its results are unverified.", attestation
        )
    return EvidenceState("verified", trust, "the attestation is intact and the run was verified.", attestation)


def evidence_verdict(folder: str | Path, identity: SolverInputIdentity) -> EvidenceVerdict:
    """Judge *folder* against *identity*: the one reuse decision a solve and the studio share."""
    state = evidence_state(folder)
    if state.attestation is None:
        return EvidenceVerdict(state, False)
    try:
        attested = SolverInputIdentity.from_dict(state.attestation["solver_input_identity"])
    except (KeyError, TypeError, ValueError):
        return EvidenceVerdict(state, False)
    return EvidenceVerdict(state, attested == identity)


def exported_study_matches(work_dir: str | Path, identity: SolverInputIdentity) -> bool:
    """Whether *work_dir* already holds a solve for *identity*.

    This is the cheap reuse probe before re-execution, not the trust check: any unreadable,
    mismatched, or incomplete attestation is a miss that re-executes, so a half-deleted work
    directory still solves instead of raising. :func:`evidence_verdict` is the full judgement;
    the artifact import still runs the full attestation validation on whatever is reused.
    """
    try:
        attestation = load_code_aster_execution_attestation(work_dir)
        if attestation is None:
            return False
        attested = SolverInputIdentity.from_dict(attestation["solver_input_identity"])
    except (KeyError, OSError, TypeError, ValueError):
        return False
    return attested == identity


_ATTESTATION_CACHE: dict[tuple[Any, ...], dict[str, Any] | None] = {}
_ATTESTATION_CACHE_LIMIT = 32


def _cached_attestation(root: Path) -> dict[str, Any] | None:
    key = _folder_signature(root)
    if key in _ATTESTATION_CACHE:
        return _ATTESTATION_CACHE[key]
    payload = load_code_aster_execution_attestation(root)
    if len(_ATTESTATION_CACHE) >= _ATTESTATION_CACHE_LIMIT:
        _ATTESTATION_CACHE.clear()
    _ATTESTATION_CACHE[key] = payload
    return payload


def _folder_signature(root: Path) -> tuple[Any, ...]:
    try:
        entries = tuple(
            sorted((path.name, path.stat().st_size, path.stat().st_mtime_ns) for path in root.iterdir() if path.is_file())
        )
    except OSError:
        entries = ()
    return (str(root), entries)
