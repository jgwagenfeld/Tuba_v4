"""The authored example declares a real mixed study and reproducible policy."""
from copy import deepcopy
from pathlib import Path
import runpy

import pytest

from tuba.meshing.policy import resolve_mesh_policy
from tuba.project import load_project
from tuba.project.study import study_settings

PROJECT = Path(__file__).resolve().parents[1] / "examples" / "mesh-refinement-review"


def test_authored_spool_geometry_policy_and_study():
    namespace = runpy.run_path(str(PROJECT / "model.py"))
    model = namespace["model"]
    assert len(model.elements) == 1
    extension = model.elements[0]
    assert model.nodes[extension.n1].coords == pytest.approx([.2, 0, 0])
    assert model.nodes[extension.n2].coords == pytest.approx([1.2, 0, 0])
    assert model.mesh_settings == {"global_size_m": .008}
    refinement = model.mesh_refinements["connection_detail"]
    assert refinement["target"] == "port:spool_outlet"
    assert refinement["size_m"] == .004
    assert refinement["influence_distance_m"] == .005
    assert refinement["transition_distance_m"] == .04
    assert {c.code_aster_option for c in model.couplings.values()} == {"3D_TUYAU"}
    assert model.load_cases["Bending"].gravity is False
    settings = study_settings(load_project(PROJECT).load_study())
    assert settings.operations == ("Bending",)
    assert settings.solver_options == {"pipe_modelization": "TUYAU_3M"}
    assert settings.mesh_convergence == {"scales": [1., .75], "relative_tolerance": .03}
    assert callable(settings.build_review)
    # Pure preview honestly leaves the finite CAD face pending until native meshing.
    assert any(s["status"] == "pending_cad_binding" for s in resolve_mesh_policy(model).preview()["samples"])
    fine = deepcopy(model)
    fine.set_mesh_size_factor(.75)
    assert fine.mesh_refinements == model.mesh_refinements
    assert fine.to_dict()["nodes"] == model.to_dict()["nodes"]
