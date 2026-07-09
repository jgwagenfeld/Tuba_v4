# Docs Visual Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every Mermaid flowchart and CSS pseudo-graphic across the 10-page static docs site with real renders from the Tuba pipeline, and restructure the explanations so the 3D mental model is taught deductively.

**Architecture:** A committed Python generator (`docs/site/assets/generate_figures.py`) renders a fixed set of docs-grade PNGs headlessly from `tuba.plotting` and commits them to `docs/site/assets/figures/`. Result figures replay committed Code_Aster studies with `run_solver=False`, so no solver is needed. Pages embed the PNGs as `<figure><img>` and add one live `viewer/?bundle=…&embed=1` iframe where orbiting the model teaches. No changes to `tuba/plotting`, `tuba/visualization`, or `viewer/` internals — reuse only.

**Tech Stack:** Python 3 + PyVista (off-screen VTK) for stills; existing Three.js viewer for embeds; static HTML/CSS; `unittest` tests; GitHub Pages workflow.

## Global Constraints

- Reuse only: never edit `tuba/plotting/*`, `tuba/visualization/*`, or `viewer/src/*`. Only call their public/existing functions.
- Figure delivery: commit rendered PNGs to `docs/site/assets/figures/`; the generator is the regeneration source. Pages CI must not render.
- Result figures must load committed studies with `run_solver=False` (no Code_Aster/WSL/Docker).
- SI units in all copy: meters, pascal, Celsius. Section `OD`/`WT` in meters.
- Local-axis colour convention (match `add_local_axes_to_plotter`): X red `#ff3b30`, Y green `#7ed321`, Z blue `#2f80ff`.
- Figure render background `#111827`; default resolution `(1600, 1000)`.
- Keep the existing light site theme, sidebar nav, and the `viewer/?bundle=code-aster-review` review links working.
- Run Python via `.\.venv\Scripts\python.exe`. Run tests with `python -m unittest`.
- Commit messages use `docs:` prefix.

---

## File Structure

- Create `docs/site/assets/generate_figures.py` — the figure generator: shared render helpers + one function per figure + a `FIGURES` registry + `main()`.
- Create `docs/site/assets/figures/*.png` — committed rendered stills (generated output).
- Create `tests/test_docs_figures.py` — renders every registered figure off-screen to a temp dir and asserts a non-empty PNG.
- Modify `tests/test_static_site_docs.py` — invert `test_core_docs_include_visual_diagrams` to the real-figure/embed contract.
- Modify all of `docs/site/*.html` (10 pages) — swap Mermaid/CSS pseudo-graphics for `<figure>`/embeds.
- Modify `docs/site/assets/site.css` — add `.figure*` styles; later remove dead sketch/Mermaid classes.
- Delete `docs/site/assets/diagrams.js` — Mermaid loader (after pages stop referencing it).
- Modify `.github/workflows/tuba-pages.yml` — ensure viewer bundles land under `_site/viewer/<bundle>/`.

---

## Task 1: Figure generator scaffold + section gallery figure

**Files:**
- Create: `docs/site/assets/generate_figures.py`
- Create: `tests/test_docs_figures.py`

**Interfaces:**
- Produces: `generate_figures.FIG_DIR: Path`, `generate_figures.RES: tuple[int,int]`, `generate_figures.FIGURES: dict[str, Callable[[Path], Path]]`, `generate_figures.main(out_dir: Path = FIG_DIR) -> None`, and helpers `_steel(model)`, `_render(model, path, *, results=None, deform_scale=None, local_axes=False, local_axes_scale=0.45, supports=False, supports_scale=0.085, res=RES, zoom=1.5) -> Path`. Each figure function has signature `fig_<name>(out_dir: Path) -> Path`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_docs_figures.py`:

```python
import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GEN = REPO / "docs" / "site" / "assets" / "generate_figures.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_figures", GEN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestDocsFigures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gen = _load_generator()

    def test_every_registered_figure_renders_a_png(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            for name, fn in self.gen.FIGURES.items():
                path = fn(out)
                self.assertTrue(path.exists(), f"{name}: no file")
                self.assertGreater(path.stat().st_size, 2000, f"{name}: PNG too small")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_docs_figures -v`
Expected: FAIL — `generate_figures.py` does not exist (import error).

- [ ] **Step 3: Create the generator with helpers + the section figure**

Create `docs/site/assets/generate_figures.py`:

```python
"""Render the documentation figures from the real Tuba pipeline.

Run:  .\\.venv\\Scripts\\python.exe docs/site/assets/generate_figures.py
Outputs committed PNGs under docs/site/assets/figures/. No solver required.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
import pyvista as pv

from tuba import Model
from tuba.plotting.scenes import build_model_scene
from tuba.plotting.plots import add_local_axes_to_plotter, _add_supports_to_plotter
from tuba.plotting.export import export_screenshot

FIG_DIR = Path(__file__).resolve().parent / "figures"
RES = (1600, 1000)


def _steel(model: Model) -> None:
    model.add_material(
        "steel", E=210e9, nu=0.3, rho=7850.0, alpha=12e-6,
        allowable_stress={20.0: 140e6, 180.0: 120e6},
    )


def _render(model, path: Path, *, results=None, deform_scale=None,
            local_axes=False, local_axes_scale=0.45,
            supports=False, supports_scale=0.085,
            res=RES, zoom=1.5) -> Path:
    plotter = build_model_scene(model, results, off_screen=True, title="",
                                deform_scale=deform_scale)
    if local_axes:
        add_local_axes_to_plotter(plotter, model, scale=local_axes_scale)
    if supports:
        _add_supports_to_plotter(plotter, model, scale=supports_scale)
    plotter.reset_camera()
    plotter.camera.zoom(zoom)
    export_screenshot(plotter, str(path), resolution=res)
    plotter.close()
    return path


def fig_sections(out_dir: Path) -> Path:
    m = Model(project_name="Sections")
    _steel(m)
    m.add_pipe_section("Pipe", OD=0.25, WT=0.02)
    m.add_bar_section("Bar", OD=0.18, WT=0.0)
    m.add_cable_section("Cable", radius=0.04, pretension=500.0)
    m.add_rectangular_section("Box", height_y=0.24, height_z=0.14,
                              thickness_y=0.012, thickness_z=0.012)
    m.add_ibeam_section("IBeam", "HE200B")
    members = [("Pipe", "pipe_straight"), ("Bar", "bar"), ("Cable", "cable"),
               ("Box", "beam"), ("IBeam", "beam")]
    for i, (sec, etype) in enumerate(members):
        y = i * 0.7
        n1 = m.add_node([0.0, y, 0.0])
        n2 = m.add_node([1.4, y, 0.0])
        m.add_element(id=f"e_{sec}", type=etype, n1=n1, n2=n2, section=sec, material="steel")
    return _render(m, out_dir / "sections.png", zoom=1.5)


FIGURES: dict[str, Callable[[Path], Path]] = {
    "sections": fig_sections,
}


def main(out_dir: Path = FIG_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, fn in FIGURES.items():
        path = fn(out_dir)
        print(f"OK  {path.relative_to(out_dir.parent)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_docs_figures -v`
Expected: PASS (renders `sections.png` to a temp dir).

- [ ] **Step 5: Commit**

```bash
git add docs/site/assets/generate_figures.py tests/test_docs_figures.py
git commit -m "docs: add figure generator scaffold with section gallery figure"
```

---

## Task 2: Modeling concept figures — element triad, placement frame, builder route

**Files:**
- Modify: `docs/site/assets/generate_figures.py`

**Interfaces:**
- Consumes: `_steel`, `_render`, `FIGURES` from Task 1.
- Produces: `fig_element_triad`, `fig_placement_frame`, `fig_builder_route`; registry keys `element_triad`, `placement_frame`, `builder_route`.

- [ ] **Step 1: Add a triad helper and the three figures**

Add near the top of `generate_figures.py` (after `_render`):

```python
from tuba import PlacementFrame
from tuba.coordinates import CoordinateSystem


def _triad(plotter, origin, cs, scale, labels) -> None:
    origin = np.asarray(origin, dtype=float)
    axes = ((cs.x_axis, "#ff3b30", labels[0]),
            (cs.y_axis, "#7ed321", labels[1]),
            (cs.z_axis, "#2f80ff", labels[2]))
    tips, texts = [], []
    for vec, col, lbl in axes:
        v = np.asarray(vec, dtype=float)
        plotter.add_mesh(pv.Arrow(start=origin, direction=v, scale=scale,
                                  tip_radius=0.07, shaft_radius=0.028),
                         color=col, lighting=False)
        tips.append(origin + v * scale * 1.08)
        texts.append(lbl)
    plotter.add_mesh(pv.Sphere(radius=scale * 0.05, center=origin), color="#e5e7eb")
    plotter.add_point_labels(np.array(tips), texts, font_size=16, text_color="white",
                             shape=None, show_points=False, always_visible=True)
```

Add the three figure functions (before the `FIGURES` dict):

```python
def fig_element_triad(out_dir: Path) -> Path:
    """One straight pipe element with its local X/Y/Z triad."""
    m = Model(project_name="ElementTriad")
    _steel(m)
    m.add_pipe_section("DN150", OD=0.1683, WT=0.0071)
    with m.pipe(section="DN150", material="steel", route="P") as p:
        p.start([0.0, 0.0, 0.0])
        p.run(2.5)
    return _render(m, out_dir / "element_triad.png", local_axes=True,
                   local_axes_scale=0.7, zoom=1.4)


def fig_placement_frame(out_dir: Path) -> Path:
    """World triad + a rotated local placement frame with a pipe authored in local coords."""
    m = Model(project_name="Placement")
    _steel(m)
    m.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    frame = PlacementFrame(id="rack", origin=(2.4, 1.4, 0.4),
                           axis=(0.0, 0.35, 1.0), ref_direction=(1.0, 0.6, 0.0))
    cs = frame.to_coordinate_system()
    start_g = cs.to_global_point(np.array([0.0, 0.0, 0.0]))
    end_g = cs.to_global_point(np.array([1.8, 0.0, 0.0]))
    n1 = m.add_node(start_g.tolist())
    n2 = m.add_node(end_g.tolist())
    m.add_element(id="local_pipe", type="pipe_straight", n1=n1, n2=n2,
                  section="DN100", material="steel")
    plotter = build_model_scene(m, off_screen=True, title="")
    _triad(plotter, (0.0, 0.0, 0.0), CoordinateSystem.identity(), 1.1,
           ["world X", "world Y", "world Z"])
    _triad(plotter, cs.origin, cs, 1.0, ["local X", "local Y", "local Z"])
    plotter.reset_camera()
    plotter.camera.zoom(1.2)
    export_screenshot(plotter, str(out_dir / "placement_frame.png"), resolution=RES)
    plotter.close()
    return out_dir / "placement_frame.png"


def fig_builder_route(out_dir: Path) -> Path:
    """Local triad following a pipe through an in-plane and an out-of-plane bend."""
    m = Model(project_name="BuilderRoute")
    _steel(m)
    m.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    with m.pipe(section="DN100", material="steel", route="P-100") as p:
        p.start([0.0, 0.0, 0.0], support="anchor")
        p.run(2.0)
        p.bend(radius=0.3, angle=90.0, plane="XY")
        p.run(1.5)
        p.bend(radius=0.3, angle=90.0, plane="XZ")
        p.run(1.2)
        p.end(support="anchor")
    return _render(m, out_dir / "builder_route.png", local_axes=True,
                   local_axes_scale=0.45, supports=True, supports_scale=0.085, zoom=1.5)
```

Extend the registry:

```python
FIGURES: dict[str, Callable[[Path], Path]] = {
    "sections": fig_sections,
    "element_triad": fig_element_triad,
    "placement_frame": fig_placement_frame,
    "builder_route": fig_builder_route,
}
```

- [ ] **Step 2: Run the figure test**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_docs_figures -v`
Expected: PASS — 4 figures now render.

- [ ] **Step 3: Commit**

```bash
git add docs/site/assets/generate_figures.py
git commit -m "docs: add element-triad, placement-frame, builder-route figures"
```

---

## Task 3: Modeling figures — supports glyphs + bend chord-vs-arc

**Files:**
- Modify: `docs/site/assets/generate_figures.py`

**Interfaces:**
- Consumes: `_steel`, `_render`, `build_model_scene`, `export_screenshot`.
- Produces: `fig_supports`, `fig_bend_chord_arc`; registry keys `supports`, `bend_chord_arc`.

- [ ] **Step 1: Confirm the arc-sampling entry point**

Run: `.\.venv\Scripts\python.exe -c "from tuba.model import sample_bend_geometry; import inspect; print(inspect.signature(sample_bend_geometry))"`
Expected: prints a signature taking a `BendGeometry` (and a steps count). If the name differs, run `.\.venv\Scripts\python.exe -c "import tuba.model as M; print([n for n in dir(M) if 'bend' in n.lower()])"` and use the sampler that returns arc points from a `BendGeometry`.

- [ ] **Step 2: Add the two figures**

```python
def fig_supports(out_dir: Path) -> Path:
    """Anchor / guide / rest / spring support glyphs on a routed pipe."""
    m = Model(project_name="Supports")
    _steel(m)
    m.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    with m.pipe(section="DN100", material="steel", route="S") as p:
        p.start([0.0, 0.0, 0.0], support="anchor")
        p.run(1.5)
        p.add_support(type="guide")
        p.run(1.5)
        p.add_support(type="rest")
        p.run(1.5)
        p.add_support(type="spring")
        p.run(1.5)
        p.end(support="anchor")
    return _render(m, out_dir / "supports.png", supports=True, supports_scale=0.1, zoom=1.4)


def fig_bend_chord_arc(out_dir: Path) -> Path:
    """The FE node chord (tangent-intersection) vs the true stored circular arc."""
    from tuba.model import sample_bend_geometry

    m = Model(project_name="BendChordArc")
    _steel(m)
    m.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    with m.pipe(section="DN100", material="steel", route="B") as p:
        p.start([0.0, 0.0, 0.0])
        p.run(1.5)
        p.bend(radius=0.6, angle=90.0, plane="XY")
        p.run(1.5)

    plotter = build_model_scene(m, off_screen=True, title="")
    # Straight FE chord: polyline through the actual stored node coordinates.
    node_pts = np.array([m.nodes[n].coords for n in m.nodes], dtype=float)
    order = [e.n1 for e in m.elements] + [m.elements[-1].n2]
    chord = np.array([m.nodes[n].coords for n in order], dtype=float)
    plotter.add_mesh(pv.lines_from_points(chord), color="#f5a623", line_width=6,
                     label="FE node chord")
    plotter.add_mesh(pv.PolyData(chord), color="#f5a623", point_size=14,
                     render_points_as_spheres=True)
    # True arc for the bend element.
    bend = next(e for e in m.elements if e.type == "pipe_bend")
    arc = np.asarray(sample_bend_geometry(bend.bend_geometry), dtype=float)
    plotter.add_mesh(pv.lines_from_points(arc), color="#2f80ff", line_width=6,
                     label="true arc")
    plotter.add_point_labels(
        np.array([chord[1], arc[len(arc) // 2]]),
        ["FE node (tangent point)", "true arc"],
        font_size=15, text_color="white", shape=None, show_points=False, always_visible=True)
    plotter.reset_camera()
    plotter.camera.zoom(1.6)
    export_screenshot(plotter, str(out_dir / "bend_chord_arc.png"), resolution=RES)
    plotter.close()
    return out_dir / "bend_chord_arc.png"
```

Register both:

```python
    "supports": fig_supports,
    "bend_chord_arc": fig_bend_chord_arc,
```

Note: `sample_bend_geometry` returns ordered arc points. If Step 1 showed it needs a `steps=` argument, pass `sample_bend_geometry(bend.bend_geometry, steps=48)`.

- [ ] **Step 3: Run the figure test and eyeball the two PNGs**

Run: `.\.venv\Scripts\python.exe docs/site/assets/generate_figures.py`
Then open `docs/site/assets/figures/bend_chord_arc.png` and `supports.png`. Confirm the amber chord visibly cuts the corner while the blue arc bulges out (the bend rise), and the four support glyphs are distinct.

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_docs_figures -v`
Expected: PASS — 6 figures.

- [ ] **Step 4: Commit**

```bash
git add docs/site/assets/generate_figures.py
git commit -m "docs: add supports and bend chord-vs-arc figures"
```

---

## Task 4: Result + route figures — model, money-shot, pre-route, candidates

**Files:**
- Modify: `docs/site/assets/generate_figures.py`

**Interfaces:**
- Consumes: `_render`, `build_model_scene`, `export_screenshot`.
- Produces: `fig_tutorial_model`, `fig_money_shot`, `fig_route_preroute`, `fig_route_candidates`; registry keys `tutorial_model`, `money_shot`, `route_preroute`, `route_candidates`.

- [ ] **Step 1: Add the shared review model + geometry and money-shot figures**

The review model is copied verbatim from `notebooks/10_interactive_postprocessor.ipynb` (it matches the committed `viz_gallery_operating` study).

```python
REPO_ROOT = Path(__file__).resolve().parents[3]  # docs/site/assets -> repo root


def _viz_gallery_model() -> Model:
    m = Model("VizGalleryDemo", standard="ASME_B31.3")
    m.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5,
                   allowable_stress={20.0: 137e6, 150.0: 127e6})
    m.add_pipe_section("DN100", OD=0.1143, WT=0.00602, corrosion_allowance=0.001)
    m.define_load_case("Operating", gravity=True, pressure=1.5e6,
                       temperature=150.0, ref_temperature=20.0)
    with m.pipe(section="DN100", material="Steel") as b:
        b.start([0, 0, 0], support="anchor")
        b.run(3.0)
        b.add_support(type="guide")
        b.bend(radius=0.3, angle=90, plane="XY")
        b.run(2.0)
        b.add_support(type="rest")
        b.bend(radius=0.3, angle=90, plane="XZ")
        b.run(2.0)
        b.end(support="anchor")
    m.validate()
    return m


def fig_tutorial_model(out_dir: Path) -> Path:
    """The review model as pure geometry — 'just data until it is solved'."""
    return _render(_viz_gallery_model(), out_dir / "tutorial_model.png",
                   supports=True, supports_scale=0.09, zoom=1.4)


def fig_money_shot(out_dir: Path) -> Path:
    """Deformed shape + Von Mises stress from the committed viz_gallery_operating study."""
    from tuba.analysis.code_aster_notebook import load_or_run_code_aster_results

    model = _viz_gallery_model()
    work_dir = REPO_ROOT / "notebooks" / "code_aster_results" / "viz_gallery_operating"
    run = load_or_run_code_aster_results(model, "Operating", work_dir, run_solver=False)
    return _render(model, out_dir / "money_shot.png", results=run.results,
                   deform_scale=50.0, zoom=1.4)
```

- [ ] **Step 2: Verify the money-shot loads committed results (no solver)**

Run: `.\.venv\Scripts\python.exe -c "import importlib.util,sys; from pathlib import Path; p=Path('docs/site/assets/generate_figures.py'); s=importlib.util.spec_from_file_location('g',p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); import tempfile; d=Path(tempfile.mkdtemp()); print(m.fig_money_shot(d))"`
Expected: prints a PNG path, no solver invocation, no WSL/Docker. If `load_or_run_code_aster_results` errors on missing exec kwargs, add `exec_method='wsl'` to the call (unused when `run_solver=False`).

- [ ] **Step 3: Add the route figures by reusing notebook 05's request/result**

Open `notebooks/05_autorouting.ipynb` and copy the model + `RouteRequest` construction from cell 7 (pre-route) and the autoroute `result` from cell 11 into the two functions below, replacing the marked lines. `build_route_plotter` already accepts `off_screen`.

```python
def _route_model_and_request():
    from tuba.routing import RouteRequest  # confirm exact import from nb05 cell imports
    m = Model("RouteDemo")
    _steel(m)
    m.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    # --- paste obstacle/endpoint/model setup from nb05 cell 7 here ---
    request = RouteRequest(...)  # --- paste the RouteRequest args from nb05 cell 7 ---
    return m, request


def fig_route_preroute(out_dir: Path) -> Path:
    from tuba.routing.visualization import build_route_plotter
    m, request = _route_model_and_request()
    plotter = build_route_plotter(m, request=request, off_screen=True)
    plotter.reset_camera(); plotter.camera.zoom(1.3)
    export_screenshot(plotter, str(out_dir / "route_preroute.png"), resolution=RES)
    plotter.close()
    return out_dir / "route_preroute.png"


def fig_route_candidates(out_dir: Path) -> Path:
    from tuba.routing.visualization import build_route_plotter
    from tuba.routing import solve_route  # confirm exact solver entry from nb05 cell 11
    m, request = _route_model_and_request()
    run = solve_route(m, request)  # --- match nb05 cell 11's solve call + .result attr ---
    plotter = build_route_plotter(m, request=request, result=run.result, off_screen=True)
    plotter.reset_camera(); plotter.camera.zoom(1.3)
    export_screenshot(plotter, str(out_dir / "route_candidates.png"), resolution=RES)
    plotter.close()
    return out_dir / "route_candidates.png"
```

Register all four:

```python
    "tutorial_model": fig_tutorial_model,
    "money_shot": fig_money_shot,
    "route_preroute": fig_route_preroute,
    "route_candidates": fig_route_candidates,
```

- [ ] **Step 4: Run the figure test**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_docs_figures -v`
Expected: PASS — 10 figures render off-screen with no solver.

- [ ] **Step 5: Commit**

```bash
git add docs/site/assets/generate_figures.py
git commit -m "docs: add model, deformed-stress money-shot, and route figures"
```

---

## Task 5: Render + commit the figure set

**Files:**
- Create: `docs/site/assets/figures/*.png` (generated)

- [ ] **Step 1: Render all figures to the committed directory**

Run: `.\.venv\Scripts\python.exe docs/site/assets/generate_figures.py`
Expected: prints `OK figures/<name>.png` for all 10.

- [ ] **Step 2: Eyeball each PNG**

Open every file in `docs/site/assets/figures/`. Each must be well-framed (no large dead margins), on the dark background, with legible triads/labels. If any is poorly framed, adjust that figure's `zoom=` and re-run Step 1.

- [ ] **Step 3: Commit the figures**

```bash
git add docs/site/assets/figures
git commit -m "docs: render committed figure set from Tuba pipeline"
```

---

## Task 6: Figure + embed CSS

**Files:**
- Modify: `docs/site/assets/site.css`

**Interfaces:**
- Produces: CSS classes `.figure`, `.figure img`, `.figure figcaption`, `.figure-grid`. `.viewer-panel` already exists and is reused for embeds.

- [ ] **Step 1: Append figure styles**

Add to `docs/site/assets/site.css` (do NOT remove any existing classes yet — pages still use them until their rewrite tasks):

```css
.figure {
  margin: 12px 0 0;
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
  background: #111827;
}

.figure img {
  display: block;
  width: 100%;
  height: auto;
}

.figure figcaption {
  padding: 10px 14px;
  border-top: 1px solid rgb(255 255 255 / 10%);
  color: #cbd5e1;
  font-size: 13px;
  line-height: 1.4;
}

.figure-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

@media (max-width: 620px) {
  .figure-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add docs/site/assets/site.css
git commit -m "docs: add figure and figure-grid styles"
```

---

## Task 7: Invert the docs visual-structure test (defines the target, goes RED)

**Files:**
- Modify: `tests/test_static_site_docs.py:78-95` (the `test_core_docs_include_visual_diagrams` method)

**Interfaces:**
- Produces: a parametrized contract mapping each page to required figure/embed references and forbidden tokens. Page-rewrite tasks (8–12) turn each page's assertions green.

- [ ] **Step 1: Replace the test method**

Replace `test_core_docs_include_visual_diagrams` (and the following `for selector in (...)` assertion block, lines ~78-95) with:

```python
    def test_pages_use_real_figures_not_sketches(self):
        # page -> figure basenames it must reference (files under assets/figures/)
        required_figures = {
            "index.html": ["money_shot.png"],
            "tutorial.html": ["tutorial_model.png", "money_shot.png"],
            "modeling.html": ["element_triad.png", "placement_frame.png",
                              "builder_route.png", "bend_chord_arc.png",
                              "sections.png", "supports.png"],
            "overview.html": ["money_shot.png"],
            "workflow.html": ["tutorial_model.png", "money_shot.png"],
            "autorouting.html": ["route_preroute.png", "route_candidates.png"],
        }
        forbidden = ['class="mermaid"', "diagrams.js", "axis-sketch",
                     "section-gallery", "routing-sketch", "artifact-lifecycle",
                     "module-map", "process-map"]
        figures_dir = self.site_dir / "assets" / "figures"
        for page, figs in required_figures.items():
            text = (self.site_dir / page).read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, f"{page} still contains {token!r}")
            for fig in figs:
                self.assertIn(f"figures/{fig}", text, f"{page} missing {fig}")
                self.assertTrue((figures_dir / fig).exists(), f"missing file {fig}")

    def test_frame_and_result_pages_embed_the_viewer(self):
        embeds = {
            "modeling.html": "imported_component_mixed_demo",
            "tutorial.html": "code-aster-review",
            "examples.html": "code-aster-review",
        }
        for page, bundle in embeds.items():
            text = (self.site_dir / page).read_text(encoding="utf-8")
            self.assertIn(f"bundle={bundle}", text, f"{page} missing viewer embed")
```

Note: use the module's existing site-dir constant if it is named differently than `self.site_dir` — match the surrounding class (check the top of `TestStaticSiteDocs`).

- [ ] **Step 2: Run the test to verify it fails (target defined)**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_static_site_docs -v`
Expected: FAIL — pages still contain Mermaid/sketches and lack figure references. This is the RED that tasks 8–12 resolve.

- [ ] **Step 3: Commit**

```bash
git add tests/test_static_site_docs.py
git commit -m "docs: assert real figures and viewer embeds instead of sketches"
```

---

## Task 8: Rewrite modeling.html (the deductive spine)

**Files:**
- Modify: `docs/site/modeling.html`

- [ ] **Step 1: Replace the pseudo-graphic sections with the figure spine**

Remove these blocks from `modeling.html`: the "Data model map" `visual-section` (the `<pre class="mermaid">` + `.model-map`), the entire `.section-gallery` block, the "Local coordinate systems" `<pre class="mermaid">` + `.axis-sketch` block, and the `<script type="module" src="./assets/diagrams.js">` include. Keep every reference table, the code-grid examples, the notes, and the error-boundary content.

Insert the deductive spine (each figure directly above the prose/table it explains). Use this exact figure markup, one per concept:

```html
<figure class="figure">
  <img src="./assets/figures/element_triad.png" width="1600" height="1000"
       alt="A straight pipe element with its local X (red, axial), Y (green), and Z (blue) axes." />
  <figcaption>A frame is three orthonormal vectors. Every element carries a local
    triad: X (red) runs along the member axis, Z (blue) is up, Y (green) = Z × X.</figcaption>
</figure>

<figure class="figure">
  <img src="./assets/figures/placement_frame.png" width="1600" height="1000"
       alt="World coordinate triad and a rotated local placement frame with a pipe authored in local coordinates." />
  <figcaption>A placement frame is a local coordinate system positioned in the world:
    <code>axis</code> is local Z, <code>ref_direction</code> is projected to local X,
    Y = Z × X. Points authored in local coordinates map to the world by
    <code>origin + basis · p</code>.</figcaption>
</figure>

<figure class="figure">
  <img src="./assets/figures/builder_route.png" width="1600" height="1000"
       alt="A pipe routed through an in-plane and an out-of-plane bend, with the local triad reorienting at each element." />
  <figcaption>The pipe builder is a moving frame. <code>run</code> advances along the
    current forward (local X); <code>bend</code> rotates it about a plane axis. Watch the
    red axial arrow turn through the in-plane and the out-of-plane bend.</figcaption>
</figure>

<figure class="figure">
  <img src="./assets/figures/bend_chord_arc.png" width="1600" height="1000"
       alt="The straight chord between finite-element nodes at the tangent point versus the true circular bend arc." />
  <figcaption>A bend stores the true circular arc, but the finite-element nodes sit at
    the tangent-intersection point — a straight chord. The gap between the amber chord
    and the blue arc is the bend rise.</figcaption>
</figure>

<figure class="figure">
  <img src="./assets/figures/sections.png" width="1600" height="1000"
       alt="Pipe, bar, cable, rectangular, and I-beam sections shown as true extruded 3D solids." />
  <figcaption>Sections give the 1-D centerline a 3-D body. Left to right: pipe (note the
    bore and wall), solid bar, cable, rectangular hollow, and I-beam. <code>OD</code>/<code>WT</code>
    are meters.</figcaption>
</figure>

<figure class="figure">
  <img src="./assets/figures/supports.png" width="1600" height="1000"
       alt="Anchor, guide, rest, and spring support glyphs on a routed pipe." />
  <figcaption>Supports are boundary conditions with real geometry: anchor, guide, rest,
    and spring hanger, each aligned to the pipe's local frame.</figcaption>
</figure>
```

- [ ] **Step 2: Add the live frames embed**

Where the old "Local coordinate systems" section was, add a live viewer (below the placement-frame figure):

```html
<section class="doc-section">
  <h2>See it live</h2>
  <p>Drag to orbit. The global gizmo and each component's local axis triad are the
    same vectors shown above, now interactive.</p>
  <iframe class="viewer-panel" title="Interactive frames viewer"
          src="./viewer/?bundle=imported_component_mixed_demo&embed=1"
          loading="lazy"></iframe>
</section>
```

- [ ] **Step 3: Verify modeling.html assertions pass**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_static_site_docs -v`
Expected: the modeling.html entries in both new tests pass (other pages may still fail — that is expected until their tasks).

- [ ] **Step 4: Commit**

```bash
git add docs/site/modeling.html
git commit -m "docs: rebuild modeling page as deductive spine with real figures"
```

---

## Task 9: Rewrite tutorial.html

**Files:**
- Modify: `docs/site/tutorial.html`

- [ ] **Step 1: Replace the "Workflow picture" section**

Remove the `visual-section` containing the `<pre class="mermaid">` flowchart and the `.process-map`, the `.artifact-lifecycle` graphic, and the `diagrams.js` script include. Keep the whole script, the "What each part does" table, the "Expected files" table, and all prose.

Replace the removed "Workflow picture" with two figures that show the real before/after of the tutorial:

```html
<section class="doc-section visual-section">
  <h2>What you are building</h2>
  <div class="figure-grid">
    <figure class="figure">
      <img src="./assets/figures/tutorial_model.png" width="1600" height="1000"
           alt="The tutorial pipe model as geometry with anchor, guide, and rest supports." />
      <figcaption>Step 1 — the model. Python data only: nodes, pipe elements, supports.
        No results yet.</figcaption>
    </figure>
    <figure class="figure">
      <img src="./assets/figures/money_shot.png" width="1600" height="1000"
           alt="The same pipe deformed under load and coloured by Von Mises stress." />
      <figcaption>Step 3 — the review. The same model after Code_Aster solved it:
        deformed shape, Von Mises stress. Only shown after real results are imported.</figcaption>
    </figure>
  </div>
</section>
```

- [ ] **Step 2: Add the result-review embed near "Expected files"**

```html
<section class="doc-section">
  <h2>Review it in the browser</h2>
  <iframe class="viewer-panel" title="Code_Aster review viewer"
          src="./viewer/?bundle=code-aster-review&embed=1" loading="lazy"></iframe>
</section>
```

- [ ] **Step 3: Verify + commit**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_static_site_docs -v`
Expected: tutorial.html entries pass.

```bash
git add docs/site/tutorial.html
git commit -m "docs: replace tutorial flowchart with real model and result figures"
```

---

## Task 10: Rewrite index.html + overview.html

**Files:**
- Modify: `docs/site/index.html`, `docs/site/overview.html`

- [ ] **Step 1: index.html — hero render**

Remove any `.flow-strip`/pseudo-graphic used as a picture. Add a hero figure after the intro:

```html
<figure class="figure">
  <img src="./assets/figures/money_shot.png" width="1600" height="1000"
       alt="A piping system deformed under operating load and coloured by Von Mises stress." />
  <figcaption>Tuba models piping, runs Code_Aster, and reviews real results — like this
    deformed, stress-coloured operating case.</figcaption>
</figure>
```

- [ ] **Step 2: overview.html — replace the "System map"**

Remove the `System map` `<pre class="mermaid">` and `.module-map` graphic and the `diagrams.js` include. Add:

```html
<figure class="figure">
  <img src="./assets/figures/money_shot.png" width="1600" height="1000"
       alt="Deformed, stress-coloured piping model produced by the Tuba pipeline." />
  <figcaption>From typed model to solved result: the system exists to turn a validated
    model into reviewable Code_Aster results.</figcaption>
</figure>
```

Keep the existing textual module descriptions and tables (convert the module-map picture to a plain list only if it was purely graphical).

- [ ] **Step 3: Verify + commit**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_static_site_docs -v`
Expected: index.html and overview.html entries pass.

```bash
git add docs/site/index.html docs/site/overview.html
git commit -m "docs: add real hero and system renders to index and overview"
```

---

## Task 11: Rewrite workflow.html + developer.html

**Files:**
- Modify: `docs/site/workflow.html`, `docs/site/developer.html`

- [ ] **Step 1: workflow.html — replace the "Execution sequence"**

Remove the `Execution sequence` `<pre class="mermaid">` and the `diagrams.js` include. Replace with a real model→result sequence:

```html
<section class="doc-section visual-section">
  <h2>Model, solve, review</h2>
  <div class="figure-grid">
    <figure class="figure">
      <img src="./assets/figures/tutorial_model.png" width="1600" height="1000"
           alt="A validated piping model as geometry." />
      <figcaption>Define &amp; validate — Python data.</figcaption>
    </figure>
    <figure class="figure">
      <img src="./assets/figures/money_shot.png" width="1600" height="1000"
           alt="The solved model, deformed and stress-coloured." />
      <figcaption>Solve &amp; review — real Code_Aster results.</figcaption>
    </figure>
  </div>
</section>
```

Keep the "Two review paths" prose/table as text.

- [ ] **Step 2: developer.html — replace the "Module dependency picture"**

Remove the `Module dependency picture` `<pre class="mermaid">` and the `diagrams.js` include. Replace the pseudo-diagram with a plain nested list of module dependencies (text is the right tool for a dependency map). Keep the "Change ownership" table.

- [ ] **Step 3: Verify + commit**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_static_site_docs -v`
Expected: workflow.html entries pass; developer.html no longer trips the forbidden-token checks (it is not in `required_figures`, but the whole-suite run below covers it).

```bash
git add docs/site/workflow.html docs/site/developer.html
git commit -m "docs: replace workflow and developer flowcharts with a render sequence and text"
```

---

## Task 12: Rewrite autorouting.html + examples.html + commands.html + setup.html

**Files:**
- Modify: `docs/site/autorouting.html`, `docs/site/examples.html`, `docs/site/commands.html`, `docs/site/setup.html`

- [ ] **Step 1: autorouting.html — real route scenes**

Remove the `Autorouting at a glance` `<pre class="mermaid">`, the `.routing-sketch` block, the `Solver-loop decision` mermaid, and the `diagrams.js` include. Add:

```html
<section class="doc-section visual-section">
  <h2>What the router sees, and what it returns</h2>
  <div class="figure-grid">
    <figure class="figure">
      <img src="./assets/figures/route_preroute.png" width="1600" height="1000"
           alt="Obstacles and start/goal endpoints before routing." />
      <figcaption>Before routing: obstacles (boxes) and the start/goal endpoints.</figcaption>
    </figure>
    <figure class="figure">
      <img src="./assets/figures/route_candidates.png" width="1600" height="1000"
           alt="Candidate routes as tubes with reserved envelopes around obstacles." />
      <figcaption>After routing: candidate routes (selected highlighted) with reserved
        clearance envelopes.</figcaption>
    </figure>
  </div>
  <p class="actions"><a class="button" href="./viewer/?bundle=code-aster-review">Open a live scene in the viewer</a></p>
</section>
```

- [ ] **Step 2: examples.html — confirm the embed target**

Ensure the existing `<iframe ... src="./viewer/?bundle=code-aster-review&embed=1">` is present and correct (the new `test_frame_and_result_pages_embed_the_viewer` asserts `bundle=code-aster-review`). Remove any leftover Mermaid/sketch on the page.

- [ ] **Step 3: commands.html + setup.html — strip pseudo-graphics**

Remove any `<pre class="mermaid">`, `.flow-strip` used as a picture, and the `diagrams.js` include from both. These pages are text/tables; add a single relevant figure only if a section clearly benefits (optional). Keep all command/setup tables and prose.

- [ ] **Step 4: Verify + commit**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_static_site_docs -v`
Expected: all `required_figures` and embed assertions pass.

```bash
git add docs/site/autorouting.html docs/site/examples.html docs/site/commands.html docs/site/setup.html
git commit -m "docs: real route scenes and cleaned pseudo-graphics on remaining pages"
```

---

## Task 13: Remove dead CSS + delete the Mermaid loader

**Files:**
- Modify: `docs/site/assets/site.css`
- Delete: `docs/site/assets/diagrams.js`

- [ ] **Step 1: Confirm nothing references the removed assets**

Run: `grep -rl "diagrams.js" docs/site/*.html || echo "clean"`
Expected: `clean`.
Run: `grep -rlE "class=\"mermaid\"|axis-sketch|section-gallery|routing-sketch|artifact-lifecycle|module-map|process-map|pipe-ring|bar-solid|cable-dot|rect-box|ibeam-shape" docs/site/*.html || echo "clean"`
Expected: `clean`.

- [ ] **Step 2: Delete the loader and dead CSS**

```bash
git rm docs/site/assets/diagrams.js
```

In `docs/site/assets/site.css`, delete the now-unused rule groups: `.mermaid`/`.mermaid-unavailable`, `.diagram-grid`/`.diagram-card`/`.visual-card`, `.process-map`/`.process-row`/`.process-node`/`.process-arrow` (and the `.artifact-*`/`.module-*` siblings if only used as graphics), `.routing-sketch` and all `.route-*`/`.obstacle-box`/`.loop-envelope`/`.routing-caption`, `.model-map`/`.model-pill`, `.section-gallery`/`.section-card`/`.section-visual` and every section-shape rule (`.pipe-ring`, `.diameter-line`, `.wall-line`, `.bar-solid`, `.cable-dot`, `.rect-box`, `.ibeam-shape`), and `.axis-sketch`/`.axis*`/`.axis-label`/`.x-label`/`.y-label`/`.z-label`. Keep `.viewer-panel`, `.figure*`, `.error-stack`, tables, and everything still referenced.

- [ ] **Step 3: Confirm no CSS class referenced by remaining HTML was deleted**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_static_site_docs -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add docs/site/assets/site.css
git commit -m "docs: remove Mermaid loader and dead sketch CSS"
```

---

## Task 14: Wire viewer bundles into the Pages build

**Files:**
- Modify: `.github/workflows/tuba-pages.yml`

**Interfaces:**
- Consumes: viewer bundles already in `viewer/public/` (`code-aster-review`, `imported_component_mixed_demo`).

- [ ] **Step 1: Confirm the required bundles exist in `viewer/public/`**

Run: `ls viewer/public`
Expected: includes `code-aster-review` and `imported_component_mixed_demo`.

- [ ] **Step 2: Ensure the build ships them under `_site/viewer/`**

Read `.github/workflows/tuba-pages.yml`. It builds `viewer/` and copies `viewer/dist` → `_site/viewer`. Vite copies `viewer/public/*` into `dist/` during build, so both bundles land under `_site/viewer/<bundle>/` automatically. If the workflow builds with a filter that excludes `public/`, add an explicit copy step:

```yaml
      - name: Copy viewer bundles
        run: |
          cp -r viewer/public/code-aster-review _site/viewer/ 2>/dev/null || true
          cp -r viewer/public/imported_component_mixed_demo _site/viewer/ 2>/dev/null || true
```

- [ ] **Step 3: Document local preview**

Add to `docs/tuba-workflow.md` (or the site setup page) a one-line note: to preview embeds locally, run `cd viewer && npm run build` then serve `docs/site/` so `docs/site/viewer/` resolves (the committed site has no built viewer; CI builds it).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/tuba-pages.yml docs/tuba-workflow.md
git commit -m "docs: ship frames and review viewer bundles with the Pages build"
```

---

## Task 15: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the docs + figure + example tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_static_site_docs tests.test_docs_figures tests.test_current_api_docs tests.test_examples tests.test_operating_state_example -v`
Expected: all PASS.

- [ ] **Step 2: HTML/whitespace lint**

Run: `git diff --check`
Expected: no output (no whitespace errors).

- [ ] **Step 3: Browser sweep (Playwright, as in the prior modeling.html pass)**

Serve the site (`.\.venv\Scripts\python.exe -m http.server 8765 --directory docs/site`) and, for all 10 pages at desktop (1280×800) and mobile (390×844): assert each `figure img` loads (naturalWidth > 0), each `iframe.viewer-panel` loads, the sidebar/nav render, and `document.documentElement.scrollWidth <= window.innerWidth` (no horizontal overflow). Note: viewer embeds only resolve if a local viewer build exists (Task 14 Step 3); if not built locally, assert the iframe element is present and skip its load check.

- [ ] **Step 4: Final commit if any fixes were needed**

```bash
git add -A docs/site
git commit -m "docs: fix figure framing and overflow issues found in browser sweep"
```

---

## Self-Review (completed during authoring)

- **Spec coverage:** figure pipeline (Tasks 1–5), both-mediums-by-role stills + embeds (Tasks 8–12), commit-PNGs delivery (Task 5), reuse-only constraint (Global Constraints), deductive spine (Task 8), test inversion (Task 7) + figure test (Task 1) + Playwright (Task 15), CI bundle wiring (Task 14), CSS/Mermaid removal (Task 13). All spec sections map to a task.
- **Placeholder scan:** the only deferred detail is the route request/result construction in Task 4 Step 3 and the `sample_bend_geometry` signature in Task 3 Step 1 — both are explicit "read this exact notebook cell / run this exact introspection command" steps, not vague TODOs, because those upstream signatures are not verifiable from the spec alone.
- **Type consistency:** figure function names, registry keys, and the filenames asserted in Task 7 (`element_triad.png`, `placement_frame.png`, `builder_route.png`, `bend_chord_arc.png`, `sections.png`, `supports.png`, `tutorial_model.png`, `money_shot.png`, `route_preroute.png`, `route_candidates.png`) match the `<img src>` paths in Tasks 8–12.
