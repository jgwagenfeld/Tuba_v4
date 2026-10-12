# Tuba v4

Tuba is an open-source Python library for modeling piping systems and their supporting structures, running Code_Aster analyses, and reviewing the results.

Tuba also provides CLI and MCP (Model Context Protocol) interfaces. Ongoing development aims to automate parts of model building.

**[Examples](#examples)** · **[CLI and MCP](#cli-and-mcp)** · **[Getting started](#getting-started)** · **[Documentation](https://jgwagenfeld.github.io/Tuba_v4/)**

## Examples

Open these reviews in your browser without installing Tuba. Each example below includes Code_Aster results and Python source you can inspect and adapt.

[![Plant layout with two process lines, a shared steel pipe rack, and surrounding equipment.](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/hydrogen-plant-layout.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=hydrogen-plant-layout)

**[Plant layout](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=hydrogen-plant-layout)** — Two process lines, an elevated rack, shoe supports and equipment obstacles in one model. Inspect displacement, pipe-wall stress and friction shoe reactions. This is an illustrative hydrogen-plant layout, not a hydrogen-service qualification. [Model source](examples/hydrogen-plant-layout/model.py) · [Study](examples/hydrogen-plant-layout/study.py).

<table>
<tr>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=multipipe-rack"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/multipipe-rack.png" width="250" alt="Three pipe lines on a shared steel rack"></a><br><b>Multipipe rack</b><br>How do three lines at different temperatures load one shared rack?<br><a href="examples/multipipe-rack/model.py">Model source</a></td>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=autorouted-expansion-loop"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/autorouted-expansion-loop.png" width="250" alt="An automatically routed hot line with an expansion loop"></a><br><b>Thermal expansion</b><br>An automatically routed line and expansion loop. Where does a hot line move, and what does it reach?<br><a href="examples/autorouted-expansion-loop/model.py">Model source</a></td>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=pipe-tee-volume-review"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/pipe-tee-volume-review.png" width="250" alt="Solid tee mesh coupled to pipe elements"></a><br><b>3D solid</b><br>How does 1D beam pipework transition into a 3D solid tee junction?<br><a href="examples/pipe-tee-volume-review/model.py">Model source</a></td>
</tr>
<tr>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=steel-portal-frame-review"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/steel-portal-frame-review.png" width="250" alt="A steel industrial hall with repeated portal frames and bracing"></a><br><b>Portal frame stability</b><br>A seven-frame hall under gravity and wind, with linear buckling modes for the ideal frame. These are reference results, not member-adequacy checks.<br><a href="examples/steel-portal-frame/model.py">Model source</a></td>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=native-friction-review"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/native-friction-review.png" width="250" alt="Comparison of frictionless and frictional pipe supports"></a><br><b>Nonlinear friction</b><br>How does friction change the same pipe and load path?<br><a href="examples/native-friction-review/model.py">Model source</a></td>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=support-rack-review"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/support-rack-review.png" width="250" alt="Pipe loads transferred through shoes to a steel rack"></a><br><b>Load transfer</b><br>What do the supports and the steel underneath actually carry?<br><a href="examples/support-rack-review/model.py">Model source</a></td>
</tr>
<tr>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=load-case-preparation"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/load-case-preparation.png" width="250" alt="The same pipework evaluated in four load cases"></a><br><b>Load-case preparation</b><br>How do sustained, thermal, occasional and pressure loads change the same pipe?<br><a href="examples/load-case-preparation/model.py">Model source</a></td>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=profile-orientation-review"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/profile-orientation-review.png" width="250" alt="Three I-section orientations under the same load"></a><br><b>Beam orientation</b><br>How does a rolled I-section change the response to the same tip force?<br><a href="examples/profile-orientation-review/model.py">Model source</a></td>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/code-aster-review.png" width="250" alt="A restrained pipe with two bends"></a><br><b>Pipe bends</b><br>What happens to a pressurised line held at both ends?<br><a href="examples/code-aster-review/model.py">Model source</a></td>
</tr>
</table>

The thermal-expansion example selects its route geometrically, then checks the solved operating clearance; it does not rank competing routes by solver results. [Browse all examples and their limits](docs/content/examples.md), including braced racks, guy cables and imported components.

Choose **Build**, edit `model.py`, and **Update geometry** to [try a browser preview](docs/content/setup.md#try-a-model-in-the-browser). **Review** shows the published analysis; edited geometry needs a new Code_Aster solve.

## CLI and MCP

Studio, the CLI and MCP use the same project files: `model.py` defines the structure, `study.py` defines the analysis, and optional `units/` holds reusable construction functions.

The CLI runs project studies. MCP provides tools for model inspection, verification, clash checks and solver execution. Both use the project's study settings and require Code_Aster for new results.

After [setup](#getting-started):

```bash
python -m tuba.project examples/multipipe-rack --output .build/multipipe-review
python -m tuba.mcp.server                         # Local MCP server (stdio)
python -m tuba.cli_studio examples/multipipe-rack  # Open the project in Studio
```

See the [CLI and MCP documentation](docs/content/workflow.md#projects-in-studio-the-cli-and-agents) for client setup and project selection. A [modeling skill](tuba/skills/tuba-modeling/SKILL.md) is included for coding agents.

## A small Python model

Define a pipe with anchored ends and an operating load case, solve it with Code_Aster, then display the imported results:

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
run.results.plot_deformed_stress(model=model)
```

For browser display, see the [web-scene workflow](docs/content/workflow.md#reviewable-web-scene) and an [example result view](docs/content/assets/figures/code_aster_review.png). Scene bundles include geometry, analysis meshes, results and run metadata. The [modeling guide](docs/content/modeling.md) covers beam, `TUYAU` pipe-wall and 3D solid idealisations, supports and fluid contents by operation.

The [process-network example](docs/content/process-networks.md) connects a typed
water-circuit graph and authored route to OpenModelica, then transfers verified
pressure, temperature and contents loads into Code_Aster. Its retained candidate
review includes hydraulic failures and structural results for solved layouts.

## Getting started

Install [Miniforge](https://github.com/conda-forge/miniforge) in Linux x86_64 (Ubuntu WSL2 on Windows), then create the shared Tuba and Code_Aster environment:

```bash
git clone --branch main --depth 1 https://github.com/jgwagenfeld/Tuba_v4.git
cd Tuba_v4
conda env create -f environment.yml
conda activate tuba
```

The environment installs Python 3.14, Code_Aster 18.0.12, Tuba, notebooks, IFC exchange and MCP support. Follow the [setup walkthrough](docs/content/setup.md) to check the solver and launch Studio in your browser. Choose **Solve**, then **Review** to inspect the results. The Windows `.venv` developer setup remains available there.

For CAD input and mesh refinement, see the [STEP and mesh guide](docs/content/step-meshing.md) and [convergence example](examples/mesh-refinement-review/README.md). To hand a project or its results to someone else, see [Share and open a project](docs/content/project-sharing.md).

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
