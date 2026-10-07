from copy import deepcopy
from pathlib import Path
import re

import pytest
import yaml

from scripts import check_pages_artifact
from scripts.check_workflow_revision import require_approved_revision
from scripts import check_workflow_revision


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40


def test_untrusted_workflow_refs_fail_before_api_or_runner_use(monkeypatch):
    values = {"GITHUB_REPOSITORY": "jgwagenfeld/Tuba_v4", "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "workflow_dispatch"}
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    for key, value in (("GITHUB_REF", "refs/heads/arbitrary"), ("GITHUB_REPOSITORY", "foreign/fork"), ("GITHUB_EVENT_NAME", "pull_request")):
        monkeypatch.setenv(key, value)
        with pytest.raises(ValueError, match="only from"):
            check_workflow_revision.main()
        monkeypatch.setenv(key, values[key])


def test_privileged_preflight_rejects_unprotected_stale_or_open_environment():
    responses = {
        "branches/main": {"protected": True, "commit": {"sha": SHA}},
        "environments/code-aster": {
            "protection_rules": [{"type": "required_reviewers", "prevent_self_review": True, "reviewers": [{}]}],
            "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True},
        },
        "environments/code-aster/deployment-branch-policies": {
            "total_count": 1, "branch_policies": [{"id": 1, "name": "main", "type": "branch"}],
        },
    }
    api = lambda endpoint: responses[endpoint.removeprefix("repos/jgwagenfeld/Tuba_v4/")]
    require_approved_revision(SHA, ["code-aster"], api)
    for endpoint, field, value in (
        ("branches/main", "protected", False),
        ("branches/main", "commit", {"sha": "b" * 40}),
        ("environments/code-aster", "protection_rules", []),
        ("environments/code-aster", "protection_rules", [{"type": "required_reviewers", "prevent_self_review": False, "reviewers": [{}]}]),
        ("environments/code-aster", "deployment_branch_policy", None),
        ("environments/code-aster/deployment-branch-policies", "branch_policies", [{"name": "*", "type": "branch"}]),
        ("environments/code-aster/deployment-branch-policies", "branch_policies", [{"name": "main", "type": "tag"}]),
    ):
        original = deepcopy(responses[endpoint])
        responses[endpoint][field] = value
        with pytest.raises(ValueError):
            require_approved_revision(SHA, ["code-aster"], api)
        responses[endpoint] = original


def test_pages_manifest_binds_revision_run_and_every_deployed_byte(tmp_path, monkeypatch):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("approved site")
    report = tmp_path / "code-aster-references.xml"
    report.write_text('<testsuite tests="1"><testcase name="native-reference"/></testsuite>')
    monkeypatch.setenv("TUBA_RUN_CODE_ASTER_INTEGRATION", "1")
    monkeypatch.setattr(check_pages_artifact.subprocess, "check_output", lambda *_args, **_kwargs: SHA)
    check_pages_artifact.attest(site, SHA, "42", "1", report)
    check_pages_artifact.verify(site, SHA, "42", "1")
    for sha, run_id, attempt in (("b" * 40, "42", "1"), (SHA, "43", "1"), (SHA, "42", "2")):
        with pytest.raises(ValueError, match="approved revision"):
            check_pages_artifact.verify(site, sha, run_id, attempt)
    (site / "index.html").write_text("changed site")
    with pytest.raises(ValueError, match="changed after"):
        check_pages_artifact.verify(site, SHA, "42", "1")
    report.write_text('<testsuite><testcase><skipped/></testcase></testsuite>')
    with pytest.raises(ValueError, match="skips are forbidden"):
        check_pages_artifact.attest(site, SHA, "42", "1", report)


def test_workflow_privileges_are_job_scoped_and_actions_are_immutable():
    for name in ("ci.yml", "release.yml", "tuba-pages.yml"):
        workflow = yaml.safe_load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"))
        assert workflow["permissions"] == {}
        for job_name, job in workflow["jobs"].items():
            assert "permissions" in job, job_name
            for step in job["steps"]:
                if "uses" in step:
                    assert re.fullmatch(r"[\w/-]+@[a-f0-9]{40}", step["uses"])
                    if step["uses"].startswith("actions/checkout@"):
                        assert step["with"]["persist-credentials"] is False
            if "self-hosted" in job["runs-on"]:
                assert job["needs"] == "approved-ref"
                assert job["environment"] == "code-aster"
                assert "refs/heads/main" in job["if"]
                assert job["steps"][0]["with"]["ref"] == "${{ needs.approved-ref.outputs.sha }}"
        if name == "tuba-pages.yml":
            gate = workflow["jobs"]["approved-ref"]
            assert "github.event.workflow_run.conclusion == 'success'" in gate["if"]
            assert "github.event.workflow_run.event == 'push'" in gate["if"]
            assert "github.event.workflow_run.event == 'workflow_dispatch'" in gate["if"]
            assert "github.event_name == 'workflow_dispatch' && inputs.update_snapshots" in gate["if"]
            assert "github.event_name == 'workflow_run'" in workflow["jobs"]["deploy"]["if"]
            assert workflow["jobs"]["artifact"]["needs"] == "approved-ref"


def test_ci_publishes_only_after_solver_refresh_browser_checks_and_attestation():
    job = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))["jobs"]["code-aster-integration"]
    steps = job["steps"]
    commands = [step.get("run", step.get("uses", "")) for step in steps]
    refresh = commands.index("uv run python scripts/refresh_code_aster_gallery.py --all")
    build = commands.index("uv run python scripts/build_pages.py pages --output .build/code-aster-pages")
    browser = commands.index("npm run e2e:pages")
    attest = commands.index("uv run python scripts/check_pages_artifact.py attest --output .build/code-aster-pages")
    upload = next(i for i, step in enumerate(steps) if step.get("with", {}).get("name", "").startswith("code-aster-pages-"))
    assert refresh < build < browser < attest < upload
    assert steps[upload]["with"]["include-hidden-files"] is True
