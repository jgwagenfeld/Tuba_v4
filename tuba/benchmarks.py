"""Small benchmark-summary helpers for generated model workflows."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from tuba.model import TubaModel


def write_model_benchmark_summary(
    model: TubaModel,
    *,
    directory: str | Path = ".benchmarks",
) -> str:
    output_dir = Path(directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "project_name": model.project_name,
        "nodes": len(model.nodes),
        "elements": len(model.elements),
        "supports": len(model.supports),
        "groups": len(model.groups),
        "node_index_entries": len(getattr(model, "_node_point_index", {})),
        "element_index_entries": len(getattr(model, "_element_ids", set())),
        "timestamp": time.time(),
    }
    path = output_dir / f"model_benchmark_{model.project_name}.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


def run_deformed_clash_benchmark(
    *,
    size: str = "smoke",
    directory: str | Path = ".benchmarks",
) -> dict[str, Any]:
    from tuba.analysis import GeometryState, ResultState
    from tuba.clash.operating import candidate_obstacle_pairs_for_envelopes, check_operating_state
    from tuba.geometry.deformed import build_deformed_envelopes

    config = _deformed_clash_size_config(size)
    model, result_state, operating_state, cold_state = _build_deformed_clash_fixture(
        straight_count=config["straight_count"],
        bend_count=config["bend_count"],
        result_state_cls=ResultState,
        geometry_state_cls=GeometryState,
    )

    started = time.perf_counter()
    envelopes = build_deformed_envelopes(
        model=model,
        result_state=result_state,
        geometry_state=operating_state,
        envelope_type="clearance",
        clearance_m=0.02,
    )
    envelope_seconds = time.perf_counter() - started

    started = time.perf_counter()
    candidate_pairs = candidate_obstacle_pairs_for_envelopes(model=model, envelopes=envelopes)
    broadphase_seconds = time.perf_counter() - started

    started = time.perf_counter()
    clashes = check_operating_state(
        model,
        cold_state=cold_state,
        operating_state=operating_state,
        result_state=result_state,
        envelope_type="clearance",
        clearance_m=0.02,
    )
    clash_seconds = time.perf_counter() - started

    cached = build_deformed_envelopes(
        model=model,
        result_state=result_state,
        geometry_state=operating_state,
        envelope_type="clearance",
        clearance_m=0.02,
    )
    all_pairs = len(envelopes) * len(model.obstacles)
    candidate_ratio = (len(candidate_pairs) / all_pairs) if all_pairs else 0.0
    summary: dict[str, Any] = {
        "benchmark": "deformed-clash",
        "size": size,
        "elements": len(model.elements),
        "obstacles": len(model.obstacles),
        "envelopes": len(envelopes),
        "all_pairs": all_pairs,
        "candidate_pairs": len(candidate_pairs),
        "candidate_ratio": candidate_ratio,
        "clashes": len(clashes),
        "cache_reused": cached is envelopes,
        "timings_seconds": {
            "envelopes": envelope_seconds,
            "broadphase": broadphase_seconds,
            "operating_clash": clash_seconds,
        },
        "thresholds": {
            "candidate_ratio_max": config["candidate_ratio_max"],
        },
    }
    if all_pairs and len(candidate_pairs) >= all_pairs:
        raise RuntimeError("Deformed clash broadphase did not reduce candidate pairs.")
    if candidate_ratio > config["candidate_ratio_max"]:
        raise RuntimeError(
            f"Deformed clash candidate ratio {candidate_ratio:.3f} exceeds "
            f"{config['candidate_ratio_max']:.3f}."
        )
    if not summary["cache_reused"]:
        raise RuntimeError("Deformed envelope cache was not reused.")

    output_dir = Path(directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"deformed_clash_{size}.json"
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    summary["path"] = str(output_path)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tuba.benchmarks")
    subparsers = parser.add_subparsers(dest="command", required=True)
    deformed_clash = subparsers.add_parser("deformed-clash")
    deformed_clash.add_argument("--size", choices=("smoke", "small"), default="smoke")
    deformed_clash.add_argument("--directory", default=".benchmarks")
    args = parser.parse_args(argv)

    if args.command == "deformed-clash":
        summary = run_deformed_clash_benchmark(size=args.size, directory=args.directory)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    parser.error(f"Unknown benchmark command {args.command!r}.")
    return 2


def _deformed_clash_size_config(size: str) -> dict[str, Any]:
    if size == "smoke":
        return {"straight_count": 24, "bend_count": 6, "candidate_ratio_max": 0.20}
    if size == "small":
        return {"straight_count": 96, "bend_count": 24, "candidate_ratio_max": 0.12}
    raise ValueError(f"Unknown deformed clash benchmark size {size!r}.")


def _build_deformed_clash_fixture(
    *,
    straight_count: int,
    bend_count: int,
    result_state_cls: type,
    geometry_state_cls: type,
):
    model = TubaModel(project_name=f"DeformedClash_{straight_count}_{bend_count}")
    model.add_material("Steel", E=2.0e11, nu=0.3)
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    model.add_insulation_spec("thin", material="mineral_wool", thickness_m=0.02)
    model.add_insulation_spec("thick", material="calcium_silicate", thickness_m=0.05)
    node_displacements: dict[str, tuple[float, float, float, float, float, float]] = {}

    for idx in range(straight_count):
        y = float(idx * 4.0)
        n0 = model.add_node([0.0, y, 0.0])
        n1 = model.add_node([2.0, y, 0.0])
        element_id = f"straight_{idx}"
        model.add_element(id=element_id, type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.assign_insulation(f"element:{element_id}", "thin" if idx % 2 == 0 else "thick")
        model.add_obstacle(
            id=f"rack_straight_{idx}",
            type="cuboid",
            min_point=[0.9, y + 0.04, -0.15],
            max_point=[1.1, y + 0.16, 0.15],
        )
        node_displacements[n0] = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        node_displacements[n1] = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    bend_offset = straight_count * 4.0 + 4.0
    for idx in range(bend_count):
        y = bend_offset + idx * 4.0
        n0 = model.add_node([0.0, y, 0.0])
        n1 = model.add_node([1.0, y + 1.0, 0.0])
        element_id = f"bend_{idx}"
        model.add_element(
            id=element_id,
            type="pipe_bend",
            n1=n0,
            n2=n1,
            section="PipeSec",
            material="Steel",
            bend_radius=0.75,
            bend_angle=90.0,
        )
        model.assign_insulation(f"element:{element_id}", "thick" if idx % 2 == 0 else "thin")
        model.add_obstacle(
            id=f"rack_bend_{idx}",
            type="cuboid",
            min_point=[0.4, y + 0.45, -0.15],
            max_point=[0.7, y + 0.75, 0.15],
        )
        node_displacements[n0] = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        node_displacements[n1] = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    result_state = result_state_cls(
        id="benchmark_result_hot",
        study_id="benchmark_study_hot",
        model_revision=0,
        solver_name="Code_Aster",
        load_case="Hot",
        mesh_id=None,
        node_displacements=node_displacements,
        node_reactions={},
        element_results={},
    )
    operating_state = geometry_state_cls(
        id="geometry_state:benchmark_hot:physical",
        model_revision=0,
        state_type="operating",
        load_case="Hot",
        result_state_id=result_state.id,
    )
    cold_state = geometry_state_cls(id="geometry_state:benchmark_cold", model_revision=0, state_type="cold")
    return model, result_state, operating_state, cold_state


if __name__ == "__main__":
    raise SystemExit(main())
