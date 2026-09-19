"""The gallery's card copy is written once, in the registry, and quoted everywhere else.

``scripts/official_gallery.py`` already refuses at import to build a card whose
question does not end in ``?`` or whose summary is under ten words, because a
gallery that cannot say what question it answers has no business being
published. That guard stops at the registry, and three other surfaces quote the
same twelve cards by hand: the docs home page, the Examples page and the README.

Nothing held them in step. ``tests/test_static_site_docs.py`` checks that each
bundle URL and thumbnail appears, and that ``examples.md`` carries each title
and summary - it never checks the question or the evidence badge. So the home
page's Beam orientation card drifted to "How do section orientation and local
axes change bending?" while the registry, the viewer and the README all said
"How does a rolled I-section change the response to the same tip force?", and
every check stayed green.

These tests make the registry the single owner: a card's copy may be edited in
``official_gallery.py``, and the hand-written surfaces have to follow.

The Examples page is deliberately exempt from the question rule. It leads each
block with the title as an ``##`` heading and states the evidence badge in
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

INDEX = ROOT / "docs" / "content" / "index.md"
EXAMPLES = ROOT / "docs" / "content" / "examples.md"
README = ROOT / "README.md"

#: Surfaces that quote a card's question verbatim beside its title.
QUESTION_SURFACES = (INDEX, README)


def test_there_are_published_galleries_to_check() -> None:
    """A registry that published nothing would make every test below vacuous."""
    assert len(PUBLISHED) >= 12


@pytest.mark.parametrize("gallery", PUBLISHED, ids=lambda g: g.id)
@pytest.mark.parametrize("path", QUESTION_SURFACES, ids=lambda p: p.name)
def test_card_question_matches_the_registry(path: Path, gallery) -> None:
    text = path.read_text(encoding="utf-8")
    assert gallery.question in text, (
        f"{path.name} does not quote {gallery.id}'s question as the registry writes it.\n"
        f"  registry: {gallery.question}\n"
        "Edit scripts/official_gallery.py, then update this page to match it."
    )


@pytest.mark.parametrize("gallery", PUBLISHED, ids=lambda g: g.id)
@pytest.mark.parametrize("path", QUESTION_SURFACES + (EXAMPLES,), ids=lambda p: p.name)
def test_card_title_matches_the_registry(path: Path, gallery) -> None:
    assert gallery.title in path.read_text(encoding="utf-8"), (
        f"{path.name} does not carry {gallery.id}'s title {gallery.title!r}"
    )


@pytest.mark.parametrize("gallery", PUBLISHED, ids=lambda g: g.id)
def test_examples_page_states_the_registry_evidence_badge(gallery) -> None:
    """The badge is what tells a reader whether numbers stand behind a card."""
    text = EXAMPLES.read_text(encoding="utf-8")
    block = _example_block(text, gallery.title)
    assert gallery.evidence in block, (
        f"examples.md's {gallery.title!r} block does not state the registry's "
        f"evidence badge {gallery.evidence!r}"
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
