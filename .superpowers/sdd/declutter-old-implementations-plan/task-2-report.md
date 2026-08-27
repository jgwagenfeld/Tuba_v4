# Task 2 report: deepen routing geometry and remove planner seam

Status: complete

## Interface and deletion evidence

- `tuba.routing.adapter.candidate_render_points()` is the adapter-owned candidate render-geometry interface. It derives real arc samples from the same private candidate-geometry expansion consumed by `build_candidate_patch()`.
- `tuba.routing.visualization._candidate_render_points` is a direct alias of that adapter interface; PyVista candidate overlays retain their existing public `build_route_plotter`, notebook-display, and HTML-export paths.
- Explicit failures remain: missing bend radius raises the adapter's `explicit bend radius` error; absent model-bend geometry still raises in `_element_render_points`; adapter render expansion rejects missing explicit bend geometry.
- Deleted `tuba/routing/planner.py`, its facade exports, and its two wrapper-only A* tests. Search command `rg -n --hidden -g '!viewer/node_modules/**' -g '!\.git/**' -g '!\.venv/**' 'AStarPipePlanner|PipePlanner|SearchState|tuba\.routing\.planner' .` returned `deleted-symbol search: no matches`.

## RED / GREEN

- RED: `uv run pytest tests/test_routing_visualization.py::TestRoutingVisualization::test_visualization_uses_adapter_owned_candidate_render_geometry -q` failed at collection with `ImportError: cannot import name 'candidate_render_points' from 'tuba.routing.adapter'`.
- GREEN: the identical command passed: `1 passed in 4.97s`.

## Files

- Modified: `tuba/routing/adapter.py`, `tuba/routing/visualization.py`, `tuba/routing/__init__.py`, `tests/test_routing_astar.py`, `tests/test_routing_visualization.py`.
- Deleted: `tuba/routing/planner.py`.
- Untouched: `tuba/plotting/pipeline.py`; all pre-existing visualization/solver worktree changes remain unstaged and unmodified.

## Verification

- `uv run pytest tests/test_routing_adapter.py tests/test_routing_astar.py tests/test_routing_visualization.py tests/test_routing_expansion.py tests/test_routing_agent.py tests/test_notebook_code_aster_results.py -q` -> `40 passed in 13.01s`.
- `$env:PYTHONPATH='.'; uv run pytest tests/test_examples.py -q` -> `5 passed, 6 subtests passed in 2.73s`.
- `uv run ruff check tuba/routing/adapter.py tuba/routing/visualization.py tuba/routing/__init__.py tests/test_routing_astar.py tests/test_routing_visualization.py` -> `All checks passed!`.
- `git diff --check` passed before commit.

## Commit

- Implementation commit: `e231bcee3af2a0a9afc484bcd163d91c8ee2e5bc` (`refactor routing geometry seam`).

## Self-review and concerns

- The shared expansion is limited to one adapter-private geometry record plus one adapter-owned render interface; no new display module, planner protocol, compatibility shim, or dependency was introduced.
- The aggregate test command that included `tests/test_examples.py` initially failed collection because pytest did not place the project root on `sys.path` for the namespace-only `examples/` directory. The example suite passed unchanged with `PYTHONPATH=.`; this is an existing test invocation condition, not a routing regression.
