"""The agent skills ship with Tuba and install into an agent harness folder."""

from pathlib import Path

from tuba.skills import DEFAULT_SKILL, install_skill, main, skill_names, skill_path

STRUCTURAL_SKILL = "tuba-structural-frames"


def test_the_modeling_skill_ships_with_the_package():
    assert DEFAULT_SKILL in skill_names()

    text = skill_path().read_text(encoding="utf-8")

    assert text.startswith(f"---\nname: {DEFAULT_SKILL}\n")
    assert "description:" in text
    # The rules that this skill exists to keep in front of an agent.
    assert "check_all" in text
    assert "bend_by_orientation" in text
    assert "Code_Aster" in text


def test_the_structural_skill_ships_and_is_discoverable():
    assert STRUCTURAL_SKILL in skill_names()

    text = skill_path(STRUCTURAL_SKILL).read_text(encoding="utf-8")

    assert text.startswith(f"---\nname: {STRUCTURAL_SKILL}\n")
    assert "description:" in text
    # The findings that cost a failed solve each, so they must stay in the skill.
    assert "no rotational stiffness" in text
    assert "ANGL_VRIL" in text
    assert "plus d'une charge repartie" in text
    assert "Mauvaise definition de ('R', 'EP')" in text
    assert "bloqué plusieurs fois" in text
    # Result coverage: a pipe-free model has no stress, and that must be stated.
    assert "not computed" in text


def test_the_modeling_skill_points_at_the_structural_one():
    """An agent that only loads the piping contract must still find the other one."""
    text = skill_path().read_text(encoding="utf-8")

    assert STRUCTURAL_SKILL in text


def test_an_unknown_skill_is_refused_with_the_shipped_names():
    try:
        skill_path("does-not-exist")
    except ValueError as error:
        assert DEFAULT_SKILL in str(error)
        assert STRUCTURAL_SKILL in str(error)
    else:  # pragma: no cover - the raise above is the contract
        raise AssertionError("skill_path accepted an unknown skill name")


def test_install_skill_copies_the_whole_skill_folder(tmp_path: Path):
    installed = install_skill(target=tmp_path)

    assert installed == tmp_path / DEFAULT_SKILL / "SKILL.md"
    assert installed.read_text(encoding="utf-8") == skill_path().read_text(encoding="utf-8")


def test_the_structural_skill_installs_too(tmp_path: Path):
    installed = install_skill(STRUCTURAL_SKILL, target=tmp_path)

    assert installed == tmp_path / STRUCTURAL_SKILL / "SKILL.md"
    assert installed.read_text(encoding="utf-8") == (
        skill_path(STRUCTURAL_SKILL).read_text(encoding="utf-8")
    )


def test_the_cli_installs_and_lists(tmp_path: Path, capsys):
    assert main(["--target", str(tmp_path)]) == 0
    assert (tmp_path / DEFAULT_SKILL / "SKILL.md").is_file()

    assert main(["--list"]) == 0
    listing = capsys.readouterr().out
    assert DEFAULT_SKILL in listing
    assert STRUCTURAL_SKILL in listing
    assert str(skill_path()) in listing
