import math

from tuba import Model
from tuba.analysis.results import ResultState
from tuba.visualization.builders._results import _result_state_reaction_overlays


def test_reaction_glyphs_preserve_magnitude_ratios_and_separate_moment_units():
    model = Model("Glyph sizing")
    a, b = model.add_node([0, 0, 0]), model.add_node([2, 0, 0])
    state = ResultState("result", "study", 0, "Code_Aster", "Hot", None, {},
                        {a: (0, 1200, 0, 0, 0, 1e6), b: (0, 300, 0, 0, 0, 5e5)}, {})
    overlays = _result_state_reaction_overlays(model, state, None)
    lengths = {
        overlay.data["result_type"]: [math.dist(v["start"], v["end"]) for v in overlay.data["vectors"]]
        for overlay in overlays
    }
    assert math.isclose(lengths["reaction_force"][0], 0.3)
    assert math.isclose(lengths["reaction_force"][1], 0.075)
    assert math.isclose(lengths["reaction_moment"][0], 0.3)
    assert math.isclose(lengths["reaction_moment"][1], 0.15)
