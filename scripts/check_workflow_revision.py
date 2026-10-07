"""Fail on a hosted runner before scheduling privileged publication/solver jobs."""

import json
import os
from pathlib import Path
import re
from urllib.parse import quote
from urllib.request import Request, urlopen


REPOSITORY = "jgwagenfeld/Tuba_v4"


def require_approved_revision(sha: str, environments: list[str], api) -> None:
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ValueError("Publication requires an immutable Git commit SHA")
    branch = api(f"repos/{REPOSITORY}/branches/main")
    if branch["commit"]["sha"] != sha or branch.get("protected") is not True:
        raise ValueError("Revision must be the current protected main commit")
    for name in environments:
        endpoint = f"repos/{REPOSITORY}/environments/{quote(name, safe='')}"
        environment = api(endpoint)
        if not any(rule.get("type") == "required_reviewers" and rule.get("prevent_self_review") is True
                   and rule.get("reviewers") for rule in environment.get("protection_rules", [])):
            raise ValueError(f"Environment {name!r} requires reviewers and prevention of self-review")
        policy = environment.get("deployment_branch_policy") or {}
        if policy.get("custom_branch_policies") is not True or policy.get("protected_branches") is not False:
            raise ValueError(f"Environment {name!r} must allow only the main branch")
        branches = api(endpoint + "/deployment-branch-policies")
        allowed = branches.get("branch_policies", [])
        if (branches.get("total_count") != 1 or len(allowed) != 1
                or allowed[0].get("name") != "main" or allowed[0].get("type") != "branch"):
            raise ValueError(f"Environment {name!r} must allow exactly the main branch and no tags")


def main() -> None:
    if (os.environ["GITHUB_REPOSITORY"] != REPOSITORY or os.environ["GITHUB_REF"] != "refs/heads/main"
            or os.environ["GITHUB_EVENT_NAME"] not in {"push", "workflow_dispatch", "workflow_run"}):
        raise ValueError("Privileged workflows run only from this repository's main branch")

    def api(endpoint):
        request = Request("https://api.github.com/" + endpoint, headers={
            "Authorization": "Bearer " + os.environ["GH_TOKEN"], "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    sha = os.environ.get("SOURCE_SHA", os.environ["GITHUB_SHA"])
    require_approved_revision(sha, os.environ.get("TUBA_APPROVED_ENVIRONMENTS", "").split(), api)
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"sha={sha}\n")


if __name__ == "__main__":
    main()
