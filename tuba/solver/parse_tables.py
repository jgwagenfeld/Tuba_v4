"""Parse Code_Aster result artifacts into transient numerical results.

Pure functions over an output directory: no solver instance, no execution, no
solver configuration beyond what the directory's own manifest records. The
manifest's compiler inputs (pipe modelization) select the stress-table path and
its ``element_sources`` map solver sub-elements back onto model elements; a
manifest-less directory falls back to a plain identity mapping.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from tuba.analysis import AnalysisStudy
from tuba.analysis.tuyau import (
    CODE_ASTER_TUYAU_NCOU,
    CODE_ASTER_TUYAU_NSEC,
    DISPLAY_GENERATRICE,
    subpoint_station,
)
from tuba.model import Element, PipeSection, TubaModel
from tuba.solver.aster_sidecar import load_and_attest_artifact_chain
from tuba.solver.base import ElementResult, FEAResults, NodeResult
from tuba.solver.modelisation import PipeModelization

logger = logging.getLogger(__name__)

# The TUYAU sub-point convention has one home; see tuba/analysis/tuyau.py.
_CODE_ASTER_TUYAU_NCOU = CODE_ASTER_TUYAU_NCOU
_CODE_ASTER_TUYAU_NSEC = CODE_ASTER_TUYAU_NSEC
_TUBA_GENE_TUYAU = np.array(DISPLAY_GENERATRICE, dtype=float)


# Result parsing
# ==================================================================

def parse_result_artifacts(
    model: TubaModel,
    work_dir: str | Path,
    load_case_name: Optional[str] = None,
    *,
    study: AnalysisStudy | None = None,
) -> FEAResults:
    """Parse an existing Code_Aster output directory without running the solver."""
    root = Path(work_dir)
    validated_study, _, _, _ = load_and_attest_artifact_chain(
        model,
        root,
        study=study,
        requested_load_case=load_case_name,
    )
    return parse_result_artifacts_after_validation(model, root, validated_study.load_case)

def parse_result_artifacts_after_validation(
    model: TubaModel,
    work_dir: Path,
    load_case: str,
) -> FEAResults:
    results = parse_results(model, work_dir)
    results.load_case = load_case
    return results

#: The modelization a manifest omits. An export records ``compiler_inputs.pipe_modelization`` only
#: when the modelization is *not* the default (POU_D_T always; TUYAU_3M when a contact, line-segment
#: or discrete-support input is added), so an absent key means TUYAU_3M — the one modelization whose
#: stress table (study_sieq.csv) this parser reads. A volume study never parses here.
DEFAULT_PIPE_MODELIZATION = PipeModelization("TUYAU_3M")


def parse_results(
    model: TubaModel,
    work_dir: Path,
    instant: float | None = None,
    *,
    solver_name: str = "Code_Aster",
) -> FEAResults:
    """Parse solver outputs into :class:`FEAResults`.

    The parser reads the CSV text tables (units 38-41), which are generated
    by the solver and fully self-contained. If a ``study.rmed`` file exists
    it is recorded on the result object, but RMED inspection is left to
    explicit visualization/import paths so solver parsing never depends on
    optional mesh readers or their file-handle behavior.

    The manifest's compiler inputs select the stress-table path and its
    ``element_sources`` map solver sub-elements back onto model entities.
    """
    manifest_path = work_dir / "study_manifest.json"
    inputs = (
        json.loads(manifest_path.read_text(encoding="utf-8")).get("study", {}).get("metadata", {}).get("compiler_inputs", {})
        if manifest_path.exists()
        else {}
    )
    pipe_modelization = (
        PipeModelization(inputs["pipe_modelization"])
        if "pipe_modelization" in inputs
        else DEFAULT_PIPE_MODELIZATION
    )
    results = FEAResults(solver_name=solver_name)
    results._model = model

    rmed_path = work_dir / "study.rmed"
    if rmed_path.exists():
        results.result_file = rmed_path

    # --- Initialise empty results for every node/element ---------------
    for nid in model.nodes:
        results.node_results[nid] = NodeResult(
            node_id=nid,
            displacement=np.zeros(6),
        )
    for elem in model.elements:
        results.element_results[elem.id] = ElementResult(
            element_id=elem.id,
            forces_n1=np.full(6, np.nan),
            forces_n2=np.full(6, np.nan),
        )

    # --- Parse CSV tables ----------------------------------------------
    node_label_map, element_label_map = read_solver_label_maps(work_dir)
    analysis_mesh_node_ids = read_analysis_mesh_node_ids(work_dir)
    displacement_nodes = parse_depl_table(
        model,
        work_dir,
        results,
        node_label_map,
        analysis_mesh_node_ids,
        instant=instant,
    )
    # Displacement is the primary result of a static solve and is always
    # emitted by a successful run.  A run that exits cleanly but produced no
    # parseable displacement rows (empty/garbled CSV, bad mesh group, no
    # loads) would otherwise return the all-zero seed above as if it were a
    # valid result.  Refuse that, per the "never present non-real values as
    # solver results" contract (AGENTS.md).
    if not displacement_nodes:
        raise RuntimeError(
            f"Code_Aster produced no displacement results in {work_dir} "
            "(study_depl.csv is missing or has no parseable rows). The solver "
            "run did not generate real results; refusing to return an all-zero "
            "result. Inspect study.mess for solver errors."
        )
    missing_displacements = sorted(set(model.nodes) - displacement_nodes)
    if missing_displacements:
        raise RuntimeError(
            f"Code_Aster output is missing displacement results for model node(s) "
            f"{missing_displacements} in {work_dir}. Refusing to substitute zeros."
        )
    force_endpoints = parse_effo_table(
        model,
        work_dir,
        results,
        node_label_map,
        element_label_map,
        instant=instant,
    )
    # Element internal forces are what external evaluators can use to calculate code
    # stress. If displacement parsed but the force table is missing/empty/mismapped,
    # every stress-bearing element keeps its all-zero seed and compliance would
    # silently report PASS on fictitious zero moments. Refuse that, mirroring the
    # displacement guard above and the AGENTS.md "no proxy values as results" contract.
    pipe_elements = [elem for elem in model.elements if elem.type in ("pipe_straight", "pipe_bend")]
    if pipe_elements and not force_endpoints:
        raise RuntimeError(
            f"Code_Aster produced no element internal forces in {work_dir} "
            "(study_effo.csv is missing or has no parseable rows) even though the "
            "model has stress-bearing pipe elements. Refusing to return zero-force "
            "results that would pass compliance on fictitious stress. Inspect "
            "study.mess for solver errors."
        )
    expected_force_endpoints = {
        (element.id, node_id)
        for element in pipe_elements
        for node_id in (element.n1, element.n2)
    }
    missing_force_endpoints = sorted(expected_force_endpoints - force_endpoints)
    if missing_force_endpoints:
        labels = [f"{element_id}:{node_id}" for element_id, node_id in missing_force_endpoints]
        raise RuntimeError(
            f"Code_Aster output is missing internal-force results for pipe endpoint(s) "
            f"{labels} in {work_dir}. Refusing to substitute zeros."
        )
    parse_reac_table(model, work_dir, results, node_label_map, instant=instant)
    if pipe_modelization is PipeModelization.TUYAU_3M:
        parse_sieq_table(
            model,
            work_dir,
            results,
            node_label_map,
            element_label_map,
            instant=instant,
        )

    return results

# ------------------------------------------------------------------
# Individual table parsers
# ------------------------------------------------------------------

def parse_result_table(path, instant: float | None = None):
    rows = parse_csv_table(path)
    if instant is not None:
        rows = [row for row in rows if abs(float(row['INST']) - instant) < 1e-12]
    return rows

def parse_csv_table(path: Path) -> List[Dict[str, str]]:
    """Parse a Code_Aster ``IMPR_TABLE`` CSV into a list of row dicts.

    The first non-comment line containing the header columns is
    detected automatically.  Blank lines and lines starting with
    ``#`` are skipped.
    """
    if not path.exists():
        logger.warning("Table file not found: %s", path)
        return []

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [
        ln.strip() for ln in text.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]

    if len(lines) < 2:
        return []

    header = [h.strip() for h in lines[0].split(",")]
    rows: List[Dict[str, str]] = []
    for line in lines[1:]:
        vals = [v.strip() for v in line.split(",")]
        if len(vals) != len(header):
            continue
        rows.append(dict(zip(header, vals)))
    return rows

def read_solver_label_maps(work_dir: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Map Code_Aster's numeric table labels back to Tuba mesh names."""
    mail_path = work_dir / "study.mail"
    node_map: dict[str, str] = {}
    element_map: dict[str, str] = {}
    if not mail_path.exists():
        return node_map, element_map
    solver_to_tuba = read_solver_name_reverse_map(work_dir)

    node_index = 0
    element_index = 0
    block: str | None = None
    for raw_line in mail_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "COOR_3D":
            block = "nodes"
            continue
        if line in {"SEG2", "SEG3"}:
            block = "elements"
            continue
        if line == "FINSF":
            block = None
            continue
        if line == "FIN" or line.startswith("GROUP_") or line == "TITRE":
            block = None
            continue

        parts = line.split()
        if not parts:
            continue
        label = parts[0].strip()
        tuba_label = solver_to_tuba.get(label, label)
        if block == "nodes":
            node_index += 1
            node_map.setdefault(label, tuba_label)
            node_map.setdefault(tuba_label, tuba_label)
            node_map[str(node_index)] = tuba_label
        elif block == "elements":
            element_index += 1
            element_map.setdefault(label, tuba_label)
            element_map.setdefault(tuba_label, tuba_label)
            element_map[str(element_index)] = tuba_label

    return node_map, element_map

def read_solver_name_reverse_map(work_dir: Path) -> dict[str, str]:
    sidecar_path = work_dir / "study_tuba_fem.json"
    if not sidecar_path.exists():
        return {}
    try:
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    name_map = payload.get("name_map", {})
    if not isinstance(name_map, dict):
        return {}
    reverse: dict[str, str] = {}
    for original, solver_name in name_map.items():
        if isinstance(original, str) and isinstance(solver_name, str):
            reverse[solver_name] = original
    return reverse

def read_analysis_mesh_node_ids(work_dir: Path) -> set[str]:
    """Read authoritative analysis-node membership from the study manifest."""
    manifest_path = work_dir / "study_manifest.json"
    if not manifest_path.exists():
        return set()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    analysis_mesh = payload.get("analysis_mesh")
    if not isinstance(analysis_mesh, dict):
        return set()
    nodes = analysis_mesh.get("nodes")
    if not isinstance(nodes, dict):
        return set()
    return {node_id for node_id in nodes if isinstance(node_id, str)}

def parse_depl_table(
    model: TubaModel,
    work_dir: Path,
    results: FEAResults,
    node_label_map: dict[str, str],
    analysis_mesh_node_ids: set[str],
    instant: float | None = None,
) -> set[str]:
    """Parse displacement table (unit 39); return covered model-node IDs."""
    rows = parse_result_table(work_dir / "study_depl.csv", instant=instant)
    covered_model_nodes: set[str] = set()
    for row in rows:
        raw_nid = row.get("NOEUD", "").strip()
        nid = node_label_map.get(raw_nid, raw_nid)
        if not nid:
            continue

        def finite_component(component: str, kind: str) -> float:
            raw_value = row.get(component, "").strip()
            try:
                value = float(raw_value)
            except (ValueError, TypeError) as exc:
                raise RuntimeError(
                    f"Code_Aster displacement row has invalid {kind} "
                    f"{component}={raw_value!r} for node {nid!r}; {kind}s must "
                    "be finite numeric values. Refusing to mark the node covered."
                ) from exc
            if not np.isfinite(value):
                raise RuntimeError(
                    f"Code_Aster displacement row has invalid {kind} "
                    f"{component}={raw_value!r} for node {nid!r}; {kind}s must "
                    "be finite numeric values. Refusing to mark the node covered."
                )
            return value

        translations = [finite_component(component, "translation") for component in ("DX", "DY", "DZ")]
        rotations = [
            np.nan
            if row.get(component, "").strip() == "-"
            else finite_component(component, "rotation")
            for component in ("DRX", "DRY", "DRZ")
        ]
        disp = np.array([*translations, *rotations])
        if nid in results.node_results:
            results.node_results[nid].displacement = disp
            covered_model_nodes.add(nid)
            continue
        results.analysis_node_results[nid] = NodeResult(node_id=nid, displacement=disp)
        if nid not in analysis_mesh_node_ids:
            results.parser_diagnostics.append(
                f"Preserved displacement row for non-native analysis node {nid!r} without mesh source mapping."
            )
    return covered_model_nodes

def result_element_lookup(model: TubaModel, work_dir: Path) -> dict[str, Element]:
    """Map solver element ids (native and sub-segments) back to model elements.

    The fold-back is read from the manifest's ``element_sources``, the record the
    mesh writer wrote of how it subdivided each model element; a manifest-less
    directory folds only native ids onto themselves.
    """
    lookup = {element.id: element for element in model.elements}
    manifest_path = work_dir / "study_manifest.json"
    if not manifest_path.exists():
        return lookup
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        element_sources = payload["analysis_mesh"]["element_sources"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return lookup
    for segment_id, source in element_sources.items():
        if not isinstance(source, dict):
            continue
        source_ref = source.get("source_ref")
        if not isinstance(source_ref, dict) or source_ref.get("kind") != "element":
            continue
        model_element = lookup.get(source_ref.get("id"))
        if model_element is not None:
            lookup[segment_id] = model_element
    return lookup

def parse_effo_table(
    model: TubaModel,
    work_dir: Path,
    results: FEAResults,
    node_label_map: dict[str, str],
    element_label_map: dict[str, str],
    instant: float | None = None,
) -> set[tuple[str, str]]:
    """Parse internal-force table (unit 38, ``EFGE_ELNO``).

    Each row contains ``MAILLE`` (element) and ``NOEUD`` (node).
    For a SEG2 element there are exactly two rows — one per end-node.
    We map them to ``forces_n1`` / ``forces_n2`` by matching the
    ``NOEUD`` field against the element's ``n1`` / ``n2``.

    Returns the model element/node endpoints that received parsed forces.
    """
    rows = parse_result_table(work_dir / "study_effo.csv", instant=instant)
    # Build a quick lookup: element_id → Element
    element_lookup = result_element_lookup(model, work_dir)
    covered: set[tuple[str, str]] = set()

    for row in rows:
        raw_eid = row.get("MAILLE", "").strip()
        raw_nid = row.get("NOEUD", "").strip()
        eid = element_label_map.get(raw_eid, raw_eid)
        nid = node_label_map.get(raw_nid, raw_nid)
            
        # The mesh subdivides members into sub-elements (pipe_bend_0_s0, _s1, …)
        # for FE accuracy. Fold them back to the single model bend element. Forces
        # attach only at the elbow's own end nodes (n1/n2) below — exactly the input
        # external end-node checks consume; interior sub-node moments feed FE
        # displacement fidelity, not the code check, so dropping them here is intended.
        elem = element_lookup.get(eid)
        if elem is None or nid not in (elem.n1, elem.n2):
            continue
        orig_eid = elem.id

        def finite_force_component(
            component: str,
            *aliases: str,
            allow_unavailable: bool = False,
        ) -> float:
            raw_value = ""
            for alias in aliases:
                candidate = row.get(alias)
                if candidate is not None and candidate.strip():
                    raw_value = candidate.strip()
                    break
            if allow_unavailable and raw_value == "-":
                return np.nan
            try:
                value = float(raw_value)
            except (ValueError, TypeError) as exc:
                raise RuntimeError(
                    f"Code_Aster row has invalid internal-force component "
                    f"{component}={raw_value!r} for element endpoint {orig_eid}:{nid}; "
                    "all force and moment components must be finite numeric values. "
                    "Refusing to mark the endpoint covered."
                ) from exc
            if not np.isfinite(value):
                raise RuntimeError(
                    f"Code_Aster row has invalid internal-force component "
                    f"{component}={raw_value!r} for element endpoint {orig_eid}:{nid}; "
                    "all force and moment components must be finite numeric values. "
                    "Refusing to mark the endpoint covered."
                )
            return value

        allow_unavailable = elem.type in ("bar", "cable")
        forces = np.array([
            finite_force_component("N", "N", "NXX"),
            finite_force_component("VY", "VY", allow_unavailable=allow_unavailable),
            finite_force_component("VZ", "VZ", allow_unavailable=allow_unavailable),
            finite_force_component("MT", "MT", allow_unavailable=allow_unavailable),
            finite_force_component("MFY", "MFY", allow_unavailable=allow_unavailable),
            finite_force_component("MFZ", "MFZ", allow_unavailable=allow_unavailable),
        ])
        er = results.element_results[orig_eid]
        if nid == elem.n1:
            er.forces_n1 = forces
            covered.add((orig_eid, nid))
        elif nid == elem.n2:
            er.forces_n2 = forces
            covered.add((orig_eid, nid))
    return covered

def parse_reac_table(
    model: TubaModel,
    work_dir: Path,
    results: FEAResults,
    node_label_map: dict[str, str],
    instant: float | None = None,
) -> None:
    """Parse reaction force table (unit 40, ``REAC_NODA``)."""
    # parse_result_table, not the raw CSV: a load-path solve writes every
    # increment to this table and only the requested instant is the result.
    rows = parse_result_table(work_dir / "study_reac.csv", instant=instant)
    # An attached support hands its load to the node it is attached to, so that node's reaction is kept too.
    support_nodes = {s.node for s in model.supports} | {s.attached_to for s in model.supports if s.attached_to is not None}
    # CABLE and BARRE elements carry three translational degrees of freedom
    # and no rotations, so Code_Aster prints "-" for DRX/DRY/DRZ at a node
    # attached only to them - the same "-" the element-force parser above
    # already accepts for those two types. A guy anchor is a pin: there is
    # no rotational restraint to react against, which is a reaction moment
    # of zero rather than a number the solver failed to produce.
    rotation_free_supports = set()
    for node in support_nodes:
        touching = [e for e in model.elements if node in (e.n1, e.n2)]
        if touching and all(e.type in ("bar", "cable") for e in touching):
            rotation_free_supports.add(node)

    for row in rows:
        raw_nid = row.get("NOEUD", "").strip()
        nid = node_label_map.get(raw_nid, raw_nid)
        if nid not in support_nodes or nid not in results.node_results:
            continue
        raw_values = [row.get(key, "").strip() for key in ("DX", "DY", "DZ", "DRX", "DRY", "DRZ")]
        if nid in rotation_free_supports:
            # Translations are never optional, so the guard below still
            # rejects a "-" anywhere in the first three components.
            raw_values[3:] = ["0.0" if value == "-" else value for value in raw_values[3:]]
        try:
            reaction = np.asarray(raw_values, dtype=float)
        except (ValueError, TypeError) as exc:
            raise RuntimeError(
                f"Code_Aster row has invalid reaction components for support node {nid!r}; "
                "all six force and moment components must be finite numeric values."
            ) from exc
        if not np.isfinite(reaction).all():
            raise RuntimeError(
                f"Code_Aster row has invalid reaction components for support node {nid!r}; "
                "all six force and moment components must be finite numeric values."
            )
        results.node_results[nid].reaction_force = reaction

def parse_sieq_table(
    model: TubaModel,
    work_dir: Path,
    results: FEAResults,
    node_label_map: dict[str, str],
    element_label_map: dict[str, str],
    instant: float | None = None,
) -> None:
    """Parse Von Mises stress table (unit 41, ``SIEQ_ELNO``)."""
    if not any(elem.type in {"pipe_straight", "pipe_bend"} for elem in model.elements):
        return
    rows = parse_result_table(work_dir / "study_sieq.csv", instant=instant)
    element_lookup = result_element_lookup(model, work_dir)
    analysis_tangents = read_analysis_element_tangents(work_dir)

    for row in rows:
        raw_eid = row.get("MAILLE", "").strip()
        raw_nid = row.get("NOEUD", "").strip()
        eid = element_label_map.get(raw_eid, raw_eid)
        nid = node_label_map.get(raw_nid, raw_nid)

        elem = element_lookup.get(eid)
        if elem is None:
            continue
        orig_eid = elem.id
        try:
            vmis = float(row.get("VMIS", ""))
        except (ValueError, TypeError) as exc:
            raise RuntimeError(
                f"Code_Aster row has invalid VMIS value for element {orig_eid!r}."
            ) from exc
        if not np.isfinite(vmis):
            raise RuntimeError(
                f"Code_Aster row has invalid VMIS value for element {orig_eid!r}."
            )

        subpoint = row.get("SOUS_POINT", "").strip()
        if subpoint:
            centerline_position: list[float] | None = None
            try:
                centerline_position = [
                    float(row["COOR_X"]),
                    float(row["COOR_Y"]),
                    float(row["COOR_Z"]),
                ]
            except (KeyError, ValueError, TypeError):
                centerline_position = None
            try:
                subpoint_index: int | str = int(float(subpoint))
            except (ValueError, TypeError):
                subpoint_index = subpoint
            tangent = analysis_tangents.get(eid)
            if tangent is None:
                tangent = model_element_tangent(model, elem)
            display_position = tuyau_subpoint_display_position(
                model=model,
                element=elem,
                centerline_position=centerline_position,
                tangent=tangent,
                subpoint_index=subpoint_index,
            )
            inner_radius_m: float | None = None
            outer_radius_m: float | None = None
            wall_section = model.sections.get(elem.section)
            if isinstance(wall_section, PipeSection):
                outer_radius_m = float(wall_section.OD) / 2.0
                inner_radius_m = outer_radius_m - float(wall_section.WT)
            results.tuyau_subpoints.append(
                {
                    "field": "SIEQ_ELNO",
                    "component": "VMIS",
                    "unit": "Pa",
                    "value": vmis,
                    "element_id": orig_eid,
                    "analysis_element_id": eid,
                    "solver_element_label": raw_eid,
                    "node_id": nid or None,
                    "solver_node_label": raw_nid or None,
                    "subpoint_index": subpoint_index,
                    "centerline_position": centerline_position,
                    "display_position": display_position,
                    "inner_radius_m": inner_radius_m,
                    "outer_radius_m": outer_radius_m,
                    "position_source": (
                        "code_aster_tuyau_subpoint_formula"
                        if display_position is not None
                        else "centerline_from_sieq_elno"
                    ),
                    "tuyau_ncou": _CODE_ASTER_TUYAU_NCOU,
                    "tuyau_nsec": _CODE_ASTER_TUYAU_NSEC,
                }
            )

        er = results.element_results[orig_eid]
        if nid == elem.n1:
            er.von_mises_n1 = vmis
        elif nid == elem.n2:
            er.von_mises_n2 = vmis
        er.max_von_mises = (
            vmis if not np.isfinite(er.max_von_mises)
            else max(er.max_von_mises, vmis)
        )

def read_analysis_element_tangents(work_dir: Path) -> dict[str, np.ndarray]:
    manifest_path = work_dir / "study_manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        mesh = manifest["analysis_mesh"]
        nodes = mesh["nodes"]
        elements = mesh["elements"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return {}

    tangents: dict[str, np.ndarray] = {}
    for element_id, node_ids in elements.items():
        if not isinstance(node_ids, list) or len(node_ids) < 2:
            continue
        try:
            start = np.asarray(nodes[node_ids[0]], dtype=float)
            end = np.asarray(nodes[node_ids[-1]], dtype=float)
        except (KeyError, TypeError, ValueError):
            continue
        tangent = end - start
        norm = float(np.linalg.norm(tangent))
        if norm > 1.0e-12:
            tangents[str(element_id)] = tangent / norm
    return tangents

def model_element_tangent(model: TubaModel, element: Element) -> np.ndarray | None:
    try:
        start = np.asarray(model.nodes[element.n1].coords, dtype=float)
        end = np.asarray(model.nodes[element.n2].coords, dtype=float)
    except (KeyError, AttributeError, TypeError, ValueError):
        return None
    tangent = end - start
    norm = float(np.linalg.norm(tangent))
    return tangent / norm if norm > 1.0e-12 else None

def tuyau_subpoint_display_position(
    *,
    model: TubaModel,
    element: Element,
    centerline_position: list[float] | None,
    tangent: np.ndarray | None,
    subpoint_index: int | str,
) -> list[float] | None:
    if centerline_position is None or tangent is None or not isinstance(subpoint_index, int):
        return None
    section = model.sections.get(element.section)
    if not isinstance(section, PipeSection):
        return None
    y_axis, z_axis = tuyau_cross_section_axes(tangent)
    y_offset, z_offset = code_aster_tuyau_fibre_offset(
        subpoint_index,
        r_ext=section.OD / 2.0,
        thickness=section.WT,
    )
    center = np.asarray(centerline_position, dtype=float)
    point = center + y_offset * y_axis + z_offset * z_axis
    return [float(value) for value in point]

def code_aster_tuyau_fibre_offset(
    subpoint_index: int,
    *,
    r_ext: float,
    thickness: float,
    ncou: int = _CODE_ASTER_TUYAU_NCOU,
    nsec: int = _CODE_ASTER_TUYAU_NSEC,
) -> tuple[float, float]:
    station = subpoint_station(subpoint_index, nsec=nsec, ncou=ncou)
    if station is None:
        return 0.0, 0.0
    r_int = r_ext - thickness
    radius = r_int + thickness * station.radius_fraction
    y_offset = radius * math.cos(station.angle_rad)
    z_offset = -radius * math.sin(station.angle_rad)
    return y_offset, z_offset

def tuyau_cross_section_axes(tangent: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x_axis = np.asarray(tangent, dtype=float)
    x_axis = x_axis / np.linalg.norm(x_axis)
    y_axis = _TUBA_GENE_TUYAU - float(np.dot(_TUBA_GENE_TUYAU, x_axis)) * x_axis
    if float(np.linalg.norm(y_axis)) <= 1.0e-12:
        fallback = np.array([0.0, 1.0, 0.0], dtype=float)
        y_axis = fallback - float(np.dot(fallback, x_axis)) * x_axis
    if float(np.linalg.norm(y_axis)) <= 1.0e-12:
        fallback = np.array([1.0, 0.0, 0.0], dtype=float)
        y_axis = fallback - float(np.dot(fallback, x_axis)) * x_axis
    y_axis = y_axis / np.linalg.norm(y_axis)
    z_axis = np.cross(x_axis, y_axis)
    z_axis = z_axis / np.linalg.norm(z_axis)
    return y_axis, z_axis
