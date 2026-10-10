import sqlite3

import pytest

from tuba.search.contracts import Candidate
from tuba.search.history import History


def create(path):
    return History.create(path, {"schema": "tuba.search.history.v1", "run_id": "R"})


def test_restart_preserves_branch_and_event_order(tmp_path):
    path = tmp_path / "history.sqlite3"
    with create(path) as h:
        h.record_candidate(Candidate("C1", (), {"depth_m": 0.8}, "Initial loop"))
        h.record_candidate(Candidate("C2", ("C1",), {"depth_m": 1.0}, "Increase depth"))
        h.append("candidate.decision", {"outcome": "rejected_constraint"}, "C1")
    before = path.read_bytes()
    with History.open(path, readonly=True) as h:
        assert [c.id for c in h.candidates()] == ["C1", "C2"]
        events = h.events()
        assert [e["sequence"] for e in events] == [1, 2, 3]
        assert events[1]["payload"]["parent_ids"] == ["C1"]
        assert h.events(after_seq=2) == events[2:]
        assert h.manifest()["run_id"] == "R"
        with pytest.raises((ValueError, sqlite3.OperationalError)):
            h.append("write", {})
    assert path.read_bytes() == before


def test_invalid_parent_and_duplicate_are_transactional(tmp_path):
    with create(tmp_path / "h.sqlite3") as h:
        with pytest.raises(ValueError):
            h.record_candidate(Candidate("C2", ("absent",), {}, "Trial"))
        h.record_candidate(Candidate("C1", (), {}, "Trial"))
        with pytest.raises(ValueError):
            h.record_candidate(Candidate("C1", (), {}, "Trial again"))
        assert len(h.candidates()) == len(h.events()) == 1
        with pytest.raises(ValueError):
            h.append("event", {}, "absent")


@pytest.mark.parametrize("table", ["events", "candidates", "run"])
@pytest.mark.parametrize("statement", ["UPDATE {table} SET {column}={column}", "DELETE FROM {table}"])
def test_sql_mutation_is_forbidden(tmp_path, table, statement):
    path = tmp_path / "h.sqlite3"
    with create(path) as h:
        h.record_candidate(Candidate("C", (), {}, "Trial"))
    column = {"events": "kind", "candidates": "id", "run": "manifest"}[table]
    with sqlite3.connect(path) as connection, pytest.raises(sqlite3.IntegrityError, match="immutable"):
        connection.execute(statement.format(table=table, column=column))


def test_busy_writer_fails_within_bounded_timeout(tmp_path):
    path = tmp_path / "h.sqlite3"
    with create(path) as h, sqlite3.connect(path) as other:
        other.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            h.append("busy", {})
        other.rollback()
        assert h.events() == []
        assert h.append("ready", {}) == 1


def test_unknown_schema_and_existing_file_are_refused(tmp_path):
    path = tmp_path / "h.sqlite3"
    with create(path):
        pass
    with pytest.raises(FileExistsError):
        create(path)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=99")
    with pytest.raises(ValueError, match="schema"):
        History.open(path)


def test_candidate_event_insertion_rolls_back_on_fault(tmp_path):
    path = tmp_path / "h.sqlite3"
    with create(path) as h:
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TRIGGER fail_event BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT, 'injected'); END")
        with pytest.raises(sqlite3.IntegrityError):
            h.record_candidate(Candidate("C", (), {}, "Trial"))
        assert h.candidates() == []
