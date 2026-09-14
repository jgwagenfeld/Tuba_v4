import unittest

import numpy as np

from tuba import Model
from tuba.analysis import AnalysisMesh, GeometryState, MeshElementSource, MeshNodeSource, ResultState
from tuba.analysis.projection import project_deformed_centerline
from tuba.refs import EntityRef


class TestDeformedProjection(unittest.TestCase):
    def _model(self):
        model = Model(project_name="Projection")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        return model

    def test_straight_projection_uses_endpoint_displacements_and_safety_factor(self):
        model = self._model()
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        elem = model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        cold_n0 = model.nodes[n0].coords.copy()
        state = _result_state(
            {
                n0: (0.0, 0.10, 0.0, 0.0, 0.0, 0.0),
                n1: (0.0, 0.20, 0.0, 0.0, 0.0, 0.0),
            }
        )
        geometry = GeometryState(
            id="geometry_state:hot:physical",
            model_revision=0,
            state_type="operating",
            load_case="Hot",
            result_state_id=state.id,
            safety_factor=2.0,
        )

        projected = project_deformed_centerline(model=model, element=elem, result_state=state, geometry_state=geometry)

        self.assertEqual(projected.diagnostics, ())
        self.assertEqual(projected.points, ((0.0, 0.20, 0.0), (1.0, 0.40, 0.0)))
        self.assertTrue(np.allclose(model.nodes[n0].coords, cold_n0))

    def test_bend_projection_uses_generated_analysis_mesh_nodes_when_available(self):
        model = self._model()
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 1.0, 0.0])
        elem = model.add_element(
            id="pipe_bend_0",
            type="pipe_bend",
            n1=n0,
            n2=n1,
            section="PipeSec",
            material="Steel",
            bend_radius=1.0,
            bend_angle=90.0,
        )
        mesh = AnalysisMesh(
            id="mesh_hot",
            model_revision=0,
            solver_name="Code_Aster",
            nodes={n0: (0.0, 0.0, 0.0), "pipe_bend_0_n1": (0.5, 0.5, 0.0), n1: (1.0, 1.0, 0.0)},
            elements={"pipe_bend_0_s0": (n0, "pipe_bend_0_n1"), "pipe_bend_0_s1": ("pipe_bend_0_n1", n1)},
            groups={"pipe_bend_0": ("pipe_bend_0_s0", "pipe_bend_0_s1")},
            node_sources={
                n0: MeshNodeSource(node_id=n0, source_ref=EntityRef("node", n0), role="native_node"),
                "pipe_bend_0_n1": MeshNodeSource(
                    node_id="pipe_bend_0_n1",
                    source_ref=EntityRef("element", elem.id),
                    role="generated_bend_node",
                    parametric_t=0.5,
                    segment_index=1,
                ),
                n1: MeshNodeSource(node_id=n1, source_ref=EntityRef("node", n1), role="native_node"),
            },
            element_sources={
                "pipe_bend_0_s0": MeshElementSource("pipe_bend_0_s0", EntityRef("element", elem.id), "bend_segment", 0),
                "pipe_bend_0_s1": MeshElementSource("pipe_bend_0_s1", EntityRef("element", elem.id), "bend_segment", 1),
            },
        )
        state = _result_state(
            {
                n0: (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
                "pipe_bend_0_n1": (0.0, 0.1, 0.0, 0.0, 0.0, 0.0),
                n1: (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            },
            mesh_id=mesh.id,
        )
        geometry = GeometryState("geometry_state:hot:physical", 0, "operating", "Hot", state.id)

        projected = project_deformed_centerline(
            model=model,
            element=elem,
            result_state=state,
            geometry_state=geometry,
            analysis_mesh=mesh,
        )

        self.assertEqual(projected.points, ((0.0, 0.0, 0.0), (0.5, 0.6, 0.0), (1.0, 1.0, 0.0)))
        self.assertEqual(projected.source_mesh_nodes, (n0, "pipe_bend_0_n1", n1))
        self.assertEqual(projected.diagnostics, ())

    def test_bend_projection_falls_back_to_endpoint_interpolation_with_diagnostic(self):
        model = self._model()
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 1.0, 0.0])
        elem = model.add_element(
            id="pipe_bend_0",
            type="pipe_bend",
            n1=n0,
            n2=n1,
            section="PipeSec",
            material="Steel",
            bend_radius=1.0,
            bend_angle=90.0,
        )
        state = _result_state({n0: (0.0, 0.0, 0.0, 0.0, 0.0, 0.0), n1: (0.1, 0.0, 0.0, 0.0, 0.0, 0.0)})
        geometry = GeometryState("geometry_state:hot:physical", 0, "operating", "Hot", state.id)

        projected = project_deformed_centerline(model=model, element=elem, result_state=state, geometry_state=geometry)

        self.assertEqual(projected.points, ((0.0, 0.0, 0.0), (1.1, 1.0, 0.0)))
        self.assertIn("bend_displacement_interpolated", projected.diagnostics)


def _result_state(displacements, *, mesh_id=None):
    return ResultState(
        id="result_hot",
        study_id="study_hot",
        model_revision=0,
        solver_name="Code_Aster",
        load_case="Hot",
        mesh_id=mesh_id,
        node_displacements=displacements,
        node_reactions={},
        element_results={},
    )


if __name__ == "__main__":
    unittest.main()
