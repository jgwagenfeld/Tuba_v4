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
from matplotlib.patches import Circle, Annulus, PathPatch, Rectangle, FancyBboxPatch
from matplotlib.path import Path as MplPath

from tuba import Model
from tuba.geometry.profiles import profile_for_section
from tuba.sections import SectionCatalog

plt.rcParams["svg.fonttype"] = "none"  # keep dimension text as <text>, searchable
plt.rcParams["svg.hashsalt"] = "tuba-sections"  # deterministic clip-path ids across runs

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
    # asymmetric x-room on the left so the WT leader text is not clipped.
    # Dimension OD + WT only; ID = OD - 2*WT is derived (no redundant bore dim).
    ax.set_aspect("equal")
    ax.set_xlim(-(ro + 74), ro + 48)
    ax.set_ylim(-(ro + 50), ro + 50)
    ax.axis("off")
    hatch(ax, Annulus((0, 0), ro, WT), (-ro, -ro, ro, ro), spacing=5)
    ax.add_patch(Circle((0, 0), ro, fill=False, ec=INK, lw=LW_OBJ, zorder=5))
    ax.add_patch(Circle((0, 0), ri, fill=False, ec=INNER, lw=LW_IN, zorder=5))
    centrelines(ax, 0, 0, ro + 30, ro + 30)
    dim_h(ax, -ro, ro, -ro - 26, f"{DIA}{OD:.1f}", obj_y=-ro)
    leader(ax, (-(ro + ri) / 2, 0), (-ro - 24, -22), f"WT {WT:.2f}", out="left")
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
    ax.text((O[0]+pr[0])/2 + 7, (O[1]+pr[1])/2 + 3, f"R{R:.0f}", ha="left", va="center",
            color=INK, fontsize=FS)
    # included angle at O
    aa = np.radians(np.linspace(-90, 0, 30))
    ax.plot(O[0] + 20*np.cos(aa), O[1] + 20*np.sin(aa), color=STEEL, lw=0.8)
    ax.text(O[0] + 24*np.cos(np.radians(-18)), O[1] + 24*np.sin(np.radians(-18)),
            "90°", ha="left", va="center", color=INK, fontsize=11)
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


# ---- data-flow architecture diagram (model -> reviewed result) -------------
def _flow_box(ax, cx, cy, w, h, title, sub, fill="#eef3f4"):
    ax.add_patch(FancyBboxPatch((cx - w/2, cy - h/2), w, h,
                 boxstyle="round,pad=0.02,rounding_size=0.12",
                 linewidth=1.6, edgecolor=STEEL, facecolor=fill, zorder=3))
    ax.text(cx, cy + 0.15, title, ha="center", va="center", fontsize=12.5,
            fontweight="bold", color=INK, zorder=4)
    ax.text(cx, cy - 0.22, sub, ha="center", va="center", fontsize=9.5,
            color="#5d6570", zorder=4)


def _flow_arrow(ax, p1, p2):
    ax.annotate("", xy=p2, xytext=p1,
                arrowprops=dict(arrowstyle="-|>", color=STEEL, lw=1.6,
                                mutation_scale=14, shrinkA=2, shrinkB=2))


def draw_dataflow(ax):
    ax.set_aspect("equal")
    ax.axis("off")
    w, h, gap = 2.7, 1.15, 0.75
    xs = [i * (w + gap) for i in range(6)]
    cy = 0.0
    stages = [("Model", "typed graph"),
              ("validate()", "schema + semantics"),
              ("Export study", ".comm · .mail · .export"),
              ("Code_Aster", "solve (WSL)"),
              ("Parse artifacts", "displ · forces · stress"),
              ("ResultState", "reviewable")]
    for x, (t, s) in zip(xs, stages):
        _flow_box(ax, x, cy, w, h, t, s)
    for a, b in zip(xs, xs[1:]):
        _flow_arrow(ax, (a + w/2, cy), (b - w/2, cy))
    x6 = xs[-1]
    xr = x6 + w + gap
    _flow_box(ax, xr, cy + 1.6, w, h, "PyVista", "notebook quick-look", fill="#eaf1ee")
    _flow_box(ax, xr, cy - 1.6, w, h, "Web bundle", "viewer/ scene", fill="#eaf1ee")
    _flow_arrow(ax, (x6 + w/2, cy + 0.25), (xr - w/2, cy + 1.6))
    _flow_arrow(ax, (x6 + w/2, cy - 0.25), (xr - w/2, cy - 1.6))
    ax.set_xlim(-w/2 - 0.4, xr + w/2 + 0.4)
    ax.set_ylim(cy - 2.5, cy + 2.6)
    ax.text((-w/2 + xr + w/2) / 2, cy + 2.4, "DATA FLOW — model to reviewed result",
            ha="center", va="center", fontsize=13, fontweight="bold", color=INK)


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
    fig.savefig(out_dir / "sections.svg", facecolor=SHEET, metadata={"Date": None})
    plt.close(fig)


def _one(out_dir, fn, name, *args):
    fig, ax = plt.subplots(figsize=(4.7, 4.9), dpi=150)
    fig.patch.set_facecolor(SHEET)
    ax.set_facecolor(SHEET)
    fn(ax, *args)
    fig.subplots_adjust(left=0.06, right=0.94, top=0.96, bottom=0.15)
    fig.savefig(out_dir / name, facecolor=SHEET, metadata={"Date": None})
    plt.close(fig)


def render_bend(out_dir):
    fig, ax = plt.subplots(figsize=(6.4, 4.6), dpi=150)
    fig.patch.set_facecolor(SHEET)
    ax.set_facecolor(SHEET)
    draw_bend(ax)
    fig.subplots_adjust(left=0.04, right=0.96, top=0.96, bottom=0.12)
    fig.savefig(out_dir / "bend_detail.svg", facecolor=SHEET, metadata={"Date": None})
    plt.close(fig)


def render_dataflow(out_dir):
    fig, ax = plt.subplots(figsize=(15.0, 4.4), dpi=150)
    fig.patch.set_facecolor(SHEET)
    ax.set_facecolor(SHEET)
    draw_dataflow(ax)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
    fig.savefig(out_dir / "dataflow.svg", facecolor=SHEET, metadata={"Date": None})
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
    render_dataflow(out_dir)
    print(f"wrote sections.svg + 5 details + bend_detail.svg + dataflow.svg to {out_dir}")


if __name__ == "__main__":
    main()
