"""Qualify the authored shipped-spool study using authentic Code_Aster artifacts.

Run with --output outside source. --comparison reuses a completed Studio job,
reverifies its attestation, and avoids repeating the two solves. One additional
unsolved mesh without the local refinement measures actual density increase.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import runpy
import shutil
import subprocess

import gmsh
import numpy as np

from tuba import Model
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.analysis.mesh_convergence import reopen_mesh_convergence, run_mesh_convergence
from tuba.geometry.step_analysis_importer import StepAnalysisImporter
from tuba.meshing._gmsh import gmsh_model
from tuba.meshing.policy import gmsh_policy, resolve_mesh_policy
from tuba.project import load_project
from tuba.project.study import study_settings

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "examples" / "mesh-refinement-review"


def edge_statistics(mesh, x_min, x_max):
    """Unique primary tetrahedron edges wholly inside a physical wall band."""
    edges = set()
    for cell_id in mesh.groups["G_spool_SOLID"]:
        nodes = mesh.elements[cell_id][:4]
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                if all(x_min - 1e-9 <= mesh.nodes[n][0] <= x_max + 1e-9 for n in (a, b)):
                    edges.add(tuple(sorted((a, b))))
    lengths = np.asarray([np.linalg.norm(np.asarray(mesh.nodes[a]) - mesh.nodes[b]) for a, b in edges])
    if not len(lengths):
        raise ValueError(f"No primary edges in wall band {x_min}..{x_max} m")
    return {"edge_count": len(lengths), "minimum_m": float(lengths.min()),
            "p10_m": float(np.quantile(lengths, .1)), "median_m": float(np.median(lengths)),
            "p90_m": float(np.quantile(lengths, .9)), "maximum_m": float(lengths.max())}


def density(mesh):
    return {"port_tri6_count": len(mesh.groups["G_spool_outlet"]),
            "near_wall_x_m": [.18, .20], "far_wall_x_m": [.00, .10],
            "near": edge_statistics(mesh, .18, .20), "far": edge_statistics(mesh, .00, .10),
            "groups": {name: len(ids) for name, ids in sorted(mesh.groups.items())},
            "mesh_review": mesh.mesh_review}


def policy_samples(model):
    asset = model.cad_assets[model.imported_components["spool"].asset.id]
    selector = model.ports["spool_outlet"].metadata["face_selector"]
    with gmsh_model(gmsh, "qualification_policy", options={"Geometry.OCCTargetUnit": "MM"}):
        imported = gmsh.model.occ.importShapes(str(asset.source_path))
        gmsh.model.occ.synchronize()
        face = StepAnalysisImporter.resolve_face_selector(imported, selector)
        with gmsh_policy(gmsh, resolve_mesh_policy(model), {}, face_bindings={"connection_detail": face}) as policy:
            return [{"point_m": [x, .045, 0], "requested_size_m": policy.size_at((x, .045, 0), source_ref="component:spool")}
                    for x in (.20, .195, .175, .155)]


def independent_checks(run, model, namespace):
    outer = namespace["OUTER_DIAMETER"] / 2
    inner = outer - namespace["WALL_THICKNESS"]
    length = namespace["SPOOL_LENGTH"] + namespace["PIPE_LENGTH"]
    force_y, young = namespace["TIP_FORCE_Y"], namespace["YOUNGS_MODULUS"]
    inertia = math.pi * (outer**4 - inner**4) / 4
    expected_uy = force_y * length**3 / (3 * young * inertia)
    extension = model.elements[0]
    observed_uy = float(run.result_state.node_displacements[extension.n2][1])
    force, moment = np.zeros(3), np.zeros(3)
    # Authored model-node aliases duplicate analysis nodes; physical mesh only.
    for node_id, point in run.analysis_mesh.nodes.items():
        reaction = run.result_state.node_reactions.get(node_id)
        if reaction is None:
            continue
        nodal_force = np.asarray(reaction[:3], dtype=float)
        nodal_moment = np.asarray([0. if v is None else v for v in reaction[3:]])
        force += nodal_force
        moment += np.cross(point, nodal_force) + nodal_moment
    expected_force = np.asarray([0, -force_y, 0])
    expected_moment = -np.cross([length, 0, 0], [0, force_y, 0])
    blocks, values = [], []
    for node_id, point in run.analysis_mesh.nodes.items():
        if abs(point[0] - namespace["SPOOL_LENGTH"]) > 1e-8:
            continue
        x, y, z = np.asarray(point) - [namespace["SPOOL_LENGTH"], 0, 0]
        blocks.append([[1, 0, 0, 0, z, -y, 0], [0, 1, 0, -z, 0, x, y], [0, 0, 1, y, -x, 0, z]])
        values.extend(run.result_state.node_displacements[node_id][:3])
    assert len(blocks) > 6, "Section fit needs more than six physical face samples"
    fit = np.linalg.lstsq(np.vstack(blocks), np.asarray(values), rcond=None)[0]
    pipe = np.asarray(run.result_state.node_displacements[extension.n1], dtype=float)
    continuity = []
    for a, b, name in ((0, 3, "translation_m"), (3, 6, "rotation_rad")):
        error = float(np.linalg.norm(fit[a:b] - pipe[a:b]))
        limit = .05 * max(float(np.linalg.norm(pipe[a:b])), 1e-9) + 1e-10
        continuity.append({"quantity": name, "fitted": fit[a:b].tolist(), "pipe": pipe[a:b].tolist(), "norm_error": error, "limit": limit})
        assert error < limit, continuity[-1]
    error_uy = abs(observed_uy - expected_uy) / abs(expected_uy)
    force_error = float(np.linalg.norm(force - expected_force) / np.linalg.norm(expected_force))
    moment_error = float(np.linalg.norm(moment - expected_moment) / np.linalg.norm(expected_moment))
    assert error_uy <= .05, (observed_uy, expected_uy, error_uy)
    assert force_error <= .01 and moment_error <= .01, (force_error, moment_error)
    return {"formula": "I=pi*(ro^4-ri^4)/4; uy=Fy*L^3/(3*E*I); reaction=-F; moment=-cross([L,0,0],F)",
            "inertia_m4": inertia, "expected_tip_uy_m": expected_uy, "actual_tip_uy_m": observed_uy,
            "tip_relative_error": error_uy, "tip_relative_tolerance": .05,
            "actual_reaction_N": force.tolist(), "expected_reaction_N": expected_force.tolist(), "reaction_norm_relative_error": force_error,
            "actual_moment_Nm": moment.tolist(), "expected_moment_Nm": expected_moment.tolist(), "moment_norm_relative_error": moment_error,
            "reaction_relative_tolerance": .01, "section_sample_count": len(blocks), "section_fit": continuity,
            "radial_expansion_fit": float(fit[6])}


def effective_study_inputs(settings):
    """The current authored inputs that a retained comparison must match."""
    if settings.mesh_convergence is None or len(settings.operations) != 1:
        raise ValueError("Qualification requires current study.py MESH_CONVERGENCE and exactly one LOAD_CASES operation.")
    # Persisted JSON uses arrays for tuples, including volume element selections.
    return json.loads(json.dumps({"load_case": settings.operations[0],
                                 "solver_options": settings.solver_options,
                                 "volume_export": settings.volume_export,
                                 **settings.mesh_convergence}, allow_nan=False))


def validate_comparison_study(settings, comparison):
    """Reject changed study inputs before reopening any retained solver artifacts."""
    expected = effective_study_inputs(settings)
    saved = json.loads((comparison / "comparison.json").read_text(encoding="utf-8"))
    mismatches = [name for name, value in expected.items() if name not in saved or saved[name] != value]
    if mismatches:
        differences = "; ".join(f"{name}: saved={saved.get(name)!r}, current={expected[name]!r}" for name in mismatches)
        raise ValueError(f"Stale study: {comparison} differs from current study.py ({differences}); "
                         "rerun mesh convergence with the current study before using --comparison.")
    return expected


def source_provenance(root=ROOT):
    """Record HEAD and the current bytes of changed source files."""
    # Bare commands can fail on Windows after Gmsh finalizes; resolve Git first.
    git = shutil.which("git") or "git"
    changed = subprocess.check_output([git, "diff", "--name-only", "-z", "HEAD", "--"], cwd=root, text=True).split("\0")
    changed += subprocess.check_output([git, "ls-files", "--others", "--exclude-standard", "-z"], cwd=root, text=True).split("\0")
    return {"source_head": subprocess.check_output([git, "rev-parse", "HEAD"], cwd=root, text=True).strip(),
            "changed_source_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                      for name in sorted(set(changed)) if name and (root / name).is_file()}}


def qualify(output, comparison=None):
    output.mkdir(parents=True, exist_ok=True)
    namespace = runpy.run_path(str(PROJECT / "model.py"))
    model = namespace["model"]
    settings = study_settings(load_project(PROJECT).load_study())
    effective_study_inputs(settings)
    comparison = comparison or output / "comparison"
    if not (comparison / "comparison.json").exists():
        report = run_mesh_convergence(model, settings.operations[0], output_dir=comparison,
            solver_options=settings.solver_options, volume_export=settings.volume_export, **settings.mesh_convergence)
        assert report["status"] == "completed", report
    validate_comparison_study(settings, comparison)
    report = reopen_mesh_convergence(model, comparison)
    evidence = {**source_provenance(ROOT),
                "comparison_directory": str(comparison.resolve()), "comparison": report, "levels": []}
    for index, level in enumerate(report["levels"]):
        root = comparison / f"level-{index:02d}"
        level_model = Model.from_json(root / "model.json")
        run = import_code_aster_artifacts(model=level_model, work_dir=root)
        run.validate_for_publication(level_model)
        checks = independent_checks(run, level_model, namespace)
        actual_density = density(run.analysis_mesh)
        samples = policy_samples(level_model)
        expected = np.asarray([.004, .004, .006, .008]) * level["scale"]
        assert np.allclose([s["requested_size_m"] for s in samples], expected, rtol=1e-8, atol=1e-12)
        assert run.result_state.metadata["result_trust"] == "verified"
        assert run.analysis_mesh.mesh_review["quality"]["invalid_count"] == 0
        assert {c.code_aster_option for c in level_model.couplings.values()} == {"3D_TUYAU"}
        assert all(len(run.analysis_mesh.elements[c]) == 10 for c in run.analysis_mesh.groups["G_spool_SOLID"])
        assert all(len(run.analysis_mesh.elements[c]) == 6 for c in run.analysis_mesh.groups["G_spool_outlet"])
        evidence["levels"].append({"scale": level["scale"], "independent_checks": checks, "density": actual_density,
            "requested_samples": samples, "trust": run.result_state.metadata["result_trust"], "mesh": level["mesh"],
            "solver_input_identity": level["solver_input_identity"], "attestation": level["attestation"]})
    tips = [v["independent_checks"]["actual_tip_uy_m"] for v in evidence["levels"]]
    evidence["successive_tip_uy_relative_change"] = abs(tips[1] - tips[0]) / abs(tips[0])
    assert evidence["successive_tip_uy_relative_change"] <= .03, tips
    baseline = deepcopy(model)
    baseline.remove_mesh_refinement("connection_detail")
    baseline_mesh = baseline.mesh(output / "no-local-refinement.med")
    baseline_density = density(baseline_mesh)
    evidence["unsolved_no_local_density_baseline"] = baseline_density
    refined = evidence["levels"][0]["density"]
    assert refined["port_tri6_count"] > baseline_density["port_tri6_count"]
    assert refined["near"]["median_m"] < baseline_density["near"]["median_m"]
    assert refined["near"]["median_m"] < refined["far"]["median_m"]
    assert set(refined["groups"]) == set(baseline_density["groups"]) == set(evidence["levels"][1]["density"]["groups"])
    evidence["passed"] = True
    evidence["accuracy_scope"] = "Cantilever stiffness/equilibrium/section continuity and authored-tip mesh change only. Peak stress is a support-specific measured comparison, not qualified accuracy."
    (output / "qualification.json").write_text(json.dumps(evidence, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"passed": True, "levels": [{"scale": v["scale"], "checks": v["independent_checks"],
          "port_tri6_count": v["density"]["port_tri6_count"], "mesh": v["mesh"]} for v in evidence["levels"]],
          "successive_tip_uy_relative_change": evidence["successive_tip_uy_relative_change"]}, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, help="Reuse and independently reverify a completed native Studio job")
    args = parser.parse_args()
    qualify(args.output.resolve(), args.comparison.resolve() if args.comparison else None)
