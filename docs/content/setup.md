# Setup

The recommended installation runs Tuba and Code_Aster in one conda environment
on Linux x86_64. On Windows, run both inside Ubuntu WSL2 and open Studio in your
Windows browser:

```text
Tuba model -> Code_Aster solve -> imported result artifacts -> result display
```

Code_Aster is required for production stress, displacement, reaction,
compliance, operating-state clash, and result visualization workflows.

## Recommended: one environment

### Windows: install Ubuntu

Run this in an administrator PowerShell, restart if requested, then launch
Ubuntu once to create a Linux user:

```powershell
wsl --install -d Ubuntu
```

Run all remaining commands in the **Ubuntu terminal**, including Tuba commands.
On native Linux x86_64, start below.

### Install Miniforge

If Miniforge is already installed, skip its download and installer commands and
source your existing installation. Ubuntu also needs the graphics libraries used
by Gmsh and the notebook renderer:

```bash
sudo apt-get update
sudo apt-get install -y git curl libglu1-mesa libxft2 libgomp1
curl -fsSLo /tmp/Miniforge3-Linux-x86_64.sh \
  https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash /tmp/Miniforge3-Linux-x86_64.sh -b -p "$HOME/miniforge3"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda init bash
```

### Create the environment

Clone into your Linux home directory. Building from a Windows-mounted drive
such as `/mnt/c` can make installation much slower:

```bash
cd ~
git clone --branch main --depth 1 https://github.com/jgwagenfeld/Tuba_v4.git
cd Tuba_v4
conda env create -f environment.yml
conda activate tuba
python -m tuba.solver.code_aster_doctor --check
```

The recipe installs Python 3.14, the non-MPI Code_Aster 18.0.12 solver, Tuba,
notebooks, IFC exchange and MCP support. It selects Tuba's Python bridge on
activation; Code_Aster still executes in a separate process. NumPy is pinned
to 2.4.6 to satisfy the solver's NumPy <2.5 requirement and preserve model
fingerprints. The viewer is already packaged with Tuba.

Conda installs the solver's native libraries and executables alongside Python.
uv can install compiled Python wheels, but it cannot install Code_Aster's conda
package. This recipe supplies both Tuba and the solver in one environment; no
additional `.venv` is needed.

The doctor must report `python_bridge: ready`. If it reports `blocked`, stop
and fix the reported dependency before solving or displaying new results.

### Solve and display your first model

Copy the authored example into your own working project, solve it afresh, then
display the processed results:

```bash
mkdir -p .build
cp -r examples/code-aster-review .build/first-pipe
python -m tuba.project .build/first-pipe --output .build/first-review --force
tuba-viewer .build/first-review/review_scene --open
```

`--force` runs Code_Aster even if the example has existing evidence. The viewer
shows stress, displacement and reactions from that solve. If WSL cannot open
the browser automatically, open the printed localhost URL in your Windows
browser. Press Ctrl+C to stop the viewer.

For further edits and solves, start Studio from the same activated environment:

```bash
python -m tuba.cli_studio .build/first-pipe
```

Choose **Solve**, then **Review**. Notebooks also run in this environment with
`jupyter lab`. In a new Ubuntu terminal, run `conda activate tuba` before
starting Tuba.

To update the source installation, pull the desired revision and recreate the
environment from its recipe. Avoid mixing this environment with `uv sync` or
a Windows `.venv`.

## Developer alternative: Windows Tuba and WSL solver

The following setup keeps Tuba on Windows and Code_Aster in a separate Linux
environment. **uv installs Tuba, not Code_Aster.**

## Prerequisites

| Requirement | Detail |
| --- | --- |
| Tuba Python | 3.14 recommended; 3.11-3.14 supported (`requires-python = ">=3.11,<3.15"`); the shared environment uses 3.14 |
| Git | Required to install the source checkout |
| Operating system | Tuba is OS-independent; the tested solver path is native Linux or Windows with WSL2 Ubuntu |
| Code_Aster | Required for solving; authoring, export inspection, and preserved-artifact review can run without it |

## Install Tuba from source

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) first.
`uv sync` downloads the Python version selected by `.python-version` and creates
a normal project `.venv`; Tuba does not need conda. Keep Code_Aster in its
separate conda environment, which supplies its compiled solver dependencies.

These instructions install the current development branch, which evolves with
the gallery and this manual. Record `git rev-parse HEAD` to identify your checkout.

```powershell
git clone --branch main --depth 1 https://github.com/jgwagenfeld/Tuba_v4.git
cd Tuba_v4
uv sync --extra course --locked
```

`uv sync` installs Tuba; it does not install Code_Aster. The `code-aster-rmed` extra installs the RMED/MED reader, not the solver:

```powershell
uv sync --extra course --extra code-aster-rmed --locked
```

There is no supported ordinary PyPI installation of the compiled Code_Aster solver.
Install it in a separate conda environment and let conda select its Python and
compiled dependencies:

```bash
conda create -y -n tuba-code-aster -c conda-forge "code-aster=18.0.12=*nompi*"
```

Run this in Linux (Ubuntu WSL on Windows) after installing Miniforge as described
above. This selects the tested non-MPI Code_Aster 18.0.12 build; conda chooses
its compatible Python and compiled dependencies. Tuba's Python 3.11-3.14 support
range applies to Tuba's own environment, not to this external solver environment.

Run the doctor and real solver smoke test below after installing or updating.

## Windows: install Code_Aster in WSL2 Ubuntu

Install Ubuntu, restart if requested, then launch it once to create a Linux user:

```powershell
wsl --install -d Ubuntu
wsl --list --verbose
wsl -d Ubuntu -- bash -lc "uname -m"
```

The architecture must report `x86_64`. Install Miniforge from PowerShell without letting PowerShell expand Linux variables:

```powershell
@'
set -euo pipefail
cd /tmp
curl -L -o Miniforge3-Linux-x86_64.sh \
  https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash Miniforge3-Linux-x86_64.sh -b -p "$HOME/miniforge3"
'@ | wsl -d Ubuntu -- bash -s
```

Install the solver and expose a stable `run_aster` wrapper. If the
`tuba-code-aster` environment already exists, skip `conda create`:

```powershell
@'
set -euo pipefail
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda create -y -n tuba-code-aster -c conda-forge "code-aster=18.0.12=*nompi*"
mkdir -p "$HOME/bin"
cat > "$HOME/bin/run_aster" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
exec "$HOME/miniforge3/envs/tuba-code-aster/bin/run_aster" "$@"
SH
chmod +x "$HOME/bin/run_aster"
grep -qxF 'export PATH="$HOME/bin:$PATH"' "$HOME/.profile" || \
  echo 'export PATH="$HOME/bin:$PATH"' >> "$HOME/.profile"
PATH="$HOME/bin:$PATH" run_aster --version
'@ | wsl -d Ubuntu -- bash -s
```

Validate the Linux runner directly:

```powershell
wsl -d Ubuntu -- bash -lc "command -v run_aster; run_aster --version"
```

Expected: `run_aster` resolves below `/home/<user>/bin` and reports the solver version.

References: [Microsoft WSL installation](https://learn.microsoft.com/windows/wsl/install), [Miniforge](https://github.com/conda-forge/miniforge), [conda-forge Code_Aster](https://anaconda.org/conda-forge/code-aster), and the official [`run_aster` guide](https://codeaster.readthedocs.io/en/latest/devguide/run_aster/run_aster.html).

## Select and check the runtime

From the Windows checkout:

```powershell
$env:TUBA_CODE_ASTER_EXEC_METHOD = "wsl"
$env:TUBA_CODE_ASTER_WSL_DISTRO = "Ubuntu"
.\.venv\Scripts\python.exe -m tuba.solver.code_aster_doctor
.\.venv\Scripts\python.exe -m tuba.solver.code_aster_doctor --check
```

If the check reports `blocked`, do not set `RUN_CODE_ASTER = True` in notebooks and do not display new solver results. Fix the runtime or keep the notebook in artifact-loading mode with existing Code_Aster artifacts.

Do not set `TUBA_CODE_ASTER_PYTHON` to a Linux path when Tuba runs from Windows; Windows cannot execute that binary directly.

## Run the real solver smoke test

```powershell
$env:TUBA_CODE_ASTER_EXEC_METHOD = "wsl"
$env:TUBA_CODE_ASTER_WSL_DISTRO = "Ubuntu"
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_real_smoke -v
```

`OK` proves that Tuba exported a study, executed Code_Aster, read the displacement, internal-force, reaction, and stress tables, and returned a verified `AnalysisRun`.

## Native Linux x86_64: separate developer environments

Keep Tuba in its virtual environment and Code_Aster in a separate conda environment:

```bash
sudo apt-get update
sudo apt-get install -y libglu1-mesa libxft2 libgomp1
uv sync --extra course --locked
. .venv/bin/activate

curl -fsSLo /tmp/Miniforge3-Linux-x86_64.sh \
  https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash /tmp/Miniforge3-Linux-x86_64.sh -b -p "$HOME/miniforge3"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda create -y -n tuba-code-aster -c conda-forge "code-aster=18.0.12=*nompi*"

export TUBA_CODE_ASTER_EXEC_METHOD=python_bridge
export TUBA_CODE_ASTER_PYTHON="$HOME/miniforge3/envs/tuba-code-aster/bin/python"
python -m tuba.solver.code_aster_doctor --check
```

The doctor must report `python_bridge: ready` before a production solve.
Set these variables again when starting a new developer shell. The Windows
alternative uses WSL to reach the Linux runtime instead.

## Environment-variable reference

| Variable | Purpose |
| --- | --- |
| `TUBA_CODE_ASTER_EXEC_METHOD` | `auto` (default), `wsl`, `docker`, `command`, or `python_bridge` |
| `TUBA_CODE_ASTER_WSL_DISTRO` | WSL distribution, normally `Ubuntu` |
| `TUBA_CODE_ASTER_RUNNER_COMMAND` / `TUBA_CODE_ASTER_RUNNER` | Explicit `run_aster` command for `command` mode |
| `TUBA_CODE_ASTER_DOCKER_IMAGE` | Advanced fallback image; a run through it is always unverified |
| `TUBA_CODE_ASTER_PYTHON` | Host-executable Python for the external-process bridge |
| `TUBA_RUN_CODE_ASTER_INTEGRATION` | Set to `1` to opt in to the real-solver smoke test |

A Code_Aster run executed through Docker is always unverified: an engineering review refuses its results, and so does a scene built from analysis runs. A mutable or placeholder image name is not a production dependency.

## Try a model in the browser

Open a [gallery example](examples.md), choose **Build**, edit `model.py`, and
click **Update geometry** (Ctrl+Enter). Python runs on your computer inside the
browser; no Tuba installation or server account is required. The first run
downloads the Python runtime; successful updates reuse it for the rest of the tab's session.
**Stop** cancels a run. **Exchange → Example actions → Reset example** restores the
published example, and **Exchange → Download model.py** saves your script.

The preview contains geometry only. **Review** continues to show the published
Code_Aster results and marks them outdated when your script differs. A preview
does not calculate stress, displacement, reactions, compliance, or operating
clashes. Download the script and use Tuba with Code_Aster for evaluation.
Native packages such as Gmsh and IFC tools are unavailable in the browser;
scripts requiring them report an error and retain the last successful preview.
Browser edits are kept while switching examples in the tab, not after a reload.

## Open the notebooks

In the shared Linux environment:

```bash
jupyter lab notebooks/04_visualization_gallery.ipynb
jupyter lab notebooks/07_bim_data_exchange.ipynb
```

In the Windows `.venv` developer alternative:

```powershell
.\.venv\Scripts\jupyter.exe lab notebooks\04_visualization_gallery.ipynb
.\.venv\Scripts\jupyter.exe lab notebooks\07_bim_data_exchange.ipynb
```

Both load preserved Code_Aster artifacts by default. Set a notebook to solve only after the runtime check passes. For the ordinary review path, open the [gallery](examples.md) instead; the [Tutorial](tutorial.md) says which two notebooks survive and why.

## Troubleshooting

| Symptom | Check | Action |
| --- | --- | --- |
| `run_aster` not found | `wsl -d Ubuntu -- bash -lc "command -v run_aster"` | Recreate the stable wrapper and check `~/.profile` |
| Doctor reports blocked | `python -m tuba.solver.code_aster_doctor --check` | Fix the selected runtime before using `run_solver=True` |
| Integration test skips | Check `TUBA_RUN_CODE_ASTER_INTEGRATION` | Set it to `1`; the opt-in is deliberate |
| Study exports but results are absent | Inspect `stdout.wsl.log`, `stderr.wsl.log`, and `study.mess` | Treat the run as failed; export does not prove execution |

## Optional surfaces


For the Windows developer alternative, add review and exchange extras to the
source installation. The shared conda environment already includes them:

```powershell
uv sync --extra course --extra viz --extra code-aster-rmed --extra ifc --locked
```

The installed package includes the built Three.js review application. Its asset
directory is available through `tuba.visualization.viewer_assets_path()`.
Start it against a generated scene bundle with:

```powershell
.\.venv\Scripts\python.exe -m tuba.visualization.viewer path/to/bundle --open
```

The command validates `scene.json`, serves only the packaged viewer and selected
bundle, and prints the exact local URL. `.\.venv\Scripts\tuba-viewer.exe` is the
equivalent installed Windows console command.

## Installing Tuba beside the solver

These notes apply to the developer alternative.

This installs Tuba from the checkout; it does not install Code_Aster. The
solver is a separate Linux runtime. On Windows, install it in WSL2 Ubuntu
following the walkthrough above. The `code-aster-rmed` extra adds result-file
reading support only; it is not the solver.

VS Code notebooks default to loading committed Code_Aster artifacts when those
artifacts are present. Set `RUN_CODE_ASTER = True` only after the doctor check
reports a ready runtime; the notebook loader preserves existing result tables
when runtime preflight fails.
