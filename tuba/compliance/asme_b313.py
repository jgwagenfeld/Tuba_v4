"""
tuba.compliance.asme_b313 — ASME B31.3 code compliance evaluator.

Evaluates sustained and displacement (expansion) stresses for every element
in a solved piping model, per ASME B31.3-2022 §302.3.5 / §302.3.6.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from tuba.compliance.sif import compute_sif_set
from tuba.model import Element, LoadCase, Material, PipeSection, TubaModel
from tuba.solver.base import FEAResults


def _edition_year(edition: object) -> int:
    """Parse a B31.3 edition (e.g. ``"2022"`` or ``2022``) to a 4-digit year."""
    try:
        return int(str(edition)[:4])
    except (ValueError, TypeError):
        return 2020


def stress_range_reduction_factor(cycles: float, edition: str = "2020") -> float:
    """ASME B31.3 §302.3.5 stress-range (fatigue) reduction factor *f*.

    Edition-gated — a real B31.3-2022 change: 2020 and earlier use
    ``f = 6.0 * N**-0.2``; 2022 and later use the steeper ``f = 20 * N**(-1/3)``.
    Both are capped at 1.2 and floored at 0.15. Shipping the 2020 curve for a
    2022 target is non-conservative at high cycle counts.

    Parameters
    ----------
    cycles : float
        Equivalent number of full displacement (thermal) cycles *N*.
    edition : str
        B31.3 edition year, e.g. ``"2020"`` or ``"2022"``.
    """
    n = max(float(cycles), 1.0)
    if _edition_year(edition) >= 2022:
        f = 20.0 * n ** (-1.0 / 3.0)
    else:
        f = 6.0 * n ** (-0.2)
    return min(1.2, max(0.15, f))


def bend_local_axes(
    element: Element,
    model: TubaModel,
    *,
    node_id: Optional[str] = None,
) -> Optional[Dict[str, List[float] | str]]:
    """Return bend local-axis metadata when explicit bend geometry exists."""
    if element.type != "pipe_bend" or element.bend_geometry is None:
        return None
    geometry = element.bend_geometry
    tangent_values = geometry.start_tangent
    if node_id == element.n2:
        tangent_values = geometry.end_tangent
    tangent = _unit_vector(tangent_values)
    out_of_plane = _unit_vector(geometry.normal)
    in_plane = np.cross(out_of_plane, tangent)
    if np.linalg.norm(in_plane) <= 1e-12:
        return None
    in_plane = in_plane / np.linalg.norm(in_plane)
    return {
        "basis": "bend_geometry",
        "node_id": node_id or "",
        "tangent": [float(value) for value in tangent],
        "in_plane": [float(value) for value in in_plane],
        "out_of_plane": [float(value) for value in out_of_plane],
    }


def _unit_vector(values) -> np.ndarray:
    vector = np.asarray(values, dtype=float)
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        raise ValueError("Cannot normalize a zero vector.")
    return vector / norm


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------

@dataclass
class ElementComplianceResult:
    """Compliance evaluation result for one element end."""

    element_id: str
    node_id: str

    # Sustained stress
    sustained_stress: float  # [Pa]
    sustained_allowable: float  # S_h [Pa]
    sustained_ratio: float  # S_L / S_h
    sustained_pass: bool

    # Expansion stress
    expansion_stress: float  # [Pa]
    expansion_allowable: float  # S_A [Pa]
    expansion_ratio: float  # S_E / S_A
    expansion_pass: bool

    # ---- Intermediate values stored for traceability ----
    pressure: float = 0.0
    Do: float = 0.0
    t: float = 0.0
    Z: float = 0.0
    i_i: float = 1.0
    i_o: float = 1.0
    k: float = 1.0
    h: float = 0.0
    M_i: float = 0.0
    M_o: float = 0.0
    M_t: float = 0.0
    moment_basis: str = "resultant_in_plane"
    S_h: float = 0.0
    S_c: float = 0.0
    f: float = 1.0


@dataclass
class ComplianceReport:
    """Full ASME B31.3 compliance report for all elements."""

    results: List[ElementComplianceResult] = field(default_factory=list)
    load_case: Optional[str] = None
    code_name: str = "ASME B31.3"
    code_edition: str = "2020"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def overall_pass(self) -> bool:
        """``True`` if every element end passes both checks."""
        return all(r.sustained_pass and r.expansion_pass for r in self.results)

    @property
    def worst_sustained_ratio(self) -> float:
        if not self.results:
            return 0.0
        return max(r.sustained_ratio for r in self.results)

    @property
    def worst_expansion_ratio(self) -> float:
        if not self.results:
            return 0.0
        return max(r.expansion_ratio for r in self.results)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Human-readable one-line summary with overall verdict."""
        status = "**PASS**" if self.overall_pass else "**FAIL**"
        worst_sus = self.worst_sustained_ratio
        worst_exp = self.worst_expansion_ratio
        n_total = len(self.results)
        n_fail = sum(
            1 for r in self.results
            if not r.sustained_pass or not r.expansion_pass
        )

        lines = [
            f"{self.code_name}-{self.code_edition} Compliance — {status}",
            f"  Load case       : {self.load_case or '(default)'}",
            f"  Elements checked : {n_total}",
            f"  Failures         : {n_fail}",
            f"  Worst sustained  : {worst_sus:.3f}",
            f"  Worst expansion  : {worst_exp:.3f}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Detailed per-element calculation trace
    # ------------------------------------------------------------------

    def get_detailed_calculation(self, element_id: str) -> str:
        """Return a markdown / LaTeX report for *element_id*.

        The report shows every step with substituted numerical values so
        that an engineer can reproduce the calculation by hand.

        Parameters
        ----------
        element_id : str
            Element identifier.

        Returns
        -------
        str
            Multi-line markdown string with embedded LaTeX math blocks.
        """
        hits = [r for r in self.results if r.element_id == element_id]
        if not hits:
            return f"No compliance results found for element `{element_id}`."

        parts: List[str] = []
        parts.append(f"# ASME B31.3 Detailed Calculation — Element `{element_id}`\n")

        for r in hits:
            parts.append(f"## Node `{r.node_id}`\n")

            # 1 — Input values
            parts.append("### 1. Input Values\n")
            parts.append("| Quantity | Symbol | Value |")
            parts.append("|----------|--------|------:|")
            parts.append(f"| Outer diameter | $D_o$ | {r.Do * 1e3:.2f} mm |")
            parts.append(f"| Corroded wall thickness | $t$ | {r.t * 1e3:.3f} mm |")
            parts.append(f"| Section modulus | $Z$ | {r.Z * 1e6:.4f} mm^3 × 10^6 |")
            parts.append(f"| Internal pressure | $P$ | {r.pressure / 1e6:.3f} MPa |")
            parts.append(f"| In-plane moment resultant | $M_i$ | {r.M_i:.2f} N·m |")
            parts.append(f"| Out-of-plane moment | $M_o$ | {r.M_o:.2f} N·m |")
            parts.append(f"| Torsional moment | $M_t$ | {r.M_t:.2f} N·m |")
            parts.append(f"| Hot allowable stress | $S_h$ | {r.S_h / 1e6:.2f} MPa |")
            parts.append(f"| Cold allowable stress | $S_c$ | {r.S_c / 1e6:.2f} MPa |")
            parts.append("")

            # 2 — SIF calculations
            parts.append("### 2. Stress Intensification Factors\n")
            if r.h > 0:
                parts.append("$$")
                parts.append(
                    rf"h = \frac{{t \cdot R}}{{r_m^2}} = {r.h:.4f}"
                )
                parts.append("$$\n")
                parts.append("$$")
                parts.append(
                    rf"i_i = \max\!\left(\frac{{0.9}}{{h^{{2/3}}}},\; 1.0\right)"
                    rf" = \max\!\left(\frac{{0.9}}{{{r.h:.4f}^{{2/3}}}},\; 1.0\right)"
                    rf" = {r.i_i:.4f}"
                )
                parts.append("$$\n")
                parts.append("$$")
                parts.append(
                    rf"i_o = \max\!\left(\frac{{0.75}}{{h^{{2/3}}}},\; 1.0\right)"
                    rf" = {r.i_o:.4f}"
                )
                parts.append("$$\n")
                parts.append("$$")
                parts.append(rf"k = \frac{{1.65}}{{h}} = {r.k:.4f}")
                parts.append("$$\n")
            else:
                parts.append(
                    "Straight pipe — $i_i = i_o = 1.0$, $k = 1.0$.\n"
                )

            # 3 — Sustained stress
            parts.append("### 3. Sustained Stress (§302.3.5)\n")
            P_Do_4t = r.pressure * r.Do / (4.0 * r.t) if r.t > 0 else 0.0
            bending_sus = (
                math.sqrt((r.i_i * r.M_i) ** 2 + (r.i_o * r.M_o) ** 2) / r.Z
                if r.Z > 0
                else 0.0
            )

            parts.append("$$")
            parts.append(
                rf"S_L = \frac{{P \cdot D_o}}{{4 t}}"
                rf" + \frac{{\sqrt{{(i_i \cdot M_i)^2 + (i_o \cdot M_o)^2}}}}{{Z}}"
            )
            parts.append("$$\n")
            parts.append("$$")
            parts.append(
                rf"S_L = \frac{{{r.pressure / 1e6:.3f} \times {r.Do * 1e3:.2f}}}"
                rf"{{4 \times {r.t * 1e3:.3f}}}"
                rf" + \frac{{\sqrt{{({r.i_i:.4f} \times {r.M_i:.2f})^2"
                rf" + ({r.i_o:.4f} \times {r.M_o:.2f})^2}}}}"
                rf"{{{r.Z:.6e}}}"
            )
            parts.append("$$\n")
            parts.append("$$")
            parts.append(
                rf"S_L = {P_Do_4t / 1e6:.3f} + {bending_sus / 1e6:.3f}"
                rf" = {r.sustained_stress / 1e6:.3f} \;\text{{MPa}}"
            )
            parts.append("$$\n")
            sus_verdict = "✅ PASS" if r.sustained_pass else "❌ FAIL"
            parts.append(
                f"Allowable $S_h = {r.sustained_allowable / 1e6:.2f}$ MPa — "
                f"Ratio $= {r.sustained_ratio:.3f}$ — {sus_verdict}\n"
            )

            # 4 — Expansion stress
            parts.append("### 4. Expansion Stress (§302.3.5(d))\n")
            parts.append("$$")
            parts.append(
                rf"S_E = \frac{{\sqrt{{(i_i \cdot M_i)^2"
                rf" + (i_o \cdot M_o)^2 + M_t^2}}}}{{Z}}"
            )
            parts.append("$$\n")
            parts.append("$$")
            parts.append(
                rf"S_E = \frac{{\sqrt{{({r.i_i:.4f} \times {r.M_i:.2f})^2"
                rf" + ({r.i_o:.4f} \times {r.M_o:.2f})^2"
                rf" + {r.M_t:.2f}^2}}}}"
                rf"{{{r.Z:.6e}}}"
                rf" = {r.expansion_stress / 1e6:.3f} \;\text{{MPa}}"
            )
            parts.append("$$\n")

            parts.append("### 5. Allowable Expansion Stress\n")
            S_A_val = r.expansion_allowable
            parts.append("$$")
            parts.append(
                rf"S_A = f \left(1.25\,S_c + 0.25\,S_h\right)"
                rf" = {r.f:.1f} \times \left(1.25 \times {r.S_c / 1e6:.2f}"
                rf" + 0.25 \times {r.S_h / 1e6:.2f}\right)"
                rf" = {S_A_val / 1e6:.2f} \;\text{{MPa}}"
            )
            parts.append("$$\n")
            exp_verdict = "✅ PASS" if r.expansion_pass else "❌ FAIL"
            parts.append(
                f"Ratio $= {r.expansion_ratio:.3f}$ — {exp_verdict}\n"
            )

            parts.append("---\n")

        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class ASMEB313Evaluator:
    """ASME B31.3 sustained / expansion stress evaluator.

    Parameters
    ----------
    f_factor : float
        Stress-range reduction factor.  Defaults to ``1.0`` (< 7 000 cycles).
    """

    def __init__(
        self,
        f_factor: float = 1.0,
        *,
        cycles: Optional[float] = None,
        edition: str = "2020",
        use_liberal_allowable: bool = False,
    ) -> None:
        self.use_liberal_allowable = use_liberal_allowable
        self.edition = str(_edition_year(edition))
        # When a cycle count is given, compute f per the (edition-gated) code
        # curve; otherwise use the explicit f_factor (default 1.0).
        self.f: float = (
            stress_range_reduction_factor(cycles, self.edition)
            if cycles is not None
            else f_factor
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        model: TubaModel,
        results: FEAResults,
    ) -> ComplianceReport:
        """Run ASME B31.3 compliance checks on every element.

        Each element is checked at **both end nodes** using SIF-amplified
        moments (``moment × SIF / Z``); a bend/elbow is one element evaluated at
        its two ends with its B31J directional indices — the standard
        component-based code check. This is distinct from
        ``FEAResults.tuyau_subpoints``, which holds detailed FE cross-section
        von Mises for visualization only, not the code stress.

        Parameters
        ----------
        model : TubaModel
            The piping model (geometry + materials + load cases).
        results : FEAResults
            Solved FEA result set.

        Returns
        -------
        ComplianceReport
            Report containing per-element-end compliance results.
        """
        report = ComplianceReport(load_case=results.load_case, code_edition=self.edition)

        # Resolve the active load case
        lc = self._resolve_load_case(model, results.load_case)
        base_pressure = lc.internal_pressure if lc else 0.0
        base_temperature = lc.temperature if lc else 20.0
        ref_temperature = lc.ref_temperature if lc else 20.0

        for elem in model.elements:
            if elem.type not in ("pipe_straight", "pipe_bend"):
                continue
            er = results.element_results.get(elem.id)
            if er is None:
                continue

            section: PipeSection = model.sections[elem.section]
            material: Material = model.materials[elem.material]
            pressure = _operation_field_value_for_element(
                model,
                lc,
                elem,
                quantity="pressure",
                default=base_pressure,
            )
            temperature = _operation_field_value_for_element(
                model,
                lc,
                elem,
                quantity="temperature",
                default=base_temperature,
            )

            # Allowable stresses. S_A (displacement range allowable) is
            # computed per node so the liberal allowable can credit unused
            # sustained stress.
            S_h = material.get_allowable(temperature)
            S_c = material.get_allowable(ref_temperature)

            # Cross-section properties (corroded)
            Do = section.OD
            t = section.corroded_WT
            Z = section.corroded_Z

            # Evaluate both ends
            for node_tag, forces in (
                (elem.n1, er.forces_n1),
                (elem.n2, er.forces_n2),
            ):
                # B31J directional indices for this specific end
                sif = compute_sif_set(elem, model, node_id=node_tag)
                M_i, M_o, M_t, moment_basis = self._moment_components(
                    model,
                    elem,
                    node_tag,
                    forces,
                )

                result = self._evaluate_node(
                    element_id=elem.id,
                    node_id=node_tag,
                    forces=forces,
                    pressure=pressure,
                    Do=Do,
                    t=t,
                    Z=Z,
                    i_i=sif.i_i,
                    i_o=sif.i_o,
                    i_t=sif.i_t,
                    k=sif.k_i,
                    h=sif.h,
                    moment_components=(M_i, M_o, M_t),
                    moment_basis=moment_basis,
                    S_h=S_h,
                    S_c=S_c,
                )
                report.results.append(result)

        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_load_case(
        model: TubaModel,
        name: Optional[str],
    ) -> Optional[LoadCase]:
        """Return the :class:`LoadCase` matching *name*, or the first one."""
        try:
            return model.resolve_load_case(name)[1]
        except ValueError:
            return None

    def _evaluate_node(
        self,
        *,
        element_id: str,
        node_id: str,
        forces: np.ndarray,
        pressure: float,
        Do: float,
        t: float,
        Z: float,
        i_i: float,
        i_o: float,
        i_t: float,
        k: float,
        h: float,
        S_h: float,
        S_c: float,
        moment_components: Optional[tuple[float, float, float]] = None,
        moment_basis: str = "resultant_in_plane",
    ) -> ElementComplianceResult:
        """Evaluate sustained and expansion stress at one element end.

        Force vector convention (beam local axes):
            ``[N, Vy, Vz, Mx, My, Mz]``
        where *Mx* is torsion, and *My*, *Mz* are bending moments.
        """
        # Extract moments
        Mx = float(forces[3])  # torsion
        My = float(forces[4])  # bending
        Mz = float(forces[5])  # bending

        # Resultant bending — in-plane and out-of-plane
        M_i = math.sqrt(My ** 2 + Mz ** 2)  # in-plane resultant
        M_o = 0.0  # For straight pipes M_o = 0; for bends, the solver
        # already decomposes into local axes — My, Mz capture both.
        # A more refined decomposition would separate in-plane vs.
        # out-of-plane via element orientation; we conservatively treat
        # the full resultant as in-plane here.
        M_t = abs(Mx)  # torsional
        if moment_components is not None:
            M_i, M_o, M_t = moment_components

        # Standard allowable displacement stress range (§302.3.5(d), Eq. 1a).
        S_A_standard = self.f * (1.25 * S_c + 0.25 * S_h)

        # Guard against zero thickness / zero Z
        if t <= 0 or Z <= 0:
            return ElementComplianceResult(
                element_id=element_id,
                node_id=node_id,
                sustained_stress=0.0,
                sustained_allowable=S_h,
                sustained_ratio=0.0,
                sustained_pass=True,
                expansion_stress=0.0,
                expansion_allowable=S_A_standard,
                expansion_ratio=0.0,
                expansion_pass=True,
            )

        # --- Sustained stress (Eq. 302.3.5-1) ---
        pressure_term = pressure * Do / (4.0 * t)
        bending_sustained = math.sqrt(
            (i_i * M_i) ** 2 + (i_o * M_o) ** 2
        ) / Z
        S_L = pressure_term + bending_sustained

        # --- Displacement (expansion) stress range (§319.4.4) ---
        # B31J torsional index i_t applied (i_t = 1.0 for elbows, so this is
        # numerically identical to the classic lumped form for bends).
        S_E = math.sqrt(
            (i_i * M_i) ** 2 + (i_o * M_o) ** 2 + (i_t * M_t) ** 2
        ) / Z

        # Allowable displacement stress range: liberal form (§302.3.5(d),
        # Eq. 1b) credits the portion of Sh not consumed by sustained stress.
        if self.use_liberal_allowable and S_h > 0.0:
            S_A = self.f * (1.25 * (S_c + S_h) - S_L)
        else:
            S_A = S_A_standard

        # Ratios
        sus_ratio = S_L / S_h if S_h > 0 else float("inf")
        exp_ratio = S_E / S_A if S_A > 0 else float("inf")

        return ElementComplianceResult(
            element_id=element_id,
            node_id=node_id,
            sustained_stress=S_L,
            sustained_allowable=S_h,
            sustained_ratio=sus_ratio,
            sustained_pass=(sus_ratio <= 1.0),
            expansion_stress=S_E,
            expansion_allowable=S_A,
            expansion_ratio=exp_ratio,
            expansion_pass=(exp_ratio <= 1.0),
            # Traceability fields
            pressure=pressure,
            Do=Do,
            t=t,
            Z=Z,
            i_i=i_i,
            i_o=i_o,
            k=k,
            h=h,
            M_i=M_i,
            M_o=M_o,
            M_t=M_t,
            moment_basis=moment_basis,
            S_h=S_h,
            S_c=S_c,
            f=self.f,
        )

    def _moment_components(
        self,
        model: TubaModel,
        elem: Element,
        node_id: str,
        forces: np.ndarray,
    ) -> tuple[float, float, float, str]:
        Mx = float(forces[3])
        My = float(forces[4])
        Mz = float(forces[5])
        if bend_local_axes(elem, model, node_id=node_id) is not None:
            return abs(My), abs(Mz), abs(Mx), "bend_geometry_local_axes"
        return math.sqrt(My ** 2 + Mz ** 2), 0.0, abs(Mx), "resultant_in_plane"


def _operation_field_value_for_element(
    model: TubaModel,
    load_case: Optional[LoadCase],
    elem: Element,
    *,
    quantity: str,
    default: float,
) -> float:
    if load_case is None:
        return default
    value = float(default)
    for field_record in getattr(load_case, "fields", []):
        if field_record.quantity != quantity:
            continue
        if field_record.profile != "uniform":
            raise ValueError(
                f"Compliance currently supports only uniform {quantity!r} operation fields."
            )
        selected = model.resolve_operation_field_elements(field_record)
        if any(selected_elem.id == elem.id for selected_elem in selected):
            value = float(field_record.value)
    return value
