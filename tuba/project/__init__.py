"""Projects: a folder holding ``model.py`` and, optionally, ``study.py``.

``model.py`` builds the model at module level and binds it to ``model``; nothing
else happens there. ``study.py`` says how that model is solved and reviewed. The
gallery build, the solver refresh, the studio and the tests all load projects
through this module, so none of them can drift into its own copy of a model.

Build a project's review from the command line (from the repository root)::

    python -m tuba.project examples/native-friction-review --output .build/friction
    python -m tuba.project examples/native-friction-review --output .build/friction \\
        --artifact-dir examples/native-friction-review/evidence/Reseat

The first form solves the study's operations into the project's ``evidence/``, reusing evidence that
still matches the model and study (``--force`` solves again). The second imports the folder it names.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from tuba.model import TubaModel

if TYPE_CHECKING:
    from tuba.project.study import StudySettings

MODEL_SCRIPT = "model.py"
STUDY_SCRIPT = "study.py"


def run_model_script(path: str | Path) -> dict[str, Any]:
    """Run a model script as ``__main__`` and return its globals.

    ``__main__`` is what links 3D objects to script lines. The script binds
    ``model`` to a TubaModel, or defines ``build_model()`` returning one.
    """
    from tuba.project.execution import execute_project_script

    script = Path(path)
    namespace = execute_project_script(script)
    model = namespace.get("model")
    if not isinstance(model, TubaModel):
        error = TypeError(
            f"{script.name} must bind 'model' to a TubaModel (or define build_model()), "
            f"got {type(model).__name__}."
        )
        error.__tuba_project_dependencies__ = namespace["__tuba_project_dependencies__"]
        raise error
    return namespace


@dataclass(frozen=True)
class Project:
    root: Path

    @property
    def name(self) -> str:
        return self.root.name

    @property
    def model_path(self) -> Path:
        return self.root / MODEL_SCRIPT

    @property
    def study_path(self) -> Path:
        return self.root / STUDY_SCRIPT

    def run_model(self) -> dict[str, Any]:
        """Build the model: the globals of ``model.py``, with ``model`` among them."""
        return run_model_script(self.model_path)

    def load_study(self, filename: str = STUDY_SCRIPT) -> SimpleNamespace | None:
        """The study's names (``LOAD_CASES``, ``build_review`` ...), or None without one.

        A project may carry more than one study of the same model (the tee has a
        solved review and a mesh-only one); ``filename`` picks which.
        """
        path = self.root / filename
        if not path.is_file():
            return None
        # Not __main__: a study is configuration and review code, not model lines.
        from tuba.project.execution import execute_project_script

        return SimpleNamespace(**execute_project_script(path, run_name=f"tuba_study.{self.name}.{path.stem}"))

    def load_settings(self, filename: str = STUDY_SCRIPT) -> "StudySettings":
        """The study's validated settings, or the empty record when it has no study.

        Every one-shot surface loads a study through here, so validation happens once. The
        studio revalidates per use instead, because study.py can be edited while it runs.
        """
        from tuba.project.study import study_settings

        return study_settings(self.load_study(filename))


def load_project(root: str | Path) -> Project:
    project = Project(Path(root).resolve())
    if not project.model_path.is_file():
        raise FileNotFoundError(f"{project.root} has no {MODEL_SCRIPT}.")
    return project


def main(argv: list[str] | None = None, *, solver: Any = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a project's review: solve what its evidence no longer matches, or import attested evidence.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Project handoff:\n"
            "  Unpack .tubaproject with python -m tuba.project.package unpack,\n"
            "  then pass the folder containing model.py and\n"
            "  study.py. Keep all referenced helpers, CAD and data beside the source.\n"
            "  Matching verified evidence/<operation>/ is reused; missing or stale\n"
            "  operations require Code_Aster. --force requests a new solve.\n\n"
            "Review handoff:\n"
            "  Share the complete scene.json bundle written by the study, including\n"
            "  geometry, reports, metadata and staged solver artifacts. View it with\n"
            "  python -m tuba.visualization.viewer <bundle-folder> --open.\n\n"
            "Guide: docs/content/project-sharing.md (Share and open a project)."
        ),
    )
    parser.add_argument("project", help="Folder holding model.py and study.py")
    parser.add_argument("--output", required=True, type=Path, help="Directory to write the review into")
    parser.add_argument("--artifact-dir", type=Path, help="Import complete attested evidence instead of solving (one operation folder, or a parent containing all study operations)")
    parser.add_argument("--force", action="store_true", help="Solve again even if matching evidence exists")
    parser.add_argument("--study", default=STUDY_SCRIPT, help="Study file inside the project (default: study.py)")
    args = parser.parse_args(argv)
    project = load_project(args.project)
    if not (project.root / args.study).is_file():
        parser.error(f"{project.root} has no {args.study}.")
    try:
        settings = project.load_settings(args.study)
    except ValueError as exc:
        parser.error(f"{args.study}: {exc}")
    operations = settings.operations
    namespace = project.run_model()
    from tuba.project.claim import SolveBusy
    from tuba.project.solve import solve_project, verify_project

    artifact_dir = args.artifact_dir
    try:
        if artifact_dir is None and operations:
            from tuba.project.evidence import study_artifact_dir

            outcome = solve_project(project, namespace, study_file=args.study, force=args.force, solver=solver)
            report = outcome.verification
            artifact_dir = study_artifact_dir(project.root, operations)
        else:
            report = verify_project(project, namespace)
            if artifact_dir is not None:
                from tuba.project.study import import_study_evidence

                import_study_evidence(namespace, settings, artifact_dir)
    except (ValueError, SolveBusy) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if settings.build_review is None:
        parser.error(f"{args.study} defines no build_review(namespace, output, ...).")
    try:
        root = settings.build_review(namespace, args.output, artifact_dir=artifact_dir)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(root)
    return 0
