# verify_features.py
import os
import tempfile
import numpy as np

import tuba
from tuba import Model
from tuba.compliance.sif import compute_sifs
from tuba.compliance.asme_b313 import ASMEB313Evaluator
from tuba.solver.base import FEAResults, ElementResult, NodeResult
from tuba.geometry.importer import StepGeometryImporter
from tuba.geometry.collision import PipingCollisionChecker


def verify_tee_sifs():
    print("--- Verifying Tee SIFs ---")
    model = Model(project_name="VerifyTee", standard="ASME_B31.3")
    model.add_material("Steel", E=2.0e11, nu=0.3, allowable_stress={20.0: 137.0e6, 200.0: 120.0e6})
    model.add_pipe_section("PipeSec", OD=0.1143, WT=0.00602, corrosion_allowance=0.001)

    # 3-way junction at N1
    with model.pipe(section="PipeSec", material="Steel") as b:
        b.start([0, 0, 0]).run(5.0)  # N0 -> N1
        b.run(5.0)                  # N1 -> N2

    with model.pipe(section="PipeSec", material="Steel") as b:
        b.start([5, 0, 0]).run(5.0)  # N1 -> N3

    # Define standard welding tee SIF
    model.define_tee("N1", type="welding_tee")

    # Run SIF calculation on N1
    i_i, i_o, k, h = compute_sifs(model.elements[0], model, node_id="N1")
    print(f"Welding Tee SIF at N1: i_i = {i_i:.4f}, i_o = {i_o:.4f}, h = {h:.4f}")

    # Build mock FEA results to check compliance evaluator integration
    results = FEAResults(solver_name="mock", load_case="Hot")
    results.node_results["N0"] = NodeResult(node_id="N0", displacement=np.zeros(6), reaction_force=np.zeros(6))
    results.node_results["N1"] = NodeResult(node_id="N1", displacement=np.zeros(6))
    results.node_results["N2"] = NodeResult(node_id="N2", displacement=np.zeros(6), reaction_force=np.zeros(6))
    results.node_results["N3"] = NodeResult(node_id="N3", displacement=np.zeros(6), reaction_force=np.zeros(6))

    for e in model.elements:
        results.element_results[e.id] = ElementResult(
            element_id=e.id,
            forces_n1=np.array([0, 0, 0, 100, 0, 500]),
            forces_n2=np.array([0, 0, 0, -100, 0, -500]),
            von_mises_n1=10e6,
            von_mises_n2=10e6,
            max_von_mises=10e6
        )

    model.define_load_case("Hot", gravity=True, pressure=1.5e6, temperature=200.0)
    evaluator = ASMEB313Evaluator()
    report = evaluator.evaluate(model, results)
    print("Compliance Report overall verdict:", "PASS" if report.overall_pass else "FAIL")
    print(report.summary())


def verify_collision():
    print("\n--- Verifying Collision Checking ---")
    # Setup temporary STEP file
    import gmsh
    if not gmsh.isInitialized():
        gmsh.initialize()
        gmsh.option.setNumber("General.Terminal", 0)

    with tempfile.TemporaryDirectory() as temp_dir:
        step_path = os.path.join(temp_dir, "verify_box.step")
        
        gmsh.model.add("verify_step")
        # Add box from [1.5, -0.5, -0.5] to [3.5, 0.5, 0.5]
        gmsh.model.occ.addBox(1.5, -0.5, -0.5, 2.0, 1.0, 1.0)
        gmsh.model.occ.synchronize()
        gmsh.write(step_path)
        gmsh.model.remove()

        model = Model(project_name="VerifyCollision")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.2, WT=0.01)

        # Pipe directly intersecting the box [1.5, -0.5, -0.5] -> [3.5, 0.5, 0.5]
        with model.pipe(section="PipeSec", material="Steel") as b:
            b.start([0, 0, 0]).run(5.0).end()

        # Add mesh obstacle
        model.add_obstacle(
            id="step_obstacle",
            type="mesh",
            file_path=step_path,
            position=[0, 0, 0]
        )

        checker = PipingCollisionChecker(model)
        collisions = checker.check_collisions()
        print("Colliding elements:", collisions)
        if "pipe_str_0" in collisions:
            print("Collision correctly detected on element 'pipe_str_0'")
        else:
            print("Error: Collision not detected!")


if __name__ == "__main__":
    verify_tee_sifs()
    verify_collision()
