"""Authoritative official viewer-gallery records and producers."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable

from examples.code_aster_artifact_review import (
    build_autorouted_expansion_model,
    build_model,
    build_support_rack_model,
    run_example,
)
from examples.code_aster_tee_volume_review import (
    build_tee_volume_model,
    run_example as run_tee_volume_example,
)
from examples.imported_component_mixed_system import run_demo


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class OfficialGallery:
    id: str
    audiences: frozenset[str]
    profile: str
    bundle_producer: Callable[[Path, Path | None], None]
    artifact_dir: Path | None = None
    refresh_producer: Callable[[Path], tuple[Any, str]] | None = None
    volume_export: bool = False


def _replace_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise ValueError(f"Producer did not create a review scene: {source}")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def _build_code_aster_review(destination: Path, artifacts: Path | None) -> None:
    with TemporaryDirectory(prefix="tuba-official-code-aster-") as temporary:
        produced = Path(temporary) / "code-aster-review"
        run_example(produced, artifact_dir=artifacts)
        _replace_tree(produced / "review_scene", destination)


def _build_model_review(destination: Path, _artifacts: Path | None) -> None:
    with TemporaryDirectory(prefix="tuba-official-model-review-") as temporary:
        produced = Path(temporary) / "imported-component"
        run_demo(
            Path("examples/assets/imported_component_demo.stl"),
            output_root=produced,
            export_study=False,
        )
        _replace_tree(produced / "review_scene", destination)


def _build_autorouted_review(destination: Path, artifacts: Path | None) -> None:
    with TemporaryDirectory(prefix="tuba-official-autorouted-") as temporary:
        root = Path(temporary)
        model, route_result = build_autorouted_expansion_model(root / "routing")
        produced = root / "review"
        run_example(
            produced,
            artifact_dir=artifacts,
            model=model,
            scene_id="scene:autorouted_expansion_loop",
            title="Solved autorouted expansion-loop review",
            route_results=[route_result],
        )
        _replace_tree(produced / "review_scene", destination)


def _build_support_rack_review(destination: Path, artifacts: Path | None) -> None:
    with TemporaryDirectory(prefix="tuba-official-support-rack-") as temporary:
        produced = Path(temporary) / "review"
        run_example(
            produced,
            artifact_dir=artifacts,
            model=build_support_rack_model(),
            scene_id="scene:support_rack_review",
            title="Solved support-rack load-path review",
            include_load_paths=True,
        )
        _replace_tree(produced / "review_scene", destination)


def _build_tee_volume_review(destination: Path, artifacts: Path | None) -> None:
    with TemporaryDirectory(prefix="tuba-official-tee-volume-") as temporary:
        produced = Path(temporary) / "review"
        run_tee_volume_example(produced, artifact_dir=artifacts)
        _replace_tree(produced / "review_scene", destination)


def _autorouted_refresh(scratch_root: Path) -> tuple[Any, str]:
    model, _route_result = build_autorouted_expansion_model(scratch_root / "routing")
    return model, "Hot"


def _code_aster_refresh(_scratch_root: Path) -> tuple[Any, str]:
    return build_model(), "Operating"


def _tee_volume_refresh(_scratch_root: Path) -> tuple[Any, str]:
    return build_tee_volume_model(), "Operating"


def _support_rack_refresh(_scratch_root: Path) -> tuple[Any, str]:
    return build_support_rack_model(), "Operating"


OFFICIAL_GALLERIES = (
    OfficialGallery(
        "autorouted-expansion-loop",
        frozenset({"dev", "pages"}),
        "engineering-review",
        _build_autorouted_review,
        ROOT / "notebooks" / "code_aster_results" / "autorouted_expansion_hot",
        _autorouted_refresh,
    ),
    OfficialGallery(
        "code-aster-review",
        frozenset({"dev", "pages"}),
        "engineering-review",
        _build_code_aster_review,
        ROOT / "notebooks" / "code_aster_results" / "viz_gallery_operating",
        _code_aster_refresh,
    ),
    OfficialGallery(
        "imported_component_mixed_demo",
        frozenset({"dev", "pages"}),
        "model-review",
        _build_model_review,
    ),
    OfficialGallery(
        "pipe-tee-volume-review",
        frozenset({"dev", "pages"}),
        "volume-engineering-review",
        _build_tee_volume_review,
        ROOT / "notebooks" / "code_aster_results" / "tee_volume_operating",
        _tee_volume_refresh,
        True,
    ),
    OfficialGallery(
        "support-rack-review",
        frozenset({"dev", "pages"}),
        "engineering-review",
        _build_support_rack_review,
        ROOT / "notebooks" / "code_aster_results" / "support_rack_operating",
        _support_rack_refresh,
    ),
)
