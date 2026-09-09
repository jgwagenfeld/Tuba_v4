import json
import os
from dataclasses import FrozenInstanceError
from importlib import import_module
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from scripts import build_pages


REQUIRED = {
    "index.html",
    "setup.html",
    "tutorial.html",
    "reference/public-api.html",
    "architecture/visualization.html",
    "commands.html",
    "overview.html",
    "viewer/index.html",
    "viewer/bundles.json",
    "viewer/autorouted-expansion-loop/scene.json",
    "viewer/licenses/font-notices.txt",
    "viewer/licenses/OFL-1.1.txt",
    "viewer/code-aster-review/scene.json",
    "viewer/elements-supports-review/scene.json",
    "viewer/imported_component_mixed_demo/scene.json",
    "viewer/native-friction-review/scene.json",
    "viewer/pipe-tee-volume-review/scene.json",
    "viewer/profile-orientation-review/scene.json",
    "viewer/support-rack-review/scene.json",
    "notebooks/10_interactive_postprocessor.ipynb",
    ".nojekyll",
}
OFFICIAL_BUNDLES = [
    "autorouted-expansion-loop",
    "code-aster-review",
    "elements-supports-review",
    "gmsh-tee-mesh-review",
    "guyed-mast-review",
    "imported_component_mixed_demo",
    "native-friction-review",
    "pipe-tee-volume-review",
    "profile-orientation-review",
    "support-rack-review",
]
# OFFICIAL_BUNDLES above stays written out by hand on purpose: it is the one
# place that says which reviews are published, so adding or losing one has to
# be a deliberate edit here. Which of them reach Pages is a property of the
# catalog, though, so that is read rather than re-implemented as a filter.
PAGES_BUNDLES = list(build_pages.PAGES_BUNDLE_IDS)


def test_official_gallery_records_drive_pages_ids_and_required_scenes():
    official_gallery = import_module("scripts.official_gallery")
    galleries = official_gallery.OFFICIAL_GALLERIES
    pages = tuple(gallery for gallery in galleries if "pages" in gallery.audiences)

    assert isinstance(galleries, tuple)
    assert tuple(gallery.id for gallery in galleries) == tuple(OFFICIAL_BUNDLES)
    assert build_pages.PAGES_BUNDLE_IDS == tuple(gallery.id for gallery in pages)
    assert {
        required
        for required in build_pages._PAGES_REQUIRED_FILES
        if required.startswith("viewer/") and required.endswith("/scene.json")
    } == {f"viewer/{gallery.id}/scene.json" for gallery in pages}

    with pytest.raises(FrozenInstanceError):
        galleries[0].profile = "model-review"


def test_public_gallery_keeps_the_unsolved_tee_as_a_dev_diagnostic():
    pages = {
        gallery.id
        for gallery in import_module("scripts.official_gallery").OFFICIAL_GALLERIES
        if "pages" in gallery.audiences
    }

    assert "gmsh-tee-mesh-review" not in pages
    assert "pipe-tee-volume-review" in pages


def test_contact_gallery_rejects_a_missing_shoe_increment():
    from tuba.solver.base import ContactResult

    contact = ContactResult("S1", "N1", "sticking", (0, 1, 0), 0,
                            (0, 0, 0), 0, (0, 0, 0), (0, 0, 0), 0, None, "solver")
    overlays, fields = [], []
    for instant in (0, 1):
        state_id = f"state:{instant}"
        overlays.append({"kind": "result_state", "data": {
            "id": state_id, "metadata": {"pseudo_time": instant},
            "contact_results": {"S1": contact.to_dict()},
        }})
        families = ["displacement"] if instant == 0 else ["displacement", "reaction_force", "reaction_moment"]
        for family in families:
            overlay_id = f"overlay:{state_id}:{family}"
            overlays.append({"id": overlay_id, "kind": "solver_result", "data": {
                "result_type": family, "result_state_id": state_id, "load_case": "Cold",
                "values": {"N1": 0},
            }})
            fields.append({"id": overlay_id.replace("overlay:", "field:", 1),
                           "overlay_id": overlay_id, "result_state_id": state_id,
                           "load_case": "Cold", "components": ["magnitude"]})
    scene = {"overlays": overlays, "result_fields": fields}
    build_pages._validate_contact_result_fields(scene)
    states = [overlay["data"] for overlay in overlays if overlay["kind"] == "result_state"]
    states[1]["contact_results"].clear()
    with pytest.raises(ValueError, match="missing a shoe increment"):
        build_pages._validate_contact_result_fields(scene)


def _project_tree(root: Path) -> None:
    viewer = root / "tuba" / "visualization" / "_viewer"
    (viewer / "assets").mkdir(parents=True)
    (viewer / "assets" / "app.js").write_text("// viewer", encoding="utf-8")
    (viewer / "licenses").mkdir()
    (viewer / "licenses" / "font-notices.txt").write_text("font notices", encoding="utf-8")
    (viewer / "licenses" / "OFL-1.1.txt").write_text("OFL", encoding="utf-8")
    (viewer / "index.html").write_text("viewer", encoding="utf-8")
    (viewer / "bundles.json").write_text("[]\n", encoding="utf-8")
    notebook = root / "notebooks" / "10_interactive_postprocessor.ipynb"
    notebook.parent.mkdir()
    notebook.write_text("{}", encoding="utf-8")
    (root / "docs" / "content").mkdir(parents=True)


def _stub_builders(monkeypatch, root: Path, *, complete: bool = True) -> list[str]:
    events: list[str] = []

    def prepare() -> int:
        events.append("prepare")
        return 0

    def zensical(command, *, cwd, check, env=None):
        # The build photographs the assembled site rather than copying
        # committed images, so the shooter is one of the subprocesses now.
        if command[1].endswith("gallery-thumbnails.mjs"):
            assert env is not None and "TUBA_PAGES_SITE_ROOT" in env
            events.append("thumbnails")
            for gallery in build_pages.PAGES_GALLERIES:
                shot = Path(command[2]) / f"{gallery.id}.png"
                shot.parent.mkdir(parents=True, exist_ok=True)
                shot.write_bytes(bytes.fromhex("89504e470d0a1a0a") + b"0" * 6_000)
            return SimpleNamespace(returncode=0)
        assert command[1:] == [
            "run",
            "--locked",
            "--group",
            "docs",
            "--extra",
            "code-aster-rmed",
            "zensical",
            "build",
            "--clean",
            "--strict",
        ]
        assert Path(cwd) == root
        assert check is True
        events.append("zensical")
        site = root / ".build" / "zensical-site"
        for relative in (
            "index.html",
            "setup.html",
            "tutorial.html",
            "reference/public-api.html",
            "architecture/visualization.html",
        ):
            target = site / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(relative, encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    def examples(viewer_root, *, audience):
        assert audience == "pages"
        assert not (root / "viewer" / "public").exists()
        events.append("examples")
        bundle_ids = PAGES_BUNDLES if complete else PAGES_BUNDLES[:1]
        for bundle_id in bundle_ids:
            bundle = viewer_root / bundle_id
            bundle.mkdir()
            (bundle / "scene.json").write_text("{}", encoding="utf-8")
        return tuple(bundle_ids)

    real_catalog = build_pages.write_bundle_catalog

    def catalog(viewer_root, bundle_ids):
        events.append("catalog")
        return real_catalog(viewer_root, bundle_ids)

    monkeypatch.setattr(build_pages, "ROOT", root)
    monkeypatch.setattr(build_pages, "prepare_release", SimpleNamespace(main=prepare), raising=False)
    monkeypatch.setattr(build_pages, "subprocess", SimpleNamespace(run=zensical), raising=False)
    monkeypatch.setattr(build_pages, "os", os, raising=False)
    monkeypatch.setattr(build_pages, "build_examples", examples)
    monkeypatch.setattr(build_pages, "write_bundle_catalog", catalog)
    return events


def test_pages_build_assembles_exact_validated_tree_in_order(tmp_path, monkeypatch):
    root = tmp_path / "project"
    _project_tree(root)
    events = _stub_builders(monkeypatch, root)
    output = tmp_path / "site"

    build_pages.assemble_pages(output)

    assert REQUIRED <= {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }
    assert [
        entry["id"]
        for entry in json.loads((output / "viewer" / "bundles.json").read_text(encoding="utf-8"))
    ] == PAGES_BUNDLES
    assert sorted(
        path.name
        for path in (output / "viewer").iterdir()
        if path.is_dir() and (path / "scene.json").is_file()
    ) == PAGES_BUNDLES
    for redirect, target in {
        "commands.html": "reference/index.html",
        "overview.html": "architecture/index.html",
    }.items():
        html = (output / redirect).read_text(encoding="utf-8")
        assert f'http-equiv="refresh" content="0; url={target}"' in html
        assert f'rel="canonical" href="{target}"' in html
    assert events == ["prepare", "zensical", "examples", "catalog", "thumbnails"]


def test_pages_build_keeps_existing_output_when_complete_tree_validation_fails(tmp_path, monkeypatch):
    root = tmp_path / "project"
    _project_tree(root)
    _stub_builders(monkeypatch, root, complete=False)
    output = tmp_path / "site"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("original", encoding="utf-8")

    with pytest.raises(ValueError, match="Pages tree is incomplete"):
        build_pages.assemble_pages(output)

    assert marker.read_text(encoding="utf-8") == "original"
    assert {path.name for path in output.iterdir()} == {"keep.txt"}


def test_pages_output_replacement_removes_backup_after_success(tmp_path):
    output = tmp_path / "site"
    output.mkdir()
    (output / "old.txt").write_text("original", encoding="utf-8")
    staged = tmp_path / "staged"
    staged.mkdir()
    (staged / "new.txt").write_text("replacement", encoding="utf-8")

    build_pages._replace_pages_output(staged, output)

    assert (output / "new.txt").read_text(encoding="utf-8") == "replacement"
    assert not (output / "old.txt").exists()
    assert not staged.exists()
    assert list(tmp_path.glob(".site.backup-*")) == []


def test_pages_build_restores_existing_output_when_final_rename_fails(tmp_path, monkeypatch):
    root = tmp_path / "project"
    _project_tree(root)
    _stub_builders(monkeypatch, root)
    output = tmp_path / "site"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("original", encoding="utf-8")
    real_replace = os.replace
    calls = 0

    def fail_new_tree(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("rename blocked")
        return real_replace(source, destination)

    monkeypatch.setattr(build_pages.os, "replace", fail_new_tree)

    with pytest.raises(OSError, match="rename blocked"):
        build_pages.assemble_pages(output)

    assert marker.read_text(encoding="utf-8") == "original"
    assert calls == 3
    assert list(tmp_path.glob(".site.backup-*")) == []


def test_pages_output_replacement_retains_original_when_install_and_rollback_fail(tmp_path, monkeypatch):
    output = tmp_path / "site"
    output.mkdir()
    (output / "keep.txt").write_text("original", encoding="utf-8")
    staged = tmp_path / "staged"
    staged.mkdir()
    (staged / "new.txt").write_text("replacement", encoding="utf-8")
    real_replace = os.replace
    calls = 0

    def fail_install_and_rollback(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("install blocked")
        if calls == 3:
            raise OSError("rollback blocked")
        return real_replace(source, destination)

    monkeypatch.setattr(build_pages.os, "replace", fail_install_and_rollback)

    with pytest.raises(RuntimeError, match="original retained at") as raised:
        build_pages._replace_pages_output(staged, output)

    backups = list(tmp_path.glob(".site.backup-*"))
    assert len(backups) == 1
    backup = backups[0]
    assert (backup / "keep.txt").read_text(encoding="utf-8") == "original"
    assert str(backup) in str(raised.value)
    assert "install blocked" in str(raised.value)
    assert "rollback blocked" in str(raised.value)
    assert isinstance(raised.value.__cause__, OSError)
    assert "rollback blocked" in str(raised.value.__cause__)
    assert "install blocked" in str(raised.value.__cause__.__context__)


@pytest.mark.parametrize(
    "dangerous",
    [
        build_pages.ROOT,
        Path.home(),
        Path(build_pages.ROOT.anchor),
        build_pages.ROOT / "docs" / "content",
        build_pages.ROOT / "viewer" / "public",
    ],
)
def test_pages_build_rejects_dangerous_output_before_running_builders(dangerous, monkeypatch):
    monkeypatch.setattr(
        build_pages,
        "prepare_release",
        SimpleNamespace(main=lambda: pytest.fail("builder ran before output validation")),
        raising=False,
    )

    with pytest.raises(ValueError, match="Refusing to replace protected Pages output"):
        build_pages.assemble_pages(dangerous)


def test_source_script_is_held_to_the_bundle_portability_rules(tmp_path):
    """The published .py is text, so the JSON scanner never reaches it alone."""
    (tmp_path / "source.py").write_text(
        'ARTIFACTS = "C:/Users/someone/secret/notebooks"\n', encoding="utf-8"
    )

    with pytest.raises(ValueError, match="non-portable path reference"):
        build_pages._validate_source_script(tmp_path, {"source_uri": "source.py"})


def test_source_script_declaration_must_resolve(tmp_path):
    with pytest.raises(ValueError, match="Referenced bundle file is missing"):
        build_pages._validate_source_script(tmp_path, {"source_uri": "source.py"})


def test_bundle_without_a_source_script_is_accepted(tmp_path):
    build_pages._validate_source_script(tmp_path, {})


def test_every_published_gallery_can_explain_itself():
    """A card is the first thing a new reader sees; none may ship blank.

    OfficialGallery enforces this at construction, so reaching this assertion
    at all means the whole published set was declared publishable. The loop
    stays as the statement of what publishable means.
    """
    for gallery in build_pages.PAGES_GALLERIES:
        assert gallery.title.strip(), f"{gallery.id} has no title"
        assert gallery.question.strip().endswith("?"), (
            f"{gallery.id} must lead with an engineering question, not a label"
        )
        assert len(gallery.summary.split()) >= 10, f"{gallery.id} summary is too thin"
        assert gallery.evidence, f"{gallery.id} has no evidence badge"


def _publishable_card(**overrides):
    OfficialGallery = import_module("scripts.official_gallery").OfficialGallery
    defaults = dict(
        title="Hot line expansion loop",
        question="Where does a hot line move, and what does it reach?",
        summary=" ".join(["a"] * 12),
        elements=("TUYAU_3M",),
    )
    return OfficialGallery(
        "demo",
        frozenset({"pages"}),
        "engineering-review",
        lambda _bundle, _artifacts: None,
        **{**defaults, **overrides},
    )


def test_a_card_that_cannot_introduce_its_review_is_rejected_where_it_is_written():
    """The rule lives with the data, not only in this file.

    Nine cards once had their questions replaced with labels - "Thermal
    displacement and clearances" over "Where does a hot line move, and what
    does it reach?" - and nothing objected until the full suite ran much later.
    The constructor now refuses, so the copy fails on the next import of the
    module it was written in.
    """
    assert _publishable_card().question.endswith("?")

    with pytest.raises(ValueError, match="not a label"):
        _publishable_card(question="Thermal displacement and clearances")

    with pytest.raises(ValueError, match="too thin"):
        _publishable_card(summary="Two words")

    with pytest.raises(ValueError, match="needs a title"):
        _publishable_card(title="   ")
