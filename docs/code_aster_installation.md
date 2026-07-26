# Code_Aster Installation Walkthrough

This guide installs Code_Aster for the Tuba v4 workflow:

```text
Tuba model -> Code_Aster solve -> imported result artifacts -> result display
```

Code_Aster is not optional for production stress, displacement, reaction,
compliance, operating-state clash, or result visualization workflows.

## Tuba And Code_Aster Are Separate Installs

Installing Tuba from its checkout with `python -m pip install .` installs Tuba
only. It does not install Code_Aster.

Likewise, this optional Tuba extra installs the RMED/MED reader, not the solver:

```bash
python -m pip install ".[code-aster-rmed]"
```

Code_Aster includes Python modules such as `code_aster` and `run_aster`, but
they are part of the compiled Linux solver distribution. There is no supported
ordinary PyPI/pip installation for the Code_Aster solver. The tested setup for
this repository installs it from conda-forge in Linux or WSL2 Ubuntu.

This walkthrough assumes a Tuba checkout. From its root, create the Windows
Python environment used by the commands below:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install ".[course]"
```

## Current Recommended Path

Use WSL2 Ubuntu with conda-forge Code_Aster.

Why this path:

- The conda-forge `code-aster` package is published for `linux-64`.
- Windows is the normal host for this repo.
- Tuba can call `run_aster` inside WSL through `exec_method="wsl"`.
- Docker remains a fallback, not the first setup path.

References:

- Microsoft WSL installation: <https://learn.microsoft.com/windows/wsl/install>
- Miniforge installation: <https://github.com/conda-forge/miniforge>
- conda-forge package: <https://anaconda.org/conda-forge/code-aster>
- Code_Aster `run_aster` docs: <https://codeaster.readthedocs.io/en/latest/devguide/run_aster/run_aster.html>
- Code_Aster Python package docs: <https://codeaster.readthedocs.io/en/latest/devguide/code_aster/code_aster.html>

## Check For An Existing Runtime

From PowerShell at the repo root:

```powershell
wsl --list --verbose
.\.venv\Scripts\python.exe -m tuba.solver.code_aster_doctor
```

Equivalent module form: `python -m tuba.solver.code_aster_doctor`.

Check the Ubuntu distro directly:

```powershell
wsl -d Ubuntu -- bash -lc "uname -m; command -v conda || true; command -v run_aster || true"
```

The architecture must print `x86_64`. If `run_aster` already resolves, skip to
Step 6 and validate it with Tuba. Otherwise, continue with the installation.

## Step 1: Install Or Start Ubuntu WSL2

If Ubuntu is missing:

```powershell
wsl --install -d Ubuntu
```

Restart Windows if WSL requests it. Launch Ubuntu once and create its Linux
username and password, then confirm from PowerShell:

```powershell
wsl --list --verbose
wsl -d Ubuntu -- bash -lc "uname -a"
```

The architecture must be `x86_64`. The conda-forge Code_Aster package is a
Linux package, not a native Windows package.

## Step 2: Install Miniforge In Ubuntu

Run from PowerShell. The script is piped to WSL stdin to avoid PowerShell
expanding Linux variables such as `$HOME`.

```powershell
@'
set -euo pipefail
cd /tmp
curl -L -o Miniforge3-Linux-x86_64.sh \
  https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash Miniforge3-Linux-x86_64.sh -b -p "$HOME/miniforge3"
'@ | wsl -d Ubuntu -- bash -s
```

Open a fresh WSL shell or use the conda profile script explicitly in the next
commands.

## Step 3: Install Code_Aster From conda-forge

Run from PowerShell:

```powershell
@'
set -euo pipefail
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda create -y -n tuba-code-aster --override-channels -c conda-forge \
  python=3.12 code-aster=18.0.12
'@ | wsl -d Ubuntu -- bash -s
```

Tuba v4 is validated with Code_Aster 18.0.12. Change the pin only after the
real solver smoke test passes with the newer solver.

## Step 4: Validate Code_Aster Inside WSL

Run:

```powershell
@'
set -euo pipefail
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate tuba-code-aster
which run_aster
run_aster --version || run_aster --help | head -40
python - <<'PY'
import run_aster
print(run_aster.__file__)
PY
'@ | wsl -d Ubuntu -- bash -s
```

Expected:

- `which run_aster` prints a path under `~/miniforge3/envs/tuba-code-aster/bin`.
- `run_aster --version` or `run_aster --help` prints Code_Aster runner output.
- Python can import `run_aster`.

## Step 5: Add A WSL run_aster Wrapper For Tuba

Tuba's Windows process calls a configured WSL distro and expects `run_aster` to
be visible in that distro's non-interactive Bash environment. Create a stable
wrapper:

```powershell
@'
set -euo pipefail
mkdir -p "$HOME/bin"
cat > "$HOME/bin/run_aster" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
exec "$HOME/miniforge3/envs/tuba-code-aster/bin/run_aster" "$@"
SH
chmod +x "$HOME/bin/run_aster"
grep -qxF 'export PATH="$HOME/bin:$PATH"' "$HOME/.profile" || \
  echo 'export PATH="$HOME/bin:$PATH"' >> "$HOME/.profile"
PATH="$HOME/bin:$PATH" run_aster --version || PATH="$HOME/bin:$PATH" run_aster --help | head -40
'@ | wsl -d Ubuntu -- bash -s
```

Validate from a fresh WSL shell:

```powershell
wsl -d Ubuntu -- bash -lc "command -v run_aster; run_aster --version || run_aster --help | head -20"
```

Expected:

```text
/home/<user>/bin/run_aster
```

## Step 6: Validate Tuba Runtime Discovery

Select WSL Ubuntu, then run the doctor from the Windows repo root:

```powershell
$env:TUBA_CODE_ASTER_EXEC_METHOD = "wsl"
$env:TUBA_CODE_ASTER_WSL_DISTRO = "Ubuntu"
.\.venv\Scripts\python.exe -m tuba.solver.code_aster_doctor
```

Use `--check` to prove the discovered runtime can find a Code_Aster runner
without starting a full solve:

```powershell
.\.venv\Scripts\python.exe -m tuba.solver.code_aster_doctor --check
```

If the check reports `blocked`, do not set `RUN_CODE_ASTER = True` in notebooks.
Keep the notebook in artifact-loading mode until the runtime check is ready.

Expected:

```text
Code_Aster runtime candidates:
- wsl: available; command=wsl
...
```

Do not set `TUBA_CODE_ASTER_PYTHON` to a Linux path when running Tuba from
Windows. Windows cannot execute the Linux Python binary directly. Use
`TUBA_CODE_ASTER_PYTHON` only when Tuba itself runs inside Linux/WSL, or when the
configured Python executable is directly executable by the host process.

## Step 7: Run The Real Solver Smoke Test

Run from the Windows repo root:

```powershell
$env:TUBA_CODE_ASTER_EXEC_METHOD = "wsl"
$env:TUBA_CODE_ASTER_WSL_DISTRO = "Ubuntu"
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_real_smoke -v
```

Expected:

```text
OK
```

This is the minimum proof that Tuba can:

1. Export a Code_Aster study.
2. Execute it with the installed solver.
3. Read `study_depl.csv`, `study_effo.csv`, `study_reac.csv`, and
   `study_sieq.csv`.
4. Return `FEAResults`.

## Step 8: Run A Notebook Workflow

After the smoke test passes, notebook cells using
`load_or_run_code_aster_results(...)` can execute missing studies instead of
stopping at missing result tables.

Recommended notebook environment:

```powershell
.\.venv\Scripts\python.exe -m pip install ".[course]"
.\.venv\Scripts\jupyter.exe lab notebooks\00_welcome_and_setup.ipynb
```

Notebook result cells configure the default runtime through
`configure_code_aster_notebook_runtime()`. The standard Windows/WSL defaults
are:

```python
CODE_ASTER_RUNTIME = configure_code_aster_notebook_runtime(
    exec_method="wsl",
    wsl_distro="Ubuntu",
)
```

Use `notebooks\03_stress_analysis_and_compliance.ipynb` for the detailed stress
and ASME B31.3 lesson after the quick welcome workflow is running.

## Native Linux

On an `x86_64` Linux host, run this from the Tuba checkout. It keeps Tuba in a
normal virtual environment and Code_Aster in its separate conda environment:

```bash
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
grep -qxF 'export PATH="$HOME/bin:$PATH"' "$HOME/.profile" || \
  echo 'export PATH="$HOME/bin:$PATH"' >> "$HOME/.profile"
export PATH="$HOME/bin:$PATH"
run_aster --version
python -m tuba.solver.code_aster_doctor --check --exec-method command
```

The check must report `command: ready` before a production solve.

## Docker Fallback

Docker is useful only if a working Code_Aster image is available.

Check local images:

```powershell
docker image ls
```

Run with Docker:

```powershell
$env:TUBA_CODE_ASTER_EXEC_METHOD = "docker"
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_real_smoke -v
```

If Docker pulls a public image, pin the image name in docs and CI before relying
on it. Do not treat a placeholder image name as a production dependency.

## Troubleshooting

### `Code_Aster runner not found`

Inside WSL:

```powershell
wsl -d Ubuntu -- bash -lc "command -v run_aster"
```

Fix: repeat Step 5, then rerun the check above.

### `conda: command not found`

Use the explicit profile path:

```powershell
wsl -d Ubuntu -- bash -lc "source ~/miniforge3/etc/profile.d/conda.sh; conda --version"
```

If that file is missing, repeat Step 2.

### Smoke test still skips

The integration test intentionally skips unless this is set:

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
```

### Smoke test creates study files but no result CSV files

Open the solver logs in the temporary work directory before it is deleted, or
run a non-temporary study manually:

```python
from pathlib import Path
from tuba.solver.aster import CodeAsterSolver

solver = CodeAsterSolver(work_dir="code_aster_study", exec_method="wsl")
# export/solve through a concrete model, then inspect:
print(Path("code_aster_study").resolve())
```

Check:

- `stdout.wsl.log`
- `stderr.wsl.log`
- `study.mess`

### Windows path passed to WSL incorrectly

Use `exec_method="wsl"` so Tuba converts the working directory to `/mnt/<drive>`.
Do not call `TUBA_CODE_ASTER_RUNNER="wsl ..."` unless the command also handles
Windows-to-WSL path conversion itself.
