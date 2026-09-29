"""Study cards: the reviewable, human-readable record of one solved Code_Aster study.

A study card answers the three questions a reviewer opens a solved study to ask, and
answers them from the artifacts themselves rather than from anything Tuba holds in
memory: *what was solved*, *which Code_Aster commands actually ran*, and *which files
prove it*. It is the piece the generated ``.comm`` and ``.export`` were missing — those
are written as text by :mod:`tuba.solver.aster_comm`, so without a card nobody can
eyeball what went to the solver without re-exporting into a scratch directory.

The card never adds a quantity the solver did not produce. The keyword inventory is
read out of the committed ``study.comm``, the unit map out of ``study.export``, the
version and the artifact hashes out of the solve attestation, and the integrity
verdict from :func:`tuba.project.evidence.evidence_state` — the same single verdict a
solve and the studio use. Nothing here is a code check, a utilization or a verdict.
"""

from __future__ import annotations

import ast
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tuba.project.evidence import EvidenceState, evidence_state

MANIFEST = "study_manifest.json"
ATTESTATION = "study_execution.json"
COMM = "study.comm"
EXPORT = "study.export"

#: Calls in a Code_Aster comm file that are field constructors, not solver commands.
_NON_COMMANDS = frozenset({"_F", "F"})

_STUDY_CARD_SCHEMA = "tuba.study_card.v1"

_UNIT_MEANING = {
    "1": "command file",
    "6": "message log",
    "8": "result database",
    "20": "mesh",
    "38": "element end forces (EFGE_ELNO)",
    "39": "displacements (DEPL)",
    "40": "node reactions (REAC_NODA)",
    "41": "stress invariants (SIEQ_ELNO)",
    "42": "contact history",
    "60": "result MED",
    "80": "result MED",
}


class StudyCardError(ValueError):
    """A folder does not hold enough of a study to describe what was solved."""


@dataclass(frozen=True)
class CommKeyword:
    """One Code_Aster command, counted in the generated command file."""

    name: str
    count: int


@dataclass(frozen=True)
class ExportUnit:
    """One ``.export`` line: the unit the solver writes, and where it lands."""

    logical: str
    filename: str
    direction: str
    unit: str

    @property
    def meaning(self) -> str:
        """What this logical unit carries, for the card's unit map."""
        return _UNIT_MEANING.get(self.unit, "unmapped unit")


@dataclass(frozen=True)
class AttestedArtifact:
    """One file the solve attestation binds, as the attestation recorded it."""

    name: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class StudyCard:
    """What one solved Code_Aster study folder holds, read from its own artifacts."""

    source: str
    evidence_status: str
    evidence_reason: str
    study_id: str
    load_case: str
    solver_name: str
    solver_version: str
    execution_method: str
    solved_at: str
    model_revision: int
    mesh_id: str
    project_name: str
    node_count: int
    element_count: int
    keywords: tuple[CommKeyword, ...]
    keyword_inventory_is_lower_bound: bool
    export_units: tuple[ExportUnit, ...]
    artifacts: tuple[AttestedArtifact, ...]

    def to_dict(self) -> dict[str, Any]:
        """The card as plain JSON-ready data, for tests and for downstream tools."""
        return {
            "schema_version": _STUDY_CARD_SCHEMA,
            "source": self.source,
            "evidence_status": self.evidence_status,
            "evidence_reason": self.evidence_reason,
            "study": {
                "id": self.study_id,
                "load_case": self.load_case,
                "solver_name": self.solver_name,
                "solver_version": self.solver_version,
                "execution_method": self.execution_method,
                "solved_at": self.solved_at,
                "model_revision": self.model_revision,
                "mesh_id": self.mesh_id,
                "project_name": self.project_name,
                "node_count": self.node_count,
                "element_count": self.element_count,
            },
            "comm_keywords": [
                {"name": keyword.name, "count": keyword.count} for keyword in self.keywords
            ],
            "keyword_inventory_is_lower_bound": self.keyword_inventory_is_lower_bound,
            "export_units": [
                {
                    "logical": unit.logical,
                    "filename": unit.filename,
                    "direction": unit.direction,
                    "unit": unit.unit,
                    "meaning": unit.meaning,
                }
                for unit in self.export_units
            ],
            "attested_artifacts": [
                {"name": artifact.name, "size_bytes": artifact.size_bytes, "sha256": artifact.sha256}
                for artifact in self.artifacts
            ],
        }


def parse_code_aster_keywords(comm_text: str) -> tuple[tuple[str, int], ...]:
    """Return the Code_Aster commands a generated command file calls, with counts.

    The command file is a sequence of top-level calls — bare for ``DEBUT``/``FIN``,
    assigned for everything that produces a result. Parsing it as Python is the
    honest way to read it: ``#`` inside a group name is not a comment, and a command
    that appears inside another call's arguments is not a separate command. The
    ``_F`` field constructor is not a command and is dropped.

    Raises
    ------
    ValueError
        The file is not readable as a command file. A card states what ran; a card
        that guessed at an unreadable file would state something nobody checked.
    """
    try:
        tree = ast.parse(comm_text)
    except SyntaxError as exc:
        raise ValueError(f"Code_Aster command file is not readable as a command sequence: {exc}") from exc

    counts: Counter[str] = Counter()
    for statement in tree.body:
        # `NAME = COMMAND(...)` and a bare `DEBUT(...)` are both calls; the embedded
        # Python blocks a comm may carry are `for`/`with` statements, not commands.
        if not isinstance(statement, (ast.Assign, ast.Expr)):
            continue
        call = statement.value
        if not isinstance(call, ast.Call):
            continue
        name = call.func.id if isinstance(call.func, ast.Name) else None
        if name is None or name in _NON_COMMANDS:
            continue
        counts[name] += 1
    return tuple(sorted(counts.items()))


def parse_export_units(export_text: str) -> tuple[ExportUnit, ...]:
    """Return the ``F`` unit map of an export file, in file order.

    ``P`` and ``A`` directives are not units and are skipped. A line that is neither
    a known directive nor four fields is not a unit map entry, so a malformed line
    is dropped rather than reported as a unit the solver never wrote.
    """
    units: list[ExportUnit] = []
    for raw in export_text.splitlines():
        line = raw.strip()
        if not line or line[0] in {"P", "A"}:
            continue
        fields = line.split()
        if len(fields) < 5 or fields[0] != "F":
            continue
        logical, filename, direction, unit = fields[1], fields[2], fields[3], fields[4]
        units.append(ExportUnit(logical, filename, direction, unit))
    return tuple(units)


def _read_manifest(folder: Path) -> Mapping[str, Any]:
    path = folder / MANIFEST
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StudyCardError(f"{path} cannot be read: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise StudyCardError(f"{path} is not a study manifest object.")
    if not isinstance(payload.get("study"), Mapping):
        raise StudyCardError(f"{path} records no study; there is nothing to describe.")
    return payload


def _attested_artifacts(state: EvidenceState) -> tuple[AttestedArtifact, ...]:
    artifacts = (state.attestation or {}).get("artifacts")
    if not isinstance(artifacts, Mapping):
        return ()
    return tuple(
        AttestedArtifact(
            name=str(name),
            size_bytes=int(entry.get("size_bytes", 0)),
            sha256=str(entry.get("sha256", "")),
        )
        for name, entry in sorted(artifacts.items())
        if isinstance(entry, Mapping)
    )


def _source_label(folder: Path, project_root: Path | None) -> str:
    """A stable name for the folder a card describes.

    Never the absolute path: a card is committed, and a card carrying one author's
    machine path is both a leak and a diff every other checkout fails.
    """
    if project_root is None:
        return folder.name
    root = Path(project_root)
    try:
        return folder.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return folder.name


def build_study_card(folder: str | Path, *, project_root: str | Path | None = None) -> StudyCard:
    """Describe the solved study in *folder* from the artifacts that folder holds.

    The folder is an evidence folder, or any work directory holding a study: the
    manifest describes the study, the attestation describes the solve, and
    ``study.comm`` / ``study.export`` describe what the solver was handed. The
    evidence verdict is taken from :func:`tuba.project.evidence.evidence_state`, so
    a folder whose artifacts no longer match its attestation is reported as damaged
    rather than described as a valid solve.

    Pass *project_root* to name the folder relative to its project; without it the
    card names the operation folder alone.
    """
    root = Path(folder)
    manifest = _read_manifest(root)
    study = manifest["study"]
    mesh = manifest.get("analysis_mesh")
    mesh = mesh if isinstance(mesh, Mapping) else {}
    metadata = study.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}

    state = evidence_state(root)

    comm_path = root / COMM
    keywords: tuple[CommKeyword, ...] = ()
    lower_bound = False
    if comm_path.is_file():
        comm_text = comm_path.read_text(encoding="utf-8", errors="replace")
        keywords = tuple(CommKeyword(name, count) for name, count in parse_code_aster_keywords(comm_text))
        # A comm that imports the command module calls commands without writing their
        # name at the call site, so the inventory is a lower bound and the card says so
        # rather than letting a reader take it for the complete set.
        lower_bound = "from code_aster.Studies.Commands import" in comm_text

    export_path = root / EXPORT
    units = (
        parse_export_units(export_path.read_text(encoding="utf-8", errors="replace"))
        if export_path.is_file()
        else ()
    )

    attestation = state.attestation or {}
    return StudyCard(
        source=_source_label(root, None if project_root is None else Path(project_root)),
        evidence_status=state.status,
        evidence_reason=state.reason,
        study_id=str(study.get("id", "")),
        load_case=str(study.get("load_case", "")),
        solver_name=str(attestation.get("solver_name") or study.get("solver_name") or "Code_Aster"),
        solver_version=str(attestation.get("solver_version") or "not attested"),
        execution_method=str(attestation.get("execution_method") or "not attested"),
        solved_at=str(attestation.get("solved_at") or "not attested"),
        model_revision=int(study.get("model_revision", 0)),
        mesh_id=str(study.get("mesh_id", "")),
        project_name=str(metadata.get("project_name") or "unnamed"),
        node_count=len(mesh.get("nodes") or {}),
        element_count=len(mesh.get("elements") or {}),
        keywords=keywords,
        keyword_inventory_is_lower_bound=lower_bound,
        export_units=units,
        artifacts=_attested_artifacts(state),
    )


def _escape(text: object) -> str:
    """Markdown-escape a value so a project name cannot break the table."""
    return str(text).replace("|", r"\|")


def _format_bytes(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} kB"
    return f"{size} B"


def render_study_card_markdown(card: StudyCard) -> str:
    """Render a study card as the page a reviewer reads and a diff tracks."""
    lines = [
        f"# Study card: {card.load_case or card.study_id}",
        "",
        f"Source folder: `{card.source}`",
        "",
        "## What was solved",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Study | {_escape(card.study_id)} |",
        f"| Load case | {_escape(card.load_case)} |",
        f"| Project | {_escape(card.project_name)} |",
        f"| Model revision | {card.model_revision} |",
        f"| Analysis mesh | {_escape(card.mesh_id)} |",
        f"| Mesh size | {card.node_count} nodes, {card.element_count} elements |",
        f"| Solver | {_escape(card.solver_name)} {card.solver_version} |",
        f"| Execution | {_escape(card.execution_method)} |",
        f"| Solved at | {_escape(card.solved_at)} |",
        f"| Evidence | **{card.evidence_status}** — {card.evidence_reason} |",
        "",
    ]

    lines += ["## Code_Aster commands in the generated .comm", ""]
    if card.keywords:
        lines += ["| Command | Calls |", "| --- | --- |"]
        lines += [f"| `{_escape(keyword.name)}` | {keyword.count} |" for keyword in card.keywords]
        if card.keyword_inventory_is_lower_bound:
            lines += [
                "",
                "The command file imports the Code_Aster command module, so commands "
                "invoked without their name at the call site are not counted here. This "
                "inventory is a lower bound.",
            ]
    else:
        lines += ["No command inventory: the folder holds no readable `study.comm`."]

    lines += ["", "## Unit map in the generated .export", ""]
    if card.export_units:
        lines += ["| Logical | File | Dir | Unit | Carries |", "| --- | --- | --- | --- | --- |"]
        lines += [
            f"| {_escape(unit.logical)} | `{_escape(unit.filename)}` | {unit.direction} | "
            f"{unit.unit} | {unit.meaning} |"
            for unit in card.export_units
        ]
        lines += [
            "",
            "A unit the command file writes but the export omits is silently lost with the "
            "run directory; the two lists above are the check on that.",
        ]
    else:
        lines += ["No unit map: the folder holds no readable `study.export`."]

    lines += ["", "## Attested artifacts", ""]
    if card.artifacts:
        lines += ["| File | Size | SHA-256 |", "| --- | --- | --- |"]
        lines += [
            f"| `{_escape(artifact.name)}` | {_format_bytes(artifact.size_bytes)} | "
            f"`{artifact.sha256[:16]}…` |"
            for artifact in card.artifacts
        ]
        lines += [
            "",
            "These hashes are what the solve attested. The evidence verdict above is taken "
            "by re-checking them against the files on disk.",
        ]
    else:
        lines += ["No attested artifacts: the folder holds no intact solve attestation."]

    lines += [
        "",
        "## What this card is not",
        "",
        "Every value above is read from solver artifacts and describes what Code_Aster "
        "was given and returned. No number here is a code check, a utilization or an "
        "acceptance verdict: Tuba performs no standards evaluation, and the stresses in "
        "this study are finite-element output.",
        "",
    ]
    return "\n".join(lines)


def write_study_card(
    folder: str | Path,
    output_dir: str | Path,
    *,
    basename: str = "study_card",
    project_root: str | Path | None = None,
) -> tuple[Path, Path]:
    """Write a study card for *folder* into *output_dir*; return the json and md paths.

    Cards are written outside the evidence folder on purpose: evidence promotion
    removes every file the solve did not attest, so a card kept beside the evidence it
    describes would be deleted by the next solve. Pass *project_root* so the card names
    the folder relative to its project instead of by absolute path.
    """
    card = build_study_card(folder, project_root=project_root)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / f"{basename}.json"
    md_path = target / f"{basename}.md"
    json_path.write_text(
        json.dumps(card.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    md_path.write_text(render_study_card_markdown(card), encoding="utf-8", newline="\n")
    return json_path, md_path


def evidence_folders(project_root: str | Path) -> tuple[Path, ...]:
    """Return every solved-operation folder under ``<project_root>/evidence/``."""
    evidence = Path(project_root) / "evidence"
    if not evidence.is_dir():
        return ()
    return tuple(
        sorted(
            child
            for child in evidence.iterdir()
            if child.is_dir() and (child / MANIFEST).is_file()
        )
    )


def write_project_study_cards(project_root: str | Path) -> Sequence[tuple[Path, Path, Path]]:
    """Write one card per solved operation into ``<project_root>/reference/<operation>/``.

    Returns the ``(operation folder, json path, md path)`` triples written, in
    operation order, so a caller can report or diff them.
    """
    root = Path(project_root)
    written: list[tuple[Path, Path, Path]] = []
    for folder in evidence_folders(root):
        json_path, md_path = write_study_card(
            folder, root / "reference" / folder.name, project_root=root
        )
        written.append((folder, json_path, md_path))
    return tuple(written)
