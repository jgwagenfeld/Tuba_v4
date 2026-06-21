"""
tuba.compliance.sif — Stress Intensification Factors per ASME B31.3 Appendix D.

This module provides low-level SIF and flexibility-factor calculations for
piping bends, as well as a convenience wrapper that reads element metadata
from a :class:`~tuba.model.TubaModel`.
"""

from __future__ import annotations

import math
import numpy as np
from typing import TYPE_CHECKING, Tuple, Optional

if TYPE_CHECKING:
    from tuba.model import Element, TubaModel


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
    connecting = [e for e in model.elements if e.n1 == node_id or e.n2 == node_id]
    if len(connecting) != 3:
        return None

    # Calculate unit vectors from junction node to other node of each element
    u_vectors = []
    j_coords = model.nodes[node_id].coords
    for e in connecting:
        other_nid = e.n2 if e.n1 == node_id else e.n1
        other_coords = model.nodes[other_nid].coords
        v = other_coords - j_coords
        norm = np.linalg.norm(v)
        u = v / norm if norm > 1e-9 else np.array([1.0, 0.0, 0.0])
        u_vectors.append(u)

    # Find the header pair (dot product closest to -1)
    d01 = np.dot(u_vectors[0], u_vectors[1])
    d12 = np.dot(u_vectors[1], u_vectors[2])
    d20 = np.dot(u_vectors[2], u_vectors[0])

    min_dot = min(d01, d12, d20)
    if min_dot == d01:
        header_el = connecting[0]
    elif min_dot == d12:
        header_el = connecting[1]
    else:
        header_el = connecting[2]

    # Use header section geometry for SIF calculation
    header_section = model.sections[header_el.section]
    t_h = header_section.corroded_WT
    r_mh = header_section.mean_radius

    # Get Tee configuration
    tee_config = model.tees.get(node_id, {"type": "unreinforced_tee", "pad_thickness": 0.0})
    tee_type = tee_config.get("type", "unreinforced_tee")
    t_r = tee_config.get("pad_thickness", 0.0)

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


def compute_sifs(
    element: "Element",
    model: "TubaModel",
    node_id: Optional[str] = None,
) -> Tuple[float, float, float, float]:
    r"""Compute SIFs, flexibility factor, and *h* for a model element.

    For **straight pipe** elements the stress intensification factors default
    to unity and the flexibility factor is 1.0.

    For **bends**, the full ASME B31.3 Appendix D calculation is performed.

    For **Tee junctions** (detected when three elements connect at a node),
    the SIF is calculated based on the branch/run geometry and Tee type.
    """
    if node_id is not None:
        tee_sifs = _get_tee_sifs(node_id, element, model)
        if tee_sifs is not None:
            return tee_sifs

    section = model.sections[element.section]

    if element.type != "pipe_bend" or element.bend_radius is None:
        # Straight pipe — no stress intensification
        return (1.0, 1.0, 1.0, 0.0)

    t = section.corroded_WT
    R = element.bend_radius
    r_m = section.mean_radius

    h = flexibility_characteristic(t, R, r_m)
    i_i = sif_inplane(h)
    i_o = sif_outplane(h)
    k = flexibility_factor(h)

    return (i_i, i_o, k, h)
