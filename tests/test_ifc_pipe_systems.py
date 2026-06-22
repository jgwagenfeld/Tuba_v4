import tempfile
import unittest
from pathlib import Path

import ifcopenshell

from tuba import Model
from tuba.external.ifc import IfcExporter


class TestIfcPipeSystems(unittest.TestCase):
    def _model(self):
        model = Model(project_name="PipeSystemIfc")
        model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0)
        model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
        n0 = model.add_node((0.0, 0.0, 0.0))
        n1 = model.add_node((1.0, 0.0, 0.0))
        n2 = model.add_node((1.0, 1.0, 0.0))
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="DN100", material="Steel")
        model.add_element(
            id="pipe_bend_0",
            type="pipe_bend",
            n1=n1,
            n2=n2,
            section="DN100",
            material="Steel",
            bend_radius=0.25,
            bend_angle=90.0,
        )
        return model

    def test_export_groups_pipe_segments_into_distribution_system(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pipes.ifc"
            IfcExporter().export_model(self._model(), path)
            f = ifcopenshell.open(str(path))

        systems = f.by_type("IfcDistributionSystem")
        self.assertEqual(len(systems), 1)
        self.assertEqual(systems[0].Name, "PipeSystemIfc")

        segments = f.by_type("IfcPipeSegment")
        fittings = f.by_type("IfcPipeFitting")
        self.assertEqual(len(segments), 1)
        self.assertEqual(len(fittings), 1)

        assigned = []
        for rel in f.by_type("IfcRelAssignsToGroup"):
            if rel.RelatingGroup == systems[0]:
                assigned.extend(rel.RelatedObjects)
        self.assertEqual({obj.Name for obj in assigned}, {"pipe_0", "pipe_bend_0"})

    def test_pipe_products_have_axis_and_body_representations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pipes.ifc"
            IfcExporter().export_model(self._model(), path)
            f = ifcopenshell.open(str(path))

        product = next(p for p in f.by_type("IfcPipeSegment") if p.Name == "pipe_0")
        identifiers = {rep.RepresentationIdentifier for rep in product.Representation.Representations}
        self.assertIn("Axis", identifiers)
        self.assertIn("Body", identifiers)
