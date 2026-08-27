# Tuba v4 Visualization Publication and Documentation Design

**Date:** 2026-07-29

**Status:** Implemented design record; automated gallery refresh gate wired 2026-08-26
**Scope:** Official web-review examples, GitHub Pages assembly, viewer production verification, and public documentation ownership

> **Authority note (2026-08-26):** This file is retained as the historical
> implementation design. Current behavior is documented under
> `docs/content/architecture/`. Self-hosted CI and beta release jobs now re-solve
> and attest all three engineering galleries before strict Pages assembly.

## Implementation Update

The single Pages builder, strict publication profiles, portable Code_Aster
evidence, Zensical documentation, production picker, section controls, browser
gates, and self-hosted gallery refresh gate described below are implemented.
The public catalog contains four deliberately reviewed examples: the original
solved pipe and imported component bundles, a solved pipe-on-rack review, and a
solved autorouted expansion loop. README and documentation entry points use the
current solved pipe review as their clickable hero image.

## Objective

Make the published Tuba documentation and visualization examples reproducible,
portable, and provably aligned with the current codebase.

The completed system must preserve Tuba's product contract:

1. Define the piping structure in Tuba.
2. Solve engineering result workflows with Code_Aster.
3. Display and report processed Code_Aster artifacts without fabricated results.

The work must also preserve the two existing visualization paths:

- `tuba/plotting/` remains the PyVista quick-look and export path.
- `tuba/visualization/` plus `viewer/` remains the reviewable web-scene path.

No third visualization path is introduced.

## Current Failure Model

The current deployment has three independent sources of drift.

### Distribution drift

The Vite development server discovers bundles under `viewer/public/`, but the
production Vite build deliberately emits `bundles.json` as `[]`. This is correct
for the Python wheel because `tuba-viewer` serves one caller-supplied bundle.
GitHub Pages then copies two example bundles beside that shell without replacing
the empty catalog. The live viewer therefore hides its example picker even
though both examples exist.

### Generated-artifact drift

`viewer/public/code-aster-review` predates the current scene contract. A fresh
run of `examples/code_aster_artifact_review.py` produces declared layer
categories and five result fields, while the published bundle contains neither.
The runtime loader correctly accepts the older shape, which means compatibility
masks publication staleness.

The public review also contains absolute workstation paths. Its committed solver
manifest and sidecar do not provide a complete current-solve attestation with
solver identity, solve timestamp, and hashes for the raw result artifacts.

### Documentation drift

Ten hand-authored HTML pages duplicate site chrome, navigation, workflow prose,
and Python signatures. Examples of confirmed drift include:

- `docs/site/commands.html` documents a removed `solver=` argument on
  `Model.solve`.
- `docs/site/index.html` describes seven visible review workflows, while the
  current viewer exposes four primary task modes plus four evidence destinations.
- `docs/site/tutorial.html` advertises sectioning, but the renderer has no
  clipping-plane implementation or public section control.
- `docs/architecture/visualization-layer-structure-design.md` remains labelled
  as ready for implementation after the layer and result-field work landed.

## Design Decisions

### 1. Use Zensical for the public documentation build

The documentation source will be Markdown and the site will be built with
Zensical. Zensical replaces the earlier MkDocs recommendation.

The decision is based on current upstream status:

- MkDocs core has not released since 1.6.1 on 2024-08-30.
- Material for MkDocs entered maintenance mode in 2025 and moved feature work to
  Zensical.
- Zensical supports custom CSS and JavaScript, strict link validation,
  `mkdocstrings`, GitHub Pages, and existing Material-compatible content.
- Zensical remains pre-1.0, so the project will constrain the supported alpha
  release and lock the complete docs environment in `uv.lock`.

Authoritative upstream references:

- <https://www.mkdocs.org/about/release-notes/>
- <https://squidfunk.github.io/mkdocs-material/changelog/>
- <https://zensical.org/docs/community/faqs/>
- <https://zensical.org/docs/setup/extensions/about/>
- <https://pypi.org/project/zensical/>

The source dependency belongs in a `docs` dependency group, not in Tuba's
runtime dependencies or published optional extras. The initial dependency is
exactly `zensical==0.0.51`, the current PyPI release on 2026-07-29. The same
group includes `mkdocstrings[python]`; `uv.lock` pins its resolved version and
all transitive docs dependencies. A Zensical upgrade is a deliberate docs-build
change with the same Windows, Linux, and production checks described below.

### 2. Give the assembled Pages artifact one owner

One Python command will own GitHub Pages assembly:

```text
uv run python scripts/build_pages.py pages --output _site
```

`scripts/build_pages.py` is a cohesive build module, not a second runtime
framework. Its public interface is the command line. Its implementation will:

1. Run the synchronized viewer production build through the existing release
   preparation path.
2. Build Markdown documentation with Zensical in strict mode.
3. Materialize the official example bundles using existing Python producers and
   scene/review writers.
4. Copy the packaged viewer shell into `_site/viewer/`.
5. Derive `_site/viewer/bundles.json` from the official bundle directories that
   were actually staged.
6. Copy the published notebook artifact.
7. Validate the complete output before returning success.

The Pages workflow will invoke this command instead of reproducing its behavior
with shell copy statements.

The package build remains intentionally different: it continues to ship the
viewer shell with an empty catalog. The installed launcher continues to serve a
single external bundle at `/bundle` and keeps the picker hidden.

### 3. Keep the bundle catalog deliberately small

The deployed `bundles.json` contract remains a sorted JSON list of bundle IDs.
The viewer already derives readable labels from those IDs. A new catalog schema,
capability manifest, or registry file is not required.

The official examples will be declared once as a small Python tuple inside the
Pages build module. Each record contains only:

- bundle ID;
- producer adapter;
- audience (`dev` and/or `pages`);
- validation profile (`engineering-review` or `model-review`).

The four published records are:

- `code-aster-review`, produced from the canonical solved Code_Aster artifact
  set;
- `support-rack-review`, a solved pipe-on-rack model with support reactions and
  load-path overlays;
- `autorouted-expansion-loop`, a solved U-loop selected by the autorouter with
  the route alternatives retained for review;
- `imported_component_mixed_demo`, explicitly labelled as a model-review bundle
  without solver results.

The adapters call the existing example functions. They do not create a factory
framework or a third scene builder.

For local development, the same command exposes an examples-only operation:

```text
uv run python scripts/build_pages.py examples --output viewer/public
```

The generated official directories become ignored build output after the
migration is complete. The tracked `smoke-scene` remains a deterministic viewer
test fixture.

### 4. Treat official scene bundles as derivatives

The real Code_Aster artifact directory is the authority for the engineering
example. Scene geometry, review tables, HTML, and viewer metadata are generated
derivatives.

The canonical engineering sample must be solved once with the current exporter
on the configured self-hosted Code_Aster runner before strict publication is
enabled. The refreshed artifact chain must record:

- non-null solver-input identity matching the current model and exporter;
- Code_Aster version and execution method;
- solve timestamp;
- hashes and byte sizes for required raw outputs;
- the existing study, mesh, result-state, and model-revision linkage.

Hosted Pages builds do not rerun Code_Aster. They materialize the viewer bundle
from the committed, attested raw artifacts and verify the attestation. A
self-hosted integration job re-solves the canonical gallery when its input model,
solver exporter, or expected artifact contract changes.

During migration, the generated public bundle may remain committed and CI will
regenerate and compare it. Once staged generation is reliable on Windows and
Linux, the committed derivative is removed.

### 5. Separate backward-compatible loading from strict publication

`VisualizationScene.from_dict()` and the JavaScript loader continue accepting
older external bundles. Missing `layers` or `result_fields` remains a valid
legacy condition at runtime.

Official publication uses a stricter profile. The engineering example must have:

- `analysis_status == "solved"`;
- real Code_Aster provenance and no fixture provenance;
- matching non-null solver-input identities;
- the five expected result-field families: stress, displacement, reaction force,
  reaction moment, and TUYAU subpoint stress;
- non-empty design, analysis-mesh, results, and annotations layer categories;
- valid scene references and geometry hashes;
- no absolute local paths anywhere in public JSON or HTML;
- no missing files referenced by the review manifest or provenance records;
- visible import warnings rather than discarded diagnostics.

The model-review example must have valid geometry and layers and must clearly
state that it contains no solver results. It must never present export-only data
as a completed engineering evaluation.

This strictness belongs at the publication seam. It does not become a new
requirement for users opening historical bundles locally.

### 6. Make shareable provenance portable

Local `AnalysisStudy` and `ResultState` records may retain paths needed during
execution. Public scene and review serialization must not expose those paths.

Portable review output will:

- copy included solver evidence under bundle-relative `artifacts/` paths;
- rewrite published provenance file references to relative URIs;
- attach SHA-256 and byte-size maps to provenance metadata;
- deduplicate source files referenced under more than one role;
- reject missing required evidence for an engineering-review profile;
- reject paths that escape the bundle root.

The existing `ReviewProvenance.files` mapping remains a mapping of role to URI,
so `engineering_review.v1` and the viewer do not need a new schema solely for
this correction. Hash and size maps are additive provenance metadata.

Scene builders will export portable artifact names or bundle URIs rather than
absolute source paths. A final recursive validation scan catches any missed
Windows drive path, UNC path, or absolute POSIX path before publication.

### 7. Propagate diagnostics through the owning data path

Diagnostics returned by `import_code_aster_artifacts()` must reach the
`ResultState` metadata used by both reporting and visualization. Review builders
and scene builders will translate those records into their existing diagnostic
contracts.

Warnings remain warnings and are displayed in the viewer. Publication fails only
for error-severity diagnostics or a violated engineering profile. An optional
RMED-reader warning does not invalidate CSV-authoritative results, but it must not
disappear from the review surface.

### 8. Preserve and clarify the viewer information architecture

The viewer keeps its current axes:

- header picker: artifact/example identity;
- task rail: Review, Model, Results, Issues;
- evidence dock: Governing Results, Warnings, Compliance, Reports;
- result controls: Load case, Field, optional Component;
- geometry display: physical/deformed state and independent display scales.

Documentation and accessible labels will describe task mode and evidence
destination as independent. Switching the task mode does not silently change the
selected evidence destination.

No broad cockpit redesign is included.

The existing section-box state will be completed as a real feature because the
public documentation already promises it and part of the state plumbing exists.
The renderer will use clipping planes, the viewer will expose an accessible
section control, and reset will remove clipping. Whole-object AABB filtering will
not be described as geometric sectioning.

Canvas and orientation controls will receive keyboard-operable equivalents.
This is an accessibility requirement, not an optional visual enhancement.

## Documentation Information Architecture

Publishable documentation source moves to `docs/content/`. Internal design specs
remain under `docs/superpowers/specs/` and are not part of the public site.

```text
docs/
  content/
    index.md
    setup.md
    tutorial.md
    modeling.md
    workflow.md
    autorouting.md
    examples.md
    developer.md
    reference/
      index.md
      public-api.md
    architecture/
      index.md
      visualization.md
    assets/
      figures/
      site.css
  superpowers/
    specs/
```

The authority rules are:

- `README.md` is the concise product entry point and documentation map.
- `docs/content/` is the public manual.
- `docs/content/reference/` uses `mkdocstrings` for live signatures and augments
  them with curated explanations and examples. Signatures are never copied by
  hand.
- `docs/content/architecture/` describes current implemented architecture.
- Roadmap and implementation-design records remain lifecycle-labelled outside
  the current behavior pages.
- `CONTRIBUTING.md` owns contribution policy and solver/result boundaries.
- `examples/` and `notebooks/` remain executable learning sources; manual pages
  link to them instead of maintaining divergent full scripts.

The existing HTML pages are converted, reviewed, and then deleted in the same
migration. `docs/tuba-workflow.md` is merged into the canonical workflow page and
removed as a separate authority. Real generated engineering figures are
preserved. The obsolete viewer poster is removed; the manual links or embeds the
current staged viewer instead.

## Pages Data Flow

```text
Markdown + figures -------- Zensical --strict -------+
viewer/src -- prepare_release.py -- packaged shell --+-- build_pages.py -- _site/
attested Code_Aster artifacts -- existing producers -+                       |
model-review inputs ---------- existing producer ----+                       +-- validator
                                                                              +-- browser gate
```

`bundles.json` is written only after the bundle directories are present. The
catalog and staged directories must match exactly.

## Failure Behavior

The Pages build fails without uploading an artifact when any of the following is
true:

- Zensical reports a broken link or other strict-build warning;
- an official producer fails;
- the engineering example lacks its attested Code_Aster inputs;
- solver-input identities do not match;
- a required field, layer category, file, or hash is missing;
- public output contains an absolute machine path;
- catalog entries and staged bundle directories differ;
- the assembled browser verification fails.

Code_Aster unavailability on a hosted Pages runner is not an error because that
runner does not solve. Code_Aster unavailability on the self-hosted refresh gate
is a hard blocker and must not fall back to fabricated or export-only results.

## Verification Contract

### Python and artifact checks

- Unit-test official example discovery and deterministic catalog ordering.
- Materialize each example in a temporary directory.
- Validate current scene contracts and all file/hash references.
- Assert portable provenance and diagnostic propagation.
- Assert that the wheel still contains only the viewer shell and `bundles.json`
  remains empty.
- Build the Zensical site with strict validation.

### Production browser checks

Serve the assembled `_site`, not the Vite development server, and verify:

- the picker is visible with exactly the four official Pages examples;
- switching the picker updates the URL and loaded scene;
- the engineering example exposes Load case, Field, and Component controls;
- displacement component selection changes the legend and rendered state;
- physical and visual deformation states retain the undeformed reference;
- task and evidence controls have correct independent ARIA state;
- import warnings appear under Warnings;
- section controls apply true clipping and reset cleanly;
- keyboard-only navigation covers tasks, evidence, results, and camera presets;
- automated accessibility checks pass;
- screenshots at desktop, compact desktop, and narrow viewport sizes match
  reviewed baselines.

Legacy scene-only behavior remains covered separately, including a missing
`review.json` and absent result-field catalog.

### Documentation checks

- The generated API page obtains signatures from current imports.
- Documentation names the four task modes and four evidence destinations.
- Export-only examples retain the explicit incomplete-evaluation warning.
- Public pages contain no stale `.html` source links after migration.
- Viewer links resolve against the assembled Pages layout.

## Migration Sequence

1. Add failing tests for catalog mismatch, stale engineering fields, absolute
   provenance paths, lost diagnostics, and current documentation drift.
2. Add Zensical configuration, the docs dependency group, and a minimal strict
   build while retaining current HTML temporarily.
3. Add `scripts/build_pages.py` and make it derive the production catalog from
   staged official examples.
4. Refresh the canonical Code_Aster artifact chain on the self-hosted runner and
   enforce the engineering publication profile.
5. Normalize public provenance and propagate import diagnostics.
6. Regenerate the engineering example and update production E2E expectations to
   the current field/layer contract.
7. Complete renderer clipping and keyboard accessibility.
8. Convert and reconcile the documentation into `docs/content/`, then remove the
   hand-authored HTML and duplicate workflow source.
9. Make the Pages workflow call the single build command and require the
   assembled-site browser gate before upload.
10. After cross-platform staged generation is stable, remove committed official
    derivative bundles and materialize them on demand.

Each step must leave the relevant build and tests green. The production picker
must not be enabled before the catalog points only to validated bundles.

## Alternatives Rejected

### Rewrite only `_site/viewer/bundles.json`

This restores the dropdown but leaves generated-artifact drift, absolute paths,
lost diagnostics, hand-maintained documentation, and development-only E2E
coverage.

### Keep Material for MkDocs

Material is in maintenance mode and is not the best new long-term dependency.

### Use Sphinx with MyST

Sphinx is the conservative fallback and is actively maintained. For Tuba's
product-style manual, current custom visuals, embedded viewer, and relatively
small curated Python API, Zensical provides the required site experience with
less theme and extension assembly. If Zensical fails the pinned Windows/Linux
proof during implementation, Sphinx with MyST is the approved fallback; the
Markdown information architecture remains portable.

### Add a versioned capability manifest

The current issue is publication ownership, not runtime capability negotiation.
The existing scene schema and `bundles.json` list are sufficient. A capability
manifest can be reconsidered only when external bundle negotiation requires it.

### Run Code_Aster during every Pages deployment

Hosted Pages runners are not the production solver environment. Re-solving on
every docs push would be slow, brittle, and contrary to the existing self-hosted
runtime gate. Pages validates attested artifacts; the self-hosted job refreshes
them.

## Out of Scope

- A third visualization frontend or replacement of Three.js.
- Solver calculations in JavaScript.
- Fabricated or deterministic fixture results in the published engineering
  example.
- A general plugin framework for official examples.
- Documentation version switching, localization, PDF generation, analytics, or
  a hosted search service.
- A wholesale cockpit layout redesign.
- Changing the PyVista quick-look path.

## Completion Criteria

The design is complete when:

1. One reproducible command builds the exact Pages artifact.
2. The live viewer catalog matches its deployed official bundles and shows the
   picker.
3. The engineering example is current, Code_Aster-backed, portable, attested,
   and exposes the current result-field controls.
4. The package viewer remains shell-only and correctly hides the picker.
5. The public manual is generated from canonical Markdown with live API
   signatures and accurate viewer terminology.
6. Hosted CI validates the assembled site in a browser before deployment.
7. The self-hosted Code_Aster gate can reproduce and attest the canonical
   engineering artifact chain.
8. Older external scene bundles continue to load through the legacy adapter.
