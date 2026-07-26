from importlib.metadata import version
from copy import deepcopy
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

    for workflow in (ci, release):
        assert "npm test" in workflow
        assert "scripts/prepare_release.py" in workflow
        assert "scripts/check_notebooks.py" in workflow
        assert "twine check" in workflow
        assert "scripts/verify_release_wheel.py dist" in workflow

    assert 'python-version: ["3.10", "3.11", "3.12"]' in ci
    assert "scripts/check_release_tag.py" in release
    assert '"${GITHUB_REF_TYPE}" "${GITHUB_REF_NAME}"' in release
    assert "TUBA_RUN_CODE_ASTER_INTEGRATION: \"1\"" in ci
    assert "tests/test_code_aster_real_smoke.py" in ci


def test_release_publish_requires_build_and_real_code_aster_gate():
    release = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    )

    jobs = release["jobs"]
    code_aster = jobs["code-aster-integration"]
    commands = [step["run"] for step in code_aster["steps"] if "run" in step]

    assert code_aster["runs-on"] == ["self-hosted", "code-aster"]
    assert code_aster["env"]["TUBA_RUN_CODE_ASTER_INTEGRATION"] == "1"
    assert "uv run python -m tuba.solver.code_aster_doctor --check" in commands
    assert "uv run pytest tests/test_code_aster_real_smoke.py" in commands
    assert set(jobs["publish"]["needs"]) == {"build", "code-aster-integration"}


def test_release_smokes_the_built_wheel_before_uploading_it():
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


def test_pages_deploys_the_synchronized_packaged_viewer():
    pages = (ROOT / ".github" / "workflows" / "tuba-pages.yml").read_text(encoding="utf-8")

    assert "scripts/prepare_release.py" in pages
    assert "tuba/visualization/_viewer" in pages
    assert "viewer/dist" not in pages
