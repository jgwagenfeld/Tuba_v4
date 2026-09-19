"""Canonical JSON digests shared by provenance fingerprints.

Floats are hashed at 9 significant digits, not by their exact repr. The same
model built by the same code can differ in the last bit between Windows and
Linux - the guyed mast's anchors come from math.cos and math.sin, and one of
them lands one ULP apart - and an exact hash made that a fingerprint mismatch:
the mast solved on Windows was refused by the Linux Pages build. 9 digits is
still far finer than any real edit to a model input, and a float that already
fits keeps its exact repr.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def platform_stable(value: Any) -> Any:
    """Round floats to 9 significant digits, recursively, for cross-platform hashing."""
    if isinstance(value, float):
        return float(f"{value:.9g}")
    if isinstance(value, dict):
        return {key: platform_stable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [platform_stable(item) for item in value]
    return value


def canonical_digest(payload: Any) -> str:
    """SHA-256 of the canonical JSON encoding of *payload*."""
    canonical = json.dumps(
        platform_stable(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
