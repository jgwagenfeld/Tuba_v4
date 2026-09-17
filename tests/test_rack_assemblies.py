import unittest

from tuba import Model
from tuba.assemblies import RackBay, RackCorner, RackRow, rack_assemblies
from tuba.clash import ClashEngine
from tuba.patches import AddElement, ModelTransaction
from tuba.schema import validate_patch_dict


class TestRackAssemblies(unittest.TestCase):
    def _model(self):
        model = Model(project_name="Rack")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_rectangular_section("RackSec", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
        return model

    def test_rack_bay_generates_patch_without_mutating_model(self):
        model = self._model()
        rack = RackBay(
            name="rack_A",
            origin=(0.0, 0.0, 0.0),
            length=4.0,
            width=1.0,
            height=3.0,
            levels=(1.5, 3.0),
            section="RackSec",
            material="Steel",
            zone="north",
        )

        patch = rack.to_patch()
        validate_patch_dict(patch.to_dict())

        self.assertEqual(len(model.nodes), 0)
        self.assertGreaterEqual(len(patch.operations), 15)
        self.assertEqual(patch.provenance["assembly"], "rack_A")

    def test_rack_bay_identity_and_attachment_points_roundtrip(self):
        model = self._model()
        rack = RackBay(
            name="rack_A",
            origin=(10.0, 0.0, 0.0),
            length=4.0,
            width=1.0,
            height=3.0,
            levels=(1.5, 3.0),
            section="RackSec",
            material="Steel",
            zone="north",
        )

        result = ModelTransaction(model).apply(rack.to_patch())
        loaded = Model.from_dict(model.to_dict())

        self.assertEqual(result.group_names, ["rack_A"])
        self.assertIn("rack_A", loaded.groups)
        group = loaded.groups["rack_A"]
        self.assertEqual(group["metadata"]["assembly_type"], "rack_bay")
        self.assertEqual(group["metadata"]["zone"], "north")
        self.assertGreaterEqual(len(group["elements"]), 12)
        self.assertTrue(group["metadata"]["attachment_points"]["level_1_left"].startswith("node:N"))
        self.assertEqual(loaded.get_attributes("group:rack_A")["rack.zone"], "north")

    def test_rack_assemblies_reports_bay_points_as_node_ids(self):
        model = self._model()
        rack = RackBay(
            name="rack_A",
            origin=(10.0, 0.0, 0.0),
            length=4.0,
            width=1.0,
            height=3.0,
            levels=(1.5, 3.0),
            section="RackSec",
            material="Steel",
            zone="north",
        )
        ModelTransaction(model).apply(rack.to_patch())

        records = rack_assemblies(model)

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.group_name, "rack_A")
        self.assertEqual(record.assembly_type, "rack_bay")
        self.assertEqual(record.levels, (1.5, 3.0))
        self.assertEqual(record.zone, "north")
        self.assertEqual(
            set(record.attachment_points),
            {"level_1_left", "level_1_right", "level_2_left", "level_2_right"},
        )
        for node_id in record.attachment_points.values():
            self.assertIn(node_id, record.nodes)
            self.assertIn(node_id, model.nodes)

    def test_rack_bay_assigns_sections_by_member_role(self):
        rack = RackBay(
            name="rack_A",
            origin=(0.0, 0.0, 0.0),
            length=4.0,
            width=1.0,
            height=3.0,
            levels=(1.5, 3.0),
            section="Fallback",
            material="Steel",
            column_section="ColumnIPE",
            longitudinal_section="LongRHS",
            transverse_section="CrossRHS",
        )

        members = [operation for operation in rack.to_patch().operations if isinstance(operation, AddElement)]

        self.assertEqual(
            {member.section for member in members if "_col_" in member.local_id},
            {"ColumnIPE"},
        )
        self.assertEqual(
            {member.section for member in members if "_long_" in member.local_id},
            {"LongRHS"},
        )
        self.assertEqual(
            {member.section for member in members if "_cross_" in member.local_id},
            {"CrossRHS"},
        )


class TestRackRow(unittest.TestCase):
    def _model(self):
        model = Model(project_name="RackRow")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_rectangular_section("RackSec", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
        return model

    def _row(self, **overrides):
        params = dict(
            name_prefix="rack_A",
            origin=(-10.0, 0.0, -3.0),
            material="Steel",
            section="RackSec",
            direction="X",
            bays=2,
            bay_length=2.0,
            width=2.0,
            height=3.0,
            levels=(2.75,),
            shoe_level=2.75,
            zone="yard",
        )
        params.update(overrides)
        return RackRow(**params)

    def test_row_is_one_continuous_frame_with_midpoint_hangers(self):
        model = self._model()
        pipe = [model.add_node([x, 1.0, 0.0]) for x in (-10.0, -8.0, -6.0)]
        row = self._row(shoes=tuple((node, station) for station, node in enumerate(pipe)))

        validate_patch_dict(row.to_patch().to_dict())
        result = ModelTransaction(model).apply(row.to_patch())

        self.assertEqual(result.group_names, ["rack_A0", "rack_A1"])
        # Shared station nodes: 3 stations, not 4 bay ends.
        self.assertEqual(len(model.nodes), 3 + 3 * 2 * 3 + 3)
        rests = [s for s in model.supports if s.type == "rest"]
        self.assertEqual(len(rests), 3)
        for support in rests:
            pipe_node = model.nodes[support.node]
            beam_node = model.nodes[support.attached_to]
            self.assertAlmostEqual(pipe_node.coords[0], beam_node.coords[0])
            self.assertAlmostEqual(pipe_node.coords[1], beam_node.coords[1])
            self.assertAlmostEqual(pipe_node.coords[2] - beam_node.coords[2], 0.25)
        self.assertEqual(row.station_point(1), (-8.0, 1.0, -0.25))

    def test_row_marches_along_y_with_the_pipe_mid_width(self):
        model = self._model()
        row = self._row(name_prefix="rack_B", origin=(0.0, 0.0, -3.0), direction="Y", shoes=())

        validate_patch_dict(row.to_patch().to_dict())
        ModelTransaction(model).apply(row.to_patch())

        self.assertEqual(row.station_point(0), (1.0, 0.0, -0.25))
        self.assertEqual(row.station_point(2), (1.0, 4.0, -0.25))
        mid = next(node for node in model.nodes.values() if abs(node.coords[1] - 2.0) < 1e-9 and abs(node.coords[0] - 1.0) < 1e-9 and abs(node.coords[2] + 0.25) < 1e-9)
        self.assertIsNotNone(mid)

    def test_row_rejects_bad_geometry(self):
        with self.assertRaises(ValueError):
            self._row(direction="Z").to_patch()
        with self.assertRaises(ValueError):
            self._row(bays=0).to_patch()
        with self.assertRaises(ValueError):
            self._row(shoe_level=9.0).to_patch()
        with self.assertRaises(ValueError):
            self._row(shoes=(("N0", 7),)).to_patch()
        with self.assertRaises(ValueError):
            self._row(shoe_level=None, shoes=(("N0", 1),)).to_patch()

    def test_row_bays_carry_their_midpoint_attachment_points(self):
        model = self._model()
        pipe = [model.add_node([x, 1.0, 0.0]) for x in (-10.0, -8.0, -6.0)]
        row = self._row(shoes=tuple((node, station) for station, node in enumerate(pipe)))
        ModelTransaction(model).apply(row.to_patch())

        records = rack_assemblies(model)

        self.assertEqual([record.group_name for record in records], ["rack_A0", "rack_A1"])
        self.assertTrue(all(record.assembly_type == "rack_row_bay" for record in records))
        self.assertTrue(all(record.levels == (2.75,) for record in records))
        self.assertTrue(all(record.zone == "yard" for record in records))
        self.assertEqual(
            {name for record in records for name in record.attachment_points},
            {"mid_0", "mid_1", "mid_2"},
        )
        # Station 1 belongs to both bays; stations 0 and 2 to one each.
        self.assertEqual(sum(len(record.attachment_points) for record in records), 4)
        for record in records:
            for node_id in record.attachment_points.values():
                self.assertIn(node_id, record.nodes)
                self.assertIn(node_id, model.nodes)

    def test_row_without_shoe_level_has_no_attachment_points(self):
        model = self._model()
        row = self._row(shoe_level=None, shoes=())
        ModelTransaction(model).apply(row.to_patch())

        records = rack_assemblies(model)

        self.assertEqual([record.group_name for record in records], ["rack_A0", "rack_A1"])
        self.assertTrue(all(record.attachment_points == {} for record in records))

    def test_row_builds_each_cross_beam_once(self):
        model = self._model()
        row = self._row(shoe_level=None, shoes=())
        ModelTransaction(model).apply(row.to_patch())

        self.assertEqual(ClashEngine().check_self(model), [])
        self.assertEqual(ClashEngine().check_duplicate_nodes(model), [])

    def test_open_start_leaves_station_zero_for_the_corner(self):
        model = self._model()
        row = self._row(shoe_level=None, shoes=(), open_start=True)
        ModelTransaction(model).apply(row.to_patch())

        # Bay 0 still connects through its station-0 nodes, but brings no
        # station-0 members of its own.
        self.assertEqual(ClashEngine().check_self(model), [])
        with self.assertRaises(ValueError):
            self._row(shoe_level=2.75, shoes=(("N0", 0)), open_start=True).to_patch()


class TestRackCorner(unittest.TestCase):
    def _model(self):
        model = Model(project_name="RackCorner")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_rectangular_section("RackSec", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
        return model

    def _first(self, **overrides):
        params = dict(
            name_prefix="rack_A",
            origin=(0.0, 0.0, 0.0),
            material="Steel",
            section="RackSec",
            direction="X",
            bays=3,
            bay_length=2.0,
            width=2.0,
            height=3.0,
            levels=(2.75,),
        )
        params.update(overrides)
        return RackRow(**params)

    def test_clean_corner_reports_no_clash(self):
        model = self._model()
        corner = RackCorner(name_prefix="rack_B", first=self._first(), turn="left", bays=2)

        self.assertEqual(corner.second_direction(), "Y")
        self.assertEqual(corner.second_origin(), (6.0, 2.0, 0.0))
        validate_patch_dict(corner.to_patch().to_dict())
        ModelTransaction(model).apply(corner.to_patch())

        self.assertEqual(ClashEngine().check_self(model), [])
        self.assertEqual(ClashEngine().check_duplicate_nodes(model), [])
        self.assertIn("rack_B0", model.groups)

    def test_second_patch_repairs_onto_an_existing_row(self):
        model = self._model()
        first = self._first()
        ModelTransaction(model).apply(first.to_patch())
        corner = RackCorner(name_prefix="rack_B", first=first, turn="left", bays=2)

        ModelTransaction(model).apply(corner.second_patch())

        self.assertEqual(ClashEngine().check_self(model), [])
        self.assertEqual(ClashEngine().check_duplicate_nodes(model), [])

    def test_y_row_turning_right(self):
        model = self._model()
        first = self._first(direction="Y", origin=(0.0, 0.0, 0.0))
        corner = RackCorner(name_prefix="rack_B", first=first, turn="right", bays=1)

        self.assertEqual(corner.second_direction(), "X")
        self.assertEqual(corner.second_origin(), (2.0, 6.0, 0.0))
        ModelTransaction(model).apply(corner.to_patch())

        self.assertEqual(ClashEngine().check_self(model), [])

    def test_inexpressible_turns_fail_loudly(self):
        with self.assertRaises(ValueError):
            RackCorner(name_prefix="x", first=self._first(direction="X"), turn="right", bays=1).second_origin()
        with self.assertRaises(ValueError):
            RackCorner(name_prefix="x", first=self._first(direction="Y"), turn="left", bays=1).second_direction()
        with self.assertRaises(ValueError):
            RackCorner(name_prefix="x", first=self._first(), turn="left", bays=0).second_row()
        with self.assertRaises(ValueError):
            RackCorner(
                name_prefix="x", first=self._first(), turn="left", bays=2, shoes=(("N0", 0),)
            ).second_row()


if __name__ == "__main__":
    unittest.main()
