"""Evidence folders: where a project's solved operations live, and how a solve lands there.

Spec decision 10: one folder per operation, ``<project>/evidence/<operation>/``. Decision 12: a solve
promotes its files first and ``study_execution.json`` last, and lands all of its operations or none.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from tuba.solver.code_aster_runtime import load_code_aster_execution_attestation

EVIDENCE = "evidence"
ATTESTATION = "study_execution.json"
_UNSAFE = frozenset('<>:"/\\|?*')
_RESERVED = frozenset({"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10))})


def evidence_dir(project_root: str | Path, operation: str) -> Path:
    """``<project>/evidence/<operation>/``, refusing an operation name that cannot be one folder name.

    The rule is what Windows and Linux both accept: no separator or reserved character, no control
    character, no trailing space or dot, and no Windows device name.
    """
    if (
        not operation
        or operation[-1] in " ."
        or any(character in _UNSAFE or ord(character) < 32 for character in operation)
        or operation.split(".")[0].upper() in _RESERVED
    ):
        raise ValueError(f"Operation {operation!r} cannot name an evidence folder.")
    return Path(project_root) / EVIDENCE / operation


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
