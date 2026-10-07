from importlib.metadata import version
from copy import deepcopy
from pathlib import Path
import subprocess
import sys

import tuba
import yaml
from tuba.model import MODEL_SERIALIZATION_VERSION


ROOT = Path(__file__).resolve().parents[1]


def test_test_only_ci_jobs_end_with_clean_tree_check():
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )

    for job_name in ("python", "ifc-windows", "notebooks-and-docs", "viewer", "assembled-pages"):
        commands = [
            step["run"]
            for step in workflow["jobs"][job_name]["steps"]
            if "run" in step
        ]
        assert commands[-1] == "git diff --exit-code"

    for job_name in ("distribution", "code-aster-integration"):
        commands = [
            step["run"]
            for step in workflow["jobs"][job_name]["steps"]
            if "run" in step
        ]
        assert "git diff --exit-code" not in commands


def test_runtime_version_comes_from_installed_package_metadata():
    source = (ROOT / "tuba" / "__init__.py").read_text(encoding="utf-8")

    assert tuba.__version__ == version("tuba")
    assert '__version__ = "' not in source


def test_model_serialization_version_is_explicit_and_separate(monkeypatch):
    payload = tuba.Model("version-contract").to_dict()
    serialized_version = payload["meta"]["version"]

    monkeypatch.setattr(tuba, "__version__", "999.0.0")

    assert serialized_version == "tuba.model.v4"
    assert serialized_version == MODEL_SERIALIZATION_VERSION
    assert serialized_version != version("tuba")
    assert tuba.Model("version-contract").to_dict()["meta"]["version"] == serialized_version

    legacy_payload = deepcopy(payload)
    legacy_payload["meta"]["version"] = "4.0.0"
    assert tuba.Model.from_dict(legacy_payload).to_dict()["meta"]["version"] == serialized_version


def test_release_tag_must_match_package_version():
    checker = ROOT / "scripts" / "check_release_tag.py"

    matching = subprocess.run(
        [sys.executable, checker, "tag", f"v{version('tuba')}"],
        capture_output=True,
        text=True,
    )
    mismatched = subprocess.run(
        [sys.executable, checker, "tag", "v999.0.0"],
        capture_output=True,
        text=True,
    )
    matching_branch = subprocess.run(
        [sys.executable, checker, "branch", f"v{version('tuba')}"],
        capture_output=True,
        text=True,
    )

    assert matching.returncode == 0, matching.stderr
    assert mismatched.returncode != 0
    assert "does not match package version" in mismatched.stderr
    assert matching_branch.returncode != 0
    assert "requires a Git tag ref" in matching_branch.stderr


def test_ci_and_release_workflows_cover_local_release_gates():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    ci_jobs = yaml.safe_load(ci)["jobs"]

    for workflow in (ci, release):
        assert "npm test" in workflow
        assert "scripts/prepare_release.py" in workflow
        assert "scripts/check_notebooks.py" in workflow
        assert "twine check" in workflow
        assert "scripts/verify_release_wheel.py dist" in workflow

    assert 'python-version: ["3.11", "3.12", "3.13", "3.14"]' in ci
    assert "uv sync --group docs --extra course --extra dev --locked" in ci
    python_steps = ci_jobs["python"]["steps"]
    assert any(step.get("uses") == "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020" for step in python_steps)
    assert any(step.get("run") == "npm ci" and step.get("working-directory") == "viewer" for step in python_steps)
    assert "uv run python -m pytest" in ci
    assert "uv run python -m pytest" in release
    for workflow in (ci, release):
        assert "libglu1-mesa" in workflow
        assert "xvfb" in workflow
        assert "xvfb-run -a uv run python -m pytest" in workflow
        assert "xvfb-run -a uv run python scripts/check_notebooks.py" in workflow
    assert "scripts/check_release_tag.py" in release
    assert 'TAG: ${{ inputs.tag }}' in release
    assert 'tag "$TAG"' in release
    assert "TUBA_RUN_CODE_ASTER_INTEGRATION: \"1\"" in ci
    assert "scripts/check_code_aster_references.py" in ci


def test_windows_ifc_job_fails_closed_on_the_locked_runtime():
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    job = workflow["jobs"]["ifc-windows"]
    commands = [step["run"] for step in job["steps"] if "run" in step]

    assert job["runs-on"] == "windows-latest"
    assert any(
        step.get("uses") == "astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7"
        and step.get("with", {}).get("python-version") == "3.14"
        for step in job["steps"]
    )
    assert "uv sync --extra dev --extra ifc --locked" in commands
    assert 'uv run python -c "import ifcopenshell"' in commands
    assert (
        "uv run python -m pytest tests/test_ifc.py tests/test_ifc_mapping.py "
        "tests/test_ifc_pipe_systems.py tests/test_ifc_placements.py "
        "tests/test_code_aster_artifact_import.py -q"
    ) in commands


def test_source_release_gates_tag_on_build_and_real_code_aster_without_pypi():
    release = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    )

    jobs = release["jobs"]
    code_aster = jobs["code-aster-integration"]
    commands = [step["run"] for step in code_aster["steps"] if "run" in step]

    assert code_aster["runs-on"] == ["self-hosted", "code-aster"]
    assert code_aster["env"]["TUBA_RUN_CODE_ASTER_INTEGRATION"] == "1"
    assert "uv run python -m tuba.solver.code_aster_doctor --check" in commands
    assert "uv run python scripts/check_code_aster_references.py" in commands
    assert jobs["build"]["needs"] == ["approved-ref", "code-aster-integration"]
    assert jobs["tag"]["needs"] == ["approved-ref", "build"]
    assert jobs["tag"]["permissions"]["contents"] == "write"
    tag_commands = [step["run"] for step in jobs["tag"]["steps"] if "run" in step]
    assert any('gh api --method POST' in command and 'sha="$SOURCE_SHA"' in command for command in tag_commands)
    assert "publish" not in jobs
    release_text = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    assert "pypa/gh-action-pypi-publish" not in release_text
    assert "environment: pypi" not in release_text


def test_self_hosted_solver_jobs_refresh_every_engineering_gallery_before_pages_validation():
    workflows = [
        yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
        for name in ("ci.yml", "release.yml")
    ]
    refresh_command = "uv run python scripts/refresh_code_aster_gallery.py --all"
    pages_command = "uv run python scripts/build_pages.py pages --output .build/code-aster-pages"

    for workflow in workflows:
        job = workflow["jobs"]["code-aster-integration"]
        steps = job["steps"]
        commands = [step["run"] for step in steps if "run" in step]

        assert any(step.get("uses") == "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020" for step in steps)
        assert "uv sync --group docs --extra dev --extra code-aster-rmed --extra ifc --locked" in commands
        assert any(
            step.get("run") == "npm ci" and step.get("working-directory") == "viewer"
            for step in steps
        )
        assert commands.count(refresh_command) == 1
        assert not any(
            command.startswith("uv run python scripts/refresh_code_aster_gallery.py ")
            and command != refresh_command
            for command in commands
        )
        assert pages_command in commands
        assert commands.index(refresh_command) < commands.index(pages_command)

    ci_job = workflows[0]["jobs"]["code-aster-integration"]
    assert "pull_request" not in ci_job["if"]
    assert "refs/heads/main" in ci_job["if"]


def test_source_release_smokes_the_build_artifact():
    release = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    )
    steps = release["jobs"]["build"]["steps"]
    commands = [step["run"] for step in steps if "run" in step]

    build_index = commands.index("uv build --no-sources")
    smoke_index = commands.index("uv run python scripts/verify_release_wheel.py dist")

    assert smoke_index == build_index + 2
    assert commands[build_index + 1] == "uvx twine check dist/*"


def test_only_stronger_real_solver_smoke_remains():
    assert (ROOT / "tests" / "test_code_aster_real_smoke.py").is_file()
    assert not (ROOT / "tests" / "integration" / "test_code_aster_real_smoke.py").exists()


def _run_steps(workflow, job):
    return [step for step in workflow["jobs"][job]["steps"] if "run" in step]


def _only_step_index(steps, predicate):
    matches = [index for index, step in enumerate(steps) if predicate(step)]
    assert len(matches) == 1, matches
    return matches[0]


def test_pages_deploys_only_the_solver_produced_exact_revision_artifact():
    source = (ROOT / ".github/workflows/tuba-pages.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(source)
    jobs = workflow["jobs"]
    assert workflow["permissions"] == {}
    assert "workflow_run:" in source and "workflows: [CI]" in source
    assert "github.event.workflow_run.conclusion == 'success'" in jobs["approved-ref"]["if"]
    assert "github.event.workflow_run.head_repository.full_name == github.repository" in jobs["approved-ref"]["if"]
    assert jobs["deploy"]["needs"] == ["approved-ref", "artifact"]
    assert jobs["deploy"]["permissions"] == {"pages": "write", "id-token": "write"}
    assert jobs["deploy"]["environment"]["name"] == "github-pages"
    artifact_steps = jobs["artifact"]["steps"]
    download = next(step for step in artifact_steps if step.get("uses", "").startswith("actions/download-artifact@"))
    assert download["with"]["run-id"] == "${{ github.event.workflow_run.id }}"
    assert download["with"]["name"] == "code-aster-pages-${{ needs.approved-ref.outputs.sha }}-${{ github.event.workflow_run.run_attempt }}"
    assert any(step.get("run") == "python3 scripts/check_pages_artifact.py verify --output _site" for step in artifact_steps)
    assert not any("build_pages.py" in step.get("run", "") for step in artifact_steps)
    assert "configure-pages" not in source  # Repository settings require a separate admin action.
    snapshot = jobs["snapshots"]
    assert "inputs.update_snapshots" in snapshot["if"]
    assert snapshot["permissions"] == {"contents": "read"}
    assert any(step.get("run") == "npm run e2e:pages -- --update-snapshots" for step in snapshot["steps"])
    assert any(step.get("with", {}).get("name") == "pages-snapshots-linux" for step in snapshot["steps"])
    assert not any("upload-pages-artifact" in step.get("uses", "") for step in snapshot["steps"])


def test_ci_gates_current_docs_viewer_and_assembled_pages():
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )

    docs = [step["run"] for step in _run_steps(workflow, "notebooks-and-docs")]
    assert "uv sync --group docs --extra course --extra dev --locked" in docs
    assert "uv run zensical build --clean --strict" in docs
    assert any("tests/test_static_site_docs.py" in command for command in docs)

    viewer_steps = workflow["jobs"]["viewer"]["steps"]
    viewer = [step["run"] for step in viewer_steps if "run" in step]
    assert "npx playwright install --with-deps chromium" in viewer
    assert "npm test" in viewer
    assert "npm run e2e -- public-code-aster-review" not in viewer
    for scenario in ("section-camera", "legacy-workflow"):
        assert f"npm run e2e -- {scenario}" in viewer

    assembled_steps = workflow["jobs"]["assembled-pages"]["steps"]
    assembled = [step["run"] for step in assembled_steps if "run" in step]
    assert "uv sync --group docs --extra dev --extra code-aster-rmed --extra ifc --locked" in assembled
    assert "uv run python -m pytest tests/test_release_metadata.py tests/test_pages_build.py -q" in assembled
    build = "uv run python scripts/build_pages.py pages --output .build/pages-check"
    assert assembled.count(build) == 1
    setup_uv = _only_step_index(
        assembled_steps, lambda step: step.get("uses") == "astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7"
    )
    setup_node = _only_step_index(
        assembled_steps, lambda step: step.get("uses") == "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020"
    )
    sync = _only_step_index(
        assembled_steps,
        lambda step: step.get("run")
        == "uv sync --group docs --extra dev --extra code-aster-rmed --extra ifc --locked",
    )
    npm = _only_step_index(
        assembled_steps,
        lambda step: step.get("run") == "npm ci"
        and step.get("working-directory") == "viewer",
    )
    graphics = _only_step_index(
        assembled_steps,
        lambda step: step.get("run")
        == "sudo apt-get update && sudo apt-get install -y libglu1-mesa libxft2 libgomp1",
    )
    python_tests = _only_step_index(
        assembled_steps,
        lambda step: step.get("run")
        == "uv run python -m pytest tests/test_release_metadata.py tests/test_pages_build.py -q",
    )
    build_step = _only_step_index(
        assembled_steps, lambda step: step.get("run") == build
    )
    chromium = _only_step_index(
        assembled_steps,
        lambda step: step.get("run") == "npx playwright install --with-deps chromium",
    )
    semantic = _only_step_index(
        assembled_steps, lambda step: "pages-catalog" in step.get("run", "")
    )
    visual = _only_step_index(
        assembled_steps, lambda step: step.get("run") == "npm run e2e:pages"
    )

    assert assembled_steps[semantic]["env"]["TUBA_PAGES_SITE_ROOT"] == "../.build/pages-check"
    assert assembled_steps[visual]["env"]["TUBA_PAGES_SITE_ROOT"] == "../.build/pages-check"
    assert setup_uv < sync
    assert setup_node < npm
    # The browser precedes the build: build_pages.py photographs every gallery card.
    assert max(sync, npm, graphics) < python_tests < chromium < build_step < semantic < visual
