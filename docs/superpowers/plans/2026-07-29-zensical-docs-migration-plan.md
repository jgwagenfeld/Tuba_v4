# Zensical Documentation Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace duplicated hand-authored HTML with one strict Zensical build from canonical Markdown and live Python API signatures.

**Architecture:** Keep the current useful prose and generated engineering figures, but move page ownership to `docs/content/` and site chrome/navigation to `zensical.toml`. Use Zensical's built-in validation and mkdocstrings compatibility; do not build a custom theme or documentation generator.

**Tech Stack:** Zensical 0.0.51, mkdocstrings Python handler, Markdown, TOML, existing Python figure scripts, pytest, uv.

## Global Constraints

- Declare `zensical==0.0.51` in a `docs` dependency group and lock the complete environment in `uv.lock`; do not add it to runtime dependencies or package extras.
- Build with `uv run zensical build --clean --strict` on Windows and Linux.
- Preserve the core workflow: model -> Code_Aster solve -> processed result display.
- Every export-only example must say it is not a completed engineering evaluation.
- Generate Python signatures from imports with mkdocstrings; never copy signatures by hand.
- Publish current behavior only; lifecycle-label roadmap/design records outside current architecture pages.
- Preserve real generated figures; remove the obsolete viewer poster.
- Do not create theme overrides, a docs plugin, PDF output, version switching, localization, analytics, or hosted search.
- Preserve the user's uncommitted `README.md`; its path-map reconciliation is handled after the isolated implementation merge.

---

## File Map

- `pyproject.toml`: PEP 735 `docs` dependency group only.
- `uv.lock`: exact resolved docs environment.
- `zensical.toml`: site identity, stable `.html` URLs, navigation, validation, theme features, custom CSS, mkdocstrings.
- `docs/content/*.md`: canonical public manual.
- `docs/content/reference/*.md`: generated public API reference directives.
- `docs/content/architecture/*.md`: concise current architecture.
- `docs/content/assets/figures/*`: retained real figures.
- `docs/content/assets/site.css`: minimal Tuba visual identity and responsive iframe styling.
- `scripts/docs/*.py`: figure-generation tools, outside the published `docs_dir`.
- `docs/site/`: deleted after parity is verified.
- `docs/tuba-workflow.md` and `docs/code_aster_installation.md`: merged into canonical manual pages and deleted.
- `docs/architecture/visualization-layer-structure-design.md`: lifecycle status corrected.
- `tests/test_static_site_docs.py`: canonical Markdown/site-output assertions.
- `tests/test_current_api_docs.py`: scan `docs/content` and verify live API directives.
- `tests/test_code_aster_docs.py`: public setup/tutorial paths moved to Markdown.
- `tests/test_docs_figures.py`: new figure paths.

### Task 1: Establish the locked Zensical build

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `.gitignore`
- Create: `zensical.toml`
- Create: `docs/content/index.md`
- Create: `docs/content/assets/site.css`
- Modify: `tests/test_static_site_docs.py`

**Interfaces:**
- CLI: `uv run zensical build --clean --strict`.
- Configuration: `docs_dir = "docs/content"`, `site_dir = ".build/zensical-site"`, `use_directory_urls = false`.
- Produces: generated `.build/zensical-site/index.html`; the final Pages builder owns `_site/`.

- [ ] **Step 1: Write the failing build-configuration test**

Replace the old hand-authored-shell assertion with checks that parse `zensical.toml` via `tomllib`:

```python
config = tomllib.loads((ROOT / "zensical.toml").read_text(encoding="utf-8"))
project = config["project"]
self.assertEqual("docs/content", project["docs_dir"])
self.assertEqual(".build/zensical-site", project["site_dir"])
self.assertFalse(project["use_directory_urls"])
self.assertTrue(project["validation"]["invalid_links"])
self.assertTrue(project["validation"]["invalid_link_anchors"])
```

Also assert `pyproject.toml` has `dependency-groups.docs` containing `zensical==0.0.51` and `mkdocstrings[python]`, and that neither appears in `[project].dependencies` or optional extras.

- [ ] **Step 2: Run the focused test and verify failure**

Run: `uv run python -m pytest tests/test_static_site_docs.py -q`

Expected: FAIL because no Zensical configuration or Markdown source exists.

- [ ] **Step 3: Add the docs dependency group and update the lock**

Add:

```toml
[dependency-groups]
docs = [
    "mkdocstrings[python]>=1.0",
    "zensical==0.0.51",
]
```

Run: `uv lock`

- [ ] **Step 4: Add the minimal production configuration**

Configure:

```toml
[project]
site_name = "Tuba v4"
site_description = "Code_Aster-backed piping engineering and result review"
site_url = "https://jgwagenfeld.github.io/Tuba_v4/"
repo_url = "https://github.com/jgwagenfeld/Tuba_v4"
docs_dir = "docs/content"
site_dir = ".build/zensical-site"
use_directory_urls = false
extra_css = ["assets/site.css"]
nav = [
    { "Home" = "index.md" },
    { "Setup" = "setup.md" },
    { "Tutorial" = "tutorial.md" },
    { "Modeling" = "modeling.md" },
    { "Workflow" = "workflow.md" },
    { "Autorouting" = "autorouting.md" },
    { "Examples" = "examples.md" },
    { "Developer" = "developer.md" },
    { "Reference" = [
        { "Overview" = "reference/index.md" },
        { "Public API" = "reference/public-api.md" },
    ] },
    { "Architecture" = [
        { "Overview" = "architecture/index.md" },
        { "Visualization" = "architecture/visualization.md" },
    ] },
]

[project.validation]
invalid_links = true
invalid_link_anchors = true

[project.theme]
variant = "modern"
language = "en"
features = ["content.code.copy", "navigation.footer", "navigation.indexes"]

[project.plugins.mkdocstrings.handlers.python]
paths = ["."]

[project.plugins.mkdocstrings.handlers.python.options]
members_order = "source"
show_source = true
show_signature_annotations = true
```

Start `index.md` with the product contract and links to Setup, Tutorial, and the live viewer. Keep CSS limited to Tuba colors, readable content width, figure sizing, and responsive `.viewer-frame`; Zensical owns layout and navigation. Add `.build/` to `.gitignore`.

- [ ] **Step 5: Build on Windows in strict mode**

Run: `uv run --group docs zensical build --clean --strict`

Expected: PASS and `.build/zensical-site/index.html` exists.

- [ ] **Step 6: Run tests and commit**

```text
uv run python -m pytest tests/test_static_site_docs.py -q
git add .gitignore pyproject.toml uv.lock zensical.toml docs/content/index.md docs/content/assets/site.css tests/test_static_site_docs.py
git commit -m "docs: establish locked Zensical build"
```

### Task 2: Migrate and reconcile the public manual

**Files:**
- Create: `docs/content/setup.md`
- Create: `docs/content/tutorial.md`
- Create: `docs/content/modeling.md`
- Create: `docs/content/workflow.md`
- Create: `docs/content/autorouting.md`
- Create: `docs/content/examples.md`
- Create: `docs/content/developer.md`
- Copy: `docs/site/assets/figures/*` to `docs/content/assets/figures/*` except `viewer_frames_poster.png`
- Move and adjust: `docs/site/assets/generate_figures.py` to `scripts/docs/generate_figures.py`
- Move and adjust: `docs/site/assets/generate_section_drawings.py` to `scripts/docs/generate_section_drawings.py`
- Modify: `tests/test_static_site_docs.py`
- Modify: `tests/test_code_aster_docs.py`
- Modify: `tests/test_docs_figures.py`

**Interfaces:**
- Consumes: current prose from `docs/site/{setup,tutorial,modeling,workflow,autorouting,examples,developer}.html`, `docs/tuba-workflow.md`, and `docs/code_aster_installation.md`.
- Produces: one authoritative Markdown page for each public topic.

- [ ] **Step 1: Convert the phrase tests to canonical Markdown paths**

Use this exact ownership map:

```python
required = {
    "setup.md": ["pip installs Tuba, not Code_Aster", "code_aster_doctor", "Run the real solver smoke test"],
    "tutorial.md": ["Build and solve a first pipe", "Expected files", "Done when"],
    "modeling.md": ["Cross-sections", "Local coordinate systems", "Schemas and serialized models", "How errors work"],
    "workflow.md": ["model.pipe", "export_analysis_study", "write_scene_bundle"],
    "autorouting.md": ["Route candidates, not magic signoff", "SolverAcceptanceCriteria", "Current limitations"],
    "examples.md": ["Local examples", "Code_Aster review scene", "Autorouting example outputs"],
    "developer.md": ["Module map", "Solver file map", "How to extend autorouting", "CONTRIBUTING.md"],
}
```

Update solver-doc tests from `docs/site/setup.html` and `tutorial.html` to `docs/content/setup.md` and `tutorial.md`. Update figure tests to `docs/content/assets`.

- [ ] **Step 2: Run the docs tests and verify missing Markdown failures**

Run:

```text
uv run python -m pytest tests/test_static_site_docs.py tests/test_code_aster_docs.py tests/test_docs_figures.py -q
```

Expected: FAIL on missing canonical pages/assets.

- [ ] **Step 3: Write each page from its named authorities**

Apply these reconciliation rules rather than transliterating HTML:

- `setup.md`: merge the full tested content of `docs/code_aster_installation.md`; keep the tagged `v4.0.1` checkout, native Linux and Windows/WSL paths, `code-aster=18.0.12`, doctor command, environment-variable reference, and explicit stop-on-blocked behavior.
- `tutorial.md`: show model -> solve/import -> processed results; exported `.comm`, `.mail`, and `.export` are handoff files, not completion; describe the four task modes and four independent evidence destinations; describe true section clipping only after the viewer plan lands.
- `modeling.md`: preserve OD/WT, section drawings, local axes, placement frames, schema/validation errors, and the imported-component model-review embed; say it has no solver results.
- `workflow.md`: merge unique content from `docs/tuba-workflow.md`; keep the two visualization paths distinct and use one path per example.
- `autorouting.md`: preserve current U-loop and sequential-network limitations and require real Code_Aster evaluation for engineering acceptance.
- `examples.md`: separate solved engineering review, model review, and export-only examples with visible status labels.
- `developer.md`: current module/file maps, extension seams, test commands, contributor link, and solver-result boundaries.

Use fenced Python/text blocks, Markdown tables, and normal relative links. Do not copy page chrome or manual Python signatures.

- [ ] **Step 4: Preserve real figures and update generators**

Copy all existing generated figures except `viewer_frames_poster.png`. Move both generators to `scripts/docs/`, update their constants/docstrings to write `docs/content/assets/figures`, and keep the existing no-solver behavior. Rename regenerated `money_shot.png` to `pyvista_deformed_stress.png` so it cannot be mistaken for a Three.js viewer screenshot; update every Markdown reference.

- [ ] **Step 5: Build and run the focused tests**

Run:

```text
uv run --group docs zensical build --clean --strict
uv run python -m pytest tests/test_static_site_docs.py tests/test_code_aster_docs.py tests/test_docs_figures.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```text
git add docs/content tests/test_static_site_docs.py tests/test_code_aster_docs.py tests/test_docs_figures.py
git commit -m "docs: migrate public manual to canonical Markdown"
```

### Task 3: Generate the public API and publish current architecture

**Files:**
- Create: `docs/content/reference/index.md`
- Create: `docs/content/reference/public-api.md`
- Create: `docs/content/architecture/index.md`
- Create: `docs/content/architecture/visualization.md`
- Modify: `docs/architecture/visualization-layer-structure-design.md`
- Modify: `tests/test_current_api_docs.py`
- Modify: `tests/test_static_site_docs.py`

**Interfaces:**
- Consumes: importable public symbols from `tuba`, `tuba.analysis`, `tuba.reporting`, `tuba.routing`, and `tuba.visualization`.
- Produces: mkdocstrings directives rendered by Zensical; curated explanations remain Markdown.

- [ ] **Step 1: Add failing generated-reference assertions**

Assert `public-api.md` contains directives, not copied definitions:

```python
text = (CONTENT / "reference" / "public-api.md").read_text(encoding="utf-8")
self.assertIn("::: tuba.model.TubaModel", text)
self.assertIn("::: tuba.visualization.build_visualization_scene", text)
self.assertNotRegex(text, r"Model\.solve\(self,")
```

Extend `_current_user_facing_sources()` to scan all `docs/content/**/*.md`, while excluding the design/spec folders.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `uv run python -m pytest tests/test_current_api_docs.py tests/test_static_site_docs.py -q`

Expected: FAIL because reference and architecture pages do not exist.

- [ ] **Step 3: Add the curated API directives**

Document only stable public entry points, grouped by Model authoring, solver/artifact workflow, reporting, autorouting, PyVista quick-look, and web-scene review. Each directive uses:

```markdown
::: tuba.model.TubaModel
    options:
      show_source: false
      members_order: source
```

Use the same form for `tuba.analysis.code_aster_artifacts.import_code_aster_artifacts`, `tuba.reporting.build_engineering_review`, `tuba.visualization.build_visualization_scene`, `tuba.visualization.write_scene_bundle`, `tuba.visualization.write_engineering_review_with_scene`, and the explicit current routing classes exported from `tuba.routing`. Explain that `tuba.Model` is the public alias for `TubaModel`; do not invent aliases or document private helpers.

- [ ] **Step 4: Add current architecture pages**

`architecture/index.md` describes the model, solver/export, artifact import, reporting, and two visualization boundaries. `architecture/visualization.md` describes `tuba/plotting/` versus `tuba/visualization/ + viewer/`, the scene contract, four task modes, four evidence destinations, field/component selection, physical versus visual deformation, and true clipping.

Change the internal layer design status from “ready for implementation planning” to “Implemented; retained as a design record”, with a link to current architecture.

- [ ] **Step 5: Prove imported signatures render**

Run: `uv run --group docs zensical build --clean --strict`

Assert generated `.build/zensical-site/reference/public-api.html` contains `Model.solve` and does not contain a `solver=` parameter for that method.

- [ ] **Step 6: Run tests and commit**

```text
uv run python -m pytest tests/test_current_api_docs.py tests/test_static_site_docs.py -q
git add docs/content/reference docs/content/architecture docs/architecture/visualization-layer-structure-design.md tests/test_current_api_docs.py tests/test_static_site_docs.py
git commit -m "docs: generate API and current architecture reference"
```

### Task 4: Remove duplicate documentation authorities

**Files:**
- Delete: `docs/site/**`
- Delete: `docs/tuba-workflow.md`
- Delete: `docs/code_aster_installation.md`
- Modify: `tests/test_static_site_docs.py`
- Modify: `tests/test_code_aster_docs.py`
- Modify: `tests/test_docs_figures.py`

**Interfaces:**
- Produces: `docs/content/` as the only public site source.
- Preserves: internal `docs/architecture/`, `docs/superpowers/`, and other lifecycle records.

- [ ] **Step 1: Add failing authority tests**

```python
self.assertFalse((ROOT / "docs" / "site").exists())
self.assertFalse((ROOT / "docs" / "tuba-workflow.md").exists())
self.assertFalse((ROOT / "docs" / "code_aster_installation.md").exists())
self.assertFalse((CONTENT / "assets" / "figures" / "viewer_frames_poster.png").exists())
```

Scan `docs/content`, tests, workflows, and scripts for `docs/site`, `.html` source links, and `docs/tuba-workflow.md`; the expected offender list is empty.

- [ ] **Step 2: Run focused tests and verify duplicate-authority failure**

Run: `uv run python -m pytest tests/test_static_site_docs.py tests/test_code_aster_docs.py tests/test_docs_figures.py -q`

Expected: FAIL while the old site and workflow source remain.

- [ ] **Step 3: Delete the migrated sources and remove stale references**

Delete `docs/site/`, `docs/tuba-workflow.md`, and the now-merged `docs/code_aster_installation.md`. Update tests to inspect only Markdown and generated-site behavior. Do not delete internal architecture records.

- [ ] **Step 4: Run full documentation verification**

Run:

```text
uv run --group docs zensical build --clean --strict
uv run python -m pytest tests/test_static_site_docs.py tests/test_current_api_docs.py tests/test_code_aster_docs.py tests/test_docs_figures.py -q
rg -n "docs/site|docs/tuba-workflow|docs/code_aster_installation|viewer_frames_poster|commands\.html|workflow\.html" docs tests .github scripts
```

Expected: build/tests PASS and `rg` reports no stale public-source references. README is intentionally excluded because it is protected user WIP for the final reconciliation.

- [ ] **Step 5: Commit**

```text
git add -A docs/site docs/tuba-workflow.md docs/code_aster_installation.md tests/test_static_site_docs.py tests/test_code_aster_docs.py tests/test_docs_figures.py
git commit -m "docs: remove duplicate hand-authored site"
```
