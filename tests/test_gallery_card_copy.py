"""The gallery's card copy is written once, in the registry, and quoted everywhere else.

``scripts/official_gallery.py`` already refuses at import to build a card whose
question does not end in ``?`` or whose summary is under ten words, because a
gallery that cannot say what question it answers has no business being
published. The docs home page and README quote its featured cards by hand;
the Examples page carries every published card.

Nothing held them in step. ``tests/test_static_site_docs.py`` checks that each
bundle URL and thumbnail appears, and that ``examples.md`` carries each title
and summary - it never checks the question or whether a solver stands behind the
card. So the home page's Beam orientation card drifted to "How do section
orientation and local axes change bending?" while the registry, the viewer and
the README all said "How does a rolled I-section change the response to the same
tip force?", and every check stayed green.

These tests make the registry the single owner: a card's copy may be edited in
``official_gallery.py``, and the hand-written surfaces have to follow.

The Examples page is deliberately exempt from the question rule. It leads each
block with the title as a Markdown heading and states the evidence badge in
prose; it has never carried the questions, and that is a layout choice rather
than drift. What it may not do is contradict the registry, which is what
``test_examples_page_quotes_no_stale_question`` pins.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.official_gallery import OFFICIAL_GALLERIES  # noqa: E402

PUBLISHED = [gallery for gallery in OFFICIAL_GALLERIES if "pages" in gallery.audiences]
FEATURED = [gallery for gallery in PUBLISHED if gallery.featured_order is not None]

INDEX = ROOT / "docs" / "content" / "index.md"
EXAMPLES = ROOT / "docs" / "content" / "examples.md"
README = ROOT / "README.md"

#: Surfaces that quote a card's question verbatim beside its title.
QUESTION_SURFACES = (INDEX, README)


def test_there_are_published_galleries_to_check() -> None:
    """A registry that published nothing would make every test below vacuous."""
    assert len(PUBLISHED) >= 12
    assert FEATURED


@pytest.mark.parametrize("gallery", FEATURED, ids=lambda g: g.id)
@pytest.mark.parametrize("path", QUESTION_SURFACES, ids=lambda p: p.name)
def test_card_question_matches_the_registry(path: Path, gallery) -> None:
    text = path.read_text(encoding="utf-8")
    assert gallery.question in text, (
        f"{path.name} does not quote {gallery.id}'s question as the registry writes it.\n"
        f"  registry: {gallery.question}\n"
        "Edit scripts/official_gallery.py, then update this page to match it."
    )


@pytest.mark.parametrize(
    "path,gallery",
    [(path, gallery) for path in QUESTION_SURFACES + (EXAMPLES,)
     for gallery in (PUBLISHED if path == EXAMPLES else FEATURED)],
    ids=lambda value: value.name if isinstance(value, Path) else value.id,
)
def test_card_title_matches_the_registry(path: Path, gallery) -> None:
    assert gallery.title in path.read_text(encoding="utf-8"), (
        f"{path.name} does not carry {gallery.id}'s title {gallery.title!r}"
    )


@pytest.mark.parametrize("gallery", PUBLISHED, ids=lambda g: g.id)
def test_examples_page_states_whether_a_solver_stands_behind_the_card(gallery) -> None:
    """Whether numbers stand behind a card, stated in the page's own words.

    This used to assert ``gallery.evidence in block`` against a per-profile
    string, which was the literal word ``"Results"`` for four of the six
    profiles. That made the check both weak - the word appears in almost any
    English sentence about a review - and wrong: the registry also mapped two
    profiles to ``"Mesh only - no results"``, so a geometry-only example had to
    be spelled a particular way to pass, and the viewer card showed the same
    string.

    The registry now says *whether* a profile is solved, and this asserts the
    page says so in prose: a solved example has to say Code_Aster or results ran,
    and an unsolved one has to say it has no solver results. Both directions are
    checked, because the failure that matters is a geometry-only card reading as
    an analysis.
    """
    block = _example_block(EXAMPLES.read_text(encoding="utf-8"), gallery.title)
    lowered = block.lower()
    if gallery.solved:
        assert "code_aster" in lowered or "results" in lowered, (
            f"examples.md's {gallery.title!r} block is a solved review but never "
            f"says Code_Aster or results ran"
        )
    else:
        assert "no solver results" in lowered, (
            f"examples.md's {gallery.title!r} block publishes geometry only but "
            f"does not say it has no solver results"
        )


@pytest.mark.parametrize("gallery", PUBLISHED, ids=lambda g: g.id)
def test_a_solved_card_claims_a_case_count_and_an_unsolved_one_claims_none(gallery) -> None:
    """A card may not claim an analysis it does not have, nor deny one it does.

    ``OfficialGallery.__post_init__`` refuses the mismatch at import. This is the
    same rule asserted from the outside, against the catalog the viewer actually
    renders - so a future profile added to ``PROFILE_SOLVED`` without wiring a
    case count through ``_project_gallery`` fails here rather than shipping a
    card that claims results it cannot show.
    """
    entry = gallery.to_catalog_entry()
    if gallery.solved:
        assert entry["solved"] is True
        assert entry["case_count"] and entry["case_count"] > 0, (
            f"{gallery.id} is a solved review and declares no load cases"
        )
    else:
        assert entry["solved"] is False
        assert entry["case_count"] == 0, (
            f"{gallery.id} publishes geometry only but its catalog entry claims "
            f"{entry['case_count']} load case(s)"
        )


@pytest.mark.parametrize("gallery", PUBLISHED, ids=lambda g: g.id)
def test_examples_page_quotes_no_stale_question(gallery) -> None:
    """examples.md need not ask the question, but it may not ask an old one.

    A question is a sentence ending in '?', so a block that carries one which
    is not the registry's is a copy that drifted rather than a layout choice.
    """
    block = _example_block(EXAMPLES.read_text(encoding="utf-8"), gallery.title)
    # A link target carries a '?' of its own (viewer/?bundle=...), and so can a
    # code span; strip both before looking for prose.
    prose = re.sub(r"\]\([^)]*\)", "]", re.sub(r"`[^`]*`", "", block))
    questions = {
        sentence.strip()
        for sentence in re.findall(r"[A-Z][^.?!]*\?", prose)
        if sentence.strip() != gallery.question and sentence.count(" ") >= 3
    }
    assert not questions, (
        f"examples.md's {gallery.title!r} block asks a question the registry does not: {sorted(questions)}"
    )


def _example_block(text: str, title: str) -> str:
    """The Examples-page section for *title*, up to the next heading."""
    start = text.index(f"## {title}")
    rest = text[start + 1 :]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]
