# Tuba v4

Piping engineering in Python: define a piping system, analyse it, and review
the results as traceable engineering evidence.

[![A solved Tuba review showing pipe geometry, the analysis mesh, wall stress, deformation and support reactions together.](docs/content/assets/figures/code_aster_review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/)

**[Open the review gallery →](https://jgwagenfeld.github.io/Tuba_v4/viewer/)**
Real analysed piping models in your browser. Nothing to install.

## What you do with it

Describe a line the way a piping engineer thinks about it — runs, bends,
sections, supports, an operating case:

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

Then read the answers back — where it moves, what the wall carries, what
arrives at each support — and keep them together with the model that produced
them:

```python
run.results.plot_deformed_stress(model=model)          # look at it now
write_scene_bundle(build_visualization_scene(model, analysis_runs=[run]), "review")
```

The second form writes a self-contained review anyone can open in a browser,
with the geometry, the analysis mesh, the results and their provenance in one
place. Every example in the gallery is one of those.

## What it can do today

- Author pipe runs, bends, supports, racks and imported components in Python.
- Route lines automatically around obstacles, including expansion loops for hot
  lines.
- Analyse with beam, `TUYAU` pipe-wall or full 3D solid idealisations.
- Recover deflection, wall stress, element forces and support reactions.
- Check operating-state clearances against the deformed line and apply your own
  design rules.
- Publish a shareable review, export to PyVista, glTF, PLY or Blender, and
  exchange with IFC.

## Getting started

Tuba needs Python 3.11 or 3.12.

```bash
git clone --branch v4.0.1 --depth 1 https://github.com/jgwagenfeld/Tuba_v4.git
cd Tuba_v4
python -m venv .venv
.venv/bin/python -m pip install .        # Windows: .\.venv\Scripts\python.exe
```

Analysis runs on [Code_Aster](https://code-aster.org), a separate open-source
solver. Authoring, routing, geometry and review work without it; computing
results does not. On Windows it installs into WSL2 Ubuntu.

**[Setup →](https://jgwagenfeld.github.io/Tuba_v4/setup.html)** ·
**[Tutorial →](https://jgwagenfeld.github.io/Tuba_v4/tutorial.html)** ·
**[Examples →](https://jgwagenfeld.github.io/Tuba_v4/examples.html)** ·
**[Documentation →](https://jgwagenfeld.github.io/Tuba_v4/)**

## Results are earned, never assumed

Tuba will not show you a number it did not compute. Writing solver input files
is a handoff, not an analysis: until the solver has run and Tuba has imported
what it produced, a study has no results, and Tuba says so rather than filling
the gap. Every published review carries the identity of the model it came from,
so evidence cannot drift from the design it describes.

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
