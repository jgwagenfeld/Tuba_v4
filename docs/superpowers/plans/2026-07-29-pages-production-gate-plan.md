# Pages Production Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make one command assemble the exact deployable documentation/viewer artifact and block deployment unless that artifact passes semantic, browser, accessibility, and visual checks.

**Architecture:** Extend the existing `scripts/build_pages.py` from the publication plan with a `pages` operation. It invokes the current viewer release builder and Zensical build, stages only validated official bundles, derives the catalog from staged directories, then atomically replaces the requested output; CI and Pages call only this owner.

**Tech Stack:** Python stdlib, Zensical 0.0.51, existing Vite/Three.js viewer, Playwright, `@axe-core/playwright`, GitHub Actions.

## Global Constraints

- The wheel remains a viewer shell with `bundles.json == []`; the installed single-bundle launcher keeps the picker hidden.
- Pages contains exactly `code-aster-review` and `imported_component_mixed_demo`, and its catalog is derived only after both validate.
- Hosted Pages builds validate attested artifacts but do not execute Code_Aster.
- The final browser gate serves `_site` directly and must not load `viewer/vite.config.js` or its dynamic development catalog.
- The assembled artifact must not be uploaded after a docs, bundle, link, browser, accessibility, or visual failure.
- Keep generated official bundles out of Git after Windows and Linux staged generation pass; retain `viewer/public/smoke-scene` as a tracked fixture.
- Do not modify the user's uncommitted `README.md` inside the isolated implementation branch.

---

## File Map

- `scripts/build_pages.py`: `pages` assembly, redirects, complete validation, atomic output replacement.
- `tests/test_pages_build.py`: exact assembled-tree and failure behavior.
- `tests/test_package_release.py`: explicit empty wheel/source catalog checks.
- `tests/test_release_metadata.py`: single-owner workflow assertions.
- `viewer/scripts/e2e-smoke.mjs`: direct static-root assembled-site semantic scenario.
- `viewer/e2e/pages-artifact.spec.js`: axe and three-viewport screenshot contract.
- `viewer/playwright.config.js`: deterministic local/CI browser settings.
- `viewer/e2e/snapshots/pages-artifact.spec.js/`: reviewed cross-platform desktop/compact/narrow screenshots.
- `viewer/package.json`, `viewer/package-lock.json`: accessibility test dependency and scripts.
- `.github/workflows/ci.yml`: docs, viewer, and assembled-site gates.
- `.github/workflows/tuba-pages.yml`: dependency setup, single build command, browser gate, upload.
- `.gitignore`: official generated viewer directories and Pages output.
- `viewer/public/code-aster-review/**`, `viewer/public/imported_component_mixed_demo/**`: deleted after staged proof.

### Task 1: Make `build_pages.py pages` the sole artifact owner

**Files:**
- Modify: `scripts/build_pages.py`
- Create: `tests/test_pages_build.py`
- Modify: `tests/test_package_release.py`
- Modify: `.gitignore`

**Interfaces:**
- CLI: `uv run python scripts/build_pages.py pages --output <directory> [--code-aster-artifacts <directory>]`.
- Consumes: `prepare_release.main()`, Zensical output at `.build/zensical-site`, and `build_examples(viewer_root, audience="pages", code_aster_artifacts=code_aster_artifacts)`.
- Produces: an atomically replaced Pages directory containing docs, viewer, two bundles, redirects, notebook, and `.nojekyll`.

- [ ] **Step 1: Write failing assembled-tree and atomicity tests**

Call the Python interface with subprocess/build runners injected only where existing tests already mock external commands. Assert the completed tree contains:

```python
required = {
    "index.html",
    "setup.html",
    "tutorial.html",
    "reference/public-api.html",
    "architecture/visualization.html",
    "commands.html",
    "overview.html",
    "viewer/index.html",
    "viewer/bundles.json",
    "viewer/code-aster-review/scene.json",
    "viewer/imported_component_mixed_demo/scene.json",
    "notebooks/10_interactive_postprocessor.ipynb",
    ".nojekyll",
}
```

Assert catalog contents exactly match the two staged directories. Pre-populate the requested output with a marker, force a validator failure, and assert the original output survives unchanged.

- [ ] **Step 2: Run focused tests and verify the missing operation fails**

Run: `uv run python -m pytest tests/test_pages_build.py tests/test_package_release.py -q`

Expected: FAIL because `pages` assembly and redirects do not exist.

- [ ] **Step 3: Implement ordered staging into a sibling temporary directory**

For `output = Path(args.output).resolve()`, create `TemporaryDirectory(dir=output.parent)`. Run in order:

1. `prepare_release.main()`;
2. `uv run --group docs zensical build --clean --strict`;
3. copy `.build/zensical-site/.` to the temporary root;
4. copy `tuba/visualization/_viewer` to `temporary/viewer`;
5. call `build_examples(temporary / "viewer", audience="pages", code_aster_artifacts=code_aster_artifacts)`;
6. call `write_bundle_catalog(temporary / "viewer", bundle_ids)` from the returned IDs;
7. copy notebook 10 and write `.nojekyll`;
8. create two small HTML meta-refresh/canonical-link redirects: `commands.html -> reference/index.html` and `overview.html -> architecture/index.html`;
9. validate the complete tree and assert packaged `tuba/visualization/_viewer/bundles.json` still decodes to `[]`;
10. rename the old output to a sibling backup, rename the completed temporary directory into place, then remove the backup. On rename failure, restore the backup.

Reject an output equal to the repository root, home directory, filesystem root, source `docs/content`, or `viewer/public`.

- [ ] **Step 4: Keep the package catalog explicitly empty**

Extend package tests to open both the source viewer shell and built wheel `bundles.json` and assert `json.loads(catalog_path.read_text(encoding="utf-8")) == []`, not merely file existence.

- [ ] **Step 5: Run a real local Pages build**

Run:

```text
uv run python scripts/build_pages.py pages --output .build/pages-check
uv run python -m pytest tests/test_pages_build.py tests/test_package_release.py -q
```

Expected: PASS and `.build/pages-check/viewer/bundles.json` contains exactly the two official IDs.

- [ ] **Step 6: Commit**

```text
git add .gitignore scripts/build_pages.py tests/test_pages_build.py tests/test_package_release.py
git commit -m "feat: assemble Pages through one validated command"
```

### Task 2: Exercise the exact assembled site in the browser

**Files:**
- Modify: `viewer/scripts/e2e-smoke.mjs`
- Create: `viewer/playwright.config.js`
- Create: `viewer/e2e/pages-artifact.spec.js`
- Create: `viewer/e2e/snapshots/pages-artifact.spec.js/pages-desktop.png`
- Create: `viewer/e2e/snapshots/pages-artifact.spec.js/pages-compact.png`
- Create: `viewer/e2e/snapshots/pages-artifact.spec.js/pages-narrow.png`
- Modify: `viewer/package.json`
- Modify: `viewer/package-lock.json`

**Interfaces:**
- CLI: `npm run e2e -- pages-catalog --site-root <path>`.
- CLI: `npm run e2e:pages -- --update-snapshots` for deliberate reviewed baseline updates; normal `npm run e2e:pages` compares without updating.
- Serves: the supplied site root with Vite `configFile: false`; navigates to `/viewer/?bundle=code-aster-review`.

- [ ] **Step 1: Add failing static-root scenario tests**

Parse `pages-catalog --site-root PATH`, resolve the path, and fail if it lacks `viewer/index.html`. The scenario asserts:

- picker visible with exactly the two official IDs and readable labels;
- switching updates the query and scene ID;
- engineering bundle exposes four field families and four layer categories;
- Field -> displacement -> Component -> DZ updates state, legend, and render;
- physical/visual deformation remain distinct with undeformed reference;
- Warnings shows propagated import warnings;
- keyboard section/camera controls work;
- model review shows `publication.model_review.no_solver_results`;
- no console error, page error, failed request, or render diagnostic occurs.

- [ ] **Step 2: Run against the assembled tree and verify scenario failure**

Run from `viewer/`: `npm.cmd run e2e -- pages-catalog --site-root ../.build/pages-check`

Expected: FAIL because static-root CLI handling/scenario is absent.

- [ ] **Step 3: Implement direct static-root serving**

Use:

```javascript
createServer({
  root: siteRoot,
  configFile: false,
  logLevel: "error",
  server: { host: "127.0.0.1", port: 0 },
});
```

Do not import or merge viewer Vite configuration. Keep all existing scenarios on their current default root.

- [ ] **Step 4: Add axe and screenshot coverage with the installed Playwright runner**

Add `@axe-core/playwright` as a dev dependency. Configure the test server command to build `.build/pages-check` and serve it directly. Set `snapshotPathTemplate` to `{testDir}/snapshots/{testFilePath}/{arg}{ext}` so one reviewed Chromium baseline is shared by Windows and Linux. In `pages-artifact.spec.js`, run `new AxeBuilder({ page }).analyze()` and assert `violations == []`. Capture the viewer workspace after Ready at:

```javascript
for (const [name, viewport] of Object.entries({
  desktop: { width: 1440, height: 900 },
  compact: { width: 1024, height: 768 },
  narrow: { width: 800, height: 900 },
})) {
  await page.setViewportSize(viewport);
  await expect(page).toHaveScreenshot(`pages-${name}`, {
    animations: "disabled",
    caret: "hide",
    maxDiffPixelRatio: 0.002,
  });
}
```

Generate baselines once with `--update-snapshots`, inspect them, then run without that flag.

- [ ] **Step 5: Run semantic, axe, and visual gates**

Run from `viewer/`:

```text
npm.cmd run e2e -- pages-catalog --site-root ../.build/pages-check
npm.cmd run e2e:pages
```

Expected: PASS.

- [ ] **Step 6: Commit**

```text
git add viewer/scripts/e2e-smoke.mjs viewer/playwright.config.js viewer/e2e/pages-artifact.spec.js viewer/e2e/snapshots viewer/package.json viewer/package-lock.json
git commit -m "test: gate the assembled Pages viewer"
```

### Task 3: Replace duplicated CI and Pages assembly

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/tuba-pages.yml`
- Modify: `tests/test_release_metadata.py`

**Interfaces:**
- CI docs command: `uv sync --group docs --extra course --locked`.
- Pages build command: `uv run python scripts/build_pages.py pages --output _site`.
- Browser commands consume `_site`; workflow contains no shell-copy assembly.

- [ ] **Step 1: Add failing workflow ownership tests**

Assert Pages contains the single build command, installs the locked docs group and Node dependencies, runs semantic and Playwright Pages gates before upload, and contains none of:

```python
forbidden = (
    "cp -R docs/site",
    "cp -R tuba/visualization/_viewer",
    "cp -R viewer/public/code-aster-review",
    "cp -R viewer/public/imported_component_mixed_demo",
)
```

Assert normal CI runs current viewer unit/E2E, strict docs build, and Pages-builder tests.

- [ ] **Step 2: Run workflow tests and verify failure**

Run: `uv run python -m pytest tests/test_release_metadata.py -q`

Expected: FAIL on duplicated shell assembly and missing browser gates.

- [ ] **Step 3: Update CI**

The docs job syncs the docs group, builds Zensical strictly, and runs docs tests. The viewer job installs Chromium and runs unit tests plus `public-code-aster-review`, `section-camera`, and `legacy-workflow`. Add an assembled-site job that builds Pages and runs `pages-catalog` plus `e2e:pages`.

- [ ] **Step 4: Update Pages deployment**

Set up Python with uv, Node 22, `uv sync --group docs --locked`, and `npm ci`. Run the one Pages build command, install Chromium, run both assembled-site browser gates, and only then configure/upload the `_site` artifact. Remove all assembly copy statements.

- [ ] **Step 5: Run metadata and local workflow-equivalent checks**

Run:

```text
uv run python -m pytest tests/test_release_metadata.py tests/test_pages_build.py -q
uv run python scripts/build_pages.py pages --output .build/pages-check
npm.cmd --prefix viewer run e2e -- pages-catalog --site-root ../.build/pages-check
npm.cmd --prefix viewer run e2e:pages
```

Expected: PASS.

- [ ] **Step 6: Commit**

```text
git add .github/workflows/ci.yml .github/workflows/tuba-pages.yml tests/test_release_metadata.py
git commit -m "ci: deploy only verified Pages artifacts"
```

### Task 4: Remove tracked official derivatives

**Files:**
- Delete: `viewer/public/code-aster-review/**`
- Delete: `viewer/public/imported_component_mixed_demo/**`
- Modify: `.gitignore`
- Modify: `tests/test_official_viewer_publication.py`
- Modify: `tests/test_pages_build.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_release_metadata.py`

**Interfaces:**
- Replaces: tracked official examples with `uv run python scripts/build_pages.py examples --output viewer/public --audience dev` for local development.
- Preserves: `viewer/public/smoke-scene/**` as a tracked deterministic test fixture.

- [ ] **Step 1: Prove Windows and Linux staged generation before deletion**

Require the local Windows Pages build/browser gate and the Linux CI assembled-site job to pass from the same commit. Record those command results in the implementer report. Do not delete the bridge if either platform fails.

- [ ] **Step 2: Replace the bridge-comparison test with source-free staging assertions**

Assert the two official directories are absent from a clean checkout, `smoke-scene` remains, and a temporary `examples` build produces exactly the two official IDs without reading tracked bundle directories.

- [ ] **Step 3: Delete tracked derivatives and ignore only their generated paths**

Add:

```gitignore
/viewer/public/code-aster-review/
/viewer/public/imported_component_mixed_demo/
```

Do not ignore `viewer/public/` broadly.

Update the ordinary viewer CI job so it no longer assumes a tracked `code-aster-review` directory. Keep source-only unit, legacy, and section/camera scenarios there; the assembled-site job remains the sole official-engineering browser authority and already generates both bundles.

- [ ] **Step 4: Run clean-source generation and package checks**

Run:

```text
uv run python -m pytest tests/test_official_viewer_publication.py tests/test_pages_build.py tests/test_package_release.py tests/test_release_metadata.py -q
uv run python scripts/build_pages.py pages --output .build/pages-check
npm.cmd --prefix viewer run e2e -- pages-catalog --site-root ../.build/pages-check
```

Expected: PASS without tracked official bundles.

- [ ] **Step 5: Commit**

```text
git add -A viewer/public/code-aster-review viewer/public/imported_component_mixed_demo .gitignore .github/workflows/ci.yml tests/test_official_viewer_publication.py tests/test_pages_build.py tests/test_release_metadata.py
git commit -m "chore: generate official viewer bundles on demand"
```

## Protected README Reconciliation After Merge

The controller, not an isolated-plan implementer, applies these narrow edits to the live dirty `README.md` after the implementation branch is integrated:

- change the public source map from `docs/site/` to `docs/content/`;
- replace `docs/code_aster_installation.md` with `docs/content/setup.md`;
- replace old `docs/site/*.html` source links with canonical Markdown paths or the existing live-site link.

The pre-existing live-docs link and Markdown table formatting must remain byte-for-byte present. Leave README unstaged unless the user separately authorizes including their existing changes in a commit.
