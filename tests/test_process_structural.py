"""Portable mapping checks use declared fixtures, never claimed solver results.

The mapping-only fixture patches the hydraulic verification seam. Separate
checks require the production verifier and reject records without raw evidence;
backend tests qualify CSV/manifest verification and root runs both real solvers.
"""

import json
import math
from dataclasses import replace

import pytest

from tuba import Model
from tuba.physical import physical_properties_for_element
from tuba.process.modelica import HydraulicResults, HydraulicSegmentResult
from tuba.process.network import (
    Connection, FixedLossComponent, HydraulicRequirements, MassFlowSource,
    OperatingScenario, PipeComponent, PressureSink, ProcessNetwork,
)
from tuba.process.structural import WALL_TEMPERATURE_MODEL, apply_fluid_loads
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.aster_loads import resolve_operation_field_groups, resolve_node_temperatures


def _circuit(*, external_pressure=100_000, reference_k=298.15, bent=False, loss=False):
    model = Model(project_name="FluidLoadMappingFixture")
    model.add_material("Steel", E=2e11, nu=0.3, alpha=1.2e-5, rho=7850)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    with model.pipe("Pipe", "Steel", route="L1") as pipe:
        pipe.start([0, 0, 0], support="anchor")
        pipe.run(1)
        if bent:
            pipe.bend(radius=0.5, angle=90, plane="XY")
        pipe.run(1)
    components = [MassFlowSource("SRC", "SRC.out"),
                  PipeComponent("L1", "L1.in", "L1.out", "L1", 4.6e-5, 0.2, "declared fixture bend K")]
    connections = [Connection("SRC.out", "L1.in")]
    if loss:
        components.append(FixedLossComponent("V", "V.in", "V.out", 0.08, 5,
                                             "declared external fixture valve K", mechanical_domain="external"))
        connections.extend([Connection("L1.out", "V.in"), Connection("V.out", "SNK.in")])
    else:
        connections.append(Connection("L1.out", "SNK.in"))
    components.append(PressureSink("SNK", "SNK.in"))
    network = ProcessNetwork("water", tuple(components), tuple(connections))
    scenario = OperatingScenario("operating", 10, 313.15, 300_000, external_pressure, reference_k)
    requirements = HydraulicRequirements("limits", 3, 10, 600_000, 300_000)
    return model, network.bind(model, scenario, requirements)


def _fixture_results(bound):
    segments = tuple(HydraulicSegmentResult(
        segment.segment_id, segment.component_id, segment.element_id,
        500_000 - 20_000 * index, 480_000 - 20_000 * index,
        10, 313.15, 998.2, 0.001, 2,
    ) for index, segment in enumerate(bound.segments))
    return HydraulicResults(
        bound.scenario.id, bound.fingerprint, bound.geometry_fingerprint,
        segments, {}, 500_000, 300_000, 10, {},
        {"source": "declared mapping-only unit fixture; no solver evidence"}, "absent-fixture-manifest.json",
    )


@pytest.fixture
def mapping_fixture(monkeypatch):
    monkeypatch.setattr(HydraulicResults, "verify_for", lambda self, bound: None)
    return _fixture_results


def _apply(model, bound, results, **kwargs):
    return apply_fluid_loads(model, bound, results, operation_name="FluidOperating",
                             wall_temperature_model=WALL_TEMPERATURE_MODEL, **kwargs)


def test_absolute_pressure_reference_temperature_and_density_use_existing_fields(mapping_fixture):
    model, bound = _circuit()
    preserved = model.define_operation("Independent", pressure=1000)
    results = mapping_fixture(bound)
    mapping = _apply(model, bound, results)
    operation = mapping.operation
    assert mapping.model is model
    assert operation is model.operations["FluidOperating"]
    assert model.operations["Independent"] is preserved
    assert operation.gravity is True
    assert operation.internal_pressure == 0
    assert operation.ref_temperature == pytest.approx(25)
    assert operation.temperature == pytest.approx(25)
    assert not operation.nodal_forces
    case = operation.to_load_case()
    assert resolve_operation_field_groups(model, case, "pressure") == [(["pipe_str_0"], 390_000), (["pipe_str_1"], 370_000)]
    assert set(resolve_node_temperatures(model, case).values()) == {40}
    for element in model.elements:
        properties = physical_properties_for_element(model, element, operation=operation.name)
        assert properties.fluid_density_kg_m3 == pytest.approx(998.2)
        assert properties.fluid_mass_kg_per_m == pytest.approx(998.2 * math.pi / 4 * 0.08**2)
    assert operation.metadata["fluid_load_mapping"] is mapping.evidence
    assert mapping.evidence["structural_status"] == "loads mapped; Code_Aster evaluation required"
    assert "piecewise constant" in mapping.evidence["pressure_discretization"]
    json.dumps(mapping.evidence, allow_nan=False)
    model.validate()


def test_export_reaches_native_pressure_temperature_and_gravity_compiler(mapping_fixture, tmp_path):
    model, bound = _circuit(bent=True, loss=True)
    mapping = _apply(model, bound, mapping_fixture(bound))
    CodeAsterSolver(work_dir=str(tmp_path)).export_study(model, mapping.operation.name, str(tmp_path))
    comm = (tmp_path / "study.comm").read_text(encoding="utf-8")
    assert "FORCE_TUYAU=(" in comm
    assert "PRES=3.900000E+05" in comm
    assert "PRES=3.700000E+05" in comm
    assert "PRES=3.500000E+05" in comm
    assert "VALE_REF=2.500000E+01" in comm
    assert "VALE=4.000000E+01" in comm
    assert "PESANTEUR" in comm
    assert "FORCE_NODALE" not in comm
    assert len(mapping.evidence["elements"]) == 3
    assert mapping.evidence["external_loss_components"][0]["component_id"] == "V"
    assert mapping.evidence["external_loss_components"][0]["mechanical_domain"] == "external"


@pytest.mark.parametrize("external,expected", [(0, 490_000), (100_000, 390_000), (480_000, 10_000)])
def test_pressure_reference_is_explicit(mapping_fixture, external, expected):
    model, bound = _circuit(external_pressure=external)
    results = mapping_fixture(bound)
    # The mapping idealization accepts zero differential pressure at an endpoint.
    if external == 480_000:
        results = replace(results, segments=tuple(replace(segment, pressure_in_pa=500_000,
                                                         pressure_out_pa=480_000) for segment in results.segments))
    mapping = _apply(model, bound, results)
    assert mapping.evidence["elements"][0]["pressure_differential_mean_pa"] == expected


@pytest.mark.parametrize("change,message", [
    ({"pressure_in_pa": 90_000}, "Negative differential pressure"),
    ({"pressure_out_pa": -1}, "positive absolute pressures"),
    ({"mass_flow_kg_s": -10}, "reversed flow"),
    ({"mass_flow_kg_s": 0}, "Zero or reversed"),
    ({"density_kg_m3": 0}, "density must be positive"),
    ({"temperature_k": 0}, "temperature.*positive"),
    ({"temperature_k": float("nan")}, "nonfinite"),
])
def test_invalid_mapping_never_adds_an_operation(mapping_fixture, change, message):
    model, bound = _circuit()
    results = mapping_fixture(bound)
    results = replace(results, segments=(replace(results.segments[0], **change), *results.segments[1:]))
    before = model.to_dict()
    with pytest.raises(ValueError, match=message):
        _apply(model, bound, results)
    assert model.to_dict() == before


def test_missing_external_loss_result_is_not_silently_ignored(mapping_fixture):
    model, bound = _circuit(loss=True)
    results = mapping_fixture(bound)
    results = replace(results, segments=tuple(segment for segment in results.segments if segment.element_id is not None))
    with pytest.raises(ValueError, match="every bound pipe and external loss"):
        _apply(model, bound, results)
    assert not model.operations


@pytest.mark.parametrize("defect", ["missing", "duplicate", "wrong_element", "wrong_component"])
def test_segment_coverage_and_associations_are_complete(mapping_fixture, defect):
    model, bound = _circuit()
    results = mapping_fixture(bound)
    segments = results.segments
    if defect == "missing":
        segments = segments[:-1]
    elif defect == "duplicate":
        segments = (*segments, segments[0])
    elif defect == "wrong_element":
        segments = (replace(segments[0], element_id="unbound"), *segments[1:])
    else:
        segments = (replace(segments[0], component_id="unbound"), *segments[1:])
    with pytest.raises(ValueError, match="coverage|duplicate|association"):
        _apply(model, bound, replace(results, segments=segments))
    assert not model.operations


def test_shared_node_temperature_conflict_requires_a_thermal_model(mapping_fixture):
    model, bound = _circuit()
    results = mapping_fixture(bound)
    results = replace(results, segments=(results.segments[0], replace(results.segments[1], temperature_k=323.15)))
    with pytest.raises(ValueError, match="shared node"):
        _apply(model, bound, results)
    assert not model.operations


@pytest.mark.parametrize("kind", ["operation", "load_case"])
def test_operation_name_collision_preserves_existing_cases(mapping_fixture, kind):
    model, bound = _circuit()
    results = mapping_fixture(bound)
    if kind == "operation":
        model.define_operation("FluidOperating", pressure=123)
    else:
        model.define_load_case("FluidOperating", pressure=123)
    before = model.to_dict()
    with pytest.raises(ValueError, match="already exists"):
        _apply(model, bound, results)
    assert model.to_dict() == before


def test_wall_temperature_approximation_must_be_chosen_explicitly(mapping_fixture):
    model, bound = _circuit()
    with pytest.raises(ValueError, match="wall_temperature_model must explicitly"):
        apply_fluid_loads(model, bound, mapping_fixture(bound), operation_name="FluidOperating",
                         wall_temperature_model="implicit-fluid-temperature")
    assert not model.operations


def test_raw_hydraulic_evidence_is_required():
    model, bound = _circuit()
    with pytest.raises(ValueError, match="solve-issued evidence"):
        _apply(model, bound, _fixture_results(bound))
    assert not model.operations


def test_geometry_changed_since_flow_binding_is_rejected(mapping_fixture):
    model, bound = _circuit()
    results = mapping_fixture(bound)
    model.nodes[model.elements[-1].n2].coords[0] += 0.1
    before = model.to_dict()
    with pytest.raises(ValueError, match="stale|changed|fingerprint|length"):
        _apply(model, bound, results)
    assert model.to_dict() == before


def test_verification_rejection_prevents_all_mutation(monkeypatch):
    model, bound = _circuit()
    def reject(self, candidate):
        assert candidate is bound
        raise ValueError("stale hydraulic scenario signature / modified raw artifact")
    monkeypatch.setattr(HydraulicResults, "verify_for", reject)
    before = model.to_dict()
    with pytest.raises(ValueError, match="stale hydraulic scenario"):
        _apply(model, bound, _fixture_results(bound))
    assert model.to_dict() == before


def test_adapter_execution_fixture_maps_with_verified_raw_artifacts(tmp_path, monkeypatch):
    from tests.test_process_modelica import install_execution_fixture
    model, bound = _circuit(loss=True)
    backend, _ = install_execution_fixture(tmp_path, monkeypatch, bound)
    results = backend.solve(bound, tmp_path / "hydraulic-fixture")
    mapping = _apply(model, bound, results)
    assert mapping.evidence["hydraulic_evidence"]["artifacts"]["csv"]["sha256"]
    assert len(mapping.evidence["elements"]) == 2
    assert mapping.evidence["elements"][0]["pressure_differential_mean_pa"] == 225_000


@pytest.mark.parametrize("defect", ["artifact", "record", "scenario"])
def test_stale_or_modified_execution_fixture_is_rejected(tmp_path, monkeypatch, defect):
    from pathlib import Path
    from tests.test_process_modelica import install_execution_fixture
    model, bound = _circuit()
    backend, _ = install_execution_fixture(tmp_path, monkeypatch, bound)
    results = backend.solve(bound, tmp_path / "hydraulic-fixture")
    if defect == "artifact":
        Path(results.artifacts["csv"]["path"]).write_text("changed raw CSV", encoding="utf-8")
    elif defect == "record":
        results = replace(results, segments=(replace(results.segments[0], pressure_in_pa=500_000), *results.segments[1:]))
    else:
        bound = bound.network.bind(model, replace(bound.scenario, external_pressure_pa=0), bound.requirements)
    before = model.to_dict()
    with pytest.raises(ValueError, match="stale|modified|solve-issued"):
        _apply(model, bound, results)
    assert model.to_dict() == before


@pytest.mark.parametrize("defect", ["missing", "duplicate"])
def test_mapper_requires_every_structural_pipe_exactly_once(mapping_fixture, monkeypatch, defect):
    model, bound = _circuit()
    # Isolate the mapper's domain guard from the binding verifier's own checks.
    monkeypatch.setattr(type(bound), "verify_for", lambda self, model: None)
    if defect == "missing":
        bound = replace(bound, segments=bound.segments[:-1])
    else:
        repeated = replace(bound.segments[0], segment_id=bound.segments[0].segment_id + ".duplicate")
        bound = replace(bound, segments=(*bound.segments, repeated))
    before = model.to_dict()
    with pytest.raises(ValueError, match="coverage is incomplete|duplicate element"):
        _apply(model, bound, mapping_fixture(bound))
    assert model.to_dict() == before
