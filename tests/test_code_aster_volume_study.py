import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tuba import Model
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.modelisation import PipeModelization


def _pressurized_pipe_model():
    model = Model("PressurizedVolume")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([0.2, 0.0, 0.0])
    model.add_element(
        id="pipe_0",
        type="pipe_straight",
        n1=n0,
        n2=n1,
        section="Pipe",
        material="Steel",
    )
    model.add_support(n0, type="anchor")
    model.define_load_case("Pressure", gravity=False, pressure=1.0e6)
    return model


def test_exports_grouped_pipe_volume_study_without_claiming_results(tmp_path):
    model = _pressurized_pipe_model()
    solver = CodeAsterSolver(work_dir=tmp_path)

    study = solver.export_volume_study(
        model,
        "Pressure",
        tmp_path,
        element_ids=["pipe_0"],
        max_element_size=0.005,
    )

    comm = Path(study.input_files["comm"]).read_text(encoding="utf-8")
    manifest = json.loads(Path(study.input_files["manifest"]).read_text(encoding="utf-8"))
    assert "LIRE_MAILLAGE(FORMAT='MED'" in comm
    assert "MODELISATION='3D'" in comm
    assert "GROUP_MA='G_SOLID_region_0'" in comm
    assert "PRES_REP=_F(" in comm
    assert "GROUP_MA='G_INNER_region_0'" in comm
    assert "RESU = MECA_STATIQUE(" in comm
    assert "RESU = CALC_CHAMP(" in comm
    assert "IMPR_RESU(" in comm
    assert study.metadata["pipe_modelization"] == PipeModelization.SOLID_3D.value
    assert study.metadata["result_status"] == "export_only"
    assert study.metadata["code_aster_solve_ready"] is False
    assert Path(study.input_files["med"]).is_file()
    assert manifest["analysis_mesh"]["surface_mesh"]["faces"]

    with patch.object(solver, "_execute") as execute:
        with pytest.raises(RuntimeError, match="export-only"):
            solver.solve_exported_study(model, study)
    execute.assert_not_called()


def test_pipe_modelization_keeps_tuyau_as_default():
    assert PipeModelization.TUYAU_3M.value == "TUYAU_3M"
    assert PipeModelization.SOLID_3D.value == "3D"
