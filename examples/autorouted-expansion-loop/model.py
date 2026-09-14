"""A hot line autorouted around equipment, keeping the expansion loop the router selected."""

from pathlib import Path
from tempfile import TemporaryDirectory

from examples.autoroute_expansion_loop import build_model, build_request, build_router
from tuba.routing import AutoroutingAgent
from tuba.routing.solver_loop import SolverLoopConfig

model = build_model()
with TemporaryDirectory(prefix="tuba-autorouted-gallery-") as routing:
    run = AutoroutingAgent(
        router=build_router(),
        solver_config=SolverLoopConfig(run_solver=False, export_study=False, load_case="Hot"),
        output_root=Path(routing),
    ).route_pipe(
        model,
        build_request(),
        apply=True,
        add_supports=True,
        support_spacing=2.0,
    )
if run.result.selected is None or not run.created_element_ids:
    raise RuntimeError("Canonical autorouting gallery did not produce a selected route.")
for candidate in run.result.candidates:
    candidate.metadata.pop("solver", None)
elements = {element.id: element for element in model.elements}
for node_id in (
    elements[run.created_element_ids[0]].n1,
    elements[run.created_element_ids[-1]].n2,
):
    model.add_support(node_id, "anchor")
# Added after routing on purpose: the router consumes model.obstacles, so an
# obstacle declared earlier would change the generated nodes and elements and
# break the solver-input fingerprint of the committed Code_Aster artifacts.
# This tray clears the cold loop and is only reached once the line expands.
model.add_obstacle(
    id="cable_tray",
    type="cuboid",
    min_point=(4.6, 0.95, -0.20),
    max_point=(6.4, 1.15, 0.20),
)
model.validate()
route_result = run.result
