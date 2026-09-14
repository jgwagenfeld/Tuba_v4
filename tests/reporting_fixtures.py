"""Reusable authoritative-model fixtures for reporting tests."""

from __future__ import annotations

from tuba.model import BendGeometry, OperationField, TubaModel


def build_review_model() -> TubaModel:
    """Build a model that exercises every native one-dimensional section type."""
    model = TubaModel(project_name="HOT-100", standard="ASME_B31.3")
    model.revision = 4

    model.add_material(
        "Steel",
        E=2.0e11,
        nu=0.3,
        rho=7850.0,
        alpha=1.2e-5,
        allowable_stress={20.0: 138.0e6, 150.0: 112.0e6},
    )
    model.add_material(
        "Aluminium",
        E=69.0e9,
        nu=0.33,
        rho=2700.0,
        alpha=2.3e-5,
        allowable_stress={20.0: 95.0e6},
    )

    model.add_rectangular_section(
        "RectSec",
        height_y=0.2,
        height_z=0.1,
        thickness_y=0.01,
        thickness_z=0.008,
    )
    model.add_pipe_section(
        "PipeSec",
        OD=0.1143,
        WT=0.00602,
        corrosion_allowance=0.001,
    )
    model.add_bar_section("BarSec", OD=0.04, WT=0.005)
    model.add_cable_section("CableSec", radius=0.012, pretension=12000.0)
    model.add_ibeam_section("IBeamSec", "IPE100")

    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([3.0, 4.0, 0.0])
    n2 = model.add_node([4.0, 5.0, 0.0])
    n3 = model.add_node([4.0, 5.0, 2.5])

    model.add_element(
        id="E-20",
        type="pipe_straight",
        n1=n0,
        n2=n1,
        section="PipeSec",
        material="Steel",
        twist_angle=2.0,
        route_id="R-100",
        station_start=0.0,
        station_end=5.0,
    )
    model.add_element(
        id="E-10",
        type="pipe_bend",
        n1=n1,
        n2=n2,
        section="PipeSec",
        material="Steel",
        bend_radius=1.0,
        bend_angle=90.0,
        bend_geometry=BendGeometry(
            center=[3.0, 5.0, 0.0],
            normal=[0.0, 0.0, 1.0],
            radius=1.0,
            angle=90.0,
            start_tangent=[1.0, 0.0, 0.0],
            end_tangent=[0.0, 1.0, 0.0],
            generation_mode="bend_in_plane",
        ),
        route_id="R-100",
        station_start=5.0,
        station_end=6.570796326794897,
    )
    model.add_element(
        id="E-30",
        type="beam",
        n1=n2,
        n2=n3,
        section="RectSec",
        material="Aluminium",
    )

    model.add_support(
        node=n1,
        type="guide",
        direction=[0.0, 1.0, 0.0],
        stiffness=2.5e6,
        stiffness_matrix=[0.0, 2.5e6, 0.0, 0.0, 0.0, 0.0],
        blocked_dof=[False, True, False, False, False, False],
        friction_coefficient=0.15,
        id="SUP-2",
    )
    model.add_support(
        node=n0,
        type="anchor",
        blocked_dof=[True, True, True, True, True, True],
        imposed_displacement=[0.0, 0.0, 0.0],
        id="SUP-1",
    )

    hot = model.define_load_case(
        "Hot",
        gravity=True,
        pressure=2.5e6,
        temperature=150.0,
        ref_temperature=20.0,
    )
    hot.add_nodal_force(n3, [1000.0, 2000.0, -3000.0], [10.0, 20.0, 30.0])
    hot.fields.append(
        OperationField(
            quantity="temperature",
            value=175.0,
            scope="route",
            profile="uniform",
            route_id="R-100",
            station_start=1.0,
            station_end=4.0,
        )
    )

    operation = model.define_operation(
        "Upset",
        gravity=False,
        pressure=3.0e6,
        temperature=180.0,
        ref_temperature=20.0,
        metadata={"design_basis": "occasional"},
    )
    operation.add_field(
        "wind",
        850.0,
        route_id="R-100",
        station_start=0.0,
        station_end=5.0,
        direction=[0.0, 1.0, 0.0],
    )

    return model
