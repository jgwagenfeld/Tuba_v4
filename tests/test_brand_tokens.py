"""The accent, focus and warning colours are one decision across four surfaces.

The docs site is light, the review app is dark and the generated report is a
printable light page, and each is built by a different tool - zensical, Vite
and a Python string. Nothing makes them import one file, so before this the
same three roles carried three different values: two focus rings that were
never the same teal, two ambers for the same warning, and a docs accent that
was near-complementary to the app's accent, so crossing between them read as
leaving the product.

The values still live once per surface because there is no shared build step
to hoist them into. What this asserts is that the copies agree, so a drift
fails here instead of surviving review and turning up as a screenshot someone
squints at months later. The review app's :root is the source of truth.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VIEWER_CSS = ROOT / "viewer" / "src" / "styles.css"
DOCS_CSS = ROOT / "docs" / "content" / "assets" / "site.css"
REPORT_WRITER = ROOT / "tuba" / "reporting" / "export.py"


def _viewer_token(name: str) -> str:
    """The value of a custom property declared in the viewer's :root block."""
    root = VIEWER_CSS.read_text(encoding="utf-8").split("\n}\n", 1)[0]
    match = re.search(rf"^\s*{re.escape(name)}:\s*(#[0-9a-fA-F]{{3,8}});", root, re.MULTILINE)
    assert match, f"{name} is not declared in the :root block of {VIEWER_CSS.name}"
    return match.group(1).lower()


@pytest.mark.parametrize("name", ["--focus-on-light", "--focus-on-dark", "--warning", "--accent"])
def test_viewer_declares_the_shared_roles(name: str) -> None:
    assert _viewer_token(name).startswith("#")


def test_docs_accent_is_the_viewer_light_focus_colour() -> None:
    """The docs accent and the app's light-surface focus ring are one colour.

    They were #e07a2d and #0b7684 - an orange and a teal, near-complementary,
    on two pages one click apart. The orange also rendered at 2.66:1 on the
    active nav item, under AA; this value clears it at 4.71:1.
    """
    accent = re.search(
        r"--md-accent-fg-color:\s*(#[0-9a-fA-F]{3,8});", DOCS_CSS.read_text(encoding="utf-8")
    )
    assert accent, "the docs site declares no --md-accent-fg-color"
    assert accent.group(1).lower() == _viewer_token("--focus-on-light")


def test_report_focus_ring_matches_the_viewer() -> None:
    """The report's scroll regions focus in the same teal as the app."""
    source = REPORT_WRITER.read_text(encoding="utf-8")
    ring = re.search(r"\.table-wrap:focus-visible \{ outline: 2px solid (#[0-9a-fA-F]{3,8});", source)
    assert ring, "the report writer emits no .table-wrap:focus-visible outline"
    assert ring.group(1).lower() == _viewer_token("--focus-on-light")


def test_report_warning_rule_matches_the_viewer() -> None:
    """An unavailable section is marked in the same amber the app warns in."""
    source = REPORT_WRITER.read_text(encoding="utf-8")
    rule = re.search(r"\.unavailable \{ border-left: \.25rem solid (#[0-9a-fA-F]{3,8});", source)
    assert rule, "the report writer emits no .unavailable border"
    assert rule.group(1).lower() == _viewer_token("--warning")


def test_viewer_uses_no_undefined_custom_properties() -> None:
    """Every var() the stylesheet reads is one the stylesheet declares.

    --graphite-highlight was referenced by .model-legend-chip:hover and never
    declared, so that hover resolved to nothing and the chip faded instead of
    lifting - a broken microinteraction no test could see and no browser
    reports.
    """
    css = VIEWER_CSS.read_text(encoding="utf-8")
    declared = set(re.findall(r"^\s*(--[\w-]+):", css, re.MULTILINE))
    used = set(re.findall(r"var\(\s*(--[\w-]+)", css))
    assert used - declared == set()
