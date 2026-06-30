# Tuba v4: Installation & Ultimate User Interface Strategy

---

## 0. Environment Management: Conda vs. UV (Hybrid Strategy)

For package and environment management, we propose a **hybrid strategy** that leverages the strengths of both tools:

| Aspect | `uv` (Python Dev Environment) | `conda` / `miniforge` (WSL2 Solver Backend) |
| :--- | :--- | :--- |
| **Role** | Manages Python package dependencies for Tuba on the host machine. | Manages compiled non-Python system dependencies inside WSL2. |
| **Speed** | Instant virtual environment creation and pip resolution (written in Rust). | Standard binary resolution for scientific applications. |
| **Scope** | PyPI packages (`pyvista`, `meshio`, `scipy`, `pandas`, `jsonschema`). | Pre-compiled compiled packages (`code-aster`, `calculix`, `gfortran`). |
| **Recommendation** | **Use `uv`** for developing/running the Tuba frontend & API on Windows. | **Use `conda`** inside WSL2 for compiling and running the Code_Aster solver. |

### Host Machine Setup (`uv`)
Run `uv` on Windows to initialize the Tuba v4 project environment:
```powershell
uv init Tuba_v4
uv add pyvista meshio scipy pandas jsonschema
uv venv
```

### WSL2 Solver Environment (`conda`)
Install Miniforge inside WSL2 to manage the compiled Code_Aster solver binaries:
```bash
wsl -d Ubuntu bash -lc "source ~/miniforge3/etc/profile.d/conda.sh && conda create -n tuba-code-aster -c conda-forge code-aster"
```

---

## 1. Updated Implementation Strategy

We will explicitly target a **zero-install, zero-gui, fully headless backend solver strategy**. 
By removing the dependency on the 4GB+ Salome-Meca GUI bundle, we make Tuba v4 lightweight, cross-platform, and highly automatable for AI agents.

```
                  ┌──────────────────────────────────────────────┐
                  │                 Tuba Model                   │
                  │        (Piping/Structural Geometry)          │
                  └──────────────────────┬───────────────────────┘
                                         │
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │          Pluggable Solver Interface          │
                  └───────┬──────────────┬───────────────┬───────┘
                          │              │               │
      (Zero Install)      ▼              ▼               ▼     (WSL2 / Docker)
                     ┌──────────┐  ┌───────────┐  ┌──────────────┐
                     │ Internal │  │ CalculiX  │  │  Code_Aster  │
                     │  Solver  │  │ (Windows) │  │  (Headless)  │
                     └──────────┘  └───────────┘  └──────────────┘
```

---

## 2. Setting Up Code_Aster Headless (The Easy Way)

For Tuba v4 production workflows, Code_Aster is a required external solver
runtime. On Windows, the recommended developer setup is Code_Aster from
conda-forge inside a named WSL2 Ubuntu distro, exposed to Tuba through
`TUBA_CODE_ASTER_EXEC_METHOD=wsl` and `TUBA_CODE_ASTER_WSL_DISTRO=Ubuntu`.
Use `TUBA_CODE_ASTER_PYTHON` only when that Python executable is directly
executable by the process running Tuba, for example when Tuba itself runs inside
Linux/WSL. A direct `run_aster` command and Docker remain fallback execution
methods.

Use the canonical walkthrough in
[`docs/code_aster_installation.md`](docs/code_aster_installation.md). It covers
Miniforge, the `tuba-code-aster` conda environment, the WSL `run_aster` wrapper,
and the real Tuba smoke test.

Instead of the painful Salome-Meca graphical installations, Tuba v4 will automate execution using standard package managers under Windows Subsystem for Linux (WSL2) or Docker containers.

### Method A: WSL2 + Conda-Forge (Recommended for Windows Users)
WSL2 is built directly into Windows 10/11. The installation of Code_Aster can be accomplished in minutes via `conda-forge`:

1. **Enable WSL2**:
   ```powershell
   wsl --install -d Ubuntu
   ```
2. **Automated Conda Setup** (Tuba will run this internally via subprocess):
   ```bash
   # Inside WSL2:
   wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
   bash Miniforge3-Linux-x86_64.sh -b -p $HOME/miniforge3
   $HOME/miniforge3/bin/conda init
   
   # Install Code_Aster
   conda config --add channels conda-forge
   conda config --set channel_priority strict
   conda create -y -n tuba-code-aster -c conda-forge code-aster
   ```
3. **Execution**: Tuba triggers Code_Aster from Windows without user intervention by calling:
   ```powershell
   $env:TUBA_CODE_ASTER_EXEC_METHOD = "wsl"
   $env:TUBA_CODE_ASTER_WSL_DISTRO = "Ubuntu"
   ```

### Method B: Docker Container
If the user prefers containers:
- Tuba pulls a lightweight community container with Code_Aster pre-installed.
- When `model.solve(backend="code_aster")` is called, Tuba mounts the local output folder, executes the container, and reads the results back.

---

## 3. The Ultimate User Interface & Workflow

The user (or AI agent) interacts with a single Python class structure. Stresses and standard compliance checks are separate, logical steps.

### Complete Workflow Code Example

```python
import tuba

# 1. Define Model and Material/Section Specs
model = tuba.Model(project_name="ExpLoop_Project")

model.add_material(
    name="P265GH",
    E=2.1e11,
    nu=0.3,
    rho=7850,
    alpha=1.2e-5,
    allowable_stress={20: 147e6, 100: 138e6, 200: 130e6}
)

model.add_pipe_section("4inch_sch40", OD=0.1143, WT=0.00602)

# 2. Build the Geometry using Cursor DSL
with model.pipe(section="4inch_sch40", material="P265GH") as builder:
    builder.start([0, 0, 0], support="anchor")
    builder.run(5.0)                       # Straight 5m run in +X
    builder.bend(radius=0.1524, angle=90)  # Elbow turning to +Y
    builder.run(2.0)
    builder.bend(radius=0.1524, angle=90)  # Elbow turning to -X
    builder.run(5.0)
    builder.end([10, 0, 0], support="anchor")

# 3. Define Load Cases (Operating conditions)
model.define_load_case("hot_op", gravity=True, pressure=1.5e6, temperature=200.0)

# 4. Run the required Code_Aster evaluation.
results = model.solve(solver="code_aster")

# 5. Check Code Compliance (ASME B31.3 / EN 13480)
compliance = results.check_compliance(standard="ASME_B31.3")

print(compliance.summary())
# Output:
#   Sustained stress: PASS (Ratio: 0.42 at Node 3)
#   Expansion stress: PASS (Ratio: 0.68 at Node 8)

# 6. Plot Stresses dynamically (using PyVista/Jupyter)
results.plot(scalar="von_mises", warp_scale=50.0)
```
