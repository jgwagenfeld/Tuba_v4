# Profile orientation: the same force at 0, 45 and 90 degrees

[Open the solved comparison](../../gallery/profile-orientation-review/index.html)

One model contains three disconnected, identical 3 m IPE100 cantilevers with
0, 45 and 90 degree section roll. All roots are anchored. Gravity is disabled;
the only difference between the members is their roll and physical offset, and
every tip carries the same 500 N force in global -Z.

Because the load is identical everywhere, the difference the review shows is
the section orientation alone: the 0 degree member bends about its weak local y
axis, the 90 degree member about its strong local z axis, and the 45 degree
member combines both responses. The force is authored once per tip in the single
`global` load case, so there is no second loading pattern to read the arrows
against.

The I-section surfaces use solved nodal translations and rotations. The
original outline is a faint reference. The deformation control exaggerates
both translations and rotation vectors by the same factor; it never changes
reported solver values. Section frames remain rigid as that factor changes.

The two independent annotation layers distinguish **Original local basis**
from **Solved section frames**, at root, midspan and tip. Red is local x, green
local y, and blue local z. These are section axes, not the viewer's global axes.

The model is `examples/profile-orientation-review/model.py` and its review is
`study.py` beside it. `python -m tuba.project examples/profile-orientation-review
--output <dir>` solves the case into the project's `evidence/global` folder,
reusing evidence that still matches (`--force` solves again); add
`--artifact-dir examples/profile-orientation-review/evidence/global` to import
the attested folder without solving. The bundle includes the complete evidence
chain under `artifacts/global`, and `orientation-checks.json` records solved tip
translations and rotations. Publication checks their signs and magnitudes
against cantilever bending equations. These beam results are not a piping-code
compliance assessment.

For the committed real solve, tip displacements are:

| Roll | Tip global Z (mm) |
| --- | ---: |
| 0 degrees | -141.371 |
| 45 degrees | -77.287 |
| 90 degrees | -13.203 |

The 45 degree case also moves +64.084 mm in global Y. The weak/strong
Z response ratio is 10.708. These are linear POU_D_T results, including shear
flexibility; they are independent of the display exaggeration.
