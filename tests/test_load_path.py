import unittest
from pathlib import Path

from tuba import Model
from tuba.assemblies import RackBay, RackRow
from tuba.analysis import ResultState
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.load_path import analyze_load_paths
from tuba.patches import ModelTransaction
from tuba.project import load_project


class TestLoadPath(unittest.TestCase):
    def _rack_model(self):
        model = Model(project_name="LoadPath")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_rectangular_section("RackSec", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
        rack = RackBay(
            name="rack_A",
            origin=(0.0, 0.0, 0.0),
            length=4.0,
            width=1.0,
            height=3.0,
            levels=(1.5, 3.0),
            section="RackSec",
            material="Steel",
        )
        ModelTransaction(model).apply(rack.to_patch())
        return model

    def _attached_support(self, model, kind="rest"):
        rack_node = model.groups["rack_A"]["metadata"]["attachment_points"]["level_1_left"].split(":", 1)[1]
        x, y, z = model.nodes[rack_node].coords
        pipe_node = model.add_node([x, y + 0.1 * len(model.supports), z + 0.25])
        return model.add_support(node=pipe_node, type=kind, attached_to=rack_node), rack_node

    def test_attached_support_associates_to_its_rack(self):
        model = self._rack_model()
        support, rack_node = self._attached_support(model)
        report = analyze_load_paths(model)
        self.assertEqual(len(report.associations), 1)
        association = report.associations[0]
        self.assertEqual(str(association.support), f"support:{support.id}")
        self.assertEqual(str(association.rack), "group:rack_A")
        self.assertEqual(str(association.node), f"node:{rack_node}")
        self.assertEqual(association.attachment_point, "level_1_left")

    def test_rack_load_is_the_reaction_at_the_attached_node(self):
        model = self._rack_model()
        _support, rack_node = self._attached_support(model)
        report = analyze_load_paths(model, node_reactions={rack_node: (100.0, 0.0, -1000.0)})
        self.assertEqual(report.rack_loads["rack_A"]["support_count"], 1)
        self.assertEqual(report.rack_loads["rack_A"]["force_x_n"], 100.0)
        self.assertEqual(report.rack_loads["rack_A"]["force_z_n"], -1000.0)

    def test_two_supports_on_one_attached_node_count_its_reaction_once(self):
        model = self._rack_model()
        _first, rack_node = self._attached_support(model)
        self._attached_support(model, kind="guide")
        report = analyze_load_paths(model, node_reactions={rack_node: (0.0, 0.0, -1000.0)})
        self.assertEqual(report.rack_loads["rack_A"]["support_count"], 2)
        self.assertEqual(report.rack_loads["rack_A"]["force_z_n"], -1000.0)

    def test_result_state_reactions_roll_up_to_rack_loads(self):
        model = self._rack_model()
        _support, rack_node = self._attached_support(model)
        result_state = ResultState(
            id="result_hot",
            study_id="study_hot",
            model_revision=0,
            solver_name="Code_Aster",
            load_case="Hot",
            mesh_id=None,
            node_displacements={},
            node_reactions={rack_node: (100.0, 0.0, -1000.0, 0.0, 0.0, 0.0)},
            element_results={},
        )
        report = analyze_load_paths(model, result_state=result_state)
        self.assertEqual(report.rack_loads["rack_A"]["force_x_n"], 100.0)
        self.assertEqual(report.rack_loads["rack_A"]["force_z_n"], -1000.0)

    def test_grounded_support_on_a_rack_node_is_not_a_rack_load(self):
        model = self._rack_model()
        rack_node = model.groups["rack_A"]["metadata"]["attachment_points"]["level_1_left"].split(":", 1)[1]
        support = model.add_support(node=rack_node, type="rest")
        report = analyze_load_paths(model)
        self.assertEqual(report.associations, [])
        self.assertIn(f"Support {support.id!r} is not associated", " ".join(report.diagnostics))


class TestRackRowLoadPath(unittest.TestCase):
    def _row_model(self):
        model = Model(project_name="RowLoadPath")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_rectangular_section("RackSec", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
        pipe = [model.add_node([x, 1.0, 0.0]) for x in (0.0, 2.0, 4.0)]
        row = RackRow(
            name_prefix="rack_A",
            origin=(0.0, 0.0, -3.0),
            material="Steel",
            section="RackSec",
            bays=2,
            bay_length=2.0,
            width=2.0,
            height=3.0,
            levels=(2.75,),
            shoe_level=2.75,
            shoes=tuple((node, station) for station, node in enumerate(pipe)),
            anchor_feet=False,
        )
        ModelTransaction(model).apply(row.to_patch())
        return model

    def _mid_nodes(self, model):
        points = {}
        for group_name in ("rack_A0", "rack_A1"):
            for point_name, node_ref in model.groups[group_name]["metadata"]["attachment_points"].items():
                points[point_name] = node_ref.split(":", 1)[1]
        return points

    def test_row_shoes_associate_with_every_bay_they_span(self):
        model = self._row_model()
        report = analyze_load_paths(model)

        self.assertEqual(report.diagnostics, [])
        self.assertEqual(
            [(association.rack.id, association.attachment_point) for association in report.associations],
            [
                ("rack_A0", "mid_0"),
                ("rack_A0", "mid_1"),
                ("rack_A1", "mid_1"),
                ("rack_A1", "mid_2"),
            ],
        )

    def test_each_bay_carries_the_reactions_at_its_midpoints_once(self):
        model = self._row_model()
        mid = self._mid_nodes(model)
        report = analyze_load_paths(
            model,
            node_reactions={
                mid["mid_0"]: (0.0, 0.0, -100.0),
                mid["mid_1"]: (0.0, 0.0, -200.0),
                mid["mid_2"]: (0.0, 0.0, -300.0),
            },
        )

        self.assertEqual(report.rack_loads["rack_A0"]["support_count"], 2)
        self.assertEqual(report.rack_loads["rack_A0"]["force_z_n"], -300.0)
        self.assertEqual(report.rack_loads["rack_A1"]["support_count"], 2)
        self.assertEqual(report.rack_loads["rack_A1"]["force_z_n"], -500.0)


class RackRowExampleEvidence(unittest.TestCase):
    def test_the_bridge_line_loads_every_bay_midpoint(self):
        project = Path(__file__).resolve().parents[1] / "examples" / "rack_bridge_demo"
        model = load_project(project).run_model()["model"]
        run = import_code_aster_artifacts(model=model, work_dir=project / "evidence" / "Operating")

        report = analyze_load_paths(model, result_state=run.result_state)

        attached = [support for support in model.supports if support.attached_to is not None]
        grounded_ids = {support.id for support in model.supports if support.attached_to is None}
        self.assertEqual(len(attached), 5)
        # Five station shoes; the two inner stations belong to two bays each.
        self.assertEqual(len(report.associations), 8)
        self.assertTrue(all(association.attachment_point.startswith("mid_") for association in report.associations))
        # Every diagnostic names a grounded support: the shoes all found their rack.
        self.assertTrue(all(message.split("'")[1] in grounded_ids for message in report.diagnostics))
        self.assertEqual(set(report.rack_loads), {"bridge_rack0", "bridge_rack1", "bridge_rack2", "bridge_rack3"})
        for bay, loads in report.rack_loads.items():
            self.assertEqual(loads["support_count"], 2, bay)
            self.assertGreater(abs(loads["force_z_n"]), 0.0, bay)


if __name__ == "__main__":
    unittest.main()
