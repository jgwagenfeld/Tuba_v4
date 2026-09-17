"""Agent skills shipped inside Tuba, so an agent knows the authoring contract.

The skill explains the Tuba workflow in the agent's own language: procedural
Python authoring, the full ``ClashEngine.check_all`` gate, the bend-sign
semantics of the fluent builder, route-endpoint proof, and how a study labels
obstacles and publishes a review. Install it into an agent harness with
``python -m tuba.skills --target <skills-folder>``.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parent
DEFAULT_SKILL = "tuba-modeling"

#: Agent harness skills folders, tried in order when ``--target`` is omitted.
HARNESS_SKILL_DIRS = (
    ("opencode", Path.home() / ".config" / "opencode" / "skills"),
    ("claude", Path.home() / ".claude" / "skills"),
    ("codex", Path.home() / ".codex" / "skills"),
    ("agents", Path.home() / ".agents" / "skills"),
)


def skill_names() -> list[str]:
    """Names of the skills shipped with this Tuba version, sorted."""
    return sorted(path.parent.name for path in SKILLS_ROOT.glob("*/SKILL.md"))


def skill_path(name: str = DEFAULT_SKILL) -> Path:
    """Path to skill *name*'s ``SKILL.md``.

    Raises ``ValueError`` naming the shipped skills when *name* is unknown.
    """
    path = SKILLS_ROOT / name / "SKILL.md"
    if not path.is_file():
        raise ValueError(f"Unknown Tuba skill {name!r}; shipped skills: {', '.join(skill_names())}")
    return path


def install_skill(name: str = DEFAULT_SKILL, *, target: str | Path | None = None) -> Path:
    """Copy skill *name* into an agent harness skills folder.

    *target* is the skills folder itself (the skill lands in ``<target>/<name>``).
    Without it the first existing harness folder from :data:`HARNESS_SKILL_DIRS`
    is used; if none exists, ``ValueError`` asks for an explicit target.
    Returns the installed ``SKILL.md`` path.
    """
    source = skill_path(name)
    destination = (Path(target) if target is not None else _default_target()) / name
    if destination.resolve() != source.parent.resolve():
        shutil.copytree(source.parent, destination, dirs_exist_ok=True)
    return destination / "SKILL.md"


def _default_target() -> Path:
    for _harness, path in HARNESS_SKILL_DIRS:
        if path.is_dir():
            return path
    raise ValueError(
        "No agent harness skills folder found; pass --target <skills-folder> "
        "(for example ~/.config/opencode/skills)."
    )


def main(argv: list[str] | None = None) -> int:
    """Install or list Tuba's agent skills."""
    parser = argparse.ArgumentParser(
        prog="tuba-skill",
        description="Install the Tuba agent skill into an agent harness skills folder.",
    )
    parser.add_argument("--name", default=DEFAULT_SKILL, help="skill to install (default: %(default)s)")
    parser.add_argument("--target", help="skills folder to copy the skill into")
    parser.add_argument("--list", action="store_true", help="list the shipped skills and exit")
    args = parser.parse_args(argv)

    if args.list:
        for name in skill_names():
            print(f"{name}: {skill_path(name)}")
        return 0
    print(install_skill(args.name, target=args.target))
    return 0
