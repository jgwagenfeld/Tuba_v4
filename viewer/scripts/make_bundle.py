#!/usr/bin/env python
"""Write a viewer example bundle ("recipe") into viewer/public/<name>/.

The viewer's example dropdown lists every public/ folder that contains a
scene.json (the vite plugin discovers them), so a bundle written here shows up
on the next browser refresh -- no code change.

Two sources:

  --model model.json   Geometry-only bundle from a saved TubaModel. No solver;
                       shows pipes/supports/loads but no results.

  --recipe recipe.py   Full control, for solved studies with results/mesh/review.
                       The file must define build() returning either:
                         - a VisualizationScene, or
                         - a dict {"scene": ..., "review": ..?, "title": ..?}
                       build() runs whatever Tuba code it needs (load a study,
                       assemble result_states / analysis_meshes, etc.) and hands
                       back the scene; this script just writes and places it.

Run from the repo root with the Tuba env active:

  python viewer/scripts/make_bundle.py --model piping_model.json --name my-recipe
  python viewer/scripts/make_bundle.py --recipe recipes/hot.py --name hot-case
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import sys
from pathlib import Path

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_DEFAULT_OUT = Path(__file__).resolve().parents[1] / "public"


def safe_name(name: str) -> str:
    """Return a validated bundle folder name, or raise ValueError.

    A name must be a single path segment: a stray slash or '..' would let the
    output escape public/ and write somewhere it should not.
    """
    if not _NAME_RE.match(name or ""):
        raise ValueError(
            f"Invalid bundle name {name!r}: use letters, digits, '-' and '_' only, "
            "starting with an alphanumeric."
        )
    return name


def bundle_spec_from(result: object) -> tuple[object, object | None, str | None]:
    """Normalise a recipe's build() return into (scene, review, title)."""
    from tuba.visualization import VisualizationScene

    if isinstance(result, VisualizationScene):
        return result, None, None
    if isinstance(result, dict):
        scene = result.get("scene")
        if not isinstance(scene, VisualizationScene):
            raise TypeError("recipe build() dict must carry a VisualizationScene under 'scene'.")
        return scene, result.get("review"), result.get("title")
    raise TypeError(
        "recipe build() must return a VisualizationScene or a dict with a 'scene' key, "
        f"got {type(result).__name__}."
    )


def _scene_from_model(model_path: Path):
    from tuba.model import TubaModel
    from tuba.visualization import build_visualization_scene

    model = TubaModel.from_json(str(model_path))
    return build_visualization_scene(model), None, None


def _scene_from_recipe(recipe_path: Path):
    recipe_path = recipe_path.resolve()
    spec = importlib.util.spec_from_file_location("tuba_bundle_recipe", recipe_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not import recipe {recipe_path}.")
    module = importlib.util.module_from_spec(spec)
    # Let a recipe import helpers that live next to it, like a directly-run script.
    sys.path.insert(0, str(recipe_path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(recipe_path.parent))
    if not hasattr(module, "build"):
        raise AttributeError(f"Recipe {recipe_path} must define a build() function.")
    return bundle_spec_from(module.build())


def write_bundle(*, source: Path, is_recipe: bool, name: str, out_dir: Path, force: bool) -> Path:
    from tuba.visualization import write_scene_bundle
    from tuba.visualization.reporting_adapter import write_engineering_review_with_scene

    target = out_dir / safe_name(name)
    if target.exists():
        if not force:
            raise FileExistsError(f"{target} already exists; pass --force to overwrite.")
        shutil.rmtree(target)

    scene, review, title = _scene_from_recipe(source) if is_recipe else _scene_from_model(source)
    scene.validate()  # fail loudly here rather than as a blank viewport later

    if review is not None:
        write_engineering_review_with_scene(review, target, scene=scene, title=title)
    else:
        write_scene_bundle(scene, target)
    return target


def _selftest() -> None:
    assert safe_name("my-recipe_1") == "my-recipe_1"
    for bad in ["", "../etc", "a/b", "a\\b", ".hidden", "-lead"]:
        try:
            safe_name(bad)
        except ValueError:
            pass
        else:  # pragma: no cover - only trips if validation regresses
            raise AssertionError(f"expected {bad!r} to be rejected")

    from tuba.visualization import VisualizationScene

    scene = VisualizationScene(scene_id="s", model_id="m")
    assert bundle_spec_from(scene) == (scene, None, None)
    assert bundle_spec_from({"scene": scene, "title": "T"}) == (scene, None, "T")
    for bad in [42, {"review": None}]:
        try:
            bundle_spec_from(bad)
        except TypeError:
            pass
        else:  # pragma: no cover
            raise AssertionError(f"expected {bad!r} to be rejected")
    print("selftest ok")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a viewer example bundle into public/.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--model", type=Path, help="TubaModel JSON -> geometry-only bundle.")
    source.add_argument("--recipe", type=Path, help="Python file defining build() -> scene.")
    parser.add_argument("--name", help="Bundle folder name under the output dir.")
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT, help="Output dir (default viewer/public).")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing bundle.")
    parser.add_argument("--selftest", action="store_true", help="Run internal checks and exit.")
    args = parser.parse_args(argv)

    if args.selftest:
        _selftest()
        return 0
    if not args.name or not (args.model or args.recipe):
        parser.error("both --name and one of --model/--recipe are required")

    target = write_bundle(
        source=args.model or args.recipe,
        is_recipe=bool(args.recipe),
        name=args.name,
        out_dir=args.out,
        force=args.force,
    )
    print(f"Wrote {target}")
    print(f"View at: http://localhost:5173/?bundle={target.name}  (refresh the viewer; it appears in the dropdown)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
