# Future-Ready Library Implementation Checkpoints

## Loop Rule

For each checkpoint:

1. Mark the checkpoint `In Progress`.
2. Write failing tests first.
3. Run the checkpoint verification command and confirm the expected failure.
4. Implement the smallest production change that passes.
5. Run checkpoint tests.
6. Run the relevant regression tests.
7. Mark the checkpoint `Complete` only after tests pass.
8. Continue to the next unblocked checkpoint.

## Status Legend

- `Pending`: not started.
- `In Progress`: actively being implemented.
- `Blocked`: cannot proceed without a dependency or decision.
- `Complete`: implemented and verified.

## Checkpoints

| ID | Package | Status | Verification Gate |
| --- | --- | --- | --- |
| CP00 | Architecture baseline and vocabulary | Complete | `.\.venv\Scripts\python.exe -m unittest discover -s tests -q` |
| CP01 | Entity refs and stable IDs | Complete | `.\.venv\Scripts\python.exe -m unittest tests.test_entity_refs -v` |
| CP02 | Typed attributes and specs | Complete | `.\.venv\Scripts\python.exe -m unittest tests.test_attributes tests.test_schema -v` |
| CP03 | Patch-first generated changes | Complete | `.\.venv\Scripts\python.exe -m unittest tests.test_patches tests.test_fragments tests.test_tuba_core -v` |
| CP04 | Physical properties and envelopes | Complete | `.\.venv\Scripts\python.exe -m unittest tests.test_physical_properties -v` |
| CP05 | Clash interface and IFC adapter | Complete | `.\.venv\Scripts\python.exe -m unittest tests.test_collision tests.test_clash_engine tests.test_ifc -v` |
| CP06 | RoutePlan module | Complete | `.\.venv\Scripts\python.exe -m unittest tests.test_route_plan tests.test_routing_adapter -v` |
| CP07 | RouteCostModel | Complete | `.\.venv\Scripts\python.exe -m unittest tests.test_route_cost_model tests.test_routing_solver_loop -v` |
| CP08 | Planner seam and network optimization | Complete | `.\.venv\Scripts\python.exe -m unittest tests.test_routing_astar tests.test_routing_network -v` |
| CP09 | Rack assemblies and construction modules | Complete | `.\.venv\Scripts\python.exe -m unittest tests.test_rack_assemblies tests.test_fragments -v` |
| CP10 | Geometry/profile adapter | Complete | `.\.venv\Scripts\python.exe -m unittest tests.test_visualizer_scenes tests.test_ifc tests.test_collision -v` |
| CP11 | Quantity, cost, weight, and wind loads | Complete | `.\.venv\Scripts\python.exe -m unittest tests.test_quantities tests.test_route_cost_model -v` |
| CP12 | IFC and BOM export upgrade | Complete | `.\.venv\Scripts\python.exe -m unittest tests.test_ifc tests.test_quantities -v` |
| CP13 | Load-path analysis | Complete | `.\.venv\Scripts\python.exe -m unittest tests.test_load_path tests.test_rack_assemblies -v` |
| CP14 | Rules and compliance engine | Complete | `.\.venv\Scripts\python.exe -m unittest tests.test_rules tests.test_validation tests.test_routing_report -v` |
| CP15 | Model indexes and benchmarks | Complete | `.\.venv\Scripts\python.exe -m unittest tests.test_model_indexes tests.test_patches -v` |
| CP16 | Final integration demos and full suite | Complete | `.\.venv\Scripts\python.exe -m unittest discover -s tests -q` |

## First Vertical Slice

The first loop slice proves that one semantic input can feed multiple adapters:

1. CP01: create entity references.
2. CP02: add minimal insulation spec assignment.
3. CP04: compute an effective pipe envelope.
4. CP05: use the envelope in structured clash results.
5. CP06: preserve route candidate intent before mutation.
6. CP07: include insulation in route cost.
