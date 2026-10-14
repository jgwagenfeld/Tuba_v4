# Scene payload performance, 14 October 2026

New scene bundles now write `scene.json` and the compatibility
`geometry/geometry_assets.json` as compact JSON. Parsed values, schema, geometry
content hashes, validation and the rule that publishes `scene.json` last are
unchanged. Smaller metadata documents retain their existing formatting. The IFC
merged-scene quota now counts the compact bytes that the exporter publishes,
including escaped Unicode and embedded newlines, without relaxing the limit.

This follows the caching and redundant-render fixes recorded in
[the frontend performance report](frontend-performance-20261014.md). It benefits
both Gallery and Studio bundles because both use `write_scene_bundle`.

## Retained scene audit

The read-only audit used an existing Code_Aster-backed local review.
Its local bundle path and original SHA-256 are retained in the untracked
diagnostic evidence manifest.

| Scene manifest | Bytes | Decimal MB |
| --- | ---: | ---: |
| Original indented JSON | 39,147,527 | 39.15 |
| Compact JSON, identical parsed values | 14,879,626 | 14.88 |
| Reduction | 24,267,901 | 61.99% |

The actual retained scene passed the existing geometry-hash validator after
compact serialization and parsing. Its file remained byte-identical. The audit
is a compatibility check using retained solver evidence, not a fresh solve or
full Gallery/Pages qualification.

## Browser comparison

A temporary read-only HTTP proxy served either the original bytes or compact
bytes from memory. All other requests used the same running source viewer and
Studio backend. Six alternating trials (`original, compact, compact, original,
original, compact`) used fresh browser contexts, a 1440 by 900 viewport and the
same retained review. The proxy and browser were closed after measurement; no
backend restart or bundle rewrite was required.

| Metric, median of three trials per variant | Original | Compact |
| --- | ---: | ---: |
| Scene resource transfer on loopback | 138 ms | 39 ms |
| Scene worker turnaround, including reply delivery | 916 ms | 805 ms |
| Page ready through the next painted frame | 9,825 ms | 9,647 ms |

These development-server samples support the byte reduction and compatibility.
They do not establish a material overall startup speedup: page-ready ranges
overlap, and observed main-thread long tasks remain roughly 2.8 to 3.4 seconds.
Whitespace removal leaves the parsed array/object count and the cost of cloning
those values from the worker unchanged. Other fetched result documents are also
unchanged. This change does not affect cached tab switching, which already avoids
scene requests.

All trials displayed the same scene, 1,305 objects, six result fields, 679
renderable items and the Operating result state. Browser and worker errors were
absent. API writes were blocked; authored source and retained scene hashes were
unchanged.

## Further opportunities

Mesh assets account for 11.89 MB of the compact scene. An exact-content audit of
the larger vertex, base-vertex, face, edge-index and vertex-value arrays found
3,593 occurrences containing 10,365,617 bytes, but only 1,227 unique arrays
containing 3,347,370 bytes. That leaves **7,018,247 duplicate bytes**. One beam-face
array occurs 1,208 times; larger meshes repeat vertex and face arrays across
result states.

The next substantial payload change is a shared array table with explicit
references. Removing those duplicates gives a 7,861,379-byte lower bound before
reference/table overhead. This is an estimate, not an implemented format or a
browser performance measurement. It needs coordinated exporter, loader, hash,
expanded-budget and compatibility checks. Transferable typed buffers are another
candidate for reducing worker reply cost. Initial graph creation and first-frame
rendering should then be profiled separately, since compaction does not remove
the observed main-thread stalls.

## Validation and activation

Exporter, security-boundary, scene, geometry and IFC reference checks passed:
50 tests and four subtests. The two new regressions failed before the
implementation and passed afterward; the final quota regression also covers
Unicode and an embedded newline. Independent code review found no unresolved
correctness/security blocker.

The change applies on subsequent exports using the updated Python code.
Existing bundles and the already running backend are retained as they were.
No packaged viewer rebuild, fresh Code_Aster solve, publication or remote push
was performed. Diagnostic recipes, sizes, browser samples, test logs and hashes
are retained under `.tmp/frontend-performance-20261014/payload-study/`; full scene
variants stayed in memory. The previously retained 1,376,987-byte build-check
directory was deleted after user approval and file-by-file hash verification.
