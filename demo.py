"""
Tuba v4 — Expansion Loop Demo and Workflow Verification.

This script demonstrates:
1. Defining a 3D piping system using the cursor DSL.
2. Exporting the model to the canonical JSON format.
3. Calculating SIFs (Stress Intensification Factors) per ASME B31.3 Appendix D.
4. Exporting Code_Aster solver study files (.comm, .mail, .export).
5. Running ASME B31.3 code compliance checks on FEA results.
6. Creating a PyVista 3D visualization and exporting interactive HTML.
"""

import os
from pathlib import Path
import numpy as np

import tuba
from tuba.solver.base import FEAResults, NodeResult, ElementResult
from tuba.solver.aster import CodeAsterSolver
from tuba.compliance import ASMEB313Evaluator


def main():
    print("=" * 70)
    print("                    TUBA V4 — PIPING DEMO WORKFLOW")
    print("=" * 70)

    # 1. Define Model and Material/Section Specs
    print("\n[1/6] Initializing TubaModel...")
    model = tuba.Model(project_name="Expansion_Loop_Project")

    # Add steel material with temperature dependent allowable stress (ASME B31.3)
    model.add_material(
        name="P265GH",
        E=2.1e11,
        nu=0.3,
        rho=7850.0,
        alpha=1.2e-5,
        allowable_stress={20.0: 147e6, 100.0: 138e6, 200.0: 130e6}
    )

    # Add standard pipe cross-section (4" Schedule 40)
    model.add_pipe_section(
        name="4inch_sch40",
        OD=0.1143,
        WT=0.00602,
        corrosion_allowance=0.0015  # 1.5mm corrosion allowance
    )

    # 2. Build the Geometry using Cursor DSL
    print("[2/6] Building geometry using cursor DSL...")
    with model.pipe(section="4inch_sch40", material="P265GH") as builder:
        builder.start([0.0, 0.0, 0.0], support="anchor")
        builder.run(4.0)                                     # 4m straight in +X direction
        builder.bend(radius=0.1524, angle=90.0, plane="XY")   # 90-degree elbow in XY plane (turns to +Y)
        builder.run(2.0)                                     # 2m straight in +Y direction
        builder.bend(radius=0.1524, angle=90.0, plane="XY")   # 90-degree elbow (turns to -X)
        builder.run(4.0)                                     # 4m straight in -X direction
        builder.end(support="anchor")                        # End anchor support

    # Define operating load case
    model.define_load_case(
        name="hot_operation",
        gravity=True,
        pressure=1.5e6,       # 1.5 MPa internal pressure
        temperature=200.0,    # 200°C design temperature
        ref_temperature=20.0  # 20°C installation temperature
    )

    # Save the canonical model to JSON
    json_path = "piping_model.json"
    model.to_json(json_path)
    print(f"  -> Model saved to: {json_path}")
    print(f"  -> Total Nodes: {len(model.nodes)}")
    print(f"  -> Total Elements: {len(model.elements)}")

    # 3. Compute and Print SIFs
    print("\n[3/6] Calculating SIFs for elbows per ASME B31.3 Appendix D:")
    for elem in model.elements:
        if elem.type == "pipe_bend":
            from tuba.compliance.sif import compute_sifs
            i_i, i_o, k, h = compute_sifs(elem, model)
            print(f"  -> Elbow '{elem.id}':")
            print(f"     h (flexibility characteristic) : {h:.4f}")
            print(f"     i_i (in-plane SIF)             : {i_i:.2f}")
            print(f"     i_o (out-of-plane SIF)         : {i_o:.2f}")
            print(f"     k (flexibility factor)         : {k:.2f}")

    # 4. Export Code_Aster solver study files
    print("\n[4/6] Exporting Code_Aster study files (.comm, .mail, .export)...")
    study_dir = Path("./code_aster_study")
    solver = CodeAsterSolver()
    solver.export_study(model, "hot_operation", study_dir)
    print(f"  -> Code_Aster study files written to directory: {study_dir.resolve()}")
    print("     Files generated:")
    print("       - study.comm   (Code_Aster command script using TUYAU_3M)")
    print("       - study.mail   (1D pipe line finite element mesh)")
    print("       - study.export (Logical unit maps for Code_Aster execute)")

    # 5. Perform ASME B31.3 Compliance check using mock results
    # (Since Code_Aster requires WSL / Docker setup, we provide mock FEAResults
    #  to verify compliance and visualization workflow instantly)
    print("\n[5/6] Simulating FEA results for code compliance...")
    results = FEAResults(solver_name="mock_solver", load_case="hot_operation")

    # Generate mock displacements (thermal expansion deflection of ~8mm in Y at midpoint)
    n_nodes = len(model.nodes)
    for i, nid in enumerate(model.nodes.keys()):
        # Max displacement at the middle of the loop
        t = i / (n_nodes - 1)
        disp_y = 0.008 * np.sin(t * np.pi)
        disp_x = 0.003 * np.sin(t * np.pi * 2)
        results.node_results[nid] = NodeResult(
            node_id=nid,
            displacement=np.array([disp_x, disp_y, 0.0, 0.0, 0.0, 0.0]),
            reaction_force=np.array([12000.0, 8000.0, 0.0, 0.0, 0.0, 1500.0]) if i in (0, n_nodes - 1) else None
        )

    # Generate mock forces and stresses (higher moments at elbows)
    for elem in model.elements:
        is_elbow = elem.type == "pipe_bend"
        max_v = 85.0e6 if is_elbow else 35.0e6
        # Simulate local bending moments (Mx, My, Mz)
        mz = 1200.0 if is_elbow else 400.0
        forces_n1 = np.array([15000.0, 0.0, 0.0, 200.0, 0.0, mz])
        forces_n2 = np.array([15000.0, 0.0, 0.0, -200.0, 0.0, -mz])
        results.element_results[elem.id] = ElementResult(
            element_id=elem.id,
            forces_n1=forces_n1,
            forces_n2=forces_n2,
            von_mises_n1=max_v,
            von_mises_n2=max_v,
            max_von_mises=max_v
        )

    # Run compliance evaluator
    evaluator = ASMEB313Evaluator()
    report = evaluator.evaluate(model, results)

    print("\n" + "=" * 50)
    print(report.summary())
    print("=" * 50)

    # Show a detailed calculation report for the first bend element
    bend_elem = next(e for e in model.elements if e.type == "pipe_bend")
    detailed_report = report.get_detailed_calculation(bend_elem.id)
    print(f"\nDetailed Calculation Report for Elbow '{bend_elem.id}':")
    print("-" * 50)
    # Output first 40 lines of detailed calculations
    print("\n".join(detailed_report.splitlines()[:35]))
    print("...")
    print("-" * 50)

    # 6. Visualization & Export
    print("\n[6/6] Building 3D visualization scene...")
    # Generate standalone interactive 3D HTML plot (vtk.js)
    html_path = "deformed_stress_view.html"
    try:
        from tuba.visualizer.export import export_html
        # We attach the model reference to results for visualization helper functions
        results._model = model
        export_html(results, html_path)
        print(f"  -> Standalone interactive 3D HTML exported to: {Path(html_path).resolve()}")
        print("     Open this file in any web browser to rotate, zoom, and inspect stress maps!")
    except Exception as e:
        print(f"  -> HTML export failed: {e}")

    # Blender Python Script Export
    blender_script_path = "blender_import_tuba.py"
    try:
        from tuba.visualizer.export import export_blender_script
        export_blender_script(results, blender_script_path, model)
        print(f"  -> Blender Python script generated: {Path(blender_script_path).resolve()}")
        print("     How to use in Blender:")
        print("       1. Open Blender")
        print("       2. Go to Scripting tab, open and run the script.")
        print("       3. The piping structure will be built automatically with 3D tubes")
        print("          and the stress values mapped to vertex colors.")
    except Exception as e:
        print(f"  -> Blender script export failed: {e}")

    print("\n" + "=" * 70)
    print("                      HOW TO RUN CODE_ASTER SOLVER")
    print("=" * 70)
    print("To execute the Code_Aster solver on this model and import the real results:")
    print("1. Ensure WSL2 and Ubuntu are set up on your machine.")
    print("2. Install Code_Aster inside WSL Ubuntu using Miniforge / Conda:")
    print("     $ wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh")
    print("     $ bash Miniforge3-Linux-x86_64.sh -b -p $HOME/miniforge3")
    print("     $ $HOME/miniforge3/bin/conda init")
    print("     $ conda config --add channels conda-forge")
    print("     $ conda config --set channel_priority strict")
    print("     $ conda install -y code-aster")
    print("3. Execute the solver from Windows:")
    print("     $ wsl conda run -n base as_run ./code_aster_study/study.export")
    print("4. Read the results back into your python script:")
    print("     >>> from tuba.solver.aster import CodeAsterSolver")
    print("     >>> solver = CodeAsterSolver(work_dir='./code_aster_study')")
    print("     >>> real_results = solver._parse_results(model, Path('./code_aster_study'))")
    print("     >>> report = evaluator.evaluate(model, real_results)")
    print("     >>> real_results.plot_deformed_stress(model=model)")
    print("=" * 70)

    # Open PyVista interactive plotter window on host machine
    if os.environ.get("TUBA_HEADLESS") == "1":
        print("\nSkipping interactive 3D window (TUBA_HEADLESS=1).")
    else:
        print("\nDisplaying interactive 3D window...")
        try:
            results.plot_deformed_stress(deform_scale=200.0, model=model)
        except Exception as e:
            print(f"Plot window could not be opened: {e}")
            print("Ensure a GUI display environment is available.")



if __name__ == "__main__":
    main()
