"""
Tuba v4 — Expansion Loop Demo and Workflow Verification.

This script demonstrates:
1. Defining a 3D piping system using the cursor DSL.
2. Exporting the model to the canonical JSON format.
3. Calculating SIFs (Stress Intensification Factors) per ASME B31.3 Appendix D.
4. Exporting Code_Aster solver study files (.comm, .mail, .export).
5. Stopping before compliance until real Code_Aster result tables exist.
6. Pointing the user at the configured runtime checks and real integration smoke.
"""

from pathlib import Path

import tuba
from tuba.solver.aster import CodeAsterSolver


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
    json_path = Path(".build") / "piping_model.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
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
    study_dir = Path(".build") / "code_aster_study"
    solver = CodeAsterSolver()
    solver.export_study(model, "hot_operation", study_dir)
    print(f"  -> Code_Aster study files written to directory: {study_dir.resolve()}")
    print("     Files generated:")
    print("       - study.comm   (Code_Aster command script using TUYAU_3M)")
    print("       - study.mail   (1D pipe line finite element mesh)")
    print("       - study.export (Logical unit maps for Code_Aster execute)")

    # 5. Stop before compliance and result visualization.
    print("\n[5/6] Code_Aster execution required before compliance or result visualization.")
    print("  -> This demo generated solver handoff files only.")
    print("  -> Exported studies are not a completed engineering evaluation.")
    print("  -> Run Code_Aster, then import study_depl.csv, study_effo.csv, study_reac.csv, and study_sieq.csv.")

    print("\n[6/6] Next command for a configured runtime:")
    print("     python -m tuba.solver.code_aster_doctor --check")
    print('     $env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"')
    print("     .\\.venv\\Scripts\\python.exe -m pytest tests/test_code_aster_real_smoke.py -q")

    print("\nNo compliance report or stress plot was produced from synthetic values.")



if __name__ == "__main__":
    main()
