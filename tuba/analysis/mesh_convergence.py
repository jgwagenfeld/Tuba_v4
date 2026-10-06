"""Sequential, verified Code_Aster mesh comparisons, never an accuracy certificate.

Each level owns its persisted model and attested files. Reopening imports those
files with that model and recomputes measurements; saved values are not evidence.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from itertools import permutations, product
import json
import math
from numbers import Real
from pathlib import Path

from tuba.canonical import canonical_digest, platform_stable


def validate_convergence_settings(settings):
    if not isinstance(settings, dict) or set(settings) - {"scales", "relative_tolerance"}:
        raise ValueError("MESH_CONVERGENCE takes scales and relative_tolerance.")
    scales = settings.get("scales")
    if not isinstance(scales, (list, tuple)) or len(scales) < 2:
        raise ValueError("Mesh convergence needs at least two distinct positive finite scales.")
    if any(isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) or v <= 0 for v in scales):
        raise ValueError("Mesh convergence scales must be positive and finite (dimensionless).")
    if len(set(scales)) != len(scales):
        raise ValueError("Mesh convergence scales must be distinct.")
    tolerance = settings.get("relative_tolerance", .05)
    if isinstance(tolerance, bool) or not isinstance(tolerance, Real) or not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("relative_tolerance must be positive and finite.")
    return {"scales": [float(v) for v in scales], "relative_tolerance": float(tolerance)}


def compare_measurements(previous, current, relative_tolerance, *, near_zero=1e-12):
    if previous is None or current is None or not all(math.isfinite(v) for v in (previous, current)):
        return {"absolute_change": None, "relative_change": None, "within_tolerance": None,
                "reason": "Quantity unavailable in one or both levels."}
    absolute = abs(current-previous)
    if abs(previous) <= near_zero:
        return {"absolute_change": absolute, "relative_change": None, "within_tolerance": None,
                "reason": "Previous value is near zero; relative change is undefined."}
    relative = absolute/abs(previous)
    return {"absolute_change": absolute, "relative_change": relative,
            "within_tolerance": relative <= relative_tolerance, "reason": None}


def mesh_topology(nodes, cells):
    """Exact connectivity canonicalization, invariant to node/cell enumeration.

    Coordinates use the repository's nine-significant-digit provenance precision.
    Cell connectivity positions retain corner/midside roles. Coincident nodes
    remain separate: canonicalize their possible numberings, not a point cloud.
    Very large ambiguous coincident sets fail explicitly rather than guessing.
    """
    nodes = {str(k): tuple(platform_stable([float(x) for x in v])) for k,v in nodes.items()}
    cells = [(str(f), tuple(str(n) for n in ns)) for f,ns in cells]
    if not nodes or not cells or any(not all(math.isfinite(x) for x in xyz) for xyz in nodes.values()):
        raise ValueError("Actual mesh must have finite coordinates and nonempty cells.")
    incidences = defaultdict(list)
    for family, connectivity in cells:
        for role, node in enumerate(connectivity):
            if node not in nodes:
                raise ValueError("Actual mesh connectivity references a missing node.")
            incidences[node].append((family, role))
    groups = defaultdict(list)
    for node, xyz in nodes.items():
        groups[(xyz, tuple(sorted(incidences[node])))].append(node)
    ordered = [groups[key] for key in sorted(groups)]
    combinations = math.prod(math.factorial(len(group)) for group in ordered)
    if combinations > 100000:
        raise ValueError("Actual mesh has too many ambiguous coincident nodes for exact topology comparison.")
    best = None
    for numbering in product(*(permutations(group) for group in ordered)):
        flat = [n for group in numbering for n in group]
        index = {n:i for i,n in enumerate(flat)}
        canonical = (tuple(nodes[n] for n in flat), tuple(sorted((f, tuple(index[n] for n in ns)) for f,ns in cells)))
        if best is None or canonical < best:
            best = canonical
    return {"signature": canonical_digest(best), "coordinate_precision": "9 significant digits",
            "node_count": len(nodes), "cell_count": len(cells), "by_family": dict(sorted(Counter(f for f,_ in cells).items()))}


def actual_mesh(directory, attestation):
    """Read only the mesh selected by the independently verified solve inventory."""
    root = Path(directory)
    meshes = [name for name in ("study.med", "study.mail") if name in attestation["artifacts"]]
    if len(meshes) != 1:
        raise ValueError("Actual topology requires exactly one attested study.med or study.mail mesh.")
    if meshes[0] == "study.med":
        import meshio
        med = meshio.read(root / "study.med")
        families = {"line":"SEG2", "line3":"SEG3", "triangle":"TRI3", "triangle6":"TRI6",
                    "quad":"QUAD4", "quad8":"QUAD8", "tetra":"TETRA4", "tetra10":"TETRA10",
                    "hexahedron":"HEXA8", "hexahedron20":"HEXA20", "vertex":"POINT1"}
        return mesh_topology({str(i):xyz for i,xyz in enumerate(med.points)},
                             [(families.get(block.type, block.type), tuple(str(i) for i in cell)) for block in med.cells for cell in block.data])
    from tuba.visualization.preview.mesh import read_native_line_mail
    nodes, cells = read_native_line_mail(root / "study.mail")
    return mesh_topology(nodes, [(f"SEG{len(ns)}", ns) for ns in cells.values()])


def physics_identity(model, load_case, options, volume):
    from tuba.analysis.provenance import build_solver_input_identity, VOLUME_CODE_ASTER_COMPILER_ID
    clone = deepcopy(model)
    clone.mesh_settings = {}
    clone.mesh_refinements = {}
    for asset in clone.cad_assets.values():
        asset.metadata.pop("interface_mesh_sizes", None)
    runtime = {"work_dir", "exec_method", "docker_image", "wsl_distro", "runner_command", "bridge_python", "timeout_seconds", "execution_controller"}
    return canonical_digest({"physical_model": build_solver_input_identity(clone, load_case, compiler_id=VOLUME_CODE_ASTER_COMPILER_ID).to_dict(),
                             "formulation": {k:v for k,v in options.items() if k not in runtime},
                             "volume": {k:v for k,v in (volume or {}).items() if k != "max_element_size"}})


def measurements(run):
    import numpy as np
    results = run.results
    def metric(quantity, field, component, support, selection, unit, values, reason):
        values = list(values)
        valid = values and all(v is not None and math.isfinite(float(v)) for v in values)
        return {"quantity": quantity, "field": field, "component": component, "support": support,
                "selection": selection, "aggregation": "maximum", "unit": unit,
                "value": float(max(values)) if valid else None, "unavailable_reason": None if valid else reason}
    # FE-node translations avoid authored aliases/duplicated spatial supports.
    translations = [np.linalg.norm(n.displacement[:3]) for n in results.analysis_node_results.values()]
    out = [metric("displacement", "DEPL", "translation_norm", "analysis nodes", "all exported FE nodes", "m",
                  translations, "No complete finite FE-node translation field was exported.")]
    out.append(metric("von_mises", "SIEQ_ELNO", "VMIS", "TUYAU through-wall/circumferential subpoints",
                      "all exported TUYAU subpoints", "Pa", (r.get("value") for r in results.tuyau_subpoints),
                      "No TUYAU VMIS subpoint field; POU_D_T does not export pipe VMIS."))
    out.append(metric("von_mises", "SIEQ_ELNO", "VMIS", "adjacent-element averaged surface nodes",
                      "selected solid volume surface", "Pa", results.volume_von_mises.values(),
                      "No solid averaged surface-node VMIS field was exported."))
    shell = results.metadata.get("shell_von_mises", {})
    out.append(metric("von_mises", "SIEQ_ELNO", "VMIS", "shell through-thickness subpoint maxima",
                      "all exported shell stress nodes", "Pa", shell.values(), "No shell through-thickness VMIS field was exported."))
    return out


def _comparison(report):
    levels = report["levels"]
    successful = [v for v in levels if v["status"] == "succeeded"]
    distinct = len({v["mesh"]["signature"] for v in successful})
    report["distinct_successful_meshes"] = distinct
    report["status"] = "completed" if len(successful) == len(report["scales"]) and distinct >= 2 else "failed"
    if distinct < 2:
        report["error"] = "Comparison needs at least two distinct successful actual meshes."
    checks = []
    for previous, current in zip(levels, levels[1:]):
        changes = []
        if previous["status"] == current["status"] == "succeeded":
            for a,b in zip(previous["measurements"], current["measurements"]):
                descriptor = {k:v for k,v in a.items() if k not in {"value", "unavailable_reason"}}
                if descriptor != {k:v for k,v in b.items() if k not in {"value", "unavailable_reason"}}:
                    raise ValueError("Mesh levels contain incompatible measurement supports or quantities.")
                if previous["mesh"]["signature"] == current["mesh"]["signature"]:
                    change = {"absolute_change": None, "relative_change": None, "within_tolerance": None,
                              "reason": "Actual mesh unchanged; change requested scales or authored sizing to compare distinct discretizations."}
                else:
                    change = compare_measurements(a["value"], b["value"], report["relative_tolerance"])
                changes.append({**descriptor, **change})
                checks.append(change["within_tolerance"])
        current["changes_from_previous"] = changes
    available = [c for c in checks if c is not None]
    report["all_available_changes_within_tolerance"] = all(available) if available and report["status"] == "completed" else None
    report["accuracy_notice"] = "Measured changes are a mesh comparison, not an accuracy or compliance certificate. Unavailable/near-zero quantities and unchanged actual meshes have no tolerance verdict."
    return report


def run_mesh_convergence(model, load_case_name, *, scales, output_dir, solver_options=None,
                         volume_export=None, relative_tolerance=.05, execution_controller=None, progress=None):
    from tuba.solver.aster import CodeAsterSolver
    from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
    from tuba.visualization.preview.mesh import atomic_json
    settings = validate_convergence_settings({"scales": scales, "relative_tolerance": relative_tolerance})
    options = deepcopy(solver_options or {})
    if "line_segments" in options:
        raise ValueError("Mesh convergence cannot combine explicit line_segments with resolved sizing; remove line_segments and author mesh sizes.")
    if "work_dir" in options or "execution_controller" in options:
        raise ValueError("Convergence owns level work directories and its execution controller.")
    if volume_export and "pipe_modelization" in options:
        raise ValueError("VOLUME_EXPORT defines solid and remaining-line formulations; remove pipe_modelization from convergence solver options.")
    case, _ = model.resolve_load_case(load_case_name)
    source = deepcopy(model.to_dict())
    basis = physics_identity(model, case, options, volume_export)
    report = {"schema": "tuba.mesh-convergence.v1", **settings, "load_case": case,
              "source_identity": canonical_digest(source), "physics_identity": basis,
              "solver_options": options, "volume_export": deepcopy(volume_export), "status": "running", "levels": []}
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    atomic_json(root / "source_model.json", source)
    baseline_factor = model.mesh_settings.get("size_factor", 1.)
    def check():
        if execution_controller is not None:
            try:
                execution_controller.check_cancelled()
            except Exception:
                if execution_controller.cancelled:
                    report["status"] = "cancelled"
                    atomic_json(root / "comparison.json", report)
                raise
        if model.to_dict() != source:
            raise ValueError("Source model changed during convergence.")
    for index, scale in enumerate(settings["scales"]):
        check()
        directory = root / f"level-{index:02d}"
        directory.mkdir(exist_ok=True)
        level_model = deepcopy(model)
        level_model.set_mesh_size_factor(baseline_factor*scale)
        atomic_json(directory / "model.json", level_model.to_dict())
        level = {"index": index, "scale": scale, "directory": str(directory.resolve()), "status": "running"}
        report["levels"].append(level)
        atomic_json(root / "comparison.json", report)
        if progress:
            progress(deepcopy(report))
        try:
            solver = CodeAsterSolver(work_dir=directory, execution_controller=execution_controller, **options)
            if volume_export:
                solver.solve_volume_study(level_model, case, **deepcopy(volume_export))
            else:
                solver.solve(level_model, case)
            check()
            run = import_code_aster_artifacts(model=level_model, work_dir=directory)
            run.validate_for_publication(level_model)
            if run.study.load_case != case or physics_identity(level_model, case, options, volume_export) != basis:
                raise ValueError("Incompatible physical model or load case in convergence level.")
            level.update(status="succeeded", mesh=actual_mesh(directory, run.result_state.metadata["solve_attestation"]), measurements=measurements(run),
                         solver_input_identity=run.study.solver_input_identity.to_dict(),
                         attestation=run.result_state.metadata["solve_attestation"],
                         artifacts={name:str((directory / name).resolve()) for name in
                                    ("model.json", *run.result_state.metadata["solve_attestation"]["artifacts"])})
        except Exception as exc:
            if execution_controller is not None and execution_controller.cancelled:
                report["status"] = "cancelled"
                level.update(status="cancelled", error=str(exc))
                atomic_json(root / "comparison.json", report)
                raise
            level.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        atomic_json(root / "comparison.json", report)
        if progress:
            progress(deepcopy(report))
    check()
    _comparison(report)
    atomic_json(root / "comparison.json", report)
    return report


def reopen_mesh_convergence(model, directory):
    """Reverify each independent level; never reattest or trust saved measurements."""
    from tuba import Model
    from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
    root = Path(directory)
    saved = json.loads((root / "comparison.json").read_text(encoding="utf-8"))
    if saved.get("schema") != "tuba.mesh-convergence.v1" or saved.get("status") != "completed":
        raise ValueError("Convergence comparison is incomplete or failed.")
    if saved["source_identity"] != canonical_digest(model.to_dict()):
        raise ValueError("Source model or mesh policy changed; rerun convergence.")
    if json.loads((root / "source_model.json").read_text(encoding="utf-8")) != model.to_dict():
        raise ValueError("Persisted convergence source model does not match the current source.")
    settings = validate_convergence_settings({k:saved[k] for k in ("scales", "relative_tolerance")})
    if len(saved["levels"]) != len(settings["scales"]):
        raise ValueError("Convergence level inventory is incomplete.")
    basis = physics_identity(model, saved["load_case"], saved["solver_options"], saved["volume_export"])
    if basis != saved["physics_identity"]:
        raise ValueError("Convergence physical model or formulation changed.")
    for index, level in enumerate(saved["levels"]):
        if level.get("index") != index:
            raise ValueError("Convergence level order/index changed.")
        directory = root / f"level-{index:02d}"
        data = json.loads((directory / "model.json").read_text(encoding="utf-8"))
        expected = deepcopy(model.to_dict())
        expected.setdefault("mesh_settings", {})["size_factor"] = model.mesh_settings.get("size_factor", 1.)*settings["scales"][index]
        if data != expected or level["scale"] != settings["scales"][index] or level["status"] != "succeeded":
            raise ValueError("Convergence level model/policy does not match its source and scale.")
        level_model = Model.from_dict(data)
        run = import_code_aster_artifacts(model=level_model, work_dir=directory)
        run.validate_for_publication(level_model)
        if run.study.load_case != saved["load_case"] or run.study.solver_input_identity.to_dict() != level["solver_input_identity"]:
            raise ValueError("Convergence level solver identity or load case mismatch.")
        level.update(mesh=actual_mesh(directory, run.result_state.metadata["solve_attestation"]), measurements=measurements(run),
                     attestation=run.result_state.metadata["solve_attestation"], directory=str(directory.resolve()))
    return _comparison(saved)
