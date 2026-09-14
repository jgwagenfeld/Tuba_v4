# Tuba v4

Tuba is an open-source Python library for modeling piping systems, running
Code_Aster analyses, and displaying the results.

[![A solved Tuba review showing pipe geometry, the analysis mesh, wall stress, deformation and support reactions together.](docs/content/assets/figures/code_aster_review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/)

## Gallery

Every review opens in your browser, no install needed. All except *Imported
components* show imported Code_Aster results.
[Browse the full gallery →](https://jgwagenfeld.github.io/Tuba_v4/viewer/)

<table>
<tr>
<td width="33%"><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=autorouted-expansion-loop"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/autorouted-expansion-loop.png" width="250" alt="Thermal expansion review in the Tuba viewer"></a><br><b>Thermal expansion</b><br>Where does a hot line move, and what does it reach?</td>
<td width="33%"><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=support-rack-review"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/support-rack-review.png" width="250" alt="Load transfer review in the Tuba viewer"></a><br><b>Load transfer</b><br>What do the supports and the steel underneath actually carry?</td>
<td width="33%"><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=profile-orientation-review"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/profile-orientation-review.png" width="250" alt="Beam orientation review in the Tuba viewer"></a><br><b>Beam orientation</b><br>How do section orientation and local axes change bending?</td>
</tr>
<tr>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/code-aster-review.png" width="250" alt="Pipe bends review in the Tuba viewer"></a><br><b>Pipe bends</b><br>What happens to a pressurised line held at both ends?</td>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=guyed-mast-review"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/guyed-mast-review.png" width="250" alt="Cable review in the Tuba viewer"></a><br><b>Cable</b><br>Which guys hold a mast in the wind, and which one goes slack?</td>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=native-friction-review"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/native-friction-review.png" width="250" alt="Nonlinear friction review in the Tuba viewer"></a><br><b>Nonlinear friction</b><br>How does friction change the same pipe and load path?</td>
</tr>
<tr>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=pipe-tee-volume-review"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/pipe-tee-volume-review.png" width="250" alt="3D solid review in the Tuba viewer"></a><br><b>3D solid</b><br>Does stress concentrate where the branch meets the header?</td>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=elements-supports-review"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/elements-supports-review.png" width="250" alt="Elements and supports review in the Tuba viewer"></a><br><b>Elements and supports</b><br>Do bars, cables and spring supports survive the trip to the solver?</td>
<td><a href="https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=imported_component_mixed_demo"><img src="https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/imported_component_mixed_demo.png" width="250" alt="Imported components model review in the Tuba viewer"></a><br><b>Imported components</b><br>How does a supplied component join an authored line?</td>
</tr>
</table>

## Example

Define a pipe with two straight runs, a bend, anchored ends, and an operating
load case, then solve it with Code_Aster:

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
- Route lines automatically around obstacles, including expansion loops for hot
  lines.
- Analyse with beam, `TUYAU` pipe-wall or full 3D solid idealisations.
- Recover deflection, wall stress, element forces and support reactions.
- Check operating-state clearances against the deformed line and apply your own
  design rules.
- Display results in PyVista or the web viewer, export glTF, PLY or Blender files, and
  exchange with IFC.

## Getting started

Tuba needs Python 3.11 or 3.12.

```bash
git clone --branch v4.0.1 --depth 1 https://github.com/jgwagenfeld/Tuba_v4.git
cd Tuba_v4
python -m venv .venv
.venv/bin/python -m pip install .        # Windows: .\.venv\Scripts\python.exe
```

Analysis requires [Code_Aster](https://code-aster.org), installed separately.
Modeling, geometric routing, and viewing existing results do not require a local
solver installation. On Windows, the supported solver setup uses WSL2 Ubuntu.

**[Setup →](https://jgwagenfeld.github.io/Tuba_v4/setup.html)** ·
**[Tutorial →](https://jgwagenfeld.github.io/Tuba_v4/tutorial.html)** ·
**[Examples →](https://jgwagenfeld.github.io/Tuba_v4/examples.html)** ·
**[Documentation →](https://jgwagenfeld.github.io/Tuba_v4/)**

## Solver results

Stress, displacement, and reaction results require a completed Code_Aster run
and imported result files. Exporting `.comm`, `.mail`, and `.export` input files
does not run an analysis. Imported results retain model and study identifiers
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
