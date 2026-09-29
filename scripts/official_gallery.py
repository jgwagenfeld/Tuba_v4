"""Authoritative official viewer-gallery records and producers."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from tuba.project import STUDY_SCRIPT, load_project

ROOT = Path(__file__).resolve().parents[1]


#: Every ``MODELISATION`` a card may declare, as produced by
#: :func:`tuba.solver.modelisation.modelisation_assignments`. A typo here would
#: otherwise ship as a chip nobody can look up.
ELEMENT_MODELISATIONS = frozenset({"TUYAU_3M", "POU_D_T", "3D", "BARRE", "CABLE", "DIS_TR", "DIS_T"})


#: Which profiles carry Code_Aster results, and which publish geometry only.
#:
#: This replaces a per-profile evidence *string*, which mapped four solved
#: profiles onto the single word "Results" - so twelve of thirteen cards wore the
#: same uppercase badge that said nothing, while the two cards with no results
#: behind them were visually identical to the eleven that had some. A grid of
#: thirteen cards must not imply thirteen analyses. The viewer now derives the
#: facts it prints from these flags plus the real case count, and a solved card
#: says how big it is rather than that it is.
PROFILE_SOLVED = {
    "engineering-review": True,
    "volume-engineering-review": True,
    "contact-engineering-review": True,
    "beam-engineering-review": True,
    "mesh-review": False,
    "model-review": False,
}

#: What a card with no results is, in the reviewer's words. Kept as a label
#: rather than dropped, so a geometry-only example still says what it is.
PROFILE_UNSOLVED_LABEL = {
    "mesh-review": "Mesh only",
    "model-review": "Model only",
}


@dataclass(frozen=True)
class OfficialGallery:
    id: str
    audiences: frozenset[str]
    profile: str
    bundle_producer: Callable[[Path, Path | None], None]
    artifact_dir: Path | None = None
    refresh_producer: Callable[[Path], tuple[Any, str]] | None = None
    #: Falsy for a line or beam study; the volume options (``element_ids``,
    #: ``max_element_size``) for one solved as 3D solids.
    volume_export: bool | dict[str, Any] = False
    #: Keyword-only and undefaulted on purpose: a gallery that cannot say what
    #: question it answers has no business being published.
    title: str = field(kw_only=True)
    question: str = field(kw_only=True)
    summary: str = field(kw_only=True)
    #: The Code_Aster ``MODELISATION`` names this review actually solves.
    #: Declared rather than derived: deriving would rebuild every gallery model
    #: on every catalog read, including the dev server's. The declaration is
    #: checked against the real models in
    #: ``test_declared_gallery_elements_match_the_models_they_publish``.
    elements: tuple[str, ...] = field(kw_only=True)
    solver_options: dict[str, Any] = field(default_factory=dict, kw_only=True)
    refresh_load_cases: tuple[str, ...] = field(default=(), kw_only=True)
    #: The example folder whose ``model.py`` this review is built from, relative to
    #: the repository root. The card tells a reader how to open it in the studio.
    project: str | None = field(default=None, kw_only=True)

    #: How many load cases Code_Aster solved. Read from the study, never guessed.
    #: ``None`` for a geometry-only example, which is what tells the viewer to say
    #: so on the card instead of implying an analysis exists.
    case_count: int | None = field(default=None, kw_only=True)

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
        if not self.elements:
            raise ValueError(
                f"{self.id}: a card must say which elements the review used"
            )
        unknown = sorted(set(self.elements) - ELEMENT_MODELISATIONS)
        if unknown:
            raise ValueError(f"{self.id}: unknown element modelisation(s) {unknown}")
        if self.profile not in PROFILE_SOLVED:
            raise ValueError(
                f"{self.id}: no solved flag is defined for profile {self.profile!r}"
            )
        # A card may not claim an analysis it does not have, nor deny one it
        # does. The two are checked here, next to the copy, because this is a
        # compliance claim on a published page and the failure mode is a grid
        # that implies thirteen solved reviews where two are geometry only.
        solved = PROFILE_SOLVED[self.profile]
        if solved and not self.case_count:
            raise ValueError(
                f"{self.id}: profile {self.profile!r} is a solved review but "
                f"declares no load cases - the card would claim results it cannot show"
            )
        if not solved and self.case_count:
            raise ValueError(
                f"{self.id}: profile {self.profile!r} publishes geometry only but "
                f"declares {self.case_count} load case(s) - the card would claim "
                f"results the bundle does not carry"
            )
        if not solved and self.summary and "no solver results" not in self.summary.lower():
            raise ValueError(
                f"{self.id}: a geometry-only example must say so in its summary, "
                f"so nobody opens it expecting a review"
            )

    @property
    def solved(self) -> bool:
        return PROFILE_SOLVED[self.profile]

    @property
    def thumbnail(self) -> str:
        return f"gallery/{self.id}.png"

    def to_catalog_entry(self) -> dict[str, Any]:
        """The record the viewer renders a gallery card from.

        ``solved`` and ``case_count`` are what the card's facts are built from.
        The viewer prints the case count, the element types and the solver, and
        says plainly when there is no analysis - rather than the single word
        "Results", which twelve of thirteen cards used to share.
        """
        entry = {
            "id": self.id,
            "title": self.title,
            "question": self.question,
            "summary": self.summary,
            "solved": self.solved,
            "case_count": self.case_count if self.solved else 0,
            "elements": list(self.elements),
            "thumbnail": self.thumbnail,
        }
        if not self.solved:
            entry["evidence"] = PROFILE_UNSOLVED_LABEL[self.profile]
        if self.project is not None:
            entry["project"] = self.project
        return entry


def _replace_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise ValueError(f"Producer did not create a review scene: {source}")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def _project_gallery(
    gallery_id: str,
    audiences: frozenset[str],
    profile: str,
    project: str,
    *,
    study: str = STUDY_SCRIPT,
    **card: Any,
) -> OfficialGallery:
    """A gallery built from an example project: ``examples/<project>/model.py`` and its study.

    The study is read here, which is cheap; models are only built when a bundle
    or a refresh is produced, never for a catalog read.
    """
    folder = load_project(ROOT / "examples" / project)
    config = folder.load_study(study)
    if config is None:
        raise ValueError(f"{gallery_id}: {folder.root} has no {study}.")
    cases = tuple(config.LOAD_CASES)

    def produce(destination: Path, artifacts: Path | None) -> None:
        with TemporaryDirectory(prefix=f"tuba-official-{gallery_id}-") as temporary:
            root = config.build_review(folder.run_model(), Path(temporary), artifact_dir=artifacts)
            _replace_tree(Path(root), destination)

    def refresh(_scratch_root: Path) -> tuple[Any, str]:
        return folder.run_model()["model"], cases[0]

    # The case count is the study's own LOAD_CASES, and it is only published when
    # the profile claims a solved review. A geometry-only example has cases in its
    # study too - it just never sends them to Code_Aster - so passing the count
    # unconditionally would be the lie the dataclass now refuses to carry.
    published_cases = len(cases) if PROFILE_SOLVED[profile] else None
    return OfficialGallery(
        gallery_id,
        audiences,
        profile,
        produce,
        config.ARTIFACT_DIR,
        refresh if published_cases else None,
        config.VOLUME_EXPORT or False,
        solver_options=dict(config.SOLVER_OPTIONS),
        refresh_load_cases=cases if len(cases) > 1 else (),
        project=f"examples/{project}",
        case_count=published_cases,
        **card,
    )


OFFICIAL_GALLERIES = (
    _project_gallery(
        "autorouted-expansion-loop",
        frozenset({"dev", "pages"}),
        "engineering-review",
        "autorouted-expansion-loop",
        title="Thermal expansion",
        elements=("TUYAU_3M", "DIS_T"),
        question="Where does a hot line move, and what does it reach?",
        summary=(
            "A 180 C line routed around equipment with an automatically selected expansion loop. "
            "The review shows thermal displacement and clearance violations around a cable tray."
        ),
    ),
    _project_gallery(
        "braced-rack-thermal-split",
        frozenset({"dev", "pages"}),
        "engineering-review",
        "braced-rack-thermal-split",
        title="Braced rack split",
        elements=("TUYAU_3M", "POU_D_T", "DIS_T"),
        question="Where does one hot line's growth go on a rack that is growing too?",
        summary=(
            "A DN250 line on a four-bay braced steel rack, anchored once at mid-run. One pipe at "
            "400 C grows at four times the rate of the steel beneath it, so the shoes slide and the "
            "end bays take the whole expansion. The review shows displacement, wall stress, the "
            "support reactions and the load path the sliding shoes actually carry."
        ),
    ),
    _project_gallery(
        "code-aster-review",
        frozenset({"dev", "pages"}),
        "engineering-review",
        "code-aster-review",
        title="Pipe bends",
        elements=("TUYAU_3M", "DIS_T"),
        question="What happens to a pressurised line held at both ends?",
        summary=(
            "A pressurised line with two anchors and two bends. The review shows displacement, "
            "pipe-wall stress, and anchor reactions from one Code_Aster run."
        ),
    ),
    _project_gallery(
        "elements-supports-review",
        frozenset({"dev", "pages"}),
        "engineering-review",
        "elements-supports-review",
        title="Elements and supports",
        elements=("TUYAU_3M", "POU_D_T", "BARRE", "CABLE", "DIS_TR", "DIS_T"),
        question="Do bars, cables and spring supports survive the trip to the solver?",
        summary=(
            "Pipe, beam, bar, cable and rectangular members in one model, with spring, rest, "
            "anchor and partly released supports. The review shows the element and support "
            "definitions alongside the imported Code_Aster results."
        ),
    ),
    _project_gallery(
        "gmsh-tee-mesh-review",
        frozenset({"dev"}),
        "mesh-review",
        # The same tee as the 3D solid review; only the study differs.
        "pipe-tee-volume-review",
        study="mesh_study.py",
        title="Mesh discretisation",
        elements=("3D",),
        question="What does the analysis actually discretise at a branch?",
        summary=(
            "A conformal quadratic-hexahedral wall mesh for a header and branch. "
            "This example shows mesh geometry only, with no solver results."
        ),
    ),
    _project_gallery(
        "guyed-mast-review",
        frozenset({"dev", "pages"}),
        "beam-engineering-review",
        "guyed-mast-review",
        title="Cable",
        question="Which guys hold a mast in the wind, and which one goes slack?",
        elements=("POU_D_T", "CABLE"),
        summary=(
            "A 12 m tubular mast held by three pretensioned guy cables under a 3 kN side load. "
            "The leeward cable goes slack and the two windward ones carry it, which is the "
            "redistribution a tension-only member exists to show."
        ),
    ),
    _project_gallery(
        "hydrogen-plant-layout",
        frozenset({"dev", "pages"}),
        "engineering-review",
        "hydrogen-plant-layout",
        title="Plant layout",
        elements=("TUYAU_3M", "POU_D_T", "DIS_T"),
        question="How do two process lines and their rack fit together on a hydrogen plant site?",
        summary=(
            "A green-hydrogen facility in plan: an electrolyzer hall, a compressor station, storage bullets "
            "and a four-bay pipe rack, with the LP and HP hydrogen lines routed between them under pressure and thermal load. "
            "The review shows displacement, pipe-wall stress and friction shoe reactions from Code_Aster."
        ),
    ),
    _project_gallery(
        "imported_component_mixed_demo",
        frozenset({"dev", "pages"}),
        "model-review",
        "imported_component_mixed_demo",
        title="Imported components",
        elements=("TUYAU_3M",),
        question="How does a supplied component join an authored line?",
        summary=(
            "A STEP/STL component placed beside Tuba pipework, showing connection ports, "
            "local frames and coupling. This example contains geometry only, with no solver results."
        ),
    ),
    _project_gallery(
        "line-load-studio",
        frozenset({"dev", "pages"}),
        "engineering-review",
        "line-load-studio",
        title="Line loads",
        elements=("TUYAU_3M", "POU_D_T", "DIS_T"),
        question="Where does a distributed line load go once the line is restrained?",
        summary=(
            "A DN100 line on an I-beam crossbeam carries a 350 N/m downward line load, a 500 N/m lateral load "
            "on the beam, and a 3.5 kN force with a moment at its elbow. The review shows the deflection, "
            "stresses and support reaction from Code_Aster."
        ),
    ),
    _project_gallery(
        "load-case-preparation",
        frozenset({"dev", "pages"}),
        "engineering-review",
        "load-case-preparation",
        title="Load-case preparation",
        elements=("TUYAU_3M",),
        question="How do sustained, thermal, occasional and pressure loads change the same pipe?",
        summary=(
            "Two restrained pipe lines solved in four states: Sustained, OperatingHot, Occasional and PressureOnly. "
            "Compare Code_Aster results and export signed expansion differences for user-owned checks; "
            "no standard or utilization verdict is assigned."
        ),
    ),
    _project_gallery(
        "multipipe-rack",
        frozenset({"dev", "pages"}),
        "engineering-review",
        "multipipe-rack",
        title="Multipipe rack",
        elements=("TUYAU_3M", "POU_D_T", "DIS_T"),
        question="How do three lines at different temperatures load one shared rack?",
        summary=(
            "Three DN100, DN150 and DN200 lines share a four-bay steel rack. "
            "Each has a mid-run fixed shoe and sliding friction shoes, with temperatures "
            "of 100, 200 and 300 C and pressures of 1, 2 and 3 MPa. Code_Aster results "
            "show pipe-wall stress, displacement and the combined support load path."
        ),
    ),
    _project_gallery(
        "native-friction-review",
        frozenset({"dev", "pages"}),
        "contact-engineering-review",
        "native-friction-review",
        title="Nonlinear friction",
        elements=("POU_D_T", "DIS_T"),
        question="How does friction change the same pipe and load path?",
        summary=(
            "Two disconnected, identical pipes share one nonlinear Code_Aster run and load history. "
            "The review compares friction coefficients of 0 and 0.3 through heating, cooling, lift-off and reseating."
        ),
    ),
    _project_gallery(
        "pipe-tee-volume-review",
        frozenset({"dev", "pages"}),
        "volume-engineering-review",
        "pipe-tee-volume-review",
        title="3D solid",
        elements=("3D", "TUYAU_3M"),
        question="How does 1D beam pipework transition into a 3D solid tee junction?",
        summary=(
            "A 3D solid quadratic hexahedral tee coupled to 1D TUYAU_3M pipe beam extensions. "
            "Under internal pressure, gravity and a 4 kN out-of-plane load at the free branch end, "
            "the review shows kinematic shell-to-solid coupling, the stress hot spot where the branch "
            "meets the junction, and the branch deflection."
        ),
    ),
    _project_gallery(
        "profile-orientation-review",
        frozenset({"dev", "pages"}),
        "beam-engineering-review",
        "profile-orientation-review",
        title="Beam orientation",
        elements=("POU_D_T",),
        question="How does a rolled I-section change the response to the same tip force?",
        summary=(
            "Three identical I-section cantilevers at 0, 45 and 90 degrees in one model, each loaded by the "
            "same 500 N tip force in global -Z. The review compares deformed profiles and section rotations "
            "relative to the original local axes, so the difference on screen is the section orientation alone."
        ),
    ),
    _project_gallery(
        "rack_bridge_demo",
        frozenset({"dev", "pages"}),
        "engineering-review",
        "rack_bridge_demo",
        title="Road crossing",
        elements=("TUYAU_3M", "POU_D_T", "DIS_T"),
        question="How does a line cross an 8 m roadway on a shoe-supported rack bridge?",
        summary=(
            "A DN150 process line rises from ground sleepers over an 8 m roadway on a four-bay steel rack bridge, "
            "then drops back to grade. Friction shoes carry it at every bay midpoint. The review shows thermal "
            "displacement, wall stress and support reactions from Code_Aster."
        ),
    ),
    _project_gallery(
        # Published since dfac5a4. It was dev-only while the evidence was still
        # finding a home in a registered project; both Gravity and Wind now
        # attest against the model, so the card can stand up in public. It sits
        # in alphabetical position because the Pages build compares a sorted
        # directory listing against the catalog order, and a published card
        # that is out of order fails the build rather than the reader noticing.
        "steel-portal-frame-review",
        frozenset({"dev", "pages"}),
        # Not engineering-review: that profile demands a stress field, and Tuba
        # only asks Code_Aster for SIEQ when the model has pipe elements. A pure
        # frame has displacement, reaction and section forces, and saying so is
        # what beam-engineering-review already checks.
        "beam-engineering-review",
        "steel-portal-frame",
        title="Portal frame stability",
        elements=("POU_D_T",),
        question="How far is this frame from buckling, and where does it deflect?",
        summary=(
            "A seven-bay steel portal-frame industrial hall solved for gravity and wind in "
            "Code_Aster, with the linear buckling eigenvalue analysis of the gravity case. "
            "The review shows displacements, reactions, member-end section forces, and the "
            "critical load factors that say how far the frame is from a buckling mode. "
            "Von Mises is absent by design: a pipe-free frame has no equivalent-stress field."
        ),
    ),
    _project_gallery(
        "support-rack-review",
        frozenset({"dev", "pages"}),
        "engineering-review",
        "support-rack-review",
        title="Load transfer",
        elements=("TUYAU_3M", "POU_D_T", "DIS_T"),
        question="What do the supports and the steel underneath actually carry?",
        summary=(
            "A DN100 line centered in an I-beam rack under distributed line loading, internal pressure "
            "and thermal expansion. The review shows ground and element rest shoe reactions, steel deflection, and support spacing."
        ),
    ),

)


def catalog_json(indent: int | None = 2) -> str:
    """The gallery catalog the viewer renders cards from, as JSON.

    The dev server reads this so the gallery you develop against is the gallery
    you ship. Without it the dev catalog is a list of directory names, the cards
    degrade to bare titles, and the question, summary, evidence badge and
    thumbnail - everything a reader actually sees - are invisible to everyone
    working locally. Copy nobody can see is copy that drifts.
    """
    return json.dumps([gallery.to_catalog_entry() for gallery in OFFICIAL_GALLERIES], indent=indent)


if __name__ == "__main__":  # pragma: no cover - a dev-server helper
    print(catalog_json())
