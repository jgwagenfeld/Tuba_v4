# Prepare load cases for user-owned checks

Run from the repository root, after configuring a working Code_Aster runtime:

```powershell
python -m tuba.cli_studio examples/load-case-preparation
python -m tuba.project examples/load-case-preparation --output .build/load-case-preparation
python -m tuba.visualization.viewer .build/load-case-preparation/review_scene --open
```

The project solves all four states with Code_Aster, preserves attested evidence
under `evidence/<case>/`, and builds one web review containing all four states.
A missing runtime or failed solve stops the workflow. Existing matching evidence
is reused; add `--force` to solve again.

| Solved state | Inputs | User-owned check basis |
| --- | --- | --- |
| Sustained | Pipe self-weight; process at 1.5 MPa, return at 0.4 MPa; both at 20 C | Sustained forces and moments |
| OperatingHot | Same weight and pressure zones; process at 150 C, return cooling from 80 C to 40 C; reference 20 C | Hot response; compare with Sustained for expansion |
| Occasional | Sustained + a 500 N global +Y force at the first bend inlet | Illustrative sustained-plus-event combination |
| PressureOnly | Process at 1.5 MPa, return at 0.4 MPa; no gravity or temperature change | Isolated pressure response |

Edit the constants, material, section, geometry and operations in `model.py`.
The 500 N event is an illustrative static force, not a calculated wind or seismic
action. Gravity includes pipe self-weight only; contents, insulation, equipment
and other project loads must be supplied by the user. All factors here are 1.0.

## Local fields in Python

`model.py` is the authoring interface. The two separate lines make the pressure
zones explicit without imposing an unexplained pressure jump in a connected pipe.
The builder records the element IDs, so the assignments survive geometry changes
without hand-maintained coordinate or element lists:

```python
hot.add_field("temperature", HOT_C,
              element_ids=model.groups["ProcessLine"]["elements"])
operation.add_field("pressure", RETURN_PRESSURE_PA, group="ReturnLine")
```

The case's `temperature` and `pressure` are defaults for regions without a local
assignment. A field selects `element_ids`, `group`, or `route_id` (optionally
`station_start` / `station_end`). Incompatible assignments on the same element
are rejected; do not stack an element exception on an overlapping group field.

The return temperature is a continuous gradient rather than a staircase:

```python
field_from_route_table(model, hot, "temperature", "ReturnLine",
                       [(0.0, RETURN_INLET_C), (return_length, RETURN_OUTLET_C)])
```

This writes temperatures at model nodes, interpolated onto the Code_Aster mesh.
For a specific node use `hot.add_field("temperature", value, node_ids=[node_id])`.
Shared nodes have one temperature; keep nodal and element temperature assignments
on separate regions. The reference temperature remains a case-wide value.

In Studio, keep `model.py` open and use **Case → Input assignments** to inspect
the selected operation, highlight an assignment's elements, or jump to its Python
line. **Compare cases** shows the authored assignments across operations;
**Solver .comm** opens only the selected case's generated input. **Solve all**
evaluates the study with Code_Aster. Review shows the case-specific results and
input assignments; solver-input generation alone is not an engineering evaluation.

## Four check categories, four solved states

Expansion is a **range between states**, not a fifth independent solve. The
study writes `review_scene/user-check-forces.csv`, containing the four states
and `ExpansionRange = OperatingHot - Sustained`. Differences are calculated
component by component at the same element end and local basis. The CSV includes
both source result-state IDs. It never subtracts scalar von Mises stresses.

The CSV components are `N, Vy, Vz` in N and `Mx, My, Mz` in N m, in each
element's solver local axes; `Mx` is torsion. `n1` and `n2` retain the solver's
signed end convention. These are model-element end samples, **not a maximum
over every interior mesh station**. Use the accompanying raw `study_effo.csv`
and FEM mapping in the staged artifacts when checking interior sections.
Displacements, reactions, FE stresses and model inputs are in the standard
engineering review; all four attested solves are staged under `artifacts/`.
Applied-load arrows, result fields and reaction vectors follow the selected case.
The input inspector and report retain the local field definitions.

The material is linear elastic with constant properties, all anchors stay
fixed, and there are no gaps or friction contacts. Thus the state difference
isolates the thermal increment for this example. Contact changes, nonlinear
materials and other operating cycles require their own analysis strategy.

**Pressure design remains a separate calculation.** PressureOnly is neither a
wall-thickness compliance check nor a hydrotest. Users must supply their chosen
design pressure/temperature, permitted material stresses, corrosion and
manufacturing allowances, joint factors and applicable component rules.

## Add the engineering checks

Use the CSV and solved artifacts as inputs to independently verified checks:
sustained, expansion range, occasional and pressure design. Select the applicable
standard and edition externally, establish load combinations and allowables,
and apply any required fitting factors and fatigue/cycle rules. The occasional
state here is cold; add hot-plus-event states if the chosen assessment needs them.

No standard, material allowable, utilization or compliance verdict is assigned.
FE stress colours in the review describe the solved stress field only.
The example's `check(solved)` verifies complete finite force components and
distinct state responses; it does not perform engineering acceptance checks.
