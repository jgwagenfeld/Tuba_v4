# Engineering Section Drawings + Modeling Page — Implementation Plan (Increment 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stylized 3D `sections.png` render with a true dimensioned 2D engineering **section plate** (plus per-section detail SVGs and a bend-geometry detail), all generated from the live Tuba section objects, and wire it into `modeling.html`.

**Architecture:** A new committed matplotlib generator `docs/site/assets/generate_section_drawings.py` reads real dimensions via `tuba.geometry.profiles.profile_for_section` and emits SVGs into `docs/site/assets/figures/`. No OpenGL, no solver → CI-safe. `modeling.html` swaps `sections.png`→`sections.svg` and adds the bend detail; the old `fig_sections` and `sections.png` are retired; tests are updated/added.

**Tech Stack:** Python 3.12, matplotlib 3.11 (already in `.venv`), Tuba package, `unittest`/pytest, static HTML/CSS.

## Global Constraints

- Reuse only: **no** changes to `tuba/` runtime, `tuba/plotting`, `tuba/visualization`, or `viewer/`. The generator only *reads* section objects.
- Every dimension shown must come from the live Tuba section object (data-driven), not a hardcoded literal in the drawing.
- Draughting palette from site tokens: object `#1b2026`, dimensions/centrelines `#2f6374`, hatch `#9aa3ad`, inner edges `#5b636d`, sheet `#ffffff`.
- `plt.rcParams["svg.fonttype"] = "none"` so dimension text stays as searchable `<text>`.
- Diameter sign = `Ø` (Ø). Do **not** use `⌀` (U+2300) or `⟂` (U+27C2) — missing from DejaVu, render as tofu.
- Section-plane convention: cut normal to member axis; local Y horizontal, local Z up.
- SI in the model; drawings display **mm** (×1000).
- Run Python via `d:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe`.

---

### Task 1: Section-drawing generator + drawings test

**Files:**
- Create: `docs/site/assets/generate_section_drawings.py`
- Create: `tests/test_section_drawings.py`
- Output (generated, committed): `docs/site/assets/figures/sections.svg`, `section_pipe.svg`, `section_bar.svg`, `section_cable.svg`, `section_rect.svg`, `section_ibeam.svg`, `bend_detail.svg`

**Interfaces:**
- Consumes: `tuba.Model`, `tuba.geometry.profiles.profile_for_section`, `tuba.sections.SectionCatalog`.
- Produces: `main(out_dir: Path = FIG_DIR) -> None` (renders all SVGs); module constant `DIA` (`"Ø"`); `build_sections() -> dict[str, dict]` mapping section name → dims dict.

- [ ] **Step 1: Write the failing test**

Create `tests/test_section_drawings.py`:

```python
import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs" / "site" / "assets" / "generate_section_drawings.py"


def _load():
    spec = importlib.util.spec_from_file_location("generate_section_drawings", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_plate_and_details_render_from_real_dims(tmp_path):
    mod = _load()
    mod.main(out_dir=tmp_path)

    plate = tmp_path / "sections.svg"
    assert plate.exists() and plate.stat().st_size > 0
    ET.parse(plate)  # well-formed XML
    text = plate.read_text(encoding="utf-8")
    # data-driven: the real Tuba dimensions must appear as text in the drawing
    for token in [mod.DIA + "114.3", "HE200B", mod.DIA + "180", "240", "R40"]:
        assert token in text, f"plate missing {token!r}"

    for name in ["section_pipe.svg", "section_bar.svg", "section_cable.svg",
                 "section_rect.svg", "section_ibeam.svg", "bend_detail.svg"]:
        f = tmp_path / name
        assert f.exists() and f.stat().st_size > 0, name
        ET.parse(f)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `d:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_section_drawings.py -q`
Expected: FAIL (module file does not exist → `FileNotFoundError`/import error).

- [ ] **Step 3: Write the generator module**

Create `docs/site/assets/generate_section_drawings.py`:

```python
"""Render dimensioned engineering cross-section drawings from real Tuba sections.

Run:  .\\.venv\\Scripts\\python.exe docs/site/assets/generate_section_drawings.py
Outputs committed SVGs under docs/site/assets/figures/. No solver, no OpenGL.
Every dimension is read from the live Tuba section objects, so the drawings
cannot drift from the model.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Annulus, PathPatch, Rectangle
from matplotlib.path import Path as MplPath

from tuba import Model
from tuba.geometry.profiles import profile_for_section
from tuba.sections import SectionCatalog

plt.rcParams["svg.fonttype"] = "none"  # keep dimension text as <text>, searchable

FIG_DIR = Path(__file__).resolve().parent / "figures"

INK, STEEL, MUTED, INNER = "#1b2026", "#2f6374", "#9aa3ad", "#5b636d"
AMBER, SHEET = "#c07a1e", "#ffffff"
FS, FS_TTL = 12.5, 15
DIA = "Ø"  # Ø
LW_OBJ, LW_IN, LW_DIM, LW_EXT, LW_CL, LW_HATCH = 2.3, 1.6, 1.05, 0.85, 0.85, 0.7
CL_DASH = (0, (16, 4, 3, 4))


# ---- draughting primitives -------------------------------------------------
def _arrow(ax, p1, p2, color=STEEL, lw=LW_DIM):
    ax.annotate("", xy=p2, xytext=p1,
                arrowprops=dict(arrowstyle="<|-|>", color=color, lw=lw,
                                mutation_scale=11, shrinkA=0, shrinkB=0))


def dim_h(ax, x1, x2, y, text, obj_y, color=STEEL):
    for x in (x1, x2):
        ax.plot([x, x], [obj_y, y - 3], color=color, lw=LW_EXT, zorder=4)
    _arrow(ax, (x1, y), (x2, y), color)
    ax.text((x1 + x2) / 2, y - 4, text, ha="center", va="top", color=INK, fontsize=FS)


def dim_v(ax, y1, y2, x, text, obj_x, color=STEEL):
    for y in (y1, y2):
        ax.plot([obj_x, x + 3], [y, y], color=color, lw=LW_EXT, zorder=4)
    _arrow(ax, (x, y1), (x, y2), color)
    ax.text(x - 5, (y1 + y2) / 2, text, ha="right", va="center", rotation=90,
            color=INK, fontsize=FS)


def leader(ax, tip, elbow, text, out="right", color=STEEL):
    """Arrow from elbow to tip; horizontal shoulder + text extends `out`."""
    ax.annotate("", xy=tip, xytext=elbow,
                arrowprops=dict(arrowstyle="-|>", color=color, lw=0.95,
                                mutation_scale=10, shrinkA=0, shrinkB=0))
    dx = 16 if out == "right" else -16
    ax.plot([elbow[0], elbow[0] + dx], [elbow[1], elbow[1]], color=color, lw=0.95)
    ax.text(elbow[0] + dx + (4 if out == "right" else -4), elbow[1], text,
            ha=("left" if out == "right" else "right"), va="center",
            color=INK, fontsize=FS)


def centrelines(ax, cx, cy, hx, hy, color=STEEL):
    ax.plot([cx - hx, cx + hx], [cy, cy], color=color, lw=LW_CL, linestyle=CL_DASH, zorder=3)
    ax.plot([cx, cx], [cy - hy, cy + hy], color=color, lw=LW_CL, linestyle=CL_DASH, zorder=3)


def hatch(ax, clip_patch, bbox, spacing=5.5, color=MUTED, lw=LW_HATCH):
    x0, y0, x1, y1 = bbox
    clip_patch.set_facecolor("none")
    clip_patch.set_edgecolor("none")
    ax.add_patch(clip_patch)
    for c in np.arange((y0 - x1) - spacing, (y1 - x0) + spacing, spacing * 1.42):
        ln, = ax.plot([x0 - 20, x1 + 20], [x0 - 20 + c, x1 + 20 + c],
                      color=color, lw=lw, zorder=1)
        ln.set_clip_path(clip_patch)


def _title(ax, name, sub):
    ax.text(0.5, -0.02, name, transform=ax.transAxes, ha="center", va="top",
            fontsize=FS_TTL, fontweight="bold", color=INK)
    ax.text(0.5, -0.10, sub, transform=ax.transAxes, ha="center", va="top",
            fontsize=11, color="#5d6570")


def _frame(ax, lim):
    ax.set_aspect("equal")
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.axis("off")


# ---- five section details --------------------------------------------------
def draw_pipe(ax, d):
    OD, ID, WT = d["OD"] * 1000, d["ID"] * 1000, d["WT"] * 1000
    ro, ri = OD / 2, ID / 2
    _frame(ax, ro + 48)
    hatch(ax, Annulus((0, 0), ro, WT), (-ro, -ro, ro, ro), spacing=5)
    ax.add_patch(Circle((0, 0), ro, fill=False, ec=INK, lw=LW_OBJ, zorder=5))
    ax.add_patch(Circle((0, 0), ri, fill=False, ec=INNER, lw=LW_IN, zorder=5))
    centrelines(ax, 0, 0, ro + 30, ro + 30)
    dim_h(ax, -ro, ro, -ro - 26, f"{DIA}{OD:.1f}", obj_y=-ro)
    leader(ax, (-ri * 0.60, ri * 0.60), (ro + 20, ro + 20), f"BORE {DIA}{ID:.2f}", out="right")
    leader(ax, (-(ro + ri) / 2, 0), (-ro - 26, -22), f"WT {WT:.2f}", out="left")
    _title(ax, "PIPE  ·  DN100", f"OD {OD:.1f} · WT {WT:.2f} · ID {ID:.2f}")


def draw_bar(ax, d):
    OD = d["OD"] * 1000
    r = OD / 2
    _frame(ax, r + 42)
    hatch(ax, Circle((0, 0), r), (-r, -r, r, r), spacing=6)
    ax.add_patch(Circle((0, 0), r, fill=False, ec=INK, lw=LW_OBJ, zorder=5))
    centrelines(ax, 0, 0, r + 26, r + 26)
    dim_h(ax, -r, r, -r - 24, f"{DIA}{OD:.0f}", obj_y=-r)
    _title(ax, "BAR  ·  solid round", f"{DIA}{OD:.0f} · solid (WT = 0)")


def draw_cable(ax, d):
    R = d["radius"] * 1000
    N = d["pretension"]
    _frame(ax, R + 42)
    hatch(ax, Circle((0, 0), R), (-R, -R, R, R), spacing=4.5)
    ax.add_patch(Circle((0, 0), R, fill=False, ec=INK, lw=LW_OBJ, zorder=5))
    centrelines(ax, 0, 0, R + 24, R + 24)
    ax.annotate("", xy=(R * np.cos(np.radians(35)), R * np.sin(np.radians(35))),
                xytext=(0, 0),
                arrowprops=dict(arrowstyle="-|>", color=STEEL, lw=LW_DIM, mutation_scale=10))
    ax.text(R * 0.30, R * 0.55, f"R{R:.0f}", ha="left", va="bottom", color=INK, fontsize=FS)
    _title(ax, "CABLE  ·  tension-only", f"R{R:.0f} · pretension {N:.0f} N")


def draw_rect(ax, d):
    hy, hz = d["height_y"] * 1000, d["height_z"] * 1000   # y horizontal, z vertical
    ty, tz = d["thickness_y"] * 1000, d["thickness_z"] * 1000
    w, h = hy, hz
    _frame(ax, max(w, h) / 2 + 54)
    outer = [(-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2), (-w/2, -h/2)]
    inner = [(-w/2 + ty, -h/2 + tz), (-w/2 + ty, h/2 - tz),
             (w/2 - ty, h/2 - tz), (w/2 - ty, -h/2 + tz), (-w/2 + ty, -h/2 + tz)]
    codes = [MplPath.MOVETO] + [MplPath.LINETO]*4 + [MplPath.MOVETO] + [MplPath.LINETO]*4
    hatch(ax, PathPatch(MplPath(outer + inner, codes)), (-w/2, -h/2, w/2, h/2), spacing=6)
    ax.add_patch(Rectangle((-w/2, -h/2), w, h, fill=False, ec=INK, lw=LW_OBJ, zorder=5))
    ax.add_patch(Rectangle((-w/2 + ty, -h/2 + tz), w - 2*ty, h - 2*tz,
                           fill=False, ec=INNER, lw=LW_IN, zorder=5))
    centrelines(ax, 0, 0, w/2 + 30, h/2 + 30)
    dim_h(ax, -w/2, w/2, -h/2 - 28, f"{hy:.0f}", obj_y=-h/2)
    dim_v(ax, -h/2, h/2, -w/2 - 28, f"{hz:.0f}", obj_x=-w/2)
    leader(ax, (w/2 - ty/2, h*0.12), (w/2 + 24, h*0.12), f"wall {ty:.0f}", out="right")
    _title(ax, "RECTANGULAR (RHS)", f"{hy:.0f} × {hz:.0f} · wall {ty:.0f}")


def _ibeam_outline(H, B, Tw, Tf, R, n=12):
    hh, hb, hw = H/2, B/2, Tw/2
    fy = hh - Tf

    def arc(cx, cy, a0, a1):
        a = np.radians(np.linspace(a0, a1, n))
        return list(zip(cx + R*np.cos(a), cy + R*np.sin(a)))

    p = [(hb, hh), (-hb, hh), (-hb, fy)]
    p += [(-(hw + R), fy)]
    p += arc(-(hw + R), fy - R, 90, 0)
    p += [(-hw, -(fy - R))]
    p += arc(-(hw + R), -(fy - R), 0, -90)
    p += [(-hb, -fy), (-hb, -hh), (hb, -hh), (hb, -fy)]
    p += [(hw + R, -fy)]
    p += arc(hw + R, -(fy - R), -90, -180)
    p += [(hw, fy - R)]
    p += arc(hw + R, fy - R, 180, 90)
    p += [(hb, fy)]
    return p


def draw_ibeam(ax, d, R):
    H, B, Tw, Tf = d["H"]*1000, d["B"]*1000, d["Tw"]*1000, d["Tf"]*1000
    R = R * 1000
    _frame(ax, max(H, B)/2 + 54)
    pts = _ibeam_outline(H, B, Tw, Tf, R)
    region = PathPatch(MplPath(pts, [MplPath.MOVETO] + [MplPath.LINETO]*(len(pts)-1)))
    hatch(ax, region, (-B/2, -H/2, B/2, H/2), spacing=6)
    ax.add_patch(PathPatch(MplPath(pts + [pts[0]],
                 [MplPath.MOVETO] + [MplPath.LINETO]*(len(pts)-1) + [MplPath.CLOSEPOLY]),
                 fill=False, ec=INK, lw=LW_OBJ, zorder=5))
    centrelines(ax, 0, 0, B/2 + 28, H/2 + 32)
    dim_h(ax, -B/2, B/2, -H/2 - 30, f"{B:.0f}", obj_y=-H/2)
    dim_v(ax, -H/2, H/2, -B/2 - 32, f"{H:.0f}", obj_x=-B/2)
    leader(ax, (Tw/2, H*0.10), (B/2 + 24, H*0.20), f"Tw {Tw:.0f}", out="right")
    leader(ax, (B*0.18, -H/2 + Tf/2), (B/2 + 24, -H/2 + Tf*0.5), f"Tf {Tf:.0f}", out="right")
    _title(ax, "I-BEAM  ·  HE200B", f"H {H:.0f} · B {B:.0f} · Tw {Tw:.0f} · Tf {Tf:.0f} · r{R:.0f}")


# ---- bend-geometry detail (FE chord vs true arc) ---------------------------
def draw_bend(ax):
    R = 100.0  # illustrative bend radius (mm); geometry is exact for a 90 deg bend
    T1, T2, PI, O = (-R, 0.0), (0.0, R), (0.0, 0.0), (-R, R)
    ax.set_aspect("equal")
    ax.set_xlim(-R - 70, R * 0.75)
    ax.set_ylim(-70, R + 70)
    ax.axis("off")
    # FE chord: straight elements meeting at PI (tangent intersection)
    ax.plot([-R - 45, 0, 0], [0, 0, R + 45], color=AMBER, lw=LW_OBJ, zorder=5)
    # true circular arc T1 -> T2 about O
    a = np.radians(np.linspace(-90, 0, 80))
    ax.plot(O[0] + R*np.cos(a), O[1] + R*np.sin(a), color=STEEL, lw=LW_OBJ, zorder=6)
    # radius dimension O -> arc(-45)
    pr = (O[0] + R*np.cos(np.radians(-45)), O[1] + R*np.sin(np.radians(-45)))
    ax.annotate("", xy=pr, xytext=O,
                arrowprops=dict(arrowstyle="-|>", color=STEEL, lw=LW_DIM, mutation_scale=10))
    ax.plot([O[0]-7, O[0]+7], [O[1], O[1]], color=STEEL, lw=0.8)
    ax.plot([O[0], O[0]], [O[1]-7, O[1]+7], color=STEEL, lw=0.8)
    ax.text((O[0]+pr[0])/2 - 4, (O[1]+pr[1])/2 + 4, f"R{R:.0f}", ha="right", va="bottom",
            color=INK, fontsize=FS)
    # included angle at O
    aa = np.radians(np.linspace(-90, 0, 30))
    ax.plot(O[0] + 20*np.cos(aa), O[1] + 20*np.sin(aa), color=STEEL, lw=0.8)
    ax.text(O[0] + 30*np.cos(np.radians(-45)), O[1] + 30*np.sin(np.radians(-45)),
            "90°", ha="center", va="center", color=INK, fontsize=11)
    # bend rise: PI -> nearest arc point
    ax.annotate("", xy=pr, xytext=PI,
                arrowprops=dict(arrowstyle="<|-|>", color="#9b3f2b", lw=LW_DIM, mutation_scale=9))
    ax.text(PI[0] + 6, PI[1] + 14, "bend rise", ha="left", va="bottom",
            color="#9b3f2b", fontsize=11)
    # node / tangent-point markers
    for p, lbl, dxy in [(PI, "FE node (PI)", (6, -18)), (T1, "tangent pt", (-4, -18)),
                        (T2, "tangent pt", (8, 4))]:
        ax.plot([p[0]], [p[1]], "o", color=INK, ms=5, zorder=7)
        ax.text(p[0] + dxy[0], p[1] + dxy[1], lbl, ha="left", va="center",
                color=INK, fontsize=10.5)
    _title(ax, "BEND  ·  FE chord vs true arc", "amber = straight FE chord · blue = stored arc")


# ---- title block + composition --------------------------------------------
def title_block(ax):
    ax.axis("off")
    ax.add_patch(Rectangle((0.04, 0.06), 0.92, 0.88, transform=ax.transAxes,
                           fill=False, ec="#c7cdd4", lw=1.2))
    ax.text(0.5, 0.86, "TUBA — CROSS-SECTION LIBRARY", transform=ax.transAxes,
            ha="center", fontsize=13, fontweight="bold", color=INK)
    for i, t in enumerate([
        "SECTION A–A  ·  cut normal to member axis",
        "Z up  ·  Y right",
        "DIMENSIONS IN MILLIMETRES",
        "NOT TO A COMMON SCALE — SEE DIMENSIONS",
    ]):
        ax.text(0.11, 0.70 - i*0.11, t, transform=ax.transAxes, ha="left",
                fontsize=10.5, color="#5d6570")
    y0 = 0.20
    ax.plot([0.11, 0.24], [y0, y0], transform=ax.transAxes, color=INK, lw=LW_OBJ)
    ax.text(0.27, y0, "object", transform=ax.transAxes, va="center", fontsize=10, color=INK)
    ax.plot([0.11, 0.24], [y0-0.09, y0-0.09], transform=ax.transAxes, color=STEEL,
            lw=LW_CL, linestyle=CL_DASH)
    ax.text(0.27, y0-0.09, "centreline", transform=ax.transAxes, va="center", fontsize=10, color=INK)
    ax.annotate("", xy=(0.24, 0.02), xytext=(0.11, 0.02), transform=ax.transAxes,
                arrowprops=dict(arrowstyle="<|-|>", color=STEEL, lw=LW_DIM, mutation_scale=10))
    ax.text(0.27, 0.02, "dimension", transform=ax.transAxes, va="center", fontsize=10, color=INK)


def build_sections() -> dict[str, dict]:
    m = Model("Sections")
    m.add_pipe_section("DN100", OD=0.1143, WT=0.00602, corrosion_allowance=0.001)
    m.add_bar_section("Bar", OD=0.18, WT=0.0)
    m.add_cable_section("Cable", radius=0.04, pretension=500.0)
    m.add_rectangular_section("Box", height_y=0.24, height_z=0.14,
                              thickness_y=0.012, thickness_z=0.012)
    m.add_ibeam_section("IBeam", "HE200B")
    return {n: profile_for_section(s).dimensions for n, s in m.sections.items()}


def render_plate(out_dir, dims, R):
    fig, axes = plt.subplots(2, 3, figsize=(14.4, 9.4), dpi=150)
    fig.patch.set_facecolor(SHEET)
    for a in axes.flat:
        a.set_facecolor(SHEET)
    draw_pipe(axes[0, 0], dims["DN100"])
    draw_bar(axes[0, 1], dims["Bar"])
    draw_cable(axes[0, 2], dims["Cable"])
    draw_rect(axes[1, 0], dims["Box"])
    draw_ibeam(axes[1, 1], dims["IBeam"], R)
    title_block(axes[1, 2])
    fig.subplots_adjust(left=0.03, right=0.97, top=0.95, bottom=0.05, wspace=0.28, hspace=0.34)
    fig.savefig(out_dir / "sections.svg", facecolor=SHEET)
    plt.close(fig)


def _one(out_dir, fn, name, *args):
    fig, ax = plt.subplots(figsize=(4.7, 4.9), dpi=150)
    fig.patch.set_facecolor(SHEET)
    ax.set_facecolor(SHEET)
    fn(ax, *args)
    fig.subplots_adjust(left=0.06, right=0.94, top=0.96, bottom=0.15)
    fig.savefig(out_dir / name, facecolor=SHEET)
    plt.close(fig)


def render_bend(out_dir):
    fig, ax = plt.subplots(figsize=(6.4, 4.6), dpi=150)
    fig.patch.set_facecolor(SHEET)
    ax.set_facecolor(SHEET)
    draw_bend(ax)
    fig.subplots_adjust(left=0.04, right=0.96, top=0.96, bottom=0.12)
    fig.savefig(out_dir / "bend_detail.svg", facecolor=SHEET)
    plt.close(fig)


def main(out_dir: Path = FIG_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    dims = build_sections()
    R = SectionCatalog.default().get_ibeam_profile("HE200B").dimensions["R"]
    render_plate(out_dir, dims, R)
    _one(out_dir, draw_pipe, "section_pipe.svg", dims["DN100"])
    _one(out_dir, draw_bar, "section_bar.svg", dims["Bar"])
    _one(out_dir, draw_cable, "section_cable.svg", dims["Cable"])
    _one(out_dir, draw_rect, "section_rect.svg", dims["Box"])
    _one(out_dir, draw_ibeam, "section_ibeam.svg", dims["IBeam"], R)
    render_bend(out_dir)
    print(f"wrote sections.svg + 5 details + bend_detail.svg to {out_dir}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `d:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_section_drawings.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Generate the committed figures + self-verify visually**

Run: `d:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe docs/site/assets/generate_section_drawings.py`
Expected stdout: `wrote sections.svg + 5 details + bend_detail.svg to .../figures`
Then render the plate to PNG in scratchpad and open it to confirm the I-beam fillets, hatching, and dimensions read cleanly:
```
d:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -c "import importlib.util,sys; from pathlib import Path; p=Path('docs/site/assets/generate_section_drawings.py'); s=importlib.util.spec_from_file_location('g',p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); import matplotlib.pyplot as plt; d=m.build_sections(); from tuba.sections import SectionCatalog; R=SectionCatalog.default().get_ibeam_profile('HE200B').dimensions['R']; m.render_plate(Path('.'),d,R)"
```
(Visual check is a human/agent gate — the SVG is the deliverable; a PNG proof is optional.)

- [ ] **Step 6: Commit**

```bash
git add docs/site/assets/generate_section_drawings.py tests/test_section_drawings.py docs/site/assets/figures/sections.svg docs/site/assets/figures/section_pipe.svg docs/site/assets/figures/section_bar.svg docs/site/assets/figures/section_cable.svg docs/site/assets/figures/section_rect.svg docs/site/assets/figures/section_ibeam.svg docs/site/assets/figures/bend_detail.svg
git commit -m "feat(docs): data-driven engineering section drawings (SVG)"
```

---

### Task 2: Wire drawings into Modeling; retire the old render; update docs test + CSS

**Files:**
- Modify: `docs/site/modeling.html` (Cross-sections `<figure>`; add bend detail near the existing bend figure)
- Modify: `docs/site/assets/site.css` (add `.figure--sheet`)
- Modify: `docs/site/assets/generate_figures.py` (remove `fig_sections` + its `FIGURES` entry)
- Delete: `docs/site/assets/figures/sections.png`
- Modify: `tests/test_static_site_docs.py` (`test_pages_use_real_figures_not_sketches`: `sections.png`→`sections.svg`, add `bend_detail.svg`; assert `sections.png` absent)

**Interfaces:**
- Consumes: `sections.svg`, `bend_detail.svg` from Task 1.
- Produces: updated modeling page + green docs test.

- [ ] **Step 1: Update the docs test to require the SVG (write the failing assertion first)**

In `tests/test_static_site_docs.py`, in `test_pages_use_real_figures_not_sketches`, change the `modeling.html` figure list and add an absence check. Replace the modeling entry:

```python
            "modeling.html": [
                "element_triad.png", "placement_frame.png", "builder_route.png",
                "bend_chord_arc.png", "sections.svg", "bend_detail.svg", "supports.png",
            ],
```

And after the existing per-page loop body (inside the method, after the `for fig in figs:` loop), add:

```python
        # the stylized 3D sections render is retired in favour of the drawing
        self.assertFalse((figures_dir / "sections.png").exists(),
                         "sections.png should be replaced by sections.svg")
        self.assertNotIn("sections.png", (SITE / "modeling.html").read_text(encoding="utf-8"))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `d:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_static_site_docs.py::TestStaticSiteDocs::test_pages_use_real_figures_not_sketches -q`
Expected: FAIL (modeling.html still references `sections.png`; `sections.png` still on disk).

- [ ] **Step 3: Swap the figure in `modeling.html`**

In `docs/site/modeling.html`, replace the Cross-sections `<figure>` block (the one referencing `sections.png`):

```html
        <figure class="figure figure--sheet">
          <img src="./assets/figures/sections.svg" width="1440" height="940"
               alt="Dimensioned engineering section details: pipe (bore + wall), solid bar, tension cable, rectangular hollow, and HE200B I-beam, each with orthographic section view, hatching, centrelines, and dimensions in millimetres." />
          <figcaption>Cross-sections as dimensioned engineering details (SECTION A–A, cut normal to
            the member axis; dimensions in mm). Left to right: pipe with bore and wall, solid bar,
            tension cable, rectangular hollow, and an HE200B I-beam. Every dimension is read from the
            live Tuba section object.</figcaption>
        </figure>
```

- [ ] **Step 4: Add the bend detail near the existing bend figure**

In `docs/site/modeling.html`, immediately after the `bend_chord_arc.png` `<figure>` (inside the "Pipe builder orientation" section), insert:

```html
        <figure class="figure figure--sheet">
          <img src="./assets/figures/bend_detail.svg" width="1280" height="920"
               alt="2D bend-geometry detail: the finite-element chord meeting at the tangent-intersection point versus the true stored circular arc, with bend radius, 90-degree included angle, tangent points, and the bend rise dimensioned." />
          <figcaption>The same idea as a dimensioned detail: FE elements meet at the tangent-intersection
            point <strong>PI</strong> (amber chord); the stored <code>BendGeometry</code> is the true arc
            (blue) of radius <code>R</code> tangent at the tangent points. Their separation is the bend
            rise.</figcaption>
        </figure>
```

- [ ] **Step 5: Add the `.figure--sheet` CSS**

In `docs/site/assets/site.css`, immediately after the `.figure img {` rule block (near the `.figure` rules ~line 469–490), add:

```css
.figure--sheet {
  background: #ffffff;
  border-color: #c7cdd4;
}
.figure--sheet img {
  background: #ffffff;
}
```

- [ ] **Step 6: Retire `fig_sections` and delete `sections.png`**

In `docs/site/assets/generate_figures.py`: delete the entire `def fig_sections(out_dir: Path) -> Path:` function (lines ~69–85) and remove its entry `"sections": fig_sections,` from the `FIGURES` dict.

Then delete the stale asset:
```bash
git rm docs/site/assets/figures/sections.png
```

- [ ] **Step 7: Guard against stale references**

Run: `grep -rn "sections.png" docs/ tests/`
Expected: no matches. If any remain (e.g., another test), update them to `sections.svg` or remove as appropriate.

- [ ] **Step 8: Run the full static-docs test suite**

Run: `d:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_static_site_docs.py -q`
Expected: PASS (all tests in the file).

- [ ] **Step 9: Regression — run the docs-related suites**

Run: `d:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_static_site_docs.py tests/test_section_drawings.py tests/test_current_api_docs.py -q`
Expected: PASS. (If a `tests/test_docs_figures.py` exists and asserted `sections` in `generate_figures.FIGURES`, update it to drop `sections`.)

- [ ] **Step 10: Commit**

```bash
git add docs/site/modeling.html docs/site/assets/site.css docs/site/assets/generate_figures.py tests/test_static_site_docs.py
git commit -m "feat(docs): modeling page uses dimensioned section drawings; retire sections.png"
```

---

## Self-Review

**Spec coverage (increment 1 items):**
- Generator `generate_section_drawings.py` (5 details + plate + individual SVGs) → Task 1 ✓
- Data-driven from `profile_for_section` → `build_sections()` + test tokens ✓
- `svg.fonttype="none"` → module constant ✓
- Bend detail (`bend_detail.svg`) → Task 1 `draw_bend`/`render_bend`, wired Task 2 Step 4 ✓
- `sections.png`→`sections.svg` in modeling → Task 2 Step 3 ✓
- Retire `fig_sections` + drop `sections.png` → Task 2 Step 6 ✓
- `.figure--sheet` CSS → Task 2 Step 5 ✓
- Update docs test → Task 2 Steps 1,3,4 ✓; add drawings test → Task 1 ✓
- Playwright sweep: deferred to a cross-increment verification pass (noted in spec); Step 8–9 cover the automated docs assertions for this increment.

**Placeholder scan:** none — all code and commands are concrete.

**Type consistency:** `main(out_dir=...)`, `build_sections()`, `DIA`, `render_plate(out_dir, dims, R)`, `draw_ibeam(ax, d, R)` names match across Task 1 module and the Task 1 test. Figure filenames (`sections.svg`, `section_*.svg`, `bend_detail.svg`) match between generator, test, and modeling wiring.
