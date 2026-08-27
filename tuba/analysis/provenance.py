"""Code_Aster solver-input identity for persistent analysis records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


MODEL_SCHEMA_ID = "tuba.model.v4"
CODE_ASTER_COMPILER_ID = "tuba.code_aster.v1"
MIXED_CODE_ASTER_COMPILER_ID = "tuba.code_aster.mixed.v1"
VOLUME_CODE_ASTER_COMPILER_ID = "tuba.code_aster.volume.v1"

_SOLVER_MODEL_KEYS = (
    "materials",
    "sections",
    "nodes",
    "elements",
    "supports",
    "groups",
    "cad_assets",
    "imported_components",
    "analysis_regions",
    "ports",
    "couplings",
)


@dataclass(frozen=True)
class SolverInputIdentity:
    fingerprint: str
    load_case: str
    schema_id: str
    compiler_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "fingerprint": self.fingerprint,
            "load_case": self.load_case,
            "schema_id": self.schema_id,
            "compiler_id": self.compiler_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SolverInputIdentity":
        return cls(
            fingerprint=str(data["fingerprint"]),
            load_case=str(data["load_case"]),
            schema_id=str(data["schema_id"]),
            compiler_id=str(data["compiler_id"]),
        )


def build_solver_input_identity(
    model: Any,
    load_case: str | None,
    *,
    compiler_id: str = CODE_ASTER_COMPILER_ID,
    compiler_inputs: dict[str, Any] | None = None,
) -> SolverInputIdentity:
    """Fingerprint the exact model inputs interpreted by a Code_Aster compiler."""
    resolved_name, resolved_case = model.resolve_load_case(load_case)
    model_data = model.to_dict()
    model_keys = _SOLVER_MODEL_KEYS + (("tees",) if compiler_id == VOLUME_CODE_ASTER_COMPILER_ID else ())
    payload = {
        "schema_id": MODEL_SCHEMA_ID,
        "compiler_id": compiler_id,
        "model": {key: model_data.get(key) for key in model_keys},
        "resolved_case": {
            "name": resolved_name,
            "gravity": bool(resolved_case.gravity),
            "internal_pressure": float(resolved_case.internal_pressure),
            "temperature": float(resolved_case.temperature),
            "ref_temperature": float(resolved_case.ref_temperature),
            "fields": [_operation_field_payload(field) for field in resolved_case.fields],
            "nodal_forces": [force.to_dict() for force in resolved_case.nodal_forces],
        },
    }
    if compiler_inputs is not None:
        payload["compiler_inputs"] = dict(compiler_inputs)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return SolverInputIdentity(
        fingerprint=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        load_case=resolved_name,
        schema_id=MODEL_SCHEMA_ID,
        compiler_id=compiler_id,
    )


def validate_solver_input_identity(
    model: Any,
    identity: SolverInputIdentity | None,
    *,
    context: str,
    expected_load_case: str,
    expected_compiler_id: str,
    compiler_inputs: dict[str, Any] | None = None,
) -> None:
    """Validate a known identity against its owning record and current model."""
    if identity is None:
        return
    if identity.load_case != expected_load_case:
        raise ValueError(
            f"{context} solver input identity load case {identity.load_case!r} does not "
            f"match declared load case {expected_load_case!r}."
        )
    if identity.compiler_id != expected_compiler_id:
        raise ValueError(
            f"{context} solver input identity compiler {identity.compiler_id!r} does not "
            f"match expected compiler {expected_compiler_id!r}."
        )
    current = build_solver_input_identity(
        model,
        expected_load_case,
        compiler_id=expected_compiler_id,
        compiler_inputs=compiler_inputs,
    )
    if current != identity:
        raise ValueError(
            f"{context} solver input fingerprint {identity.fingerprint} does not match "
            f"current model fingerprint {current.fingerprint}."
        )


def require_matching_solver_input_identities(
    first: SolverInputIdentity | None,
    second: SolverInputIdentity | None,
    *,
    context: str,
) -> None:
    if first is not None and second is not None and first != second:
        raise ValueError(f"{context} solver input fingerprints do not match.")


def _operation_field_payload(field: Any) -> dict[str, Any]:
    return {
        "quantity": field.quantity,
        "value": float(field.value),
        "direction": list(field.direction) if field.direction is not None else None,
        "scope": field.scope,
        "profile": field.profile,
        "group": field.group,
        "route_id": field.route_id,
        "station_start": field.station_start,
        "station_end": field.station_end,
        "element_ids": list(field.element_ids),
    }
