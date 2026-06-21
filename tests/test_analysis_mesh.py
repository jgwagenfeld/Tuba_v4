import unittest

from tuba.analysis import AnalysisMesh, MeshElementSource, MeshNodeSource
from tuba.refs import EntityRef


class TestAnalysisMesh(unittest.TestCase):
    def test_analysis_mesh_roundtrips_source_refs(self):
        mesh = AnalysisMesh(
            id="mesh_hot",
            model_revision=7,
            solver_name="code_aster",
            nodes={"N0": (0.0, 0.0, 0.0), "pipe_bend_0_n1": (0.5, 0.1, 0.0)},
            elements={"pipe_bend_0_s0": ("N0", "pipe_bend_0_n1")},
            groups={"G_PIPE": ("pipe_bend_0_s0",)},
            node_sources={
                "N0": MeshNodeSource(node_id="N0", source_ref=EntityRef("node", "N0"), role="native_node"),
                "pipe_bend_0_n1": MeshNodeSource(
                    node_id="pipe_bend_0_n1",
                    source_ref=EntityRef("element", "pipe_bend_0"),
                    role="generated_bend_node",
                    parametric_t=0.25,
                    segment_index=1,
                ),
            },
            element_sources={
                "pipe_bend_0_s0": MeshElementSource(
                    element_id="pipe_bend_0_s0",
                    source_ref=EntityRef("element", "pipe_bend_0"),
                    role="bend_segment",
                    segment_index=0,
                )
            },
            files={"mail": "study.mail"},
        )

        loaded = AnalysisMesh.from_dict(mesh.to_dict())

        self.assertEqual(loaded, mesh)
        self.assertEqual(str(loaded.node_sources["pipe_bend_0_n1"].source_ref), "element:pipe_bend_0")
        self.assertEqual(loaded.nodes["pipe_bend_0_n1"], (0.5, 0.1, 0.0))

    def test_analysis_mesh_rejects_sources_for_missing_mesh_entities(self):
        with self.assertRaises(ValueError):
            AnalysisMesh(
                id="mesh_hot",
                model_revision=7,
                solver_name="code_aster",
                nodes={"N0": (0.0, 0.0, 0.0)},
                elements={},
                groups={},
                node_sources={
                    "missing": MeshNodeSource(
                        node_id="missing",
                        source_ref=EntityRef("node", "N0"),
                        role="native_node",
                    )
                },
                element_sources={},
            )


if __name__ == "__main__":
    unittest.main()
