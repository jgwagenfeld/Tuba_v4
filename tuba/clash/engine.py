"""Internal clash detection engines."""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np

from tuba.clash.types import ClashResult
from tuba.model import TubaModel
from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.results import ResultState
from tuba.analysis.states import GeometryState
from tuba.physical import physical_properties_for_element
from tuba.refs import EntityRef


class ClashEngine:
    """Analytic clash engine for model elements against cuboid/cylinder obstacles.

    This is the default clash engine used across rules, routing, and
    visualization. It computes segment-vs-AABB distances analytically and
    returns structured :class:`ClashResult` objects, so it has no trimesh / IFC
    / viewer dependency.

    Model clash checks cover analytic cuboid/cylinder obstacles; operating
    checks use the current result and geometry states. Other obstacle types are
    intentionally outside this review path.

    Element-versus-element checks distinguish intended joins from unintended
    clashes by topology, not by geometry alone. An intended connection is an
    explicit model record: a shared node id (welded/bolted joint, tee header,
    same-row bay joint), a support linking the two endpoints (pipe shoe/rest
    on steel), or couplings sharing one port target. Anything close in space
    without such a record is reported. Near-duplicate nodes (different ids
    within ``duplicate_tol_m``) are a modeling error reported separately, so
    the element check suppresses endpoint-only near-misses it would otherwise
    double-report.
    """

    #: Different node ids within this distance are one joint modelled twice.
    #: Matches the 1 mm collapse tolerance used by the IFC importer.
    DUPLICATE_NODE_TOL_M = 0.001

    def check_model(self, model: TubaModel, *, clearance_m: float = 0.0) -> list[ClashResult]:
        clashes: list[ClashResult] = []
        for elem in model.elements:
            try:
                props = physical_properties_for_element(model, elem)
            except ValueError:
                continue
            p1 = model.nodes[elem.n1].coords
            p2 = model.nodes[elem.n2].coords
            for obs in model.obstacles:
                clashes.extend(
                    self._check_element_obstacle(
                        elem_id=elem.id,
                        p1=p1,
                        p2=p2,
                        hard_radius=props.effective_radius_m,
                        clearance_radius=props.effective_radius_m + clearance_m,
                        obstacle=obs,
                    )
                )
        return clashes

    def check_self(
        self,
        model: TubaModel,
        *,
        clearance_m: float = 0.0,
        duplicate_tol_m: float | None = None,
    ) -> list[ClashResult]:
        """Element-versus-element clashes without a topological connection.

        Two elements clash when their centreline distance is below the sum of
        their effective radii plus *clearance_m*, unless topology authorizes
        the contact: a shared node id, a support linking an endpoint pair, or
        couplings sharing one port target. A duplicated element (same node
        set) is always reported. Pairs whose only proximity is an
        endpoint-to-endpoint near-miss within *duplicate_tol_m* are skipped
        here because :meth:`check_duplicate_nodes` reports the root cause.
        """
        from tuba.geometry.spatial import SpatialIndex

        duplicate_tol = self.DUPLICATE_NODE_TOL_M if duplicate_tol_m is None else float(duplicate_tol_m)
        entries: list[tuple[Any, np.ndarray, np.ndarray, float]] = []
        for elem in model.elements:
            try:
                props = physical_properties_for_element(model, elem)
            except ValueError:
                continue
            try:
                p1 = np.asarray(model.nodes[elem.n1].coords, dtype=float)
                p2 = np.asarray(model.nodes[elem.n2].coords, dtype=float)
            except KeyError:
                continue
            radius = float(props.effective_radius_m)
            entries.append((elem, p1, p2, radius))
        if len(entries) < 2:
            return []

        bounds_items = []
        for index, (_elem, p1, p2, radius) in enumerate(entries):
            pad = radius + float(clearance_m)
            lo = np.minimum(p1, p2) - pad
            hi = np.maximum(p1, p2) + pad
            bounds_items.append((index, (*[float(v) for v in lo], *[float(v) for v in hi])))
        index = SpatialIndex.from_bounds(bounds_items)

        support_links = _support_link_map(model)
        coupling_targets = _coupling_target_map(model)
        clashes: list[ClashResult] = []
        for i, (elem_a, a1, a2, ra) in enumerate(entries):
            pad_a = ra + float(clearance_m)
            lo = np.minimum(a1, a2) - pad_a
            hi = np.maximum(a1, a2) + pad_a
            for j in index.query((*[float(v) for v in lo], *[float(v) for v in hi])):
                if int(j) <= i:
                    continue
                elem_b, b1, b2, rb = entries[int(j)]
                verdict = _intended_connection(
                    elem_a, elem_b, support_links=support_links, coupling_targets=coupling_targets
                )
                if verdict is not None and verdict[0] != "duplicate_element":
                    continue
                distance, c1, _c2, s, t = _segment_segment_distance(a1, a2, b1, b2)
                limit = ra + rb + float(clearance_m)
                if distance >= limit:
                    continue
                if verdict is not None and verdict[0] == "duplicate_element":
                    overlap = "duplicate_element"
                else:
                    if _min_endpoint_distance(a1, a2, b1, b2) <= duplicate_tol:
                        # One joint modelled as two nodes; duplicate check owns it.
                        continue
                    overlap = _classify_pair_overlap(a1, a2, b1, b2, s, t)
                severity = "hard" if distance < ra + rb else "clearance"
                penetration = max(limit - distance, 0.0)
                location = tuple(float(v) for v in (c1))
                diagnostics = _self_clash_diagnostics(
                    elem_a, elem_b, a1, a2, b1, b2, ra, rb,
                    distance=distance, location=location, overlap_type=overlap,
                )
                clashes.append(
                    ClashResult(
                        left=EntityRef("element", elem_a.id),
                        right=EntityRef("element", elem_b.id),
                        severity=severity,  # type: ignore[arg-type]
                        distance_m=float(distance),
                        penetration_m=float(penetration),
                        location=location,
                        diagnostics=diagnostics,
                        metadata={
                            "check": "self",
                            "reason": "no_topological_connection" if overlap != "duplicate_element" else "duplicate_element",
                            "overlap_type": overlap,
                            "sum_radii_m": float(ra + rb),
                            "clearance_m": float(clearance_m),
                            "closest_s": float(s),
                            "closest_t": float(t),
                        },
                    )
                )
        return clashes

    def check_duplicate_nodes(
        self, model: TubaModel, *, tolerance_m: float | None = None
    ) -> list[ClashResult]:
        """Node pairs with different ids sharing (near-)identical coordinates.

        Such pairs are one joint modelled twice: downstream elements cannot
        share a node id, so every later self-clash or solver disconnect traces
        back here. Tolerance defaults to :attr:`DUPLICATE_NODE_TOL_M`.
        """
        from tuba.geometry.spatial import SpatialIndex

        tolerance = self.DUPLICATE_NODE_TOL_M if tolerance_m is None else float(tolerance_m)
        ids = list(model.nodes)
        if len(ids) < 2:
            return []
        items = []
        for node_id in ids:
            point = np.asarray(model.nodes[node_id].coords, dtype=float)
            items.append((node_id, (
                float(point[0] - tolerance), float(point[1] - tolerance), float(point[2] - tolerance),
                float(point[0] + tolerance), float(point[1] + tolerance), float(point[2] + tolerance),
            )))
        spatial = SpatialIndex.from_bounds(items)
        seen: set[frozenset[str]] = set()
        clashes: list[ClashResult] = []
        for node_id in ids:
            point = np.asarray(model.nodes[node_id].coords, dtype=float)
            query = (
                float(point[0] - tolerance), float(point[1] - tolerance), float(point[2] - tolerance),
                float(point[0] + tolerance), float(point[1] + tolerance), float(point[2] + tolerance),
            )
            for other_id in spatial.query(query):
                if other_id == node_id:
                    continue
                key = frozenset((node_id, other_id))
                if key in seen:
                    continue
                seen.add(key)
                other = np.asarray(model.nodes[other_id].coords, dtype=float)
                distance = float(np.linalg.norm(point - other))
                if distance > tolerance:
                    continue
                midpoint = tuple(float(v) for v in (point + other) / 2.0)
                clashes.append(
                    ClashResult(
                        left=EntityRef("node", node_id),
                        right=EntityRef("node", other_id),
                        severity="hard",
                        distance_m=distance,
                        penetration_m=max(tolerance - distance, 0.0),
                        location=midpoint,
                        diagnostics=[
                            f"Nodes {node_id!r} and {other_id!r} are {distance * 1000.0:.2f} mm apart "
                            f"(tolerance {tolerance * 1000.0:.2f} mm): merge to one node id so connected "
                            "elements share it, instead of overlapping as separate joints.",
                        ],
                        metadata={
                            "check": "duplicate_node",
                            "reason": "duplicate_node",
                            "tolerance_m": float(tolerance),
                        },
                    )
                )
        return clashes

    def check_all(
        self,
        model: TubaModel,
        *,
        clearance_m: float = 0.0,
        duplicate_tol_m: float | None = None,
    ) -> list[ClashResult]:
        """Every cold-model check in one pass: obstacles, self, and duplicate nodes.

        The combined triple a studio or rule runs to judge "clash free": element
        vs obstacle, element vs element without a topological connection, and
        near-duplicate nodes. ``duplicate_tol_m`` reaches both the self-check's
        endpoint near-miss and the duplicate-node check.
        """
        return [
            *self.check_model(model, clearance_m=clearance_m),
            *self.check_self(model, clearance_m=clearance_m, duplicate_tol_m=duplicate_tol_m),
            *self.check_duplicate_nodes(model, tolerance_m=duplicate_tol_m),
        ]

    def check_new(
        self,
        model: TubaModel,
        *,
        new_element_ids: Iterable[str] = (),
        new_node_ids: Iterable[str] = (),
    ) -> list[ClashResult]:
        """Clashes touching freshly built records, for inline feedback after a build.

        The delta view of :meth:`check_all`: a result is kept only when one side
        is a new element (obstacle/self) or a new node (duplicate nodes).
        """
        fresh_elements = set(new_element_ids)
        fresh_nodes = set(new_node_ids)
        clashes: list[ClashResult] = []
        for clash in self.check_self(model):
            if clash.left.id in fresh_elements or clash.right.id in fresh_elements:
                clashes.append(clash)
        for clash in self.check_model(model):
            if clash.left.kind == "element" and clash.left.id in fresh_elements:
                clashes.append(clash)
        for clash in self.check_duplicate_nodes(model):
            if clash.left.id in fresh_nodes or clash.right.id in fresh_nodes:
                clashes.append(clash)
        return clashes

    def check_operating_state(
        self,
        model: TubaModel,
        *,
        cold_state: GeometryState,
        operating_state: GeometryState,
        result_state: ResultState,
        envelope_type: str = "insulation",
        clearance_m: float = 0.0,
        analysis_mesh: AnalysisMesh | None = None,
    ) -> list[ClashResult]:
        from tuba.clash.operating import check_operating_state

        return check_operating_state(
            model,
            cold_state=cold_state,
            operating_state=operating_state,
            result_state=result_state,
            envelope_type=envelope_type,
            clearance_m=clearance_m,
            analysis_mesh=analysis_mesh,
        )

    def _check_element_obstacle(
        self,
        *,
        elem_id: str,
        p1: np.ndarray,
        p2: np.ndarray,
        hard_radius: float,
        clearance_radius: float,
        obstacle: dict,
    ) -> Iterable[ClashResult]:
        obs_type = obstacle.get("type")
        obs_id = obstacle.get("id", "obstacle")
        if obs_type not in ("cuboid", "cylinder"):
            return []
        if obstacle.get("min_point") is None or obstacle.get("max_point") is None:
            return []

        lo = np.asarray(obstacle["min_point"], dtype=float)
        hi = np.asarray(obstacle["max_point"], dtype=float)
        distance, location = _segment_aabb_distance(p1, p2, lo, hi)
        if distance >= clearance_radius:
            return []

        severity = "hard" if distance < hard_radius else "clearance"
        penetration = max(clearance_radius - distance, 0.0)
        return [
            ClashResult(
                left=EntityRef("element", elem_id),
                right=EntityRef("obstacle", obs_id),
                severity=severity,
                distance_m=distance,
                penetration_m=penetration,
                location=tuple(float(value) for value in location),
            )
        ]


def _segment_aabb_distance(
    p1: np.ndarray,
    p2: np.ndarray,
    lo: np.ndarray,
    hi: np.ndarray,
) -> tuple[float, np.ndarray]:
    lower = np.minimum(lo, hi)
    upper = np.maximum(lo, hi)
    lo = lower
    hi = upper
    if _segment_intersects_aabb(p1, p2, lo, hi):
        return 0.0, (p1 + p2) / 2.0

    direction = p2 - p1
    left = 0.0
    right = 1.0
    for _ in range(72):
        m1 = left + (right - left) / 3.0
        m2 = right - (right - left) / 3.0
        d1 = _point_aabb_distance(p1 + direction * m1, lo, hi)
        d2 = _point_aabb_distance(p1 + direction * m2, lo, hi)
        if d1 < d2:
            right = m2
        else:
            left = m1
    t = (left + right) / 2.0
    point = p1 + direction * t
    return _point_aabb_distance(point, lo, hi), point


def _segment_intersects_aabb(p1: np.ndarray, p2: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> bool:
    t_min = 0.0
    t_max = 1.0
    direction = p2 - p1
    for axis in range(3):
        if abs(direction[axis]) < 1e-12:
            if p1[axis] < lo[axis] or p1[axis] > hi[axis]:
                return False
            continue
        inv = 1.0 / direction[axis]
        t1 = (lo[axis] - p1[axis]) * inv
        t2 = (hi[axis] - p1[axis]) * inv
        t_low = min(t1, t2)
        t_high = max(t1, t2)
        t_min = max(t_min, t_low)
        t_max = min(t_max, t_high)
        if t_min > t_max:
            return False
    return True


def _point_aabb_distance(point: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    below = np.maximum(lo - point, 0.0)
    above = np.maximum(point - hi, 0.0)
    return float(np.linalg.norm(below + above))


def _support_link_map(model: TubaModel) -> dict[frozenset[str], str]:
    """Endpoint pairs joined by a support, mapped to the support id."""
    links: dict[frozenset[str], str] = {}
    for support in model.supports:
        if support.attached_to is None or support.attached_to == support.node:
            continue
        links.setdefault(frozenset((support.node, support.attached_to)), support.id or "support")
    return links


def _coupling_target_map(model: TubaModel) -> dict[str, set[str]]:
    """Element ids mapped to the port/component targets their couplings name."""
    targets: dict[str, set[str]] = {}
    for coupling in getattr(model, "couplings", {}).values():
        source = getattr(coupling.source, "id", None)
        target = getattr(coupling.target, "id", None)
        if getattr(coupling.source, "kind", None) != "element" or not source or not target:
            continue
        targets.setdefault(str(source), set()).add(str(target))
    return targets


def _intended_connection(
    elem_a: Any,
    elem_b: Any,
    *,
    support_links: dict[frozenset[str], str],
    coupling_targets: dict[str, set[str]],
) -> tuple[str, str] | None:
    """Why two elements may touch, or None when no record authorizes it."""
    nodes_a = {elem_a.n1, elem_a.n2}
    nodes_b = {elem_b.n1, elem_b.n2}
    shared = nodes_a & nodes_b
    if shared:
        if nodes_a == nodes_b:
            return ("duplicate_element", f"elements share both endpoints {sorted(nodes_a)!r}")
        node_id = sorted(shared)[0]
        return ("shared_node", f"elements share node {node_id!r}")
    for node_a in nodes_a:
        for node_b in nodes_b:
            key = frozenset((node_a, node_b))
            if key in support_links:
                return ("support_link", f"support {support_links[key]!r} links {node_a!r} to {node_b!r}")
    targets_a = coupling_targets.get(elem_a.id, set())
    targets_b = coupling_targets.get(elem_b.id, set())
    common = targets_a & targets_b
    if common:
        return ("shared_coupling_target", f"couplings share target {sorted(common)[0]!r}")
    return None


def _segment_segment_distance(
    p1: np.ndarray, q1: np.ndarray, p2: np.ndarray, q2: np.ndarray
) -> tuple[float, np.ndarray, np.ndarray, float, float]:
    """Closest distance between segments p1-q1 and p2-q2 with parameters."""
    p1 = np.asarray(p1, dtype=float)
    q1 = np.asarray(q1, dtype=float)
    p2 = np.asarray(p2, dtype=float)
    q2 = np.asarray(q2, dtype=float)
    d1 = q1 - p1
    d2 = q2 - p2
    len1_sq = float(np.dot(d1, d1))
    len2_sq = float(np.dot(d2, d2))
    if len1_sq <= 1e-24 and len2_sq <= 1e-24:
        return float(np.linalg.norm(p1 - p2)), p1.copy(), p2.copy(), 0.0, 0.0
    if len1_sq <= 1e-24:
        t = float(np.clip(np.dot(p1 - p2, d2) / len2_sq, 0.0, 1.0)) if len2_sq > 0 else 0.0
        c2 = p2 + t * d2
        return float(np.linalg.norm(p1 - c2)), p1.copy(), c2, 0.0, t
    if len2_sq <= 1e-24:
        s = float(np.clip(np.dot(p2 - p1, d1) / len1_sq, 0.0, 1.0)) if len1_sq > 0 else 0.0
        c1 = p1 + s * d1
        return float(np.linalg.norm(c1 - p2)), c1, p2.copy(), s, 0.0

    r = p1 - p2
    a = len1_sq
    e = len2_sq
    f = float(np.dot(d2, r))
    c = float(np.dot(d1, r))
    b = float(np.dot(d1, d2))
    denom = a * e - b * b
    s = float(np.clip((b * f - c * e) / denom, 0.0, 1.0)) if denom > 1e-18 else 0.0
    t = (b * s + f) / e if e > 1e-24 else 0.0
    if t < 0.0:
        t = 0.0
        s = float(np.clip(-c / a, 0.0, 1.0)) if a > 1e-24 else 0.0
    elif t > 1.0:
        t = 1.0
        s = float(np.clip((b - c) / a, 0.0, 1.0)) if a > 1e-24 else 0.0
    c1 = p1 + s * d1
    c2 = p2 + t * d2
    # Refine against the other segment's endpoints (standard two-pass).
    s2 = float(np.clip(np.dot(c2 - p1, d1) / a, 0.0, 1.0)) if a > 1e-24 else 0.0
    c1b = p1 + s2 * d1
    if float(np.linalg.norm(c1b - c2)) < float(np.linalg.norm(c1 - c2)):
        s, c1 = s2, c1b
    t2 = float(np.clip(np.dot(c1 - p2, d2) / e, 0.0, 1.0)) if e > 1e-24 else 0.0
    c2b = p2 + t2 * d2
    if float(np.linalg.norm(c1 - c2b)) < float(np.linalg.norm(c1 - c2)):
        t, c2 = t2, c2b
    return float(np.linalg.norm(c1 - c2)), c1, c2, float(s), float(t)


def _min_endpoint_distance(a1: np.ndarray, a2: np.ndarray, b1: np.ndarray, b2: np.ndarray) -> float:
    return min(
        float(np.linalg.norm(a1 - b1)),
        float(np.linalg.norm(a1 - b2)),
        float(np.linalg.norm(a2 - b1)),
        float(np.linalg.norm(a2 - b2)),
    )


def _classify_pair_overlap(
    a1: np.ndarray, a2: np.ndarray, b1: np.ndarray, b2: np.ndarray, s: float, t: float
) -> str:
    direction_a = np.asarray(a2, dtype=float) - np.asarray(a1, dtype=float)
    direction_b = np.asarray(b2, dtype=float) - np.asarray(b1, dtype=float)
    norm_a = float(np.linalg.norm(direction_a))
    norm_b = float(np.linalg.norm(direction_b))
    if norm_a > 1e-12 and norm_b > 1e-12:
        parallel = abs(float(np.dot(direction_a / norm_a, direction_b / norm_b))) > 0.99
        if parallel:
            return "colinear_overlap"
    at_end = lambda value: value <= 1e-9 or value >= 1.0 - 1e-9
    if at_end(s) and at_end(t):
        return "end_touch"
    return "crossing"


def _self_clash_diagnostics(
    elem_a: Any,
    elem_b: Any,
    a1: np.ndarray,
    a2: np.ndarray,
    b1: np.ndarray,
    b2: np.ndarray,
    ra: float,
    rb: float,
    *,
    distance: float,
    location: tuple[float, ...],
    overlap_type: str,
) -> list[str]:
    point = f"[{location[0]:.4f}, {location[1]:.4f}, {location[2]:.4f}]"
    base = (
        f"{elem_a.id!r} ({elem_a.type} "
        f"[{a1[0]:.3f}, {a1[1]:.3f}, {a1[2]:.3f}]->[{a2[0]:.3f}, {a2[1]:.3f}, {a2[2]:.3f}]) "
        f"is {distance:.4f} m from {elem_b.id!r} ({elem_b.type}) at {point} "
        f"(sum of radii {ra + rb:.4f} m); no shared node, support link, or shared "
        "coupling target authorizes this contact."
    )
    if overlap_type == "duplicate_element":
        return [base + " Both elements use the same endpoints: delete one."]
    if overlap_type == "colinear_overlap":
        return [
            base
            + " The centrelines run parallel and overlap: merge into one run or model an "
            "explicit corner/miter joint instead of stacking two members."
        ]
    if overlap_type == "end_touch":
        return [
            base
            + " The closest points are both endpoints: give the joint one shared node id "
            "(or merge the near-duplicate nodes) instead of two abutting ends."
        ]
    return [base]
