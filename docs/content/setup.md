# Setup

Tuba authoring and Code_Aster solving are separate installations:

```text
Tuba model -> Code_Aster solve -> imported result artifacts -> result display
```

**pip installs Tuba, not Code_Aster.** Code_Aster is required for production stress, displacement, reaction, compliance, operating-state clash, and result visualization workflows.

## Prerequisites

| Requirement | Detail |
| --- | --- |
| Python | 3.10, 3.11, or 3.12 (`requires-python >= 3.10`) |
| Git | Required to install the tagged checkout |
| Operating system | Tuba is OS-independent; the tested solver path is native Linux or Windows with WSL2 Ubuntu |
| Code_Aster | Required for solving; authoring, export inspection, and preserved-artifact review can run without it |

## Install Tuba from the tagged checkout

```powershell
git clone --branch v4.0.1 --depth 1 https://github.com/jgwagenfeld/Tuba_v4.git
cd Tuba_v4
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install ".[course]"
```

`python -m pip install .` installs Tuba; it does not install Code_Aster. The `code-aster-rmed` extra installs the RMED/MED reader, not the solver:

```powershell
python -m pip install ".[code-aster-rmed]"
```

There is no supported ordinary PyPI installation of the compiled Code_Aster solver. Tuba v4 is currently validated with `code-aster=18.0.12`; change that pin only after the real solver smoke test passes with the newer release.

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

Install the pinned solver and expose a stable `run_aster` wrapper:

```powershell
@'
set -euo pipefail
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda create -y -n tuba-code-aster --override-channels -c conda-forge \
  python=3.12 code-aster=18.0.12
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

`OK` proves that Tuba exported a study, executed Code_Aster, read the displacement, internal-force, reaction, and stress tables, and returned `FEAResults`.

## Native Linux x86_64

Keep Tuba in its virtual environment and Code_Aster in a separate conda environment:

```bash
sudo apt-get update
sudo apt-get install -y libglu1-mesa
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ".[course]"

curl -fsSLo /tmp/Miniforge3-Linux-x86_64.sh \
  https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash /tmp/Miniforge3-Linux-x86_64.sh -b -p "$HOME/miniforge3"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda create -y -n tuba-code-aster --override-channels -c conda-forge \
  python=3.12 code-aster=18.0.12

mkdir -p "$HOME/bin"
cat > "$HOME/bin/run_aster" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
exec "$HOME/miniforge3/envs/tuba-code-aster/bin/run_aster" "$@"
SH
chmod +x "$HOME/bin/run_aster"
export PATH="$HOME/bin:$PATH"
run_aster --version
python -m tuba.solver.code_aster_doctor --check --exec-method command
```

The doctor must report `command: ready` before a production solve.

## Environment-variable reference

| Variable | Purpose |
| --- | --- |
| `TUBA_CODE_ASTER_EXEC_METHOD` | `auto` (default), `wsl`, `docker`, `command`, or `python_bridge` |
| `TUBA_CODE_ASTER_WSL_DISTRO` | WSL distribution, normally `Ubuntu` |
| `TUBA_CODE_ASTER_RUNNER_COMMAND` / `TUBA_CODE_ASTER_RUNNER` | Explicit `run_aster` command for `command` mode |
| `TUBA_CODE_ASTER_DOCKER_IMAGE` | Advanced fallback image; pin a verified digest before production use |
| `TUBA_CODE_ASTER_PYTHON` | Host-executable Python for the in-process bridge |
| `TUBA_RUN_CODE_ASTER_INTEGRATION` | Set to `1` to opt in to the real-solver smoke test |

Docker remains a fallback and requires a verified Code_Aster image. A mutable or placeholder image name is not a production dependency.

## Open the notebooks

```powershell
.\.venv\Scripts\jupyter.exe lab notebooks\00_welcome_and_setup.ipynb
.\.venv\Scripts\jupyter.exe lab notebooks\10_interactive_postprocessor.ipynb
```

Open the postprocessor only after the runtime check passes or when loading preserved Code_Aster artifacts.

## Troubleshooting

| Symptom | Check | Action |
| --- | --- | --- |
| `run_aster` not found | `wsl -d Ubuntu -- bash -lc "command -v run_aster"` | Recreate the stable wrapper and check `~/.profile` |
| Doctor reports blocked | `python -m tuba.solver.code_aster_doctor --check` | Fix the selected runtime before using `run_solver=True` |
| Integration test skips | Check `TUBA_RUN_CODE_ASTER_INTEGRATION` | Set it to `1`; the opt-in is deliberate |
| Study exports but results are absent | Inspect `stdout.wsl.log`, `stderr.wsl.log`, and `study.mess` | Treat the run as failed; export does not prove execution |
