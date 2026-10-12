"""Fluid fields on the existing web scene, distinct from Code_Aster fields."""

from __future__ import annotations

from tuba.visualization.scene import Overlay, SceneLayer
from tuba.visualization.builders._layers import build_result_fields


def attach_process_review(scene, payload):
    """Attach a projection read from a verified, sealed candidate attempt.

    The search exporter owns archive verification. No ResultState or structural
    output is manufactured here: fields retain their hydraulic solver basis.
    """
    basis = payload.get("basis")
    if payload.get("schema") != "tuba.process.review.v1" or basis not in ("openmodelica", "pandapipes"):
        raise ValueError("Expected a retained supported hydraulic process review")
    solver = "OpenModelica" if basis == "openmodelica" else "pandapipes"
    if payload.get("provenance", {}).get("solver", solver) != solver:
        raise ValueError("Process review basis does not match its solver provenance")
    objects = {obj.entity_ref.id: obj for obj in scene.objects
               if obj.entity_ref and obj.entity_ref.kind == "element" and obj.kind == "pipe"}
    segments = [segment for segment in payload["segments"] if segment["element_id"]]
    if len({segment["element_id"] for segment in segments}) != len(segments):
        raise ValueError("Process review contains duplicate structural element associations")
    if {segment["element_id"] for segment in segments} != set(objects):
        raise ValueError("Process review does not cover the scene's mechanical pipes")
    quantities = (
        ("fluid_velocity", f"{solver}: fluid velocity", "m/s", lambda row: row["velocity_m_s"]),
        ("fluid_pressure", f"{solver}: mean absolute pressure", "Pa",
         lambda row: (row["pressure_in_pa"] + row["pressure_out_pa"]) / 2),
        ("fluid_pressure_drop", f"{solver}: element pressure drop", "Pa",
         lambda row: row["pressure_in_pa"] - row["pressure_out_pa"]),
        ("fluid_temperature", f"{solver}: bulk fluid temperature", "K", lambda row: row["temperature_k"]),
    )
    overlays = []
    for key, label, unit, extract in quantities:
        values = {objects[row["element_id"]].id: extract(row) for row in segments}
        value_range = {"min": min(values.values()), "max": max(values.values())}
        overlays.append(Overlay(
            id=f"overlay:process:{key}", kind="solver_result", name=label,
            object_ids=list(values), data={
                "result_type": key, "field": key, "load_case": payload["operation"],
                "result_state_id": "", "support": "cell", "values": values,
                "unit": unit, "range": value_range, "basis": basis,
                "scenario_id": payload["scenario_id"],
                "compliance_role": "hydraulic_result_not_structural_acceptance",
                "legend": {"field": label, "unit": unit, "range": value_range,
                           "color_map": "cividis", "thresholds": {}},
            },
        ))
    for row in segments:
        objects[row["element_id"]].metadata["hydraulics"] = row | {
            "basis": solver, "pressure_reference": "absolute"}
    scene.overlays.extend(overlays)
    scene.result_fields.extend(build_result_fields(overlays))
    scene.layers.append(SceneLayer("solver_result:process", "results", f"{solver} fluid fields"))
    scene.extra["process"] = payload
    scene.validate()
