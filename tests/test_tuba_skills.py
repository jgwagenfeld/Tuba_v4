"""The agent skill ships with Tuba and installs into an agent harness folder."""

from pathlib import Path

from tuba.skills import DEFAULT_SKILL, install_skill, main, skill_names, skill_path


def test_the_modeling_skill_ships_with_the_package():
    assert DEFAULT_SKILL in skill_names()

    text = skill_path().read_text(encoding="utf-8")

    assert text.startswith(f"---\nname: {DEFAULT_SKILL}\n")
    assert "description:" in text
    # The rules that this skill exists to keep in front of an agent.
    assert "check_all" in text
    assert "bend_by_orientation" in text
    assert "Code_Aster" in text


def test_an_unknown_skill_is_refused_with_the_shipped_names():
    try:
        skill_path("does-not-exist")
    except ValueError as error:
        assert DEFAULT_SKILL in str(error)
    else:  # pragma: no cover - the raise above is the contract
        raise AssertionError("skill_path accepted an unknown skill name")


def test_install_skill_copies_the_whole_skill_folder(tmp_path: Path):
    installed = install_skill(target=tmp_path)

    assert installed == tmp_path / DEFAULT_SKILL / "SKILL.md"
    assert installed.read_text(encoding="utf-8") == skill_path().read_text(encoding="utf-8")


def test_the_cli_installs_and_lists(tmp_path: Path, capsys):
    assert main(["--target", str(tmp_path)]) == 0
    assert (tmp_path / DEFAULT_SKILL / "SKILL.md").is_file()

    assert main(["--list"]) == 0
    listing = capsys.readouterr().out
    assert DEFAULT_SKILL in listing
    assert str(skill_path()) in listing
