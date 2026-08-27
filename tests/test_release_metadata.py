from importlib.metadata import version
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import tuba
import yaml
from tuba.model import MODEL_SERIALIZATION_VERSION


ROOT = Path(__file__).resolve().parents[1]


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

    assert 'python-version: ["3.11", "3.12"]' in ci
    assert "uv sync --group docs --extra course --extra dev --locked" in ci
    python_steps = ci_jobs["python"]["steps"]
    assert any(step.get("uses") == "actions/setup-node@v4" for step in python_steps)
    assert any(step.get("run") == "npm ci" and step.get("working-directory") == "viewer" for step in python_steps)
    assert "uv run python -m pytest" in ci
    assert "uv run python -m pytest" in release
    for workflow in (ci, release):
        assert "libglu1-mesa" in workflow
        assert "xvfb" in workflow
        assert "xvfb-run -a uv run python -m pytest" in workflow
        assert "xvfb-run -a uv run python scripts/check_notebooks.py" in workflow
    assert "scripts/check_release_tag.py" in release
    assert 'tag "${{ inputs.tag }}"' in release
    assert "TUBA_RUN_CODE_ASTER_INTEGRATION: \"1\"" in ci
    assert "tests/test_code_aster_real_smoke.py" in ci


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
    assert "uv run python -m pytest tests/test_code_aster_real_smoke.py" in commands
    assert jobs["build"]["needs"] == "code-aster-integration"
    assert jobs["tag"]["needs"] == "build"
    assert jobs["tag"]["permissions"]["contents"] == "write"
    tag_commands = [step["run"] for step in jobs["tag"]["steps"] if "run" in step]
    assert any('git push origin "$TAG"' in command for command in tag_commands)
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
    refresh_commands = [
        "uv run python scripts/refresh_code_aster_gallery.py --gallery code-aster-review "
        "--output notebooks/code_aster_results/viz_gallery_operating",
        "uv run python scripts/refresh_code_aster_gallery.py --gallery support-rack-review "
        "--output notebooks/code_aster_results/support_rack_operating",
        "uv run python scripts/refresh_code_aster_gallery.py --gallery autorouted-expansion-loop "
        "--output notebooks/code_aster_results/autorouted_expansion_hot",
    ]
    pages_command = "uv run python scripts/build_pages.py pages --output .build/code-aster-pages"

    for workflow in workflows:
        job = workflow["jobs"]["code-aster-integration"]
        steps = job["steps"]
        commands = [step["run"] for step in steps if "run" in step]

        assert any(step.get("uses") == "actions/setup-node@v4" for step in steps)
        assert "uv sync --group docs --extra dev --extra code-aster-rmed --locked" in commands
        assert any(
            step.get("run") == "npm ci" and step.get("working-directory") == "viewer"
            for step in steps
        )
        assert all(command in commands for command in refresh_commands)
        assert pages_command in commands
        assert max(commands.index(command) for command in refresh_commands) < commands.index(pages_command)

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


def test_pages_deploys_only_the_verified_single_owner_artifact():
    source = (ROOT / ".github" / "workflows" / "tuba-pages.yml").read_text(
        encoding="utf-8"
    )
    workflow = yaml.safe_load(source)
    steps = workflow["jobs"]["build"]["steps"]
    commands = [step["run"] for step in steps if "run" in step]

    build = "uv run python scripts/build_pages.py pages --output _site"
    assert source.count(build) == 1
    assert "uv sync --group docs --extra code-aster-rmed --locked" in commands
    assert any(
        step.get("run") == "npm ci" and step.get("working-directory") == "viewer"
        for step in steps
    )
    assert any(
        step.get("uses") == "astral-sh/setup-uv@v6"
        and step.get("with", {}).get("python-version") == "3.12"
        for step in steps
    )
    assert any(
        step.get("uses") == "actions/setup-node@v4"
        and step.get("with", {}).get("node-version") == 22
        for step in steps
    )

    setup_uv = _only_step_index(
        steps, lambda step: step.get("uses") == "astral-sh/setup-uv@v6"
    )
    setup_node = _only_step_index(
        steps, lambda step: step.get("uses") == "actions/setup-node@v4"
    )
    sync = _only_step_index(
        steps,
        lambda step: step.get("run")
        == "uv sync --group docs --extra code-aster-rmed --locked",
    )
    npm = _only_step_index(
        steps,
        lambda step: step.get("run") == "npm ci"
        and step.get("working-directory") == "viewer",
    )
    graphics = _only_step_index(
        steps,
        lambda step: step.get("run")
        == "sudo apt-get update && sudo apt-get install -y libglu1-mesa libxft2 libgomp1",
    )
    build_step = _only_step_index(steps, lambda step: step.get("run") == build)
    chromium = _only_step_index(
        steps,
        lambda step: step.get("run") == "npx playwright install --with-deps chromium",
    )
    semantic = _only_step_index(
        steps, lambda step: "pages-catalog" in step.get("run", "")
    )
    visual = _only_step_index(
        steps, lambda step: step.get("run") == "npm run e2e:pages"
    )
    configure = _only_step_index(
        steps, lambda step: step.get("uses") == "actions/configure-pages@v5"
    )
    upload = _only_step_index(
        steps, lambda step: step.get("uses") == "actions/upload-pages-artifact@v3"
    )

    assert steps[semantic]["env"]["TUBA_PAGES_SITE_ROOT"] == "../_site"
    assert steps[visual]["env"]["TUBA_PAGES_SITE_ROOT"] == "../_site"
    assert setup_uv < sync
    assert setup_node < npm
    assert max(sync, npm, graphics) < build_step < chromium < semantic < visual < configure < upload
    assert steps[upload]["with"]["path"] == "_site"
    assert not any(
        command in source
        for command in (
            "cp -R docs/site",
            "cp -R tuba/visualization/_viewer",
            "cp -R viewer/public/code-aster-review",
            "cp -R viewer/public/imported_component_mixed_demo",
        )
    )
    assert "code_aster_doctor" not in source
    assert "TUBA_RUN_CODE_ASTER_INTEGRATION" not in source


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
    assert "uv sync --group docs --extra dev --extra code-aster-rmed --locked" in assembled
    assert "uv run python -m pytest tests/test_release_metadata.py tests/test_pages_build.py -q" in assembled
    build = "uv run python scripts/build_pages.py pages --output .build/pages-check"
    assert assembled.count(build) == 1
    setup_uv = _only_step_index(
        assembled_steps, lambda step: step.get("uses") == "astral-sh/setup-uv@v6"
    )
    setup_node = _only_step_index(
        assembled_steps, lambda step: step.get("uses") == "actions/setup-node@v4"
    )
    sync = _only_step_index(
        assembled_steps,
        lambda step: step.get("run")
        == "uv sync --group docs --extra dev --extra code-aster-rmed --locked",
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
    assert max(sync, npm, graphics) < python_tests < build_step < chromium < semantic < visual


def test_playwright_pages_gate_can_serve_the_prebuilt_workflow_artifact():
    script = (
        "import config from './viewer/playwright.config.js';"
        "console.log(JSON.stringify({"
        "webServer: config.webServer, snapshotPathTemplate: config.snapshotPathTemplate"
        "}));"
    )
    default_environment = os.environ.copy()
    default_environment.pop("TUBA_PAGES_SITE_ROOT", None)
    default_result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        env=default_environment,
        capture_output=True,
        text=True,
    )
    environment = default_environment | {"TUBA_PAGES_SITE_ROOT": "../_site"}
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert default_result.returncode == 0, default_result.stderr
    default_config = json.loads(default_result.stdout)
    default_server = default_config["webServer"]
    assert default_config["snapshotPathTemplate"] == (
        "{testDir}/snapshots/{testFilePath}/{platform}/{arg}{ext}"
    )
    assert "scripts/build_pages.py pages --output .build/pages-check" in default_server["command"]
    assert "../.build/pages-check" in default_server["command"]
    assert result.returncode == 0, result.stderr
    web_server = json.loads(result.stdout)["webServer"]
    assert "../_site" in web_server["command"]
    assert "configFile: false" in web_server["command"]
    assert "scripts/build_pages.py" not in web_server["command"]
