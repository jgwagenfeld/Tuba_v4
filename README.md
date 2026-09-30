# Tuba v4

Tuba is an open-source Python library for modeling piping systems, running
Code_Aster analyses, and displaying the results.

[![A solved Tuba review showing pipe geometry, the analysis mesh, wall stress, deformation and support reactions together.](docs/content/assets/figures/code_aster_review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/)

## Gallery

Open a review without installing Tuba. Choose **Build**, edit `model.py`, and **Update geometry** to [try a geometry preview](docs/content/setup.md#try-a-model-in-the-browser).
**Review** shows published Code_Aster results (except *Imported components*); edited geometry needs a new Code_Aster solve.
[Browse the full gallery →](https://jgwagenfeld.github.io/Tuba_v4/viewer/)

<table>
<tr>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/code-aster-review.png" width="250" alt="Pipe bends"></a><br><b>Pipe bends</b><br>What happens to a pressurised line held at both ends?</td>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=load-case-preparation"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/load-case-preparation.png" width="250" alt="Load-case preparation"></a><br><b>Load-case preparation</b><br>How do sustained, thermal, occasional and pressure loads change the same pipe?</td>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=support-rack-review"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/support-rack-review.png" width="250" alt="Load transfer"></a><br><b>Load transfer</b><br>What do the supports and the steel underneath actually carry?</td>
</tr>
<tr>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=autorouted-expansion-loop"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/autorouted-expansion-loop.png" width="250" alt="Thermal expansion"></a><br><b>Thermal expansion</b><br>Where does a hot line move, and what does it reach?</td>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=native-friction-review"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/native-friction-review.png" width="250" alt="Nonlinear friction"></a><br><b>Nonlinear friction</b><br>How does friction change the same pipe and load path?</td>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=multipipe-rack"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/multipipe-rack.png" width="250" alt="Multipipe rack"></a><br><b>Multipipe rack</b><br>How do three lines at different temperatures load one shared rack?</td>
</tr>
<tr>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=profile-orientation-review"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/profile-orientation-review.png" width="250" alt="Beam orientation"></a><br><b>Beam orientation</b><br>How does a rolled I-section change the response to the same tip force?</td>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=pipe-tee-volume-review"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/pipe-tee-volume-review.png" width="250" alt="3D solid"></a><br><b>3D solid</b><br>How does 1D beam pipework transition into a 3D solid tee junction?</td>
</tr>
</table>

## Example

Define a pipe with two straight runs, a bend, anchored ends, and an operating load case, then solve it with Code_Aster:

```python
from tuba import Model

model = Model("HotLine")
model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
model.define_operation("Operating", gravity=True, pressure=1.5e6, temperature=150.0)

with model.pipe(section="DN100", material="Steel") as pipe:
    pipe.start([0.0, 0.0, 0.0], support="anchor")
    pipe.run(3.0)
    pipe.bend(radius=0.3, angle=90.0, plane="XY")
    pipe.run(2.0)
    pipe.end(support="anchor")

model.validate()
run = model.solve("Operating")
```

Display the imported stress and displacement results with PyVista:

```python
run.results.plot_deformed_stress(model=model)
```

For browser display, see the [web-scene workflow](docs/content/workflow.md#reviewable-web-scene).
Scene bundles contain model geometry, analysis meshes, results, and run metadata.

## Features

- Define pipe runs, bends, supports, racks and imported components in Python.
- Route lines automatically around obstacles and add thermal expansion loops.
- Analyse with beam, `TUYAU` pipe-wall or full 3D solid idealisations.
- Assign [fluid contents by operation](docs/content/modeling.md#fluid-contents-by-operation) for empty, operating and hydrotest 1D piping, with separate mass reporting.
- Recover deflection, wall stress, element forces and support reactions.
- Check operating-state clearances against the deformed line and apply your own design rules.
- Display results in PyVista or the web viewer, export glTF, PLY or Blender files, and
  exchange with IFC.

## Tuba Studio & 3D Review

Tuba separates parametric modeling (`model.py`) from FEA solver configuration (`study.py`):

```bash
python -m tuba.cli_studio examples/line-load-studio                          # Live Three.js studio, .comm inspector & solve
python -m tuba.visualization.viewer .build/studio/line-load-studio/review    # Serve the bundle the studio wrote
python -m tuba.mcp.server                                                    # Model Context Protocol for external AI agents
python -m tuba.skills --target ~/.config/opencode/skills                     # Agent skill: how to author and verify model.py
```

## Getting started

Install [Miniforge](https://github.com/conda-forge/miniforge) in Linux x86_64 (Ubuntu WSL2 on Windows), then create the shared Tuba and Code_Aster environment:

```bash
git clone --branch main --depth 1 https://github.com/jgwagenfeld/Tuba_v4.git
cd Tuba_v4
conda env create -f environment.yml
conda activate tuba
```

The environment installs Python 3.14, Code_Aster 18.0.12, Tuba, notebooks, IFC exchange and MCP support. Follow the [setup walkthrough](docs/content/setup.md) to check the solver and launch Studio in your browser. Choose **Solve**, then **Review** to inspect the results. The Windows `.venv` developer setup remains available there.

**[Setup →](https://jgwagenfeld.github.io/Tuba_v4/setup.html)** ·
**[Tutorial →](https://jgwagenfeld.github.io/Tuba_v4/tutorial.html)** ·
**[Examples →](https://jgwagenfeld.github.io/Tuba_v4/examples.html)** ·
**[Documentation →](https://jgwagenfeld.github.io/Tuba_v4/)**

## Solver results

Stress, displacement, and reaction results require a completed Code_Aster run and imported result files. Exporting `.comm`, `.mail`, and `.export` input files does not run an analysis. Imported results retain model and study identifiers
for checking which model was analysed.

## Engineering and standards disclaimer

Tuba is an engineering analysis tool, not a substitute for professional
engineering judgment or independent verification. Before relying on results for
design, construction, or operation, a qualified engineer should verify the model,
inputs, solver setup, results, and suitability for the intended application.
Code_Aster results and passing individual checks do not by themselves establish
the safety or full code compliance of a piping system.

Users are responsible for selecting the applicable piping standards and editions,
defining the required checks and acceptance criteria, and establishing compliance
for their application. Consult the official standards and account for the
software's documented assumptions and limitations. Tuba's analysis outputs do
not constitute certification or approval by a standards organization. The
project's license does not grant rights to third-party standards or material.

The software is provided "as is", without warranty, to the extent permitted by
applicable law. The warranty disclaimer and limitation of liability in
[LICENSE](LICENSE) and [LICENSE.GPL](LICENSE.GPL), particularly GPL sections 15
and 16, apply. This notice does not change the project's open-source license.

## License

`LGPL-3.0-or-later`. See `LICENSE` and `LICENSE.GPL`.
