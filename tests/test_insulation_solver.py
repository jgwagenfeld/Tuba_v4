import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from tuba import Model
from tuba.analysis.provenance import build_solver_input_identity
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.aster_loads import resolve_wind_field_groups
from tuba.visualization import build_visualization_scene


def insulated_cantilever():
    model = Model(project_name="InsulationVerification")
    model.add_material("Steel", E=2e11, nu=0.3, rho=7850)
    model.add_pipe_section("DN100", OD=0.1, WT=0.01)
    a = model.add_node([0, 0, 0])
    b = model.add_node([2, 0, 0])
    model.add_element(id="pipe", type="pipe_straight", n1=a, n2=b, section="DN100", material="Steel")
    model.add_support(node=a, type="anchor", id="anchor")
    model.define_load_case("Weight", gravity=True)
    model.add_insulation_spec("wool", material="mineral wool", thickness_m=0.05, density_kg_m3=100)
    model.assign_insulation("element:pipe", "wool")
    return model, a, b


def test_insulation_reaches_solver_identity_wind_and_surface():
    model, _, _ = insulated_cantilever()
    fingerprint = build_solver_input_identity(model, "Weight").fingerprint
    with TemporaryDirectory() as root:
        CodeAsterSolver().export_study(model, "Weight", root)
        comm = (Path(root) / "study.comm").read_text()
    mass = math.pi * (0.1**2 - 0.05**2) * 100
    steel_area = math.pi * (0.05**2 - 0.04**2)
    assert f"RHO={7850 + mass / steel_area:.12E}" in comm
    assert "MATER=IM0" in comm
    assert "VALE=(5.00000000E-02, 1.00000000E-02)" in comm
    case = model.define_operation("Wind", gravity=False)
    case.add_field("wind", 1000, direction=[0, 1, 0])
    model.get_element("pipe").type = "beam"
    assert resolve_wind_field_groups(model, case)[0][2] == pytest.approx(200)
    model.operations.pop("Wind")
    model.get_element("pipe").type = "pipe_straight"
    scene = build_visualization_scene(model)
    envelopes = [a for a in scene.geometry_assets if a.format == "tube_envelope"]
    assert len(envelopes) == 1
    assert envelopes[0].generation_config["radius_m"] == pytest.approx(0.1)
    model.add_insulation_spec("wool", material="mineral wool", thickness_m=0.05, density_kg_m3=0)
    with TemporaryDirectory() as root, pytest.raises(ValueError, match="positive density"):
        CodeAsterSolver().export_study(model, "Weight", root)
    model.add_insulation_spec("wool", material="mineral wool", thickness_m=0.06, density_kg_m3=100)
    assert build_solver_input_identity(model, "Weight").fingerprint != fingerprint
    model.attributes.clear()
    assert not any(a.format == "tube_envelope" for a in build_visualization_scene(model).geometry_assets)
    with pytest.raises(ValueError, match="finite"):
        model.add_insulation_spec("bad", material="wool", thickness_m=float("nan"))


@pytest.mark.skipif(os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") != "1", reason="real Code_Aster required")
def test_insulated_pipe_gravity_matches_total_weight():
    model, fixed, _ = insulated_cantilever()
    root = Path(os.environ.get("TUBA_INSULATION_CHECK_DIR", ".build/insulation-check"))
    run = model.solve(load_case="Weight", work_dir=str(root), exec_method="wsl")
    expected = (7850 * math.pi * (0.05**2 - 0.04**2) + 100 * math.pi * (0.1**2 - 0.05**2)) * 2 * 9.81
    reaction = run.results.node_results[fixed].reaction_force
    assert reaction[2] == pytest.approx(expected, rel=1e-5)
    assert abs(reaction[4]) == pytest.approx(expected, rel=1e-5)

    model.get_element("pipe").type = "beam"
    model.define_operation("Wind", gravity=False).add_field("wind", 1000, direction=[0, 1, 0])
    wind = model.solve(load_case="Wind", work_dir=str(root / "wind"), exec_method="wsl")
    reaction = wind.results.node_results[fixed].reaction_force
    assert reaction[1] == pytest.approx(-400, rel=1e-5)
    assert abs(reaction[5]) == pytest.approx(400, rel=1e-5)
