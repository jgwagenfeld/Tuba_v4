"""Supports: the closed type list and attachment to another node."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.load_path import analyze_load_paths
from tuba.model import SUPPORT_TYPES
from tuba.patches import ModelPatch, ModelTransaction
from tuba.project import load_project
from tuba.project.script import generate_model_script
from tuba.solver.aster import CodeAsterSolver
from tuba.validation import ModelValidationError


def cantilever():
    """A 6 m DN100 pipe along X with its two end nodes."""
    model = Model("Attach")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.006)
    root = model.add_node([0.0, 0.0, 0.0])
    tip = model.add_node([6.0, 0.0, 0.0])
    model.add_element(id="pipe", type="pipe_straight", n1=root, n2=tip, section="DN100", material="Steel")
    return model, root, tip


class SupportTypes(unittest.TestCase):
    def test_documented_types_are_accepted(self):
        self.assertEqual(SUPPORT_TYPES, ("anchor", "guide", "rest", "spring", "hanger", "custom"))
        model, _root, tip = cantilever()
        for kind in SUPPORT_TYPES:
            model.add_support(tip, kind)

    def test_unknown_type_is_refused_with_the_valid_types(self):
        model, _root, tip = cantilever()
        with self.assertRaisesRegex(
            ValueError, "Unknown support type 'sliding'; use one of anchor, guide, rest, spring, hanger, custom"
        ):
            model.add_support(tip, "sliding")


class SupportAttachment(unittest.TestCase):
    def test_attachment_round_trips_through_dict_script_and_patch(self):
        model, _root, tip = cantilever()
        rack = model.add_node([6.0, 0.0, -0.25])
        model.add_support(tip, "rest", attached_to=rack, id="shoe")
        self.assertEqual(Model.from_dict(model.to_dict()).supports[-1].attached_to, rack)
        self.assertIn(f"attached_to={rack!r}", generate_model_script(model))

        patched, _root, tip = cantilever()
        result = ModelTransaction(patched).apply(ModelPatch.from_dict({"operations": [
            {"op": "add_node", "local_id": "rack", "coords": [6.0, 0.0, -0.25]},
            {"op": "add_support", "node": tip, "type": "rest", "attached_to": "rack"},
        ]}))
        self.assertEqual(patched.supports[-1].attached_to, result.node_ids["rack"])

    def test_builder_carries_the_attachment(self):
        model, _root, _tip = cantilever()
        rack = model.add_node([0.0, 3.0, -0.25])
        with model.pipe(section="DN100", material="Steel") as builder:
            builder.start([0.0, 3.0, 0.0])
            builder.add_support("rest", attached_to=rack)
        self.assertEqual(model.supports[-1].attached_to, rack)

    def test_attachment_must_name_another_existing_node(self):
        model, _root, tip = cantilever()
        model.add_support(tip, "rest", attached_to="N99", id="lost")
        with self.assertRaisesRegex(ModelValidationError, "Support 'lost' is attached to missing node 'N99'"):
            model.validate()

    def test_a_support_cannot_attach_to_its_own_node(self):
        model, _root, tip = cantilever()
        model.add_support(tip, "rest", attached_to=tip, id="self")
        with self.assertRaisesRegex(ModelValidationError, "Support 'self' is attached to its own node"):
            model.validate()

    def test_attached_support_cannot_impose_a_displacement(self):
        model, _root, tip = cantilever()
        rack = model.add_node([6.0, 0.0, -0.25])
        model.add_support(tip, "anchor", attached_to=rack, imposed_displacement=[0.0, 0.0, 0.01], id="moved")
        with self.assertRaisesRegex(ModelValidationError, "Support 'moved' is attached to a node, so it cannot impose a displacement"):
            model.validate()

    def test_attached_spring_cannot_also_block_dofs(self):
        model, _root, tip = cantilever()
        rack = model.add_node([6.0, 0.0, -0.25])
        model.add_support(tip, "spring", attached_to=rack, stiffness_matrix=[0.0, 0.0, 1.0e7, 0.0, 0.0, 0.0], blocked_dof=[0, 0, 1, 0, 0, 0], id="blocking")
        with self.assertRaisesRegex(ModelValidationError, "Support 'blocking' is an attached spring, so it cannot also block DOFs"):
            model.validate()


def export(model, case="Hot", **options):
    with TemporaryDirectory() as tmpdir:
        study = CodeAsterSolver(work_dir=tmpdir, **options).export_analysis_study(model, case, tmpdir)
        root = Path(study.work_dir)
        return (root / "study.comm").read_text(encoding="utf-8"), (root / "study.mail").read_text(encoding="utf-8")


def attached_model(kind, **support):
    """The cantilever, a post under its tip, and a support at the tip attached to the post top."""
    model, root, tip = cantilever()
    model.add_rectangular_section("Post", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
    other = model.add_node([6.0, 0.0, -0.25])
    base = model.add_node([6.0, 0.0, -1.25])
    model.add_element(id="post", type="beam", n1=base, n2=other, section="Post", material="Steel")
    model.add_support(root, "anchor")
    model.add_support(base, "anchor")
    model.add_support(tip, kind, attached_to=other, id="attached", **support)
    model.define_load_case("Hot", gravity=True, temperature=120.0, ref_temperature=20.0)
    return model, tip, other


class AttachedExport(unittest.TestCase):
    def test_attached_anchor_ties_all_six_dofs(self):
        model, tip, other = attached_model("anchor")
        comm, mail = export(model)
        for dof in ("DX", "DY", "DZ", "DRX", "DRY", "DRZ"):
            self.assertIn(
                f"_F(GROUP_NO=('GN_{tip}', 'GN_{other}'), DDL=('{dof}', '{dof}'), COEF_MULT=(1.0, -1.0), COEF_IMPO=0.0),",
                comm,
            )
        self.assertIn(f"GROUP_NO NOM=GN_{other}", mail)

    def test_attached_guide_ties_only_its_direction(self):
        model, _tip, _other = attached_model("guide", direction=[0.0, 1.0, 0.0])
        comm, _mail = export(model)
        self.assertIn("DDL=('DY', 'DY')", comm)
        self.assertNotIn("DDL=('DX', 'DX')", comm)
        self.assertNotIn("DDL=('DZ', 'DZ')", comm)

    def test_attached_rest_ties_its_shoe_helper_instead_of_fixing_it(self):
        model, _tip, other = attached_model("rest", friction_coefficient=0.3)
        comm, _mail = export(model)
        self.assertIn("GROUND0 = AFFE_CHAR_MECA(MODELE=MODELE, LIAISON_DDL=(", comm)
        self.assertIn(f"'GN_{other}'),DDL=('DZ','DZ')", comm)
        self.assertNotIn("DDL_IMPO=_F(GROUP_NO='GROUND_", comm)

    def test_attached_spring_is_a_helper_seg2_tied_to_the_attached_node(self):
        model, tip, other = attached_model("spring", stiffness_matrix=[0.0, 0.0, 1.0e7, 0.0, 0.0, 0.0])
        comm, mail = export(model)
        self.assertIn("CARA='K_TR_D_L'", comm)
        self.assertNotIn("CREA_POI1", comm)
        self.assertIn("MODELISATION='DIS_TR'", comm)
        self.assertIn("SPRING0 = AFFE_CHAR_MECA(MODELE=MODELE, LIAISON_DDL=(", comm)
        self.assertIn(f"'GN_{other}'),DDL=('DRZ','DRZ')", comm)
        self.assertIn("    AFFE_VARC=_F(\n        GROUP_MA=('AllPipes', 'G_TUBE'),\n", comm)
        self.assertIn(f" SPRING_2 SPRHLP_2 {tip}", mail)
        # The helper sits 1 m below the tip at (6, 0, 0), and its tie is applied as a load.
        self.assertIn("  SPRHLP_2 +6.0000000000E+00 +0.0000000000E+00 -1.0000000000E+00", mail.splitlines())
        self.assertIn("        _F(CHARGE=SPRING0),", comm.splitlines())


class RackExampleEvidence(unittest.TestCase):
    def test_the_rack_example_pipe_slides_on_two_shoes_that_load_the_rack(self):
        project = Path(__file__).resolve().parents[1] / "examples" / "support-rack-review"
        model = load_project(project).run_model()["model"]
        run = import_code_aster_artifacts(model=model, work_dir=project / "evidence" / "Operating")
        shoes = [run.results.contact_results[support.id] for support in model.supports if support.type == "rest"]
        self.assertEqual(len(shoes), 2)
        for shoe in shoes:
            self.assertEqual(shoe.status, "sliding")
            self.assertLess(shoe.gap, 1e-9)
            # Read from the committed evidence: each shoe carries 2412.36 N.
            self.assertAlmostEqual(shoe.normal_force, 2412.36, delta=0.05)
        rack = analyze_load_paths(model, result_state=run.result_state).rack_loads["rack_A"]
        self.assertEqual(rack["support_count"], 2)
        carried = sum(shoe.normal_force for shoe in shoes)
        self.assertAlmostEqual(rack["force_z_n"], -carried, delta=0.02 * carried)
        # The rack also takes the shoes' friction; a converged solve balances it to well under 1 N.
        for axis, key in ((0, "force_x_n"), (1, "force_y_n")):
            self.assertAlmostEqual(rack[key], -sum(shoe.tangential_force[axis] for shoe in shoes), delta=1.0)


if __name__ == "__main__":
    unittest.main()
