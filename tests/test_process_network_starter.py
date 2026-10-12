"""Portable contract checks; synthetic CSV fixtures are not solver evidence."""

import csv
import math
from dataclasses import replace

import pytest

from examples.process_network_starter import (
    OUTPUTS, StarterDesign, build_model, network_snapshot, read_results, run_example,
)


def snapshot(design=StarterDesign()):
    return network_snapshot(build_model(design), design)


def test_route_edit_preserves_process_connections_and_nozzles_but_changes_evidence():
    before = snapshot()
    after = snapshot(StarterDesign(offset_m=3.0))
    assert before["connections"] == after["connections"]
    assert before["components"] == after["components"]
    assert before["route"]["end_m"] == pytest.approx(after["route"]["end_m"])
    assert before["route"]["start_m"] == after["route"]["start_m"]
    assert after["route"]["length_m"] - before["route"]["length_m"] == pytest.approx(4)
    assert before["route"]["length_m"] == pytest.approx(8 + 2 * math.pi * 0.3)
    assert before["candidate_sha256"] != after["candidate_sha256"]
    assert snapshot()["candidate_sha256"] == before["candidate_sha256"]


def test_bore_is_taken_from_built_section_and_changes_candidate_identity():
    before = snapshot()
    after = snapshot(StarterDesign(outside_diameter_m=0.0603, wall_thickness_m=0.00391))
    assert after["route"]["bore_m"] == pytest.approx(0.05248)
    assert before["connections"] == after["connections"]
    assert before["candidate_sha256"] != after["candidate_sha256"]


@pytest.mark.parametrize("changes", [
    {"offset_m": float("nan")}, {"mass_flow_kg_s": 0}, {"outside_diameter_m": 0.001},
    {"wall_thickness_m": True}, {"max_source_pressure_pa": 100_000},
])
def test_invalid_design_is_rejected(changes):
    with pytest.raises(ValueError):
        replace(StarterDesign(), **changes)


def test_unknown_route_cannot_be_silently_dropped():
    design = StarterDesign()
    model = build_model(design)
    model.elements[-1].route_id = "L-102"
    with pytest.raises(ValueError, match="exactly one route"):
        network_snapshot(model, design)


def test_unavailable_compiler_creates_no_results(tmp_path):
    output = tmp_path / "results"
    with pytest.raises(RuntimeError, match="unavailable"):
        run_example(StarterDesign(), output, tmp_path / "missing-omc")
    assert not output.exists()


def test_existing_run_is_never_reused_as_fresh_evidence(tmp_path):
    executable = tmp_path / "omc"
    executable.touch()
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(FileExistsError):
        run_example(StarterDesign(), output, executable)


@pytest.mark.parametrize("mutation", [
    {"time": 0}, {"massFlow": 0}, {"sinkMassFlow": 9}, {"velocity": float("nan")},
    {"velocity": 0}, {"sinkPressure": 200_000}, {"pressureDrop": 1},
])
def test_invalid_solver_output_cannot_be_accepted(tmp_path, mutation):
    network = snapshot()
    row = {"time": 1, "massFlow": 10, "sinkMassFlow": 10, "inletPressure": 350_000,
           "sinkPressure": 300_000, "pressureDrop": 50_000, "fluidDensity": 1000,
           "dynamicViscosity": 0.001,
           "velocity": 10 / (1000 * math.pi * network["route"]["bore_m"] ** 2 / 4)}
    row.update(mutation)
    artifact = tmp_path / "synthetic_test_fixture.csv"
    with artifact.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["time", *OUTPUTS])
        writer.writeheader()
        writer.writerow(row)
    with pytest.raises(ValueError):
        read_results(artifact, network)
