"""Authored thermal route and guide proposal; evaluate with real Code_Aster."""

from tuba import Model


def expansion_line(model, *, distance, radius, rise, crown, section, material):
    """Build one anchored planar expansion line.

    distance is nozzle spacing; radius is the bend radius; rise and crown are
    straight loop-leg and top lengths, all in metres. section and material name
    existing model definitions. Return the two approach midpoint nodes.
    """
    approach = (distance - crown - 4 * radius) / 2
    if min(approach, radius, rise, crown) <= 0:
        raise ValueError('Expected positive bend/loop dimensions and approach length.')
    with model.pipe(section=section, material=material) as pipe:
        pipe.start([0., 0., 0.], support='anchor').run(approach / 2)
        first_guide = pipe.last_node_id
        pipe.run(approach / 2)
        for angle, length in ((90., rise), (-90., crown), (-90., rise), (90., approach / 2)):
            pipe.bend(radius=radius, angle=angle, axis=[0., 0., 1.]).run(length)
        second_guide = pipe.last_node_id
        pipe.run(approach / 2).end(support='anchor')
    return first_guide, second_guide


LOOP_RISE = 0.4
GUIDE_DIRECTION = [0., 0., 1.]

model = Model('Authored piping iteration with approach guides')
model.add_material('Steel', E=2.1e11, nu=0.3, rho=7850., alpha=1.2e-5)
model.add_pipe_section('DN100', OD=0.1143, WT=0.00602)
model.define_load_case('Hot', gravity=False, temperature=200., ref_temperature=20.)
guide_nodes = expansion_line(model, distance=12., radius=.3, rise=LOOP_RISE,
                             crown=2., section='DN100', material='Steel')
for node in guide_nodes:
    model.add_support(node, 'guide', direction=GUIDE_DIRECTION)
model.validate()
