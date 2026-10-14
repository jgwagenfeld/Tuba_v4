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

## Follow-up: share arrays across the worker boundary

The parser worker now interns equal numeric geometry arrays and transfers their
unique numbers in one Float64 buffer. The UI restores ordinary arrays and shares
equal source arrays. Published JSON, geometry hashes and renderer inputs retain
their existing format, so this also benefits existing bundles. It does not yet
reduce the 14.88 MB compact scene's network bytes; a public reference encoding
would require coordinating the older consumers of that scene contract.

The retained review's 3,595 eligible array occurrences become 1,229 unique arrays
in a 2,194,200-byte transferable buffer. Array dimensions, Float64 precision and
signed zeros survive the worker boundary. Irregular or nonnumeric arrays retain
the existing structured-clone path. The worker validates the original expanded
document and reports its original value count before sharing anything; compact
storage does not reduce receiving quotas or per-asset rendering costs.

The final paired browser comparison used the same compact scene bytes for both
variants. A read-only proxy substituted the pre-change worker for the baseline;
the new loader accepts that original reply too. Six trials used the order
`baseline, new, new, baseline, baseline, new`, fresh browser contexts, the same
1440 by 900 viewport, and the same running backend. Each trial also exercised
both stage caches, then measured the main JavaScript heap after garbage
collection. The diagnostic browser and temporary proxy were closed afterward.

| Median, three trials per variant | Previous worker | Shared arrays |
| --- | ---: | ---: |
| Scene worker reply, before UI array restoration | 711 ms | 597 ms |
| Page ready through the next painted frame | 8,089 ms | 7,029 ms |
| Main JavaScript heap after loading both cached stages | 87.50 MB | 75.52 MB |
| Warm Build switch | 416 ms | 416 ms |
| Warm Review switch | 567 ms | 583 ms |

This is a local development-server sample, not a general latency guarantee.
Startup fell about 13% and retained JavaScript heap fell about 12 MB. Warm tab
switching remains around 0.4/0.6 seconds, with no demonstrated improvement from
this change. Scene/result summaries matched across all trials; there were no
browser/worker errors or API writes, and the authored source and retained scene
file remained unchanged. Existing Code_Aster artifacts were reused.

The regression runs the production worker across an actual structured-clone and
transfer boundary. Other checks cover precision, signed zeros, skipped arrays,
expanded quotas, geometry costs and deformation isolation: changing one graph
leaves shared source values and another graph unchanged. Review caught a
quadratic signed-zero fingerprint collision; sign positions now distinguish
those keys, with a deterministic comparison-count regression. Per-row iterator
allocation and oversized small arrays were also ruled out during measurement.

Final checks and file hashes are retained in
`.tmp/frontend-performance-20261014/worker-sharing/`. The source preview uses
the updated worker. All 863 viewer tests passed, as did frontend-only production
compilation and a browser smoke check of that compiled viewer, including stage
switches and the transferred buffer. A final real-scene worker check compared
every restored value and geometry budget total with the original input.
The packaged viewer and browser Python runtime were not
rebuilt; frontend-only production compilation checks the new worker bundle
without regenerating those unrelated payloads. No solver execution or remote
push was performed in this follow-up.
