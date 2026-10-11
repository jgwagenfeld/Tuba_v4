"""Thermal-only starter for the LLM design benchmark; geometry is editable.

Keep the material, section, Hot operation, nozzle coordinates and anchors fixed.
Run the benchmark evaluator for actual reactions before judging this design.
"""

from tuba import Model

NOZZLE_DISTANCE = 12.0
BEND_RADIUS = 0.3
LOOP_RISE = 0.4  # straight length between the two bends on each loop leg [m]
LOOP_CROWN = 2.0  # straight length across the top of the loop [m]
APPROACH = (NOZZLE_DISTANCE - LOOP_CROWN - 4 * BEND_RADIUS) / 2

model = Model('LLM thermal flexibility benchmark')
model.add_material('Steel', E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
model.add_pipe_section('DN100', OD=0.1143, WT=0.00602)
model.define_load_case('Hot', gravity=False, temperature=200.0, ref_temperature=20.0)

with model.pipe(section='DN100', material='Steel') as pipe:
    pipe.start([0., 0., 0.], support='anchor').run(APPROACH)
    pipe.bend(radius=BEND_RADIUS, angle=90., axis=[0., 0., 1.])
    pipe.run(LOOP_RISE)
    pipe.bend(radius=BEND_RADIUS, angle=-90., axis=[0., 0., 1.])
    pipe.run(LOOP_CROWN)
    pipe.bend(radius=BEND_RADIUS, angle=-90., axis=[0., 0., 1.])
    pipe.run(LOOP_RISE)
    pipe.bend(radius=BEND_RADIUS, angle=90., axis=[0., 0., 1.])
    pipe.run(APPROACH).end(support='anchor')

model.validate()
