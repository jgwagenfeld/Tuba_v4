"""A pressurised DN100 line held by two anchors, with two bends between them."""

from tuba import Model

model = Model("VizGalleryDemo")
model.add_material(
    "Steel",
    E=2.1e11,
    nu=0.3,
    rho=7850.0,
    alpha=1.2e-5,
    allowable_stress={20.0: 137e6, 150.0: 127e6},
)
model.add_pipe_section("DN100", OD=0.1143, WT=0.00602, corrosion_allowance=0.001)
model.define_load_case(
    "Operating",
    gravity=True,
    pressure=1.5e6,
    temperature=150.0,
    ref_temperature=20.0,
)
with model.pipe(section="DN100", material="Steel") as builder:
    builder.start([0.0, 0.0, 0.0], support="anchor")
    builder.run(3.0)
    builder.add_support(type="guide")
    builder.bend(radius=0.3, angle=90.0, plane="XY")
    builder.run(2.0)
    builder.add_support(type="rest")
    builder.bend(radius=0.3, angle=90.0, plane="XZ")
    builder.run(3.0)
    builder.end(support="anchor")
model.validate()
