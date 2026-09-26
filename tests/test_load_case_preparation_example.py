"""The example's check inputs must preserve signed state differences."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from tuba.project import load_project

PROJECT = load_project(Path(__file__).resolve().parents[1] / "examples/load-case-preparation")


def test_four_states_and_signed_expansion_inputs():
    namespace = PROJECT.run_model()
    model = namespace["model"]
    study = PROJECT.load_study()
    assert tuple(model.operations) == study.LOAD_CASES
    assert model.standard == ""
    assert not model.materials["Steel"].allowable_stress
    cases = {case: model.resolve_load_case(case)[1] for case in study.LOAD_CASES}
    assert [(case.gravity, case.internal_pressure, case.temperature, case.ref_temperature)
            for case in cases.values()] == [
                (True, 1.5e6, 20, 20), (True, 1.5e6, 20, 20),
                (True, 1.5e6, 20, 20), (False, 1.5e6, 20, 20)]
    assert [len(case.nodal_forces) for case in cases.values()] == [0, 0, 1, 0]
    assert cases["Occasional"].nodal_forces[0].components == [0, 500, 0, 0, 0, 0]
    from tuba.solver.aster_loads import resolve_node_temperatures, resolve_operation_field_groups
    for case in cases.values():
        pressures = {element: value for elements, value in resolve_operation_field_groups(model, case, "pressure")
                     for element in elements}
        assert {pressures[e] for e in model.groups["ProcessLine"]["elements"]} == {1.5e6}
        assert {pressures[e] for e in model.groups["ReturnLine"]["elements"]} == {0.4e6}
    hot = cases["OperatingHot"]
    assert resolve_operation_field_groups(model, hot, "temperature") == [(model.groups["ProcessLine"]["elements"], 150.0)]
    temperatures = resolve_node_temperatures(model, hot)
    assert min(temperatures.values()) == 40.0
    assert max(temperatures.values()) == 80.0
    assert len(set(temperatures.values())) > 2
    from tuba.visualization.builders._loads import build_load_scene
    overlays = build_load_scene(model).overlays
    inputs = next(overlay.data for overlay in overlays if overlay.data["load_case"] == "OperatingHot")
    assert inputs["source_line"] > 0
    assert inputs["fields"][0]["affected_element_ids"] == model.groups["ProcessLine"]["elements"]
    assert inputs["fields"][0]["source_line"] > inputs["source_line"]
    assert inputs["fields"][-1]["group"] == "ReturnLine"
    assert inputs["fields"][-1]["affected_element_ids"] == model.groups["ReturnLine"]["elements"]
    assert all(field["affected_element_ids"] for field in inputs["fields"])
    # Deterministic unit-test vectors only; never written as solver evidence.
    vectors = ([10, -20, 30, -40, 50, -60], [-5, 4, -3, 2, -1, 0],
               [30, 40, 50, 60, 70, 80], [1, 2, 3, 4, 5, 6])
    runs = {case: SimpleNamespace(result_state=SimpleNamespace(
        id=f"test:{case}", load_case=case,
        element_results={element.id: {"forces_n1": vector, "forces_n2": [-v for v in vector]}
                         for element in model.elements}))
        for case, vector in zip(study.LOAD_CASES, vectors)}
    rows = study.force_rows(model, runs)
    assert len(rows) == len(model.elements) * 2 * 5
    for row in rows:
        if row["case"] == "ExpansionRange":
            sign = 1 if row["end"] == "n1" else -1
            np.testing.assert_array_equal([row[key] for key in study.COMPONENTS],
                                          sign * np.array([-15, 24, -33, 42, -51, 60]))
            assert row["reference_result_state_id"] == "test:Sustained"
    study.check(SimpleNamespace(model=model, runs=runs))
    runs["OperatingHot"].result_state.element_results[model.elements[0].id]["forces_n1"] = [np.nan] * 6
    with pytest.raises(ValueError, match="non-finite forces"):
        study.force_rows(model, runs)
