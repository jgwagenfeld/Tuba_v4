# verify_features.py
import os
import tempfile

import tuba
from tuba import Model
from tuba.compliance.sif import compute_sifs
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
    print("Compliance evaluation requires real Code_Aster result artifacts.")
    print("Run the exported study with Code_Aster, then import the result tables before reporting compliance.")


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
