"""Projects: a folder holding ``model.py`` and, optionally, ``study.py``.

``model.py`` builds the model at module level and binds it to ``model``; nothing
else happens there. ``study.py`` says how that model is solved and reviewed. The
gallery build, the solver refresh, the studio and the tests all load projects
through this module, so none of them can drift into its own copy of a model.

Build a project's review from the command line (from the repository root)::

    python -m tuba.project examples/native-friction-review --output .build/friction
    python -m tuba.project examples/native-friction-review --output .build/friction \\
        --artifact-dir examples/native-friction-review/evidence/Cold

The first form solves the study's operations into the project's ``evidence/``, reusing evidence that
still matches the model and study (``--force`` solves again). The second imports the folder it names.
"""

from __future__ import annotations

import argparse
import runpy
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tuba.model import TubaModel

MODEL_SCRIPT = "model.py"
STUDY_SCRIPT = "study.py"


def run_model_script(path: str | Path) -> dict[str, Any]:
    """Run a model script as ``__main__`` and return its globals.

    ``__main__`` is what links 3D objects to script lines. The script binds
    ``model`` to a TubaModel, or defines ``build_model()`` returning one.
    """
    script = Path(path)
    namespace = runpy.run_path(str(script), run_name="__main__")
    model = namespace.get("model")
    if model is None and callable(namespace.get("build_model")):
        model = namespace["model"] = namespace["build_model"]()
    if not isinstance(model, TubaModel):
        raise TypeError(
            f"{script.name} must bind 'model' to a TubaModel (or define build_model()), "
            f"got {type(model).__name__}."
        )
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
        return SimpleNamespace(**runpy.run_path(str(path), run_name=f"tuba_study.{self.name}.{path.stem}"))


def load_project(root: str | Path) -> Project:
    project = Project(Path(root).resolve())
    if not project.model_path.is_file():
        raise FileNotFoundError(f"{project.root} has no {MODEL_SCRIPT}.")
    return project


def main(argv: list[str] | None = None, *, solver: Any = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a project's review: solve what its evidence no longer matches, or import attested evidence."
    )
    parser.add_argument("project", help="Folder holding model.py and study.py")
    parser.add_argument("--output", required=True, type=Path, help="Directory to write the review into")
    parser.add_argument("--artifact-dir", type=Path, help="Import this attested evidence instead of solving")
    parser.add_argument("--force", action="store_true", help="Solve again even if matching evidence exists")
    parser.add_argument("--study", default=STUDY_SCRIPT, help="Study file inside the project (default: study.py)")
    args = parser.parse_args(argv)
    project = load_project(args.project)
    study = project.load_study(args.study)
    if study is None:
        parser.error(f"{project.root} has no {args.study}.")
    from tuba.project.study import study_settings

    try:
        operations = study_settings(study).operations
    except ValueError as exc:
        parser.error(f"{args.study}: {exc}")
    namespace = project.run_model()
    artifact_dir = args.artifact_dir
    if artifact_dir is None and operations:
        from tuba.project.claim import SolveBusy
        from tuba.project.evidence import study_artifact_dir
        from tuba.project.solve import solve_project

        try:
            solve_project(project, namespace, study_file=args.study, force=args.force, solver=solver)
        except SolveBusy as exc:
            print(exc, file=sys.stderr)
            return 1
        artifact_dir = study_artifact_dir(project.root, operations)
    root = study.build_review(namespace, args.output, artifact_dir=artifact_dir)
    print(root)
    return 0
