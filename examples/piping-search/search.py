"""A fixed bounded experiment; the goal is evidence, not a hidden penalty score."""

from tuba.search import SearchDefinition

SEARCH = SearchDefinition(
    parameter_grid={"width_m": (1.6, 2.4), "depth_m": (0.55, 0.8, 1.8),
                    "guide_layout": ("end_guides", "mid_guide")},
    objective_fields=("pipe_length_m", "bend_count", "support_count"),
    candidate_limit=12,
    max_solver_calls=24,
    max_artifact_bytes=512 * 1024 * 1024,
)
