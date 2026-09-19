"""Code_Aster solver-input identity for persistent analysis records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tuba.canonical import canonical_digest


MODEL_SCHEMA_ID = "tuba.model.v4"
CODE_ASTER_COMPILER_ID = "tuba.code_aster.v2"
MIXED_CODE_ASTER_COMPILER_ID = "tuba.code_aster.mixed.v2"
VOLUME_CODE_ASTER_COMPILER_ID = "tuba.code_aster.volume.v2"

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


# The solver reads group names (they are reserved in the compiler) and group
# members (operation fields scope to member elements). Group metadata is rack
# and inspection annotation the solver never reads, so it must not move the
# fingerprint - W1 watched rack attachment points stale solved bridge evidence.
_GROUP_MEMBER_KEYS = ("nodes", "elements", "supports")


def _solver_groups_projection(groups: dict[str, Any]) -> dict[str, Any]:
    return {
        name: {key: list(group[key]) for key in _GROUP_MEMBER_KEYS if group.get(key)}
        for name, group in groups.items()
    }


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
    model_keys = _SOLVER_MODEL_KEYS + (
        ("tees",)
        if compiler_id in {VOLUME_CODE_ASTER_COMPILER_ID, MIXED_CODE_ASTER_COMPILER_ID}
        else ()
    )
    model_payload = {key: model_data.get(key) for key in model_keys}
    model_payload["groups"] = _solver_groups_projection(model_data.get("groups") or {})
    payload = {
        "schema_id": MODEL_SCHEMA_ID,
        "compiler_id": compiler_id,
        "model": model_payload,
        "resolved_case": {
            "name": resolved_name,
            "gravity": bool(resolved_case.gravity),
            "internal_pressure": float(resolved_case.internal_pressure),
            "temperature": float(resolved_case.temperature),
            "ref_temperature": float(resolved_case.ref_temperature),
            "fields": [field.to_dict() for field in resolved_case.fields],
            "nodal_forces": [force.to_dict() for force in resolved_case.nodal_forces],
        },
    }
    if compiler_inputs is not None:
        payload["compiler_inputs"] = dict(compiler_inputs)
        if compiler_inputs.get('load_path'):
            all_cases = {**model_data.get('load_cases', {}), **model_data.get('operations', {})}
            payload['load_path_cases'] = {
                name: all_cases[name] for name in compiler_inputs['load_path']
            }
    insulation = {
        element.id: {"thickness_m": float(spec.thickness_m), "density_kg_m3": float(spec.density_kg_m3)}
        for element in model.elements
        if (spec := model.get_insulation(f"element:{element.id}")) is not None
    }
    if insulation:
        payload["insulation"] = insulation
    canonical = canonical_digest(payload)
    return SolverInputIdentity(
        fingerprint=canonical,
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


