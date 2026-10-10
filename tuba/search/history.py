"""One-coordinator, append-only SQLite event history."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .contracts import Candidate, json_copy

SCHEMA = "tuba.search.history.v1"


def encode(value) -> str:
    return json.dumps(json_copy(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


class History:
    def __init__(self, connection: sqlite3.Connection, path: Path, readonly: bool):
        self.connection, self.path, self.readonly = connection, path, readonly
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=1000")

    @classmethod
    def create(cls, path: Path, manifest: dict) -> History:
        path = Path(path).absolute()
        manifest = json_copy(manifest)
        if manifest.get("schema") != SCHEMA or not manifest.get("run_id"):
            raise ValueError("Expected a supported history schema and run_id")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb"):
            pass
        h = cls(sqlite3.connect(path), path, False)
        h.connection.executescript("""
            PRAGMA user_version=1;
            CREATE TABLE run (id INTEGER PRIMARY KEY CHECK(id=1), manifest TEXT NOT NULL);
            CREATE TABLE candidates (id TEXT PRIMARY KEY, record TEXT NOT NULL);
            CREATE TABLE events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL, kind TEXT NOT NULL,
                candidate_id TEXT REFERENCES candidates(id), producer TEXT NOT NULL,
                payload TEXT NOT NULL);
        """)
        with h.connection:
            h.connection.execute("INSERT INTO run VALUES (1, ?)", (encode(manifest),))
        for table in ("run", "candidates", "events"):
            for action in ("UPDATE", "DELETE"):
                h.connection.execute(f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} "
                                     f"BEGIN SELECT RAISE(ABORT, 'search {table} are immutable'); END")
        h.connection.commit()
        return h

    @classmethod
    def open(cls, path: Path, readonly: bool = False) -> History:
        path = Path(path).absolute()
        if not path.is_file():
            raise FileNotFoundError(path)
        connection = sqlite3.connect(path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"), uri=True)
        h = cls(connection, path, readonly)
        try:
            if connection.execute("PRAGMA user_version").fetchone()[0] != 1 or h.manifest().get("schema") != SCHEMA:
                raise ValueError("Unsupported history schema")
        except BaseException:
            connection.close()
            raise
        return h

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.connection.close()

    def _writable(self):
        if self.readonly:
            raise ValueError("History is read-only")

    def _has(self, candidate_id):
        return self.connection.execute("SELECT 1 FROM candidates WHERE id=?", (candidate_id,)).fetchone() is not None

    def _insert_event(self, kind, payload, candidate_id):
        if not isinstance(kind, str) or not kind:
            raise ValueError("Event kind is required")
        if candidate_id is not None and not self._has(candidate_id):
            raise ValueError(f"Unknown candidate: {candidate_id}")
        return self.connection.execute(
            "INSERT INTO events(timestamp,kind,candidate_id,producer,payload) VALUES (?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), kind, candidate_id, "tuba.search", encode(payload)),
        ).lastrowid

    def record_candidate(self, candidate: Candidate):
        self._writable()
        with self.connection:
            if self._has(candidate.id):
                raise ValueError(f"Duplicate candidate id: {candidate.id}")
            if any(not self._has(parent) for parent in candidate.parent_ids):
                raise ValueError("Parents must already exist in this run")
            self.connection.execute("INSERT INTO candidates VALUES (?,?)", (candidate.id, encode(candidate.to_dict())))
            self._insert_event("candidate.proposed", candidate.to_dict(), candidate.id)

    def append(self, kind: str, payload: dict, candidate_id: str | None = None) -> int:
        self._writable()
        with self.connection:
            return self._insert_event(kind, payload, candidate_id)

    def events(self, after_seq: int = 0) -> list[dict]:
        if type(after_seq) is not int or after_seq < 0:
            raise ValueError("Sequence must be a nonnegative integer")
        return [dict(row) | {"payload": json.loads(row["payload"])} for row in self.connection.execute(
            "SELECT * FROM events WHERE sequence>? ORDER BY sequence", (after_seq,))]

    def candidates(self) -> list[Candidate]:
        return [Candidate.from_dict(json.loads(row[0])) for row in self.connection.execute(
            "SELECT record FROM candidates ORDER BY rowid")]

    def manifest(self) -> dict:
        return json.loads(self.connection.execute("SELECT manifest FROM run WHERE id=1").fetchone()[0])
