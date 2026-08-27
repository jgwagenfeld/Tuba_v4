import unittest
import tempfile
from pathlib import Path
import numpy as np
import pytest

ifcopenshell = pytest.importorskip("ifcopenshell", exc_type=ImportError)

from tuba import Model
from tests.operating_state_fixtures import straight_pipe_hot_clash_fixture
from tuba.analysis import AnalysisStudy
from tuba.analysis.results import result_state_from_fea_results
from tuba.analysis.states import create_cold_geometry_state, create_operating_geometry_state
from tuba.clash import TrimeshClashEngine
from tuba.model import TubaModel, IBeamSection, RectangularSection, BarSection, CableSection
from tuba.solver.base import FEAResults, NodeResult, ElementResult
from tuba.external.ifc import IfcExporter, IfcImporter


class TestIfcIntegration(unittest.TestCase):
    def test_ifc_export_adds_operating_state_property_set(self):
        fixture = straight_pipe_hot_clash_fixture()
        study = AnalysisStudy(
            id="analysis_study:Hot",
            model_revision=0,
            solver_name=fixture.results.solver_name,
            load_case="Hot",
            work_dir=None,
            input_files={},
            mesh_id="analysis_mesh:Hot",
        )
        result_state = result_state_from_fea_results(model=fixture.model, study=study, results=fixture.results)
        operating_state = create_operating_geometry_state(model=fixture.model, result_state=result_state)
        clashes = TrimeshClashEngine().check_operating_state(
            fixture.model,
            cold_state=create_cold_geometry_state(fixture.model),
            operating_state=operating_state,
            result_state=result_state,
            envelope_type="bare",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ifc_path = Path(tmpdir) / "operating.ifc"
            IfcExporter().export_model(
                fixture.model,
                ifc_path,
                result_state=result_state,
                operating_clash_results=clashes,
            )
            ifc_file = ifcopenshell.open(str(ifc_path))

        pipe = next(product for product in ifc_file.by_type("IfcPipeSegment") if product.Name == "pipe_0")
        psets = [
            definition.RelatingPropertyDefinition
            for definition in pipe.IsDefinedBy
            if definition.is_a("IfcRelDefinesByProperties")
        ]
        operating = next(pset for pset in psets if pset.Name == "Pset_TubaOperatingState")
        props = {prop.Name: prop.NominalValue.wrappedValue for prop in operating.HasProperties}
        self.assertEqual(props["LoadCase"], "Hot")
        self.assertEqual(props["ResultStateId"], result_state.id)
        self.assertEqual(props["OperatingClashCount"], 1)

    def test_ifc_export_and_import_roundtrip(self):
        # 1. Create a model
        model = Model(project_name="TestIfcProject", standard="ASME_B31.3")
        model.add_material("S235JR", E=2.1e11, nu=0.3, rho=7850.0, allowable_stress={20.0: 137e6})
        
        # Add sections
        model.add_pipe_section("StandardPipe", OD=0.1143, WT=0.00602)
        model.add_ibeam_section("Beam1", "IPE100")
        model.sections["RectHollow"] = RectangularSection(name="RectHollow", height_y=0.1, height_z=0.1, thickness_y=0.005, thickness_z=0.005)
        model.sections["SolidBar"] = BarSection(name="SolidBar", OD=0.05, WT=0.0)

        # Add nodes
        n0 = model.add_node(np.array([0.0, 0.0, 0.0]))
        n1 = model.add_node(np.array([5.0, 0.0, 0.0]))
        n2 = model.add_node(np.array([5.0, 3.0, 0.0]))
        n3 = model.add_node(np.array([0.0, 3.0, 0.0]))

        # Add elements
        # Pipe straight
        model.add_element(id="p_str", type="pipe_straight", n1=n0, n2=n1, section="StandardPipe", material="S235JR")
        # Pipe bend
        model.add_element(id="p_bend", type="pipe_bend", n1=n1, n2=n2, section="StandardPipe", material="S235JR", bend_radius=0.15)
        # Structural Beam (horizontal)
        model.add_element(id="b_beam", type="beam", n1=n2, n2=n3, section="Beam1", material="S235JR")
        # Structural Column (vertical)
        model.add_element(id="b_col", type="beam", n1=n0, n2=n3, section="RectHollow", material="S235JR")

        # Add supports
        model.add_support(node=n0, type="anchor")
        model.add_support(node=n2, type="rest", friction_coefficient=0.3)
        model.add_support(node=n3, type="guide")

        # Add obstacle
        model.add_obstacle(id="Obs1", type="cuboid", min_point=[2.0, -0.5, -0.5], max_point=[3.0, 0.5, 0.5])

        # Create mock FEA results
        results = FEAResults(solver_name="mock_fea", load_case="hot")
        results.node_results[n0] = NodeResult(node_id=n0, displacement=np.zeros(6), reaction_force=np.array([1000.0, 2000.0, 3000.0, 0.0, 0.0, 0.0]))
        results.node_results[n2] = NodeResult(node_id=n2, displacement=np.zeros(6), reaction_force=np.array([10.0, 500.0, 0.0, 0.0, 0.0, 0.0]))
        results.node_results[n3] = NodeResult(node_id=n3, displacement=np.zeros(6), reaction_force=np.zeros(6))

        for elem in model.elements:
            results.element_results[elem.id] = ElementResult(
                element_id=elem.id,
                forces_n1=np.zeros(6),
                forces_n2=np.zeros(6),
                max_von_mises=50e6
            )

        model.define_load_case("hot", gravity=True, pressure=1.5e6, temperature=200.0)

        # 2. Export to temp file
        with tempfile.TemporaryDirectory() as tmpdir:
            ifc_path = Path(tmpdir) / "test_model.ifc"
            exporter = IfcExporter()
            exporter.export_model(model, ifc_path, results=results)

            self.assertTrue(ifc_path.exists())

            # 3. Check property sets inside the generated IFC file using raw ifcopenshell
            ifc_file = ifcopenshell.open(str(ifc_path))
            
            # Find supports
            fasteners = ifc_file.by_type("IfcMechanicalFastener")
            self.assertEqual(len(fasteners), 3)

            # Check that pset is attached
            found_pset = False
            for f in fasteners:
                for definition in f.IsDefinedBy:
                    if definition.is_a("IfcRelDefinesByProperties"):
                        prop_def = definition.RelatingPropertyDefinition
                        if prop_def.is_a("IfcPropertySet") and prop_def.Name == "Pset_TubaSupportForces":
                            found_pset = True
                            props = {p.Name: p.NominalValue.wrappedValue for p in prop_def.HasProperties}
                            self.assertEqual(props["SupportType"], "rest" if "rest" in f.Description.lower() else ("anchor" if "anchor" in f.Description.lower() else "guide"))
                            if "rest" in f.Description.lower():
                                self.assertEqual(props["FrictionCoefficient"], 0.3)
            self.assertTrue(found_pset)

            # Check columns and beams
            columns = ifc_file.by_type("IfcColumn")
            beams = ifc_file.by_type("IfcBeam")
            # We had one vertical column (b_col from N0 to N3) and one horizontal beam (b_beam from N2 to N3)
            self.assertEqual(len(columns), 1)
            self.assertEqual(len(beams), 1)

            # 4. Import from temp file
            importer = IfcImporter()
            imported_model = importer.import_model(ifc_path)

            # Verify imported elements count
            pipes_imported = [e for e in imported_model.elements if e.type in ("pipe_straight", "pipe_bend")]
            beams_imported = [e for e in imported_model.elements if e.type == "beam"]
            self.assertEqual(len(pipes_imported), 2)
            self.assertEqual(len(beams_imported), 2)

            # Verify supports imported
            self.assertEqual(len(imported_model.supports), 3)
            imported_sup_types = {s.node: s.type for s in imported_model.supports}

            def find_imported_node_near(coords):
                for nid, n in imported_model.nodes.items():
                    if np.linalg.norm(n.coords - coords) < 0.05:
                        return nid
                return None

            n0_imported = find_imported_node_near([0.0, 0.0, 0.0])
            n2_imported = find_imported_node_near([5.0, 3.0, 0.0])
            n3_imported = find_imported_node_near([0.0, 3.0, 0.0])

            self.assertIsNotNone(n0_imported)
            self.assertIsNotNone(n2_imported)
            self.assertIsNotNone(n3_imported)

            self.assertEqual(imported_sup_types[n0_imported], "anchor")
            self.assertEqual(imported_sup_types[n2_imported], "rest")
            self.assertEqual(imported_sup_types[n3_imported], "guide")

            # Verify obstacles imported
            self.assertEqual(len(imported_model.obstacles), 1)
            obs = imported_model.obstacles[0]
            self.assertEqual(obs["type"], "cuboid")
            self.assertAlmostEqual(obs["min_point"][0], 2.0)
            self.assertAlmostEqual(obs["max_point"][0], 3.0)


if __name__ == "__main__":
    unittest.main()
