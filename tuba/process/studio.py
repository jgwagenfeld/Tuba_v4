"""Studio projections and a copied structural snapshot from verified hydraulics."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict

from .network import BoundProcessNetwork
from .structural import WALL_TEMPERATURE_MODEL, apply_fluid_loads
from .workflow import hydraulic_checks


def process_bound(namespace):
    """An optional authored declaration must be bound to this exact geometry."""
    bound = namespace.get("process")
    if bound is not None:
        if not isinstance(bound, BoundProcessNetwork):
            raise ValueError("model.py process must be a BoundProcessNetwork.")
        bound.verify_for(namespace["model"])
    return bound


def process_projection(bound, hydraulic):
    """Keep native verified measurements and every declared hydraulic check."""
    checks = hydraulic_checks(bound, hydraulic)
    status = "passed" if all(check.verdict == "pass" for check in checks) else "rejected"
    return {
        "schema": "tuba.process.review.v1", "status": status,
        "basis": hydraulic.provenance["solver"].lower(), "operation": bound.scenario.id,
        "scenario_id": bound.scenario.id, "bound_fingerprint": bound.fingerprint,
        "geometry_fingerprint": bound.geometry_fingerprint,
        "segments": [asdict(segment) for segment in hydraulic.segments],
        "checks": [check.to_dict() for check in checks], "pressure_reference": "absolute",
        "limitations": list(hydraulic.limitations), "provenance": hydraulic.provenance,
    }


def validate_process_study(bound, study):
    """Validate the explicit structural transfer contract before mapping."""
    from tuba.project.study import study_settings

    if study_settings(study).operations != (bound.scenario.id,):
        raise ValueError("Process coupling requires one LOAD_CASES operation matching process.scenario.id.")
    wall = getattr(study, "WALL_TEMPERATURE_MODEL", None)
    if wall != WALL_TEMPERATURE_MODEL:
        raise ValueError(f"study.py WALL_TEMPERATURE_MODEL must explicitly be {WALL_TEMPERATURE_MODEL!r}.")
    return wall


def mapped_namespace(namespace, bound, hydraulic, study):
    """Leave authored globals intact when transferring verified operating loads."""
    wall = validate_process_study(bound, study)
    mapping = apply_fluid_loads(deepcopy(namespace["model"]), bound, hydraulic,
                               operation_name=bound.scenario.id, wall_temperature_model=wall)
    return namespace | {"model": mapping.model}
