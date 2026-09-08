# Pipe insulation

Assign an insulation spec with material, thickness in metres and density in
kg/m³ using `add_insulation_spec` and `assign_insulation`. Positive thickness
requires positive density when solving gravity loads.

The static line-element compiler carries insulation mass through equivalent
section density: `(steel mass/m + insulation mass/m) / steel area`. Steel
stiffness, thermal expansion and pipe-wall dimensions stay unchanged. This is
non-structural insulation, not a bonded composite section or thermal-conduction
model. Insulation changes invalidate the solver-input identity.

Wind loading on the supported beam path uses the insulated outside diameter.
Clash checks use the insulated radius, plus any explicitly requested additional
clearance. Clearance is empty space and adds neither weight nor wind area.
TUYAU wind and insulated 3D-volume studies remain explicitly unsupported and
must fail before evaluation rather than omit loads.

The viewer draws an independently controlled **Insulation** shell only when
insulation is assigned, labelled with material and thickness. Bare-pipe, wind
and clearance envelopes are not display surfaces, including in older bundles.
Solver reactions use `REAC_NODA`, not internal nodal forces `FORC_NODA`.

Verification: `TUBA_RUN_CODE_ASTER_INTEGRATION=1 python -m pytest
tests/test_insulation_solver.py` runs real gravity and wind solves and compares
support forces and moments with independent total-load calculations.
