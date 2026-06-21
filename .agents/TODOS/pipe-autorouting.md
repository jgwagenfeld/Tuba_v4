# Pipe Autorouting TODO

## Phase 0 - Baseline and Guardrails

- [ ] Verify current test baseline in the workspace virtualenv.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest discover -s tests -v
  ```

- [ ] Add `.agents/SPECS/pipe-autorouting.md`, `.agents/TODOS/pipe-autorouting.md`, and `.agents/DECISIONS/pipe-autorouting.md`.
  Verify:
  ```powershell
  Test-Path .agents\SPECS\pipe-autorouting.md
  Test-Path .agents\TODOS\pipe-autorouting.md
  Test-Path .agents\DECISIONS\pipe-autorouting.md
  ```

## Phase 1 - Fix Current Model Prerequisites

- [ ] Add model-level element ID generation to `tuba/model.py`.
  Implementation notes:
  - Add `_element_counters: dict[str, int]`.
  - Add `next_element_id(prefix: str) -> str`.
  - Initialize counters from existing element IDs during `from_dict`.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_tuba_core -v
  ```

- [ ] Update `tuba/builder.py` to use `model.next_element_id("pipe_str")` and `model.next_element_id("pipe_bend")`.
  Implementation notes:
  - Remove local `_segment_counter` as the source of element IDs.
  - Keep any local state only for builder cursor behavior.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_tuba_core.TestModelAndBuilder -v
  ```

- [ ] Add regression test for unique element IDs across multiple builder contexts and branches.
  Suggested file: `tests/test_tuba_core.py`.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_tuba_core.TestModelAndBuilder -v
  ```

- [ ] Harden Code_Aster export path behavior.
  Implementation notes:
  - Ensure `study.export` contains paths valid for the selected execution directory.
  - Add tests for explicit relative `output_dir` and absolute temp directory.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_tuba_core.TestCodeAsterSolver -v
  ```

## Phase 2 - Routing Package Skeleton

- [ ] Add `tuba/routing/__init__.py`.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -c "import tuba.routing; print('ok')"
  ```

- [ ] Add `tuba/routing/types.py` with public dataclasses.
  Include:
  - `RouteEndpoint`
  - `RoutingGridSpec`
  - `RoutingConstraints`
  - `RoutingCostWeights`
  - `PipeRouteRequest`
  - `RouteSegment`
  - `PipeRouteCandidate`
  - `PipeRouteResult`
  - `NetworkRouteRequest`
  - `NetworkRouteResult`
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -c "from tuba.routing.types import PipeRouteRequest, RouteEndpoint; print(RouteEndpoint(id='a', point=(0,0,0)))"
  ```

- [ ] Add serialization helpers for route results.
  Implementation notes:
  - Prefer `dataclasses.asdict`.
  - Keep numpy arrays out of public route dataclasses.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_types -v
  ```

## Phase 3 - Routing Grid

- [ ] Add `tuba/routing/grid.py`.
  Implementation notes:
  - Numpy occupancy array.
  - `world_to_index` and `index_to_world`.
  - Bounds derived from model/request plus margin.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_grid -v
  ```

- [ ] Add cuboid obstacle voxelization.
  Implementation notes:
  - Inflate by pipe radius + insulation + clearance.
  - Use `model.obstacles` entries of type `cuboid`.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_grid.TestRoutingGrid.test_cuboid_obstacle_inflation -v
  ```

- [ ] Add existing-pipe occupancy.
  Implementation notes:
  - Approximate existing elements as inflated cylinders.
  - Phase 1 may use sampled points along segment centerlines.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_grid.TestRoutingGrid.test_existing_pipe_blocks_cells -v
  ```

- [ ] Add grid-size guardrails.
  Implementation notes:
  - Fail early with diagnostic if requested grid exceeds max cells.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_grid.TestRoutingGrid.test_grid_size_guardrail -v
  ```

## Phase 4 - Single-Pipe A* Router

- [ ] Add `tuba/routing/cost.py`.
  Implementation notes:
  - Length cost.
  - Bend cost.
  - Vertical movement cost.
  - Cell penalty cost.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_astar -v
  ```

- [ ] Add `tuba/routing/astar.py` with `GridRouter`.
  Implementation notes:
  - Priority queue with deterministic tie-breaking.
  - State includes index and incoming direction.
  - Manhattan heuristic for orthogonal routing.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_astar.TestGridRouter.test_direct_route_empty_space -v
  ```

- [ ] Add obstacle-avoidance test.
  Scenario:
  - Start `(0, 0, 0)`.
  - Goal `(5, 0, 0)`.
  - Cuboid blocks direct path.
  - Route must detour.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_astar.TestGridRouter.test_routes_around_cuboid -v
  ```

- [ ] Add no-route test.
  Scenario:
  - Fully blocked wall separates start and goal.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_astar.TestGridRouter.test_no_route_when_blocked -v
  ```

- [ ] Add endpoint direction test.
  Scenario:
  - Start/goal have required initial/final direction.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_astar.TestGridRouter.test_endpoint_direction_preference -v
  ```

- [ ] Add candidate generation.
  Implementation notes:
  - `candidate_count`.
  - Weight perturbation or previous-path penalties.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_astar.TestGridRouter.test_multiple_candidates -v
  ```

## Phase 5 - Postprocessing and Model Adapter

- [ ] Add `tuba/routing/postprocess.py`.
  Implementation notes:
  - Remove collinear points.
  - Snap endpoints.
  - Build straight/bend segments.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_adapter -v
  ```

- [ ] Add bend geometry validation.
  Implementation notes:
  - Minimum bend radius.
  - Minimum straight between bends.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_adapter.TestRoutePostprocess.test_bend_validation -v
  ```

- [ ] Add `tuba/routing/adapter.py`.
  Implementation notes:
  - `apply_candidate_to_model`.
  - Node reuse by coordinate tolerance.
  - Unique element IDs.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_adapter.TestRouteAdapter -v
  ```

- [ ] Add integration test from route to `TubaModel`.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_adapter.TestRouteAdapter.test_apply_candidate_to_model -v
  ```

## Phase 6 - Collision Verification and Reports

- [ ] Validate postprocessed route with collision checker.
  Implementation notes:
  - Build temporary model or temporary collision geometry.
  - Diagnostics should name colliding elements/obstacles.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_astar.TestGridRouter.test_postprocessed_route_is_collision_free -v
  ```

- [ ] Add `tuba/routing/report.py`.
  Implementation notes:
  - Markdown report.
  - JSON result export.
  - Optional HTML visualization only if dependencies are installed.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_report -v
  ```

- [ ] Add clear optional visualization dependency diagnostics.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_report.TestRoutingReport.test_html_export_missing_dependency_is_nonfatal -v
  ```

## Phase 7 - Network Routing

- [ ] Add `tuba/routing/network.py` with prioritized planning.
  Implementation notes:
  - Route requests in selected order.
  - Add accepted route as temporary obstacle for later requests.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_network.TestNetworkRouter.test_prioritized_two_pipe_route -v
  ```

- [ ] Add route order strategies.
  Include:
  - `given`
  - `large_bore_first`
  - `critical_first`
  - `least_flexible_first`
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_network.TestNetworkRouter.test_order_strategies -v
  ```

- [ ] Add conflict detection between candidate routes.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_network.TestNetworkRouter.test_detects_candidate_conflict -v
  ```

- [ ] Add basic reroute-on-conflict.
  Implementation notes:
  - Penalize or block conflict cells.
  - Stop with unresolved conflict diagnostics after max attempts.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_network.TestNetworkRouter.test_reroutes_on_conflict -v
  ```

## Phase 8 - Solver-In-The-Loop

- [ ] Add `tuba/routing/solver_loop.py`.
  Implementation notes:
  - Cheap geometry scoring first.
  - Optional study export.
  - Optional solver execution.
  - Metadata attached to candidates.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_solver_loop -v
  ```

- [ ] Add candidate study export.
  Scenario:
  - Generate two candidates.
  - Export Code_Aster studies for top two.
  - Do not run solver.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_solver_loop.TestSolverLoop.test_exports_candidate_studies_without_running_solver -v
  ```

- [ ] Add solver-unavailable fallback.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_solver_loop.TestSolverLoop.test_solver_unavailable_is_nonfatal -v
  ```

- [ ] Integrate `ASMEB313Evaluator` when real or parsed results are available.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests.test_routing_solver_loop.TestSolverLoop.test_compliance_metadata_added_when_results_available -v
  ```

## Phase 9 - Examples and Documentation

- [ ] Add `examples/autoroute_single_pipe.py`.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe examples\autoroute_single_pipe.py
  ```

- [ ] Add `examples/autoroute_network.py`.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe examples\autoroute_network.py
  ```

- [ ] Update `README.md` with minimal autorouting usage after implementation.
  Verify:
  ```powershell
  Get-Content README.md
  ```

- [ ] Add troubleshooting notes for:
  - no route found,
  - grid too large,
  - solver unavailable,
  - visualization dependency missing.
  Verify:
  ```powershell
  rg -n "autorout|routing|solver unavailable|grid too large" README.md .agents\SPECS\pipe-autorouting.md
  ```

## Phase 10 - Final Verification

- [ ] Run full test suite.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest discover -s tests -v
  ```

- [ ] Run demo without GUI.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe -c "import os; os.environ['TUBA_HEADLESS']='1'; import demo; demo.main()"
  ```

- [ ] Run autorouting examples.
  Verify:
  ```powershell
  .\.venv\Scripts\python.exe examples\autoroute_single_pipe.py
  .\.venv\Scripts\python.exe examples\autoroute_network.py
  ```

- [ ] Review generated route report manually.
  Verify:
  ```powershell
  Get-ChildItem routing_reports -Recurse
  ```

