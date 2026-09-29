"""Write the reviewable study cards and reference figures for the committed examples.

A solved example folder is evidence; a card is what makes that evidence reviewable.
This driver reads every ``examples/<name>/evidence/<operation>/`` folder, writes
``examples/<name>/reference/<operation>/study_card.md`` and ``study_card.json`` next to
it, and asks the example — if it ships a ``reference_series.py`` — for the analytical
series to draw beside the solved one.

Cards go in ``reference/`` rather than beside the evidence because evidence promotion
removes every file the solve did not attest: a card kept inside the evidence folder
would be deleted by the next solve.

Usage, from the repository root::

    python scripts/build_study_cards.py                 # write the cards and figures
    python scripts/build_study_cards.py --check         # fail if committed cards are stale
    python scripts/build_study_cards.py examples/rack_bridge_demo

``--check`` is the CI form: it regenerates into a temporary directory and compares, so
a committed card that no longer describes its evidence fails the run instead of quietly
lying. A card is a review artifact and a review artifact that drifts is worse than none.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tuba.reporting.study_card import StudyCardError, write_study_card  # noqa: E402

MODEL_SCRIPT = "model.py"
REFERENCE_SERIES_SCRIPT = "reference_series.py"
EXAMPLES = "examples"
REFERENCE = "reference"


def project_roots(examples_dir: Path, requested: list[str] | None) -> tuple[Path, ...]:
    """Return the example folders to process, optionally narrowed to *requested* names."""
    if requested:
        return tuple(examples_dir / name for name in requested)
    if not examples_dir.is_dir():
        return ()
    return tuple(
        sorted(
            child
            for child in examples_dir.iterdir()
            if child.is_dir() and (child / MODEL_SCRIPT).is_file()
        )
    )


def _load_reference_series(project_root: Path) -> Any:
    """Import an example's optional ``reference_series.py``, or return ``None``.

    The hook is loaded by path rather than by package import because an example folder
    is not a package; the loader is private to this script on purpose, so a hook's
    contract is its docstring and this function, nothing else.
    """
    path = project_root / REFERENCE_SERIES_SCRIPT
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(f"tuba_reference_{project_root.name}", path)
    if spec is None or spec.loader is None:
        raise StudyCardError(f"{path} cannot be loaded as a Python module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    entry = getattr(module, "reference_figures", None)
    if not callable(entry):
        raise StudyCardError(
            f"{path} defines no callable reference_figures(project_root, evidence_folder)."
        )
    return entry


def _figure_texts(project_root: Path, evidence_folder: Path) -> dict[str, str]:
    """Return ``{filename: svg}`` for an example's reference figures, or an empty map."""
    from tuba.reporting.reference_figure import render_reference_figure

    entry = _load_reference_series(project_root)
    if entry is None:
        return {}
    produced = entry(project_root, evidence_folder)
    if not isinstance(produced, dict):
        raise StudyCardError(
            f"reference_figures for {project_root.name} returned {type(produced).__name__}, "
            "expected a mapping of filename to (series, labels)."
        )
    return {
        str(name): render_reference_figure(series, **labels) for name, (series, labels) in produced.items()
    }


def _expected(project_root: Path, evidence_folder: Path) -> dict[str, str]:
    """The exact text this driver would commit for one evidence folder."""
    with TemporaryDirectory(prefix="tuba_study_card_") as scratch:
        json_path, md_path = write_study_card(
            evidence_folder, Path(scratch), project_root=project_root
        )
        cards = {
            "study_card.json": json_path.read_text(encoding="utf-8"),
            "study_card.md": md_path.read_text(encoding="utf-8"),
        }
    return {**cards, **_figure_texts(project_root, evidence_folder)}


def process(project_root: Path, *, write: bool, check: bool) -> list[str]:
    """Write or check one example's reference artifacts; return the problems found."""
    problems: list[str] = []
    evidence_root = project_root / "evidence"
    if not evidence_root.is_dir():
        return problems
    for evidence_folder in sorted(child for child in evidence_root.iterdir() if child.is_dir()):
        reference_root = project_root / REFERENCE / evidence_folder.name
        if write:
            write_study_card(evidence_folder, reference_root, project_root=project_root)
            for name, text in _figure_texts(project_root, evidence_folder).items():
                target = reference_root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8", newline="\n")
        if not check:
            continue
        for name, expected in _expected(project_root, evidence_folder).items():
            committed = reference_root / name
            if not committed.is_file():
                problems.append(f"{committed} is missing.")
            elif committed.read_text(encoding="utf-8") != expected:
                problems.append(f"{committed} does not match its evidence folder.")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("examples", nargs="*", help="example folder names; default is every example with a model.py")
    parser.add_argument("--check", action="store_true", help="fail instead of writing when committed cards are stale")
    args = parser.parse_args(argv)

    examples_dir = REPOSITORY_ROOT / EXAMPLES
    problems: list[str] = []
    for project_root in project_roots(examples_dir, args.examples):
        try:
            problems.extend(process(project_root, write=not args.check, check=args.check))
        except (StudyCardError, OSError, ValueError) as exc:
            problems.append(f"{project_root.relative_to(REPOSITORY_ROOT)}: {exc}")

    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(f"{len(problems)} problem(s); run without --check to write the cards.", file=sys.stderr)
        return 1
    print("study cards and reference figures are current." if args.check else "study cards and reference figures written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
