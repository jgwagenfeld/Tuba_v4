# Clash Detection And IFC TODO

- [ ] Create `tuba.clash.types` with `ClashCheckConfig`, `ClashPair`, `ClashResult`, and `ClashReport`.
  Verify: `.\.venv\Scripts\python.exe -m unittest tests.test_clash_types -v`

- [ ] Add `EntityRef` or equivalent stable target refs for elements, obstacles, supports, groups, routes, and assemblies.
  Verify: `.\.venv\Scripts\python.exe -m unittest tests.test_clash_types -v`

- [ ] Add `tuba.clash.envelopes` for bare pipe, insulation, cladding, and clearance envelope computation.
  Verify: `.\.venv\Scripts\python.exe -m unittest tests.test_clash_envelopes -v`

- [ ] Wrap existing `PipingCollisionChecker` behind `TrimeshClashEngine`.
  Verify: `.\.venv\Scripts\python.exe -m unittest tests.test_collision -v`

- [ ] Return structured clash results with left/right refs, severity, required clearance, distance/penetration when available, and diagnostics.
  Verify: `.\.venv\Scripts\python.exe -m unittest tests.test_clash_engine -v`

- [ ] Preserve compatibility for `PipingCollisionChecker(model).check_collisions()`.
  Verify: `.\.venv\Scripts\python.exe -m unittest tests.test_collision -v`

- [ ] Add insulation envelope tests where a bare pipe clears an obstacle but an insulated pipe clashes.
  Verify: `.\.venv\Scripts\python.exe -m unittest tests.test_clash_envelopes tests.test_clash_engine -v`

- [ ] Add pipe-to-pipe clash checks and shared-endpoint filters.
  Verify: `.\.venv\Scripts\python.exe -m unittest tests.test_clash_engine tests.test_routing_network -v`

- [ ] Add deformed-state structured clash checks using `FEAResults`.
  Verify: `.\.venv\Scripts\python.exe -m unittest tests.test_clash_engine -v`

- [ ] Make `RoutingGrid` use the shared envelope provider for OD, insulation, and clearance.
  Verify: `.\.venv\Scripts\python.exe -m unittest tests.test_routing_grid tests.test_routing_astar -v`

- [ ] Make `ClashObjective` consume the new clash interface.
  Verify: `.\.venv\Scripts\python.exe -m unittest tests.test_routing_solver_loop -v`

- [ ] Add JSON and Markdown clash report serialization.
  Verify: `.\.venv\Scripts\python.exe -m unittest tests.test_clash_report -v`

- [ ] Add optional IFC review export of clash results as Tuba property sets.
  Verify: `.\.venv\Scripts\python.exe -m unittest tests.test_ifc -v`

- [ ] Replace silent IFC geometry export failures with diagnostics while keeping non-strict export usable.
  Verify: `.\.venv\Scripts\python.exe -m unittest tests.test_ifc -v`

- [ ] Add documentation for internal clash checks versus IFC exchange checks.
  Verify: `.\.venv\Scripts\python.exe -m unittest discover -s tests -q`

- [ ] Run full suite.
  Verify: `.\.venv\Scripts\python.exe -m unittest discover -s tests -q`

