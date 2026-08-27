"""
tuba.compliance.sif — Stress Intensification / flexibility factors.

Low-level SIF and flexibility-factor calculations plus a convenience wrapper
that reads element metadata from a :class:`~tuba.model.TubaModel`.

Standard basis
--------------
ASME B31.3-2020 deleted Appendix D and made ASME B31J-2017/2023 mandatory for
i-factors and k-factors. B31J is a *directional* index system (separate
in-plane / out-of-plane / torsional / axial indices and direction-specific
flexibility) — see :class:`SIFSet`.

For **bends/elbows** the B31J i-factors and flexibility factor are numerically
unchanged from Appendix D (``h = tR/r_m^2``, ``i_i = 0.9/h^(2/3)``,
``i_o = 0.75/h^(2/3)``, ``k = 1.65/h``), verified against the pveng.com B31.3
sample report — so the bend results here are current-code correct.

For **branch connections / tees** the exact B31J Table 1-1 branch/run
coefficients are only in the licensed standard and are NOT encoded here. The
legacy helper below can reproduce pre-2020 Appendix-D (Markl) values only when
the caller explicitly passes ``allow_appendix_d_tee=True``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Tuple, Optional

from tuba.geometry.junctions import classify_tee_junction

if TYPE_CHECKING:
    from tuba.model import Element, TubaModel


@dataclass(frozen=True)
class SIFSet:
    """B31J directional stress-intensification and flexibility indices.

    ``basis`` records provenance: ``"b31j_elbow"`` (bend values confirmed
    current under B31J), ``"straight"`` (trivially unity), or
    ``"appendix_d_legacy"`` (explicitly requested pre-2020 Markl tee values).
    """

    i_i: float          # in-plane SIF
    i_o: float          # out-of-plane SIF
    i_t: float = 1.0    # torsional SIF (B31J; = 1.0 for elbows)
    i_a: float = 1.0    # axial SIF (B31J; = 1.0 for elbows)
    k_i: float = 1.0    # in-plane flexibility factor
    k_o: float = 1.0    # out-of-plane flexibility factor
    h: float = 0.0      # flexibility characteristic
    basis: str = "b31j_elbow"

    @property
    def k(self) -> float:
        """Scalar flexibility factor (= ``k_i``; ``k_i == k_o`` for elbows)."""
        return self.k_i


def flexibility_characteristic(t: float, R: float, r_m: float) -> float:
    r"""Compute the flexibility characteristic *h* for a pipe bend.

    .. math::

        h = \frac{t \cdot R}{r_m^2}

    Parameters
    ----------
    t : float
        Nominal (or corroded) wall thickness [m].
    R : float
        Bend radius [m].
    r_m : float
        Mean radius of the pipe cross-section [m].

    Returns
    -------
    float
        Flexibility characteristic *h* (dimensionless).

    Raises
    ------
    ValueError
        If any input is non-positive.
    """
    if t <= 0 or R <= 0 or r_m <= 0:
        raise ValueError(
            f"All inputs must be positive: t={t}, R={R}, r_m={r_m}"
        )
    return t * R / (r_m ** 2)


def sif_inplane(h: float) -> float:
    r"""In-plane stress intensification factor for a pipe bend.

    .. math::

        i_i = \max\!\left(\frac{0.9}{h^{2/3}},\; 1.0\right)

    Parameters
    ----------
    h : float
        Flexibility characteristic (from :func:`flexibility_characteristic`).

    Returns
    -------
    float
        In-plane SIF, never less than 1.0.
    """
    if h <= 0:
        raise ValueError(f"Flexibility characteristic must be positive: h={h}")
    return max(0.9 / h ** (2.0 / 3.0), 1.0)


def sif_outplane(h: float) -> float:
    r"""Out-of-plane stress intensification factor for a pipe bend.

    .. math::

        i_o = \max\!\left(\frac{0.75}{h^{2/3}},\; 1.0\right)

    Parameters
    ----------
    h : float
        Flexibility characteristic.

    Returns
    -------
    float
        Out-of-plane SIF, never less than 1.0.
    """
    if h <= 0:
        raise ValueError(f"Flexibility characteristic must be positive: h={h}")
    return max(0.75 / h ** (2.0 / 3.0), 1.0)


def flexibility_factor(h: float) -> float:
    r"""Flexibility factor for a pipe bend.

    .. math::

        k = \frac{1.65}{h}

    Parameters
    ----------
    h : float
        Flexibility characteristic.

    Returns
    -------
    float
        Flexibility factor *k*.
    """
    if h <= 0:
        raise ValueError(f"Flexibility characteristic must be positive: h={h}")
    return 1.65 / h


def _get_tee_sifs(node_id: str, element: "Element", model: "TubaModel") -> Optional[Tuple[float, float, float, float]]:
    connecting = [
        e for e in model.elements
        if (e.n1 == node_id or e.n2 == node_id) and e.type.startswith("pipe")
    ]
    if len(connecting) != 3:
        return None

    junction = classify_tee_junction(model, node_id)
    header_el = model.get_element(junction.header_element_ids[0])
    assert header_el is not None

    # Use header section geometry for SIF calculation
    header_section = model.sections[header_el.section]
    t_h = header_section.corroded_WT
    r_mh = header_section.mean_radius

    # Get Tee configuration
    tee_config = model.tees.get(node_id)
    tee_type = tee_config.type if tee_config is not None else "unreinforced_tee"
    t_r = tee_config.pad_thickness if tee_config is not None else 0.0

    # Compute flexibility characteristic h
    if t_h <= 0 or r_mh <= 0:
        return (1.0, 1.0, 1.0, 0.0)

    if tee_type == "welding_tee":
        h = 4.4 * t_h / r_mh
    elif tee_type == "reinforced_tee":
        h = ((t_h + 0.5 * t_r) ** 2.5) / (t_h ** 1.5 * r_mh)
    else: # unreinforced_tee
        h = t_h / r_mh

    # Compute SIFs
    if h <= 0:
        return (1.0, 1.0, 1.0, 0.0)

    i_i = max(0.9 / (h ** (2.0 / 3.0)), 1.0)
    i_o = max(0.9 / (h ** (2.0 / 3.0)), 1.0)
    k = 1.0 # Tee is rigid

    return (i_i, i_o, k, h)


def compute_sif_set(
    element: "Element",
    model: "TubaModel",
    node_id: Optional[str] = None,
    *,
    allow_appendix_d_tee: bool = False,
) -> SIFSet:
    r"""Compute the full B31J directional index set for a model element.

    - **Straight pipe**: all indices unity.
    - **Bends/elbows**: B31J i-factors (== Appendix D: ``i_i = 0.9/h^(2/3)``,
      ``i_o = 0.75/h^(2/3)``), torsional/axial indices ``= 1.0``, directional
      flexibility ``k_i = k_o = 1.65/h``. Large-D/thin-wall pressure corrections
      are not applied.
    - **Tee/branch junctions** (three elements at *node_id*): rejected by
      default because exact B31J Table 1-1 branch/run coefficients require the
      licensed standard. Set ``allow_appendix_d_tee=True`` only for explicit
      legacy Appendix-D checks.
    """
    if node_id is not None:
        tee_sifs = _get_tee_sifs(node_id, element, model)
        if tee_sifs is not None:
            if not allow_appendix_d_tee:
                raise ValueError(
                    "Tee SIF calculation requires B31J Table 1-1 data. "
                    "Appendix-D tee equations are disabled unless allow_appendix_d_tee=True."
                )
            i_i, i_o, k, h = tee_sifs
            return SIFSet(
                i_i=i_i, i_o=i_o, i_t=1.0, i_a=1.0, k_i=k, k_o=k, h=h,
                basis="appendix_d_legacy",
            )

    section = model.sections[element.section]

    if element.type != "pipe_bend" or element.bend_radius is None:
        return SIFSet(i_i=1.0, i_o=1.0, i_t=1.0, i_a=1.0, k_i=1.0, k_o=1.0, h=0.0, basis="straight")

    t = section.corroded_WT
    R = element.bend_radius
    r_m = section.mean_radius

    h = flexibility_characteristic(t, R, r_m)
    k = flexibility_factor(h)
    return SIFSet(
        i_i=sif_inplane(h), i_o=sif_outplane(h), i_t=1.0, i_a=1.0,
        k_i=k, k_o=k, h=h, basis="b31j_elbow",
    )


def compute_sifs(
    element: "Element",
    model: "TubaModel",
    node_id: Optional[str] = None,
    *,
    allow_appendix_d_tee: bool = False,
) -> Tuple[float, float, float, float]:
    r"""Backward-compatible ``(i_i, i_o, k, h)`` tuple.

    Thin wrapper over :func:`compute_sif_set`; use that for the full B31J index
    set (torsional/axial indices and directional flexibility).
    """
    s = compute_sif_set(element, model, node_id=node_id, allow_appendix_d_tee=allow_appendix_d_tee)
    return (s.i_i, s.i_o, s.k_i, s.h)
