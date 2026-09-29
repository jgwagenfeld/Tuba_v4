"""The compiler contract: what one Code_Aster export compiles, decided once.

One pure decision feeds both the writers and the solver input identity. The writers read the
contract's values instead of re-deciding, the exporters record its inputs in study metadata, and
every consumer that needs the compiler id asks :func:`compiler_id_for` rather than reading the
metadata flags itself.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

from tuba.analysis.provenance import (
    CODE_ASTER_COMPILER_ID,
    MIXED_CODE_ASTER_COMPILER_ID,
    VOLUME_CODE_ASTER_COMPILER_ID,
)
from tuba.model import Element, LoadCase, TubaModel, resolve_buckling_options
from tuba.solver.modelisation import PipeModelization, needs_discrete_element


@dataclass(frozen=True)
class CompilerContract:
    """What one export compiles: the compiler id and the inputs the model fingerprint hashes.

    ``compiler_inputs`` is None when nothing beyond the model and the resolved case matters, which
    keeps the plain beam fingerprint payload unchanged. ``bend_segments`` and ``line_segments`` are
    the values the writers must use, so the mesh and the identity cannot disagree.
    """

    compiler_id: str
    compiler_inputs: dict[str, Any] | None
    bend_segments: int
    line_segments: int
    discrete_support_nodes: bool = False
    mixed_analysis: bool = False


def bend_segments(pipe_modelization: PipeModelization | str) -> int:
    """Bend interior segments per modelization: POU_D_T needs more than TUYAU_3M's sixteen."""
    return 32 if PipeModelization(pipe_modelization) is PipeModelization.POU_D_T else 16


def subdivides_straight_segments(
    element: Element,
    *,
    pipe_modelization: PipeModelization,
    line_segments: int,
) -> bool:
    """Whether a straight element is split into ``line_segments`` solver elements."""
    if line_segments == 1:
        return False
    return element.type in {"beam", "cable"} or (
        element.type == "pipe_straight" and pipe_modelization is PipeModelization.POU_D_T
    )


def compiler_id_for(metadata: Mapping[str, Any]) -> str:
    """The compiler id the flags in *metadata* describe: the one mapping every consumer reads."""
    if metadata.get("mixed_analysis"):
        return MIXED_CODE_ASTER_COMPILER_ID
    if metadata.get("volume_analysis"):
        return VOLUME_CODE_ASTER_COMPILER_ID
    return CODE_ASTER_COMPILER_ID


def beam_contract(
    model: TubaModel,
    load_case_name: str,
    load_case: LoadCase,
    *,
    pipe_modelization: PipeModelization,
    line_segments: int,
    load_path: tuple[str, ...] | None,
    load_step: float,
) -> CompilerContract:
    """The pipe/beam compilation: modelization, subdivision, discrete supports and contact."""
    from tuba.solver.aster_contact import shoes, validate_path
    from tuba.physical import _fluid_density_by_element, _physical_properties_for_element, _element_quantities

    if pipe_modelization is PipeModelization.POU_D_T:
        if load_case.internal_pressure != 0 or any(f.quantity == "pressure" and f.value != 0 for f in load_case.fields):
            raise ValueError("POU_D_T pipe pressure is unsupported: pressure end thrust and pressure stress require qualification.")
        pipe_degree = {}
        for elem in [e for e in model.elements if e.type in {"pipe_straight", "pipe_bend"}]:
            for node in (elem.n1, elem.n2):
                pipe_degree[node] = pipe_degree.get(node, 0) + 1
        if getattr(model, "tees", []) or any(degree > 2 for degree in pipe_degree.values()):
            raise ValueError("POU_D_T pipe tee/branch flexibility is unsupported.")

    densities = _fluid_density_by_element(model, load_case)
    total_mass = 0.0
    for element in model.elements:
        if densities:
            props = _physical_properties_for_element(model, element, densities.get(element.id, 0.0))
            total_mass += _element_quantities(model, element, props).total_mass_kg
            if props.metal_area_m2 <= 0 or not math.isfinite(props.mass_kg_per_m / props.metal_area_m2):
                raise ValueError(f"Element {element.id!r} fluid_density effective material density must be finite.")
    if not math.isfinite(total_mass):
        raise ValueError(f"Operation {load_case_name!r} fluid_density total mass must be finite.")

    inputs: dict[str, Any] | None = (
        {"pipe_modelization": pipe_modelization.value, "bend_segments": bend_segments(pipe_modelization)}
        if pipe_modelization is PipeModelization.POU_D_T
        else None
    )
    if any(
        subdivides_straight_segments(element, pipe_modelization=pipe_modelization, line_segments=line_segments)
        for element in model.elements
        if element.type != "pipe_bend"
    ):
        inputs = dict(inputs or {}, line_segments=line_segments)
    discrete = any(needs_discrete_element(support) for support in model.supports)
    if discrete:
        # CREA_POI1 once named its node with NOEUD and put these supports on the wrong node;
        # evidence solved before GROUP_NO lacks this input, so it reads stale.
        inputs = dict(inputs or {}, discrete_support_nodes="GROUP_NO")
    contact_specs = shoes(model, pipe_modelization)
    if contact_specs:
        reject_fluid_contents(load_case, "native contact studies")
    if load_path is not None and (not contact_specs or pipe_modelization is not PipeModelization.POU_D_T):
        raise ValueError("load_path histories require pipe_modelization='POU_D_T' and a resting shoe.")
    if contact_specs:
        if load_path is not None:
            names, _cases = validate_path(model, load_case, load_path)
        else:
            names = (load_case_name,)
        inputs = dict(
            inputs or {},
            pipe_modelization=pipe_modelization.value,
            load_path=list(names),
            load_step=load_step,
            contact_law="DIS_CHOC",
            contact_stiffness_defaults=[1e10, 1e8],
        )
        if load_path is not None:
            model_dict = model.to_dict()
            all_cases = {**model_dict.get("load_cases", {}), **model_dict.get("operations", {})}
            inputs["load_path_inputs"] = {name: all_cases[name] for name in names}
    if load_case.buckling is not None:
        if contact_specs:
            # The geometric stiffness is built from a single SIEF_ELGA of a
            # linear run; a contact history is a field over increments, and
            # picking one increment would silently report a partial prestress.
            raise ValueError(
                f"Operation {load_case_name!r}: buckling analysis is unsupported on native contact "
                "studies; the geometric stiffness would be built from one increment of a contact "
                "history and read as a partial prestress."
            )
        # Resolved through the one coercion point so a dict assigned onto an
        # existing operation after declaration behaves like one passed to
        # define_operation, instead of failing later with an AttributeError.
        inputs = dict(
            inputs or {},
            buckling=resolve_buckling_options(load_case.buckling).to_dict(),
        )
    return CompilerContract(
        compiler_id=CODE_ASTER_COMPILER_ID,
        compiler_inputs=inputs,
        bend_segments=bend_segments(pipe_modelization),
        line_segments=line_segments,
        discrete_support_nodes=discrete,
    )


def reject_fluid_contents(load_case: LoadCase, context: str) -> None:
    """Contents weight is qualified only for linear 1D pipe studies."""
    if any(field.quantity == "fluid_density" for field in load_case.fields):
        raise ValueError(f"Operation {load_case.name!r}: fluid_density is unsupported in {context}.")


def volume_contract(
    model: TubaModel,
    *,
    element_ids: Sequence[str],
    line_element_ids: Sequence[str],
    element_order: int,
    max_element_size: float,
    export_tensor_stress: bool,
) -> CompilerContract:
    """The pipe-volume compilation; line elements left outside the volume make it a mixed study."""
    mixed_analysis = bool(line_element_ids)
    inputs: dict[str, Any] = {
        "element_ids": sorted(element_ids),
        **({"line_element_ids": sorted(line_element_ids)} if mixed_analysis else {}),
        "element_order": element_order,
        "max_element_size": float(max_element_size),
        "export_tensor_stress": bool(export_tensor_stress),
    }
    return CompilerContract(
        compiler_id=MIXED_CODE_ASTER_COMPILER_ID if mixed_analysis else VOLUME_CODE_ASTER_COMPILER_ID,
        compiler_inputs=inputs,
        bend_segments=bend_segments(PipeModelization.SOLID_3D),
        line_segments=1,
        mixed_analysis=mixed_analysis,
    )


def mixed_contract(model: TubaModel) -> CompilerContract:
    """The export-only mixed study: records the composition it compiles so its identity is auditable."""
    inputs: dict[str, Any] = {
        "analysis_regions": sorted(model.analysis_regions),
        "ports": sorted(port.face_group for port in model.ports.values() if port.face_group),
        "couplings": sorted(
            f"{coupling.source_node.id}->{coupling.target.id}" for coupling in model.couplings.values()
        ),
        "line_element_ids": sorted(element.id for element in model.elements),
    }
    return CompilerContract(
        compiler_id=MIXED_CODE_ASTER_COMPILER_ID,
        compiler_inputs=inputs,
        bend_segments=bend_segments(PipeModelization.SOLID_3D),
        line_segments=1,
        mixed_analysis=True,
    )
