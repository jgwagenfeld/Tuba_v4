"""Publish the connected model as a model-only review: nothing here is solved."""

from pathlib import Path

from examples.imported_component_mixed_system import run_demo

LOAD_CASES = ()
SOLVER_OPTIONS: dict = {}
ARTIFACT_DIR = None
VOLUME_EXPORT = None


def build_review(namespace, output, *, artifact_dir=None, force=False):
    summary = run_demo(namespace["SOURCE"], output_root=output, export_study=False, model=namespace["model"])
    return Path(summary["scene_dir"])
