"""A guyed flagpole mast held by three pretensioned cables under a side load.

Cables are the reason this study is nonlinear. A cable takes no compression, so
the leeward guy sheds its load as the mast leans downwind and the two windward
guys pick it up - a redistribution ``MECA_STATIQUE`` cannot express.
The solver subdivides each guy and mast span; gravity produces sag in the
lightly loaded guy, which still carries tension from its own weight.
Increase ``CodeAsterSolver(line_segments=...)`` to check mesh convergence.
"""

import math

from tuba import Model

#: Overall mast height [m], and the height the guys attach at. The top 4 m
#: cantilevers above the guy collar, which is where a flagpole actually bends.
MAST_HEIGHT_M = 12.0
GUY_ATTACHMENT_M = 8.0
#: Ground-anchor radius [m]. Three anchors at 120 degrees.
ANCHOR_RADIUS_M = 6.0
GUY_COUNT = 3
#: Lateral wind resultant [N] applied at the mast top, in +X.
WIND_FORCE_N = 3000.0
#: Guy pretension [N]. Enough to keep every cable taut before the wind case,
#: which is what stops the mast from starting the solve as a mechanism.
GUY_PRETENSION_N = 5000.0

model = Model("Guyed_Mast_Review")
model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5, rho=7850)

# 219.1 x 8 CHS mast, 12 mm guy wire.
model.add_pipe_section("MastSec", OD=0.2191, WT=0.008)
# The guys are the point, so they are modelled as guys: near-zero compression
# stiffness lets the leeward one go slack instead of propping the mast up from
# the downwind side, which no wire can do.
model.add_cable_section(
    "GuySec",
    radius=0.006,
    pretension=GUY_PRETENSION_N,
    compression_modulus_ratio=1.0e-4,
)

# Two runs so the guy collar gets a node of its own to hang from.
with model.pipe(section="MastSec", material="Steel") as mast:
    mast.start([0.0, 0.0, 0.0], support="anchor")
    mast.set_direction([0.0, 0.0, 1.0])
    mast.beam(GUY_ATTACHMENT_M)
    mast.beam(MAST_HEIGHT_M - GUY_ATTACHMENT_M)
    top_node = mast.last_node_id

guy_length = math.hypot(ANCHOR_RADIUS_M, GUY_ATTACHMENT_M)
for index in range(GUY_COUNT):
    bearing = 2.0 * math.pi * index / GUY_COUNT
    anchor = [
        ANCHOR_RADIUS_M * math.cos(bearing),
        ANCHOR_RADIUS_M * math.sin(bearing),
        0.0,
    ]
    with model.pipe(section="GuySec", material="Steel") as guy:
        # start() reuses the collar node, so the guy hangs off the mast rather
        # than off a coincident free node beside it.
        guy.start([0.0, 0.0, GUY_ATTACHMENT_M])
        guy.set_direction([anchor[0], anchor[1], -GUY_ATTACHMENT_M])
        guy.cable(guy_length)
        model.add_support(node=guy.last_node_id, type="anchor")

load_case = model.define_load_case("Wind", gravity=True)
load_case.add_nodal_force(node=top_node, force=[WIND_FORCE_N, 0.0, 0.0])
