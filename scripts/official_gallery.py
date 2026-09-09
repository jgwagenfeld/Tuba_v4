"""Authoritative official viewer-gallery records and producers."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
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
from examples.elements_supports_review import (
    build_elements_supports_model,
    run_example as run_elements_supports_example,
)
from examples.gmsh_tee_mesh_review import run_example as run_gmsh_tee_mesh_example
from examples.code_aster_friction_review import LOAD_PATH, build_friction_comparison_model, build_friction_review
from examples.code_aster_profile_orientation import CASES as PROFILE_CASES, build_model as build_profile_model, run_example as run_profile_example
from examples.imported_component_mixed_system import run_demo
from tuba.rules import SupportSpacingRule
from tuba.visualization import SceneBuildOptions


ROOT = Path(__file__).resolve().parents[1]

#: Clearance band applied around the bare pipe radius for the autorouted
#: gallery's operating clash check, and for the envelope geometry published
#: beside it so the reviewer sees the band the check used.
#:
#: This is NOT the router's reserved corridor. The router reserves
#: ``OD/2 + insulation_thickness + clearance`` (0.194 m for this line), while
#: the model carries no insulation spec, so the published envelope is
#: ``OD/2 + 0.10`` = 0.144 m. The two numbers answer different questions and
#: are deliberately not unified here.
_AUTOROUTED_CLEARANCE_M = 0.10


#: How much evidence a profile actually carries, in the reviewer's words rather
#: than the solver's. This is the honest half of hiding the solver: the badge
#: never disappears, it just stops being the headline.
PROFILE_EVIDENCE = {
    "engineering-review": "Results",
    "volume-engineering-review": "Results",
    "contact-engineering-review": "Results",
    "beam-engineering-review": "Results",
    "mesh-review": "Mesh only - no results",
    "model-review": "Model only - no results",
}


@dataclass(frozen=True)
class OfficialGallery:
    id: str
    audiences: frozenset[str]
    profile: str
    bundle_producer: Callable[[Path, Path | None], None]
    artifact_dir: Path | None = None
    refresh_producer: Callable[[Path], tuple[Any, str]] | None = None
    volume_export: bool = False
    #: Keyword-only and undefaulted on purpose: a gallery that cannot say what
    #: question it answers has no business being published.
    title: str = field(kw_only=True)
    question: str = field(kw_only=True)
    summary: str = field(kw_only=True)
    solver_options: dict[str, Any] = field(default_factory=dict, kw_only=True)
    refresh_load_cases: tuple[str, ...] = field(default=(), kw_only=True)

    def __post_init__(self) -> None:
        """Reject a card that cannot introduce its review.

        The gallery is the front door for a reader who has never heard of Tuba,
        and it describes reviews by the engineering question each one answers
        rather than by the study that produced it - so the question leading the
        card is what the card is for, not a house style.

        Checked here rather than only in a test because the copy is written in
        this file: a label pasted over a question fails on the next import,
        with the id and the offending string, instead of surviving review and
        turning up much later as one assertion in the full suite.
        """
        if not self.title.strip():
            raise ValueError(f"{self.id}: a gallery card needs a title")
        if not self.question.strip().endswith("?"):
            raise ValueError(
                f"{self.id}: a card leads with the engineering question it answers, "
                f"not a label - got {self.question!r}"
            )
        if len(self.summary.split()) < 10:
            raise ValueError(
                f"{self.id}: the summary is too thin to explain the review "
                f"({len(self.summary.split())} words)"
            )
        if self.profile not in PROFILE_EVIDENCE:
            raise ValueError(
                f"{self.id}: no evidence badge is defined for profile {self.profile!r}"
            )

    @property
    def evidence(self) -> str:
        return PROFILE_EVIDENCE[self.profile]

    @property
    def thumbnail(self) -> str:
        return f"gallery/{self.id}.png"

    def to_catalog_entry(self) -> dict[str, str]:
        """The record the viewer renders a gallery card from."""
        return {
            "id": self.id,
            "title": self.title,
            "question": self.question,
            "summary": self.summary,
            "evidence": self.evidence,
            "thumbnail": self.thumbnail,
        }


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


def _build_elements_supports_review(destination: Path, artifacts: Path | None) -> None:
    with TemporaryDirectory(prefix="tuba-official-elements-supports-") as temporary:
        produced = Path(temporary) / "review"
        run_elements_supports_example(produced, artifact_dir=artifacts)
        _replace_tree(produced / "review_scene", destination)


def _build_gmsh_tee_mesh_review(destination: Path, _artifacts: Path | None) -> None:
    with TemporaryDirectory(prefix="tuba-official-gmsh-mesh-") as temporary:
        produced = Path(temporary) / "gmsh-tee-mesh"
        run_gmsh_tee_mesh_example(produced)
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
            clash_clearance_m=_AUTOROUTED_CLEARANCE_M,
            scene_options=SceneBuildOptions(
                include_physical_envelopes=True,
                clearance_m=_AUTOROUTED_CLEARANCE_M,
                include_cost_overlays=True,
                # The default metric is insulation_cost, which is identically
                # zero for a line with no insulation spec. Mass is a quantity
                # this model actually carries.
                cost_metric="total_mass_kg",
            ),
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
            # An engineer-authored project limit, not a code requirement: the
            # 4 m rack span exceeds it, so the review carries a design-rule
            # annotation beside its solver evidence.
            model_rules=[SupportSpacingRule(max_span_m=3.5)],
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


def _elements_supports_refresh(_scratch_root: Path) -> tuple[Any, str]:
    return build_elements_supports_model(), "LoadCase1"


def _tee_volume_refresh(_scratch_root: Path) -> tuple[Any, str]:
    return build_tee_volume_model(), "Operating"


def _support_rack_refresh(_scratch_root: Path) -> tuple[Any, str]:
    return build_support_rack_model(), "Operating"


def _build_friction_review(destination: Path, artifacts: Path | None) -> None:
    with TemporaryDirectory(prefix="tuba-official-friction-") as temporary:
        root = Path(temporary)
        build_friction_review(root, artifact_dir=artifacts)
        _replace_tree(root, destination)


def _friction_refresh(_scratch_root: Path) -> tuple[Any, str]:
    return build_friction_comparison_model(), LOAD_PATH[-1]


def _build_profile_review(destination: Path, artifacts: Path | None) -> None:
    with TemporaryDirectory(prefix="tuba-official-profiles-") as temporary:
        produced = Path(temporary)
        run_profile_example(produced, artifact_dir=artifacts)
        _replace_tree(produced / "review_scene", destination)


def _profile_refresh(_scratch_root: Path) -> tuple[Any, str]:
    return build_profile_model(), PROFILE_CASES[0]


OFFICIAL_GALLERIES = (
    OfficialGallery(
        "autorouted-expansion-loop",
        frozenset({"dev", "pages"}),
        "engineering-review",
        _build_autorouted_review,
        ROOT / "notebooks" / "code_aster_results" / "autorouted_expansion_hot",
        _autorouted_refresh,
        title="Hot line expansion loop",
        question="Where does a hot line move, and what does it reach?",
        summary=(
            "A 180 C line routed around equipment with an automatically selected expansion loop. "
            "The review shows thermal displacement and clearance violations around a cable tray."
        ),
    ),
    OfficialGallery(
        "code-aster-review",
        frozenset({"dev", "pages"}),
        "engineering-review",
        _build_code_aster_review,
        ROOT / "notebooks" / "code_aster_results" / "viz_gallery_operating",
        _code_aster_refresh,
        title="Anchored line with two bends",
        question="What happens to a pressurised line held at both ends?",
        summary=(
            "A pressurised line with two anchors and two bends. The review shows displacement, "
            "pipe-wall stress, and anchor reactions from one Code_Aster run."
        ),
    ),
    OfficialGallery(
        "elements-supports-review",
        frozenset({"dev", "pages"}),
        "engineering-review",
        _build_elements_supports_review,
        ROOT / "notebooks" / "code_aster_results" / "elements_supports_loadcase1",
        _elements_supports_refresh,
        title="Mixed elements and supports",
        question="Do bars, cables and spring supports survive the trip to the solver?",
        summary=(
            "Pipe, beam, bar, cable and rectangular members in one model, with spring, rest, "
            "anchor and partly released supports. The review shows the element and support "
            "definitions alongside the imported Code_Aster results."
        ),
    ),
    OfficialGallery(
        "gmsh-tee-mesh-review",
        frozenset({"dev"}),
        "mesh-review",
        _build_gmsh_tee_mesh_review,
        title="Tee junction mesh",
        question="What does the analysis actually discretise at a branch?",
        summary=(
            "A conformal quadratic-hexahedral wall mesh for a header and branch. "
            "This example shows mesh geometry only, with no solver results."
        ),
    ),
    OfficialGallery(
        "imported_component_mixed_demo",
        frozenset({"dev", "pages"}),
        "model-review",
        _build_model_review,
        title="Imported equipment connection",
        question="How does a supplied component join an authored line?",
        summary=(
            "A STEP/STL component placed beside Tuba pipework, showing connection ports, "
            "local frames and coupling. This example contains geometry only, with no solver results."
        ),
    ),
    OfficialGallery(
        "native-friction-review",
        frozenset({"dev", "pages"}),
        "contact-engineering-review",
        _build_friction_review,
        ROOT / "notebooks" / "code_aster_results" / "native-friction-review",
        _friction_refresh,
        title="Pipe-shoe friction comparison",
        question="How does friction change the same pipe and load path?",
        summary=(
            "Two disconnected, identical pipes share one nonlinear Code_Aster run and load history. "
            "The review compares friction coefficients of 0 and 0.3 through heating, cooling, lift-off and reseating."
        ),
        solver_options={"pipe_modelization": "POU_D_T", "load_path": LOAD_PATH, "load_step": 0.1},
    ),
    OfficialGallery(
        "pipe-tee-volume-review",
        frozenset({"dev", "pages"}),
        "volume-engineering-review",
        _build_tee_volume_review,
        ROOT / "notebooks" / "code_aster_results" / "tee_volume_operating",
        _tee_volume_refresh,
        True,
        title="3D solid tee",
        question="Does stress concentrate where the branch meets the header?",
        summary=(
            "A tee meshed with 3D solid elements. The review shows the stress distribution around the branch junction."
        ),
    ),
    OfficialGallery(
        "profile-orientation-review",
        frozenset({"dev", "pages"}),
        "beam-engineering-review",
        _build_profile_review,
        ROOT / "notebooks" / "code_aster_results" / "profile-orientation-review",
        _profile_refresh,
        refresh_load_cases=PROFILE_CASES,
        title="I-section orientation and local axes",
        question="How do section orientation and local axes change bending?",
        summary=(
            "Three identical I-section cantilevers at 0, 45 and 90 degrees in one model. "
            "The review compares global and local loading, deformed profiles, and section rotations "
            "relative to the original local axes."
        ),
    ),
    OfficialGallery(
        "support-rack-review",
        frozenset({"dev", "pages"}),
        "engineering-review",
        _build_support_rack_review,
        ROOT / "notebooks" / "code_aster_results" / "support_rack_operating",
        _support_rack_refresh,
        title="Pipe on a support rack",
        question="What do the supports and the steel underneath actually carry?",
        summary=(
            "An I-beam rack and pipe analysed together under gravity, 1.5 MPa internal pressure, "
            "and a temperature increase from 20 C to 180 C, with no imposed nodal forces. "
            "The review shows support reactions and a support-spacing check."
        ),
    ),
)
