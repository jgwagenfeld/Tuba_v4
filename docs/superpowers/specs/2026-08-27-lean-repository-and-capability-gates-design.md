# Lean Repository and Capability Gates Design

**Date:** 2026-08-27

**Status:** Draft for review

**Scope:** Supported Python and IFC runtimes, capability-owned test gates,
generated-output ownership, and prevention of speculative public APIs

## Decision Summary

Tuba will make its supported environments explicit and keep optional native
dependencies out of unrelated failure paths.

- Python 3.11 and 3.12 are supported; unsupported newer interpreters are
  rejected until their full capability matrix is green.
- IfcOpenShell is pinned to the newest version proven to import and pass Tuba's
  IFC tests on both Windows and Linux. The initial pin is `0.8.4.post1` because
  the locked 0.8.5 Windows wheels fail to load while 0.8.4.post1 imports under
  Windows Python 3.12.
- The existing Linux all-extras suite remains the broad integration gate. One
  focused Windows IFC job owns Windows import and IFC behavior.
- JavaScript configuration behavior is tested by the viewer's Node test suite,
  not by a Python test that spawns Node.
- All Tuba-owned disposable output defaults move under `.build/`. Canonical
  attested Code_Aster artifacts remain committed under
  `notebooks/code_aster_results/`.
- No cleanup service, dependency wrapper, compatibility alias, custom test
  runner, or dead-code framework is added.

The product workflow remains unchanged: Tuba model -> real Code_Aster solve ->
attested artifact import -> processed result display.

## Problem

The current repository has four unrelated concerns coupled into one broad
failure surface:

1. `requires-python = ">=3.11"` accepts interpreters beyond the versions named
   in the package classifiers and CI matrix.
2. `ifcopenshell>=0.8` allows a broken native wheel to enter a locked
   environment even though Tuba's IFC code has not changed.
3. Optional-dependency tests import their dependencies during collection, so a
   missing or unloadable optional package prevents unrelated tests from running.
4. A Python metadata test launches Node to inspect Playwright configuration,
   crossing runtime ownership and making the Python suite depend on PATH state.

Disposable example, review, and benchmark outputs also use both `.build/` and
`.benchmarks/`. Multiple ignored roots make local cleanup harder and allow old
artifacts to accumulate without adding engineering value.

## Runtime Contract

### Supported Python versions

`pyproject.toml` will declare `requires-python = ">=3.11,<3.13"`, matching the
existing Python 3.11 and 3.12 classifiers and CI matrix. Python 3.13 support is
added only when core, IFC, visualization, packaging, and notebook gates pass on
that interpreter.

This is an honest support boundary, not a permanent ban on newer Python.

### IfcOpenShell pin

Both the `ifc` and `course` extras will use `ifcopenshell==0.8.4.post1`.
`uv.lock` remains the only lock file.

An IfcOpenShell upgrade requires:

1. a successful import on Windows and Linux using a supported Python version;
2. the focused IFC tests passing on both platforms; and
3. the existing Linux all-extras suite remaining green.

The version is changed directly when those checks pass. No platform-specific
resolver helper or fallback importer is introduced.

## Test-Gate Ownership

### Broad Python gate

The existing Ubuntu Python 3.11/3.12 all-extras matrix remains the broad Python
integration gate. It continues to exercise interactions between optional
capabilities without changing the Code_Aster execution contract.

Tests that require an optional dependency will use `pytest.importorskip()` at
module collection. A developer with only the `dev` extra can therefore run the
available suite without unrelated collection errors.

Skipping is acceptable only in the broad local suite. Capability jobs must
prove their dependency is present before invoking pytest.

### Windows IFC gate

One `windows-latest`, Python 3.12 CI job will:

1. install the locked `dev` and `ifc` extras;
2. run `python -c "import ifcopenshell"` as a non-skippable import smoke test;
3. run the focused IFC and IFC-artifact tests; and
4. fail if any focused test skips because IfcOpenShell is unavailable.

The initial focused set is:

- `tests/test_ifc.py`
- `tests/test_ifc_mapping.py`
- `tests/test_ifc_pipe_systems.py`
- `tests/test_ifc_placements.py`
- `tests/test_code_aster_artifact_import.py`

The job does not install visualization, notebook, collision, or documentation
extras. It owns one capability and stays fast.

### Viewer configuration gate

The Playwright web-server and snapshot-path assertions move from
`tests/test_release_metadata.py` to a focused Node test under `viewer/test/`.
That test imports `viewer/playwright.config.js` with and without
`TUBA_PAGES_SITE_ROOT` and preserves the current assertions.

The Python release-metadata test continues to validate workflow ordering and
environment declarations, but no longer launches Node. The existing viewer job
already runs `npm test`, so no new job is required.

### Tee fixture

The tee-SIF fixture must explicitly set the branch direction before extending
the branch. The current staged correction uses
`set_direction([0, 1, 0]).run(2.0)` and should be verified rather than
reimplemented. Production junction classification remains strict; an invalid
collinear fixture must not weaken its ambiguity check.

### Code_Aster gate

The self-hosted real-Code_Aster job remains separate and authoritative. No
mock, export-only result, or IFC gate may substitute for it.

## Artifact Ownership

`.build/` is the single Tuba-owned disposable repository-local output root.
Existing defaults under `.benchmarks/` move to `.build/benchmarks/`, including
benchmark summaries and generated example/review bundles. Standard tool-owned
caches and package build directories keep their native ignored locations.

The boundary is:

- `.build/**`: ignored, disposable, and safe to remove when no command is
  running;
- `notebooks/code_aster_results/**`: committed canonical solver inputs,
  attestations, and imported result artifacts;
- source examples and notebooks: committed inputs, never cleanup targets; and
- release artifacts: produced from source plus canonical attested artifacts,
  never treated as source authority.

The documented cleanup command is the existing Git primitive:

```text
git clean -fdX -- .build
```

No automatic age-based deletion runs in application code. CI workspaces are
ephemeral, and local deletion remains explicit and exactly scoped.

Test-only CI jobs will finish with `git diff --exit-code` so tests cannot
silently rewrite tracked source or canonical artifacts. Distribution assembly
and the self-hosted gallery-refresh job are exempt because refreshing generated
or canonical artifacts is their explicit responsibility.

## Public API Ownership

New exports require a real example, CLI, production caller, or public
documentation entry. Tests that only instantiate a symbol do not justify a
public API. When the last real caller disappears, the symbol and its self-test
are deleted together; no compatibility alias is retained unless a released
external contract requires one.

This remains a review rule. Tuba will not add a custom unused-code analyzer or
a second API manifest.

## Failure Behavior

- Unsupported Python versions fail during dependency resolution.
- A broken or missing Windows IfcOpenShell wheel fails the import smoke test;
  it cannot be converted into a passing skip.
- Developers without optional extras see explicit pytest skips while unrelated
  tests continue.
- Node configuration failures appear in the viewer gate that owns the runtime.
- Generated tracked changes fail non-solver CI.
- Missing Code_Aster remains a loud blocker for engineering evaluation and
  result publication.

## Migration Sequence

1. Tighten the Python range and pin IfcOpenShell in both relevant extras; update
   the lock file.
2. Make optional IFC and notebook imports collection-safe, then add the focused
   Windows IFC job with its non-skippable import smoke.
3. Move the Playwright configuration behavior test to the viewer suite and
   remove the Python subprocess test.
4. Verify the existing tee fixture correction with its focused test.
5. Move `.benchmarks/` defaults to `.build/benchmarks/`, update documentation,
   and add clean-tree checks to test-only CI jobs.
6. Run focused gates, the broad Python matrix, viewer tests, documentation
   checks, and the real Code_Aster gate before release.

Each step should be independently reviewable and should delete superseded code
or configuration in the same change.

## Alternatives Rejected

### Pin IfcOpenShell and keep the monolithic local failure surface

This is the smallest immediate patch but leaves optional-dependency collection
and cross-runtime Node ownership broken. The next bad native wheel would repeat
the same incident.

### Put all development and CI in one container

This hides Windows wheel failures instead of supporting Windows IFC, adds a new
runtime layer, and conflicts with the existing native Python and self-hosted
Code_Aster boundaries.

### Skip IFC whenever its import fails

This can make CI green while IFC is unusable. Only the general local suite may
skip an absent optional capability; the dedicated IFC gate must fail closed.

### Add a cleanup daemon or retention service

One disposable output root and one exact Git cleanup command solve the current
problem without background behavior, configuration, or another maintenance
surface.

## Verification Contract

The implementation is complete when:

1. Python 3.13 is rejected by package metadata and 3.11/3.12 remain installable.
2. Windows Python 3.12 imports the locked IfcOpenShell and passes the focused IFC
   tests without skips.
3. The Ubuntu 3.11/3.12 all-extras matrix passes.
4. A dev-only environment collects and runs tests without optional-import
   errors.
5. `npm test` owns and passes the Playwright configuration assertions.
6. The tee-SIF focused test builds a real three-direction junction and passes.
7. No tracked default writes to `.benchmarks/` remain.
8. Test-only CI leaves the tracked checkout unchanged.
9. The self-hosted Code_Aster workflow still solves, imports, attests, and
   publishes real solver results.

## Out of Scope

- changing IFC schemas or export semantics;
- adding Python 3.13 support before its matrix is green;
- changing Code_Aster execution or attestation;
- replacing uv, pytest, GitHub Actions, or Node's test runner;
- automatically deleting canonical solver artifacts; and
- adding compatibility shims for removed cleanup surfaces.
