"""Regenerate the committed gallery card images.

Run this when a published review's geometry or default view changes:

    uv run python scripts/docs/generate_gallery_thumbnails.py

The images are committed, so the Pages build only copies them and never needs a
browser. That trades freshness for a release path that cannot fail on a
headless-browser problem; this script is the manual half of that trade.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_pages import GALLERY_THUMBNAIL_DIR, PAGES_GALLERIES, build_examples

VIEWER_PUBLIC = ROOT / "viewer" / "public"
SHOOTER = ROOT / "viewer" / "scripts" / "gallery-thumbnails.mjs"


def main() -> int:
    bundle_ids = [gallery.id for gallery in PAGES_GALLERIES]
    print(f"Building {len(bundle_ids)} bundles into {VIEWER_PUBLIC} ...")
    build_examples(VIEWER_PUBLIC, audience="dev")

    GALLERY_THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
    node = shutil.which("node") or "node"
    subprocess.run(
        [node, str(SHOOTER), str(GALLERY_THUMBNAIL_DIR), *bundle_ids],
        cwd=ROOT / "viewer",
        check=True,
    )
    print(f"Gallery thumbnails written to {GALLERY_THUMBNAIL_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
