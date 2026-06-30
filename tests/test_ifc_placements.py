import tempfile
import unittest
from pathlib import Path

from tuba.external.ifc import _HAS_IFCOPENSHELL
from tuba.placements import PlacementFrame


@unittest.skipUnless(_HAS_IFCOPENSHELL, "ifcopenshell is not installed")
class TestIfcPlacements(unittest.TestCase):
    def test_create_axis2placement_from_frame(self):
        import ifcopenshell

        from tuba.external.ifc_placements import create_axis2placement3d

        ifc_file = ifcopenshell.file(schema="IFC4")
        placement = create_axis2placement3d(
            ifc_file,
            PlacementFrame(
                id="rack_A",
                origin=(1.0, 2.0, 3.0),
                axis=(0.0, 0.0, 1.0),
                ref_direction=(0.0, 1.0, 0.0),
            ),
        )

        self.assertTrue(placement.is_a("IfcAxis2Placement3D"))
        self.assertEqual(tuple(float(v) for v in placement.Location.Coordinates), (1.0, 2.0, 3.0))
        self.assertEqual(tuple(float(v) for v in placement.RefDirection.DirectionRatios), (0.0, 1.0, 0.0))


@unittest.skipUnless(_HAS_IFCOPENSHELL, "ifcopenshell is not installed")
class TestIfcPlacementExport(unittest.TestCase):
    def test_export_uses_native_product_placement_when_available(self):
        import ifcopenshell

        from tuba import Model
        from tuba.external.ifc import IfcExporter
        from tuba.placements import PlacementAssignment

        model = Model("IfcPlacement")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        with model.pipe(section="PipeSec", material="Steel") as b:
            b.start([10.0, 20.0, 0.0]).run(1.0)
        elem = model.elements[0]
        model.placement_frames["pipe_frame"] = PlacementFrame(
            id="pipe_frame",
            origin=(10.0, 20.0, 0.0),
            frame_type="product",
        )
        model.placement_assignments.append(
            PlacementAssignment(
                target=f"element:{elem.id}",
                frame="placement_frame:pipe_frame",
                role="object_placement",
                source="native",
            )
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "placement.ifc"
            IfcExporter().export_model(model, path)
            ifc_file = ifcopenshell.open(str(path))
            product = ifc_file.by_type("IfcPipeSegment")[0]

        self.assertIsNotNone(product.ObjectPlacement)
        self.assertTrue(product.ObjectPlacement.RelativePlacement.is_a("IfcAxis2Placement3D"))


@unittest.skipUnless(_HAS_IFCOPENSHELL, "ifcopenshell is not installed")
class TestIfcPlacementImport(unittest.TestCase):
    def test_extract_frame_from_ifc_local_placement(self):
        import ifcopenshell

        from tuba.external.ifc_placements import create_local_placement, frame_from_local_placement

        ifc_file = ifcopenshell.file(schema="IFC4")
        original = PlacementFrame(
            id="frame_1",
            origin=(1.0, 2.0, 3.0),
            axis=(0.0, 0.0, 1.0),
            ref_direction=(0.0, 1.0, 0.0),
            source="ifc",
        )
        local_placement = create_local_placement(ifc_file, original)

        imported = frame_from_local_placement("frame_1", local_placement)

        self.assertEqual(imported.origin, original.origin)
        self.assertEqual(imported.axis, original.axis)
        self.assertEqual(imported.ref_direction, original.ref_direction)


if __name__ == "__main__":
    unittest.main()
