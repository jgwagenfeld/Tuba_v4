"""The compiler contract: one decision for what an export compiles and what its identity hashes."""

from tuba import Model
from tuba.analysis.provenance import (
    CODE_ASTER_COMPILER_ID,
    MIXED_CODE_ASTER_COMPILER_ID,
    VOLUME_CODE_ASTER_COMPILER_ID,
)
from tuba.solver.compiler_contract import (
    beam_contract,
    bend_segments,
    compiler_id_for,
    mixed_contract,
    subdivides_straight_segments,
    volume_contract,
)
from tuba.solver.modelisation import PipeModelization


def _pipe_model():
    model = Model("Contract")
    model.add_material("Steel", E=2.1e11, nu=0.3)
    model.add_pipe_section("DN", OD=0.1, WT=0.01)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([1.0, 0.0, 0.0])
    model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="DN", material="Steel")
    model.add_support(n0, type="anchor")
    model.define_load_case("Hot", gravity=False)
    return model


def test_bend_segments_are_one_rule():
    assert bend_segments(PipeModelization.POU_D_T) == 32
    assert bend_segments(PipeModelization.TUYAU_3M) == 16
    assert bend_segments(PipeModelization.SOLID_3D) == 16


def test_straight_elements_subdivide_by_type_and_modelization():
    model = _pipe_model()
    pipe = model.elements[0]
    beam = type(pipe)(id="beam_0", type="beam", n1="N0", n2="N1", section="DN", material="Steel")

    assert subdivides_straight_segments(pipe, pipe_modelization=PipeModelization.POU_D_T, line_segments=8)
    assert not subdivides_straight_segments(pipe, pipe_modelization=PipeModelization.TUYAU_3M, line_segments=8)
    assert subdivides_straight_segments(beam, pipe_modelization=PipeModelization.TUYAU_3M, line_segments=8)
    assert not subdivides_straight_segments(beam, pipe_modelization=PipeModelization.TUYAU_3M, line_segments=1)


def test_compiler_id_follows_the_metadata_flags():
    assert compiler_id_for({}) == CODE_ASTER_COMPILER_ID
    assert compiler_id_for({"volume_analysis": True}) == VOLUME_CODE_ASTER_COMPILER_ID
    assert compiler_id_for({"mixed_analysis": True}) == MIXED_CODE_ASTER_COMPILER_ID
    assert compiler_id_for({"volume_analysis": True, "mixed_analysis": True}) == MIXED_CODE_ASTER_COMPILER_ID


def test_a_plain_tuyau_beam_contract_keeps_the_fingerprint_payload_bare():
    model = _pipe_model()

    contract = beam_contract(
        model,
        "Hot",
        model.load_cases["Hot"],
        pipe_modelization=PipeModelization.TUYAU_3M,
        line_segments=8,
        load_path=None,
        load_step=0.1,
    )

    assert contract.compiler_id == CODE_ASTER_COMPILER_ID
    assert contract.compiler_inputs is None
    assert contract.bend_segments == 16
    assert contract.line_segments == 8


def test_a_pou_d_t_contract_records_modelization_bends_and_subdivision():
    model = _pipe_model()

    contract = beam_contract(
        model,
        "Hot",
        model.load_cases["Hot"],
        pipe_modelization=PipeModelization.POU_D_T,
        line_segments=4,
        load_path=None,
        load_step=0.1,
    )

    assert contract.compiler_inputs == {
        "pipe_modelization": "POU_D_T",
        "bend_segments": 32,
        "line_segments": 4,
    }


def test_a_volume_contract_marks_leftover_line_elements_mixed():
    model = _pipe_model()

    pure = volume_contract(
        model,
        element_ids=["pipe_0"],
        line_element_ids=[],
        element_order=2,
        max_element_size=0.01,
        export_tensor_stress=False,
    )
    mixed = volume_contract(
        model,
        element_ids=["pipe_0"],
        line_element_ids=["line_9"],
        element_order=2,
        max_element_size=0.01,
        export_tensor_stress=True,
    )

    assert pure.compiler_id == VOLUME_CODE_ASTER_COMPILER_ID
    assert pure.compiler_inputs == {
        "element_ids": ["pipe_0"],
        "element_order": 2,
        "max_element_size": 0.01,
        "export_tensor_stress": False,
    }
    assert mixed.compiler_id == MIXED_CODE_ASTER_COMPILER_ID
    assert mixed.compiler_inputs["line_element_ids"] == ["line_9"]
    assert mixed.mixed_analysis is True


def test_a_mixed_contract_records_the_composition_it_compiles():
    contract = mixed_contract(_pipe_model())

    assert contract.compiler_id == MIXED_CODE_ASTER_COMPILER_ID
    assert contract.compiler_inputs["line_element_ids"] == ["pipe_0"]
    assert contract.mixed_analysis is True
