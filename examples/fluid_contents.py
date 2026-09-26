"""Empty, operating and hydrotest contents: model -> Code_Aster -> review.

Run with ``uv run python -m examples.fluid_contents`` after configuring a real
Code_Aster runtime. The example publishes no results if any solve fails.
Density means a completely filled bore in kg/m3 and is independent of pressure.
"""

from pathlib import Path

from tuba import Model
from tuba.reporting import build_engineering_review
from tuba.visualization import (
    SceneRequest,
    build_visualization_scene,
    write_engineering_review_with_scene,
)


def build_model() -> Model:
    """One insulated cantilever, evaluated in three contents states."""
    PIPE_LENGTH_M = 2.0
    OUTSIDE_DIAMETER_M = 0.1
    WALL_THICKNESS_M = 0.01
    INSULATION_THICKNESS_M = 0.02
    model = Model('Fluid contents: empty, operating and hydrotest')
    model.add_material('Steel', E=2e11, nu=0.3, rho=7850)
    model.add_pipe_section('Pipe', OD=OUTSIDE_DIAMETER_M, WT=WALL_THICKNESS_M)
    with model.pipe('Pipe', 'Steel', route='P-100') as pipe:
        pipe.start([0, 0, 0], support='anchor')
        pipe.run(PIPE_LENGTH_M)
    model.add_insulation_spec('wool', material='mineral wool',
                              thickness_m=INSULATION_THICKNESS_M, density_kg_m3=100)
    for element in model.elements:
        model.assign_insulation(f'element:{element.id}', 'wool')
    model.define_operation('Empty', gravity=True)
    for name, density, pressure in [('Operating', 800, 1e6), ('Hydrotest', 1000, 1.5e6)]:
        model.define_operation(name, gravity=True, pressure=pressure).add_field(
            'fluid_density', density, route_id='P-100')
    return model


def main(output: str | Path = '.build/fluid-contents') -> Path:
    model = build_model()
    root = Path(output).resolve()
    # TUYAU_3M is required here because the filled cases include pressure.
    runs = [model.solve(operation=name, pipe_modelization='TUYAU_3M',
                        work_dir=str(root / 'evidence' / name))
            for name in model.operations]
    review = build_engineering_review(model, analysis_runs=runs)
    scene = build_visualization_scene(SceneRequest(model, analysis_runs=runs))
    result = write_engineering_review_with_scene(review, root / 'review', scene=scene, source=__file__)
    print(f'Code_Aster contents review: {result.index_path}')
    return result.root


if __name__ == '__main__':
    main()
