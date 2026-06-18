from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from review_gauntlet.findings import FindingState, NormalizedFinding, assert_transition_allowed
from review_gauntlet.review_cells import CellState, ReviewCell


@dataclass(frozen=True)
class SessionStore:
    root: Path

    @property
    def state_dir(self) -> Path:
        return self.root / ".review-gauntlet"

    @property
    def ledger_path(self) -> Path:
        return self.state_dir / "ledger.sqlite"

    @property
    def active_path(self) -> Path:
        return self.state_dir / "active-session.json"

    def initialize(self) -> None:
        self.state_dir.mkdir(mode=0o755, exist_ok=True)
        with self.connect() as conn:
            _create_schema(conn)

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.ledger_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def create_session(self, metadata: dict[str, Any], cells: tuple[ReviewCell, ...]) -> str:
        self.initialize()
        session_id = str(metadata["session_id"])
        with self.connect() as conn:
            conn.execute(
                "insert into sessions(session_id, metadata, state) values (?, ?, 'active')",
                (session_id, json.dumps(metadata, sort_keys=True)),
            )
            conn.executemany(
                """
                insert into review_cells(
                  session_id, cell_id, file_path, rule_id, slice_id, state, content_digest
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        session_id,
                        cell.id,
                        cell.file_path,
                        cell.rule_id,
                        cell.slice_id,
                        cell.state,
                        cell.content_digest,
                    )
                    for cell in cells
                ],
            )
        self.active_path.write_text(
            json.dumps({"session_id": session_id}, indent=2), encoding="utf-8"
        )
        return session_id

    def active_session_id(self) -> str:
        if not self.active_path.exists():
            raise LookupError("no active review session; run review-gauntlet init")
        data = json.loads(self.active_path.read_text(encoding="utf-8"))
        return str(data["session_id"])

    def cancel_active_session(self) -> str:
        session_id = self.active_session_id()
        with self.connect() as conn:
            cur = conn.execute(
                "update sessions set state = 'cancelled' where session_id = ?",
                (session_id,),
            )
        if cur.rowcount != 1:
            raise LookupError(f"unknown session: {session_id}")
        self.active_path.unlink(missing_ok=True)
        return session_id

    def session_metadata(self, session_id: str | None = None) -> dict[str, Any]:
        sid = session_id or self.active_session_id()
        with self.connect() as conn:
            row = conn.execute(
                "select metadata from sessions where session_id = ?", (sid,)
            ).fetchone()
        if row is None:
            raise LookupError(f"unknown session: {sid}")
        data = json.loads(str(row["metadata"]))
        if not isinstance(data, dict):
            raise ValueError(f"invalid session metadata for {sid}")
        return cast(dict[str, Any], data)

    def list_cells(self, session_id: str | None = None) -> list[sqlite3.Row]:
        sid = session_id or self.active_session_id()
        with self.connect() as conn:
            return list(conn.execute("select * from review_cells where session_id = ?", (sid,)))

    def create_run(self, session_id: str, target_digest: str) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "insert into runs(session_id, target_digest) values (?, ?)",
                (session_id, target_digest),
            )
            if cur.lastrowid is None:
                raise RuntimeError("failed to create review run")
            return cur.lastrowid

    def add_cells(self, session_id: str, cells: tuple[ReviewCell, ...]) -> None:
        if not cells:
            return
        with self.connect() as conn:
            conn.executemany(
                """
                insert into review_cells(
                  session_id, cell_id, file_path, rule_id, slice_id, state, content_digest
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        session_id,
                        cell.id,
                        cell.file_path,
                        cell.rule_id,
                        cell.slice_id,
                        cell.state,
                        cell.content_digest,
                    )
                    for cell in cells
                ],
            )

    def update_cell_state(self, session_id: str, cell_id: str, state: CellState) -> None:
        with self.connect() as conn:
            cur = conn.execute(
                """
                update review_cells
                set state = ?
                where session_id = ? and cell_id = ?
                """,
                (state, session_id, cell_id),
            )
        if cur.rowcount != 1:
            raise LookupError(f"unknown review cell: session_id={session_id} cell_id={cell_id}")

    def mark_cell_reviewed(self, session_id: str, cell: ReviewCell) -> None:
        with self.connect() as conn:
            cur = conn.execute(
                """
                update review_cells
                set state = ?, content_digest = ?
                where session_id = ? and cell_id = ?
                """,
                (CellState.REVIEWED, cell.content_digest, session_id, cell.id),
            )
        if cur.rowcount != 1:
            raise LookupError(f"unknown review cell: session_id={session_id} cell_id={cell.id}")

    def refresh_file_digest(
        self,
        session_id: str,
        file_path: str,
        content_digest: str,
    ) -> None:
        with self.connect() as conn:
            session_row = conn.execute(
                "select 1 from sessions where session_id = ?",
                (session_id,),
            ).fetchone()
            if session_row is None:
                raise LookupError(f"unknown session: {session_id}")
            cur = conn.execute(
                """
                update review_cells
                set content_digest = ?
                where session_id = ? and file_path = ?
                """,
                (content_digest, session_id, file_path),
            )
        if cur.rowcount < 1:
            raise LookupError(
                f"unknown review cell path: session_id={session_id} file_path={file_path}"
            )

    _TERMINAL_FINDING_STATES_CLAUSE = (
        "('confirmed', 'fixed_verified', 'false_positive', 'accepted_risk', 'waived', 'dismissed')"
    )

    def count_terminally_complete_cells(self, session_id: str) -> int:
        with self.connect() as conn:
            row = conn.execute(
                f"""
                select count(*) as count from review_cells rc
                where rc.session_id = ?
                  and rc.state = 'reviewed'
                  and not exists (
                    select 1 from finding_occurrences fo
                    inner join findings f
                      on f.finding_id = fo.finding_id
                      and f.session_id = ?
                      and f.state not in {self._TERMINAL_FINDING_STATES_CLAUSE}
                    where fo.cell_id = rc.cell_id
                  )
                """,
                (session_id, session_id),
            ).fetchone()
            return int(row["count"]) if row else 0

    def last_run_target_digest(self, session_id: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                select target_digest from runs
                where session_id = ?
                order by run_id desc
                limit 1
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return str(row["target_digest"])

    def upsert_finding(
        self, session_id: str, run_id: int, cell_id: str, finding: NormalizedFinding
    ) -> str:
        with self.connect() as conn:
            row = conn.execute(
                "select finding_id, state from findings where session_id = ? and fingerprint = ?",
                (session_id, finding.fingerprint),
            ).fetchone()
            if row is None:
                finding_id = _next_finding_id(conn, session_id)
                conn.execute(
                    """
                    insert into findings(
                      session_id, finding_id, fingerprint, state, path, rule_id, content, metadata
                    ) values (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        finding_id,
                        finding.fingerprint,
                        FindingState.OPEN,
                        finding.path,
                        finding.rule_id,
                        finding.content,
                        finding.model_dump_json(),
                    ),
                )
            else:
                finding_id = str(row["finding_id"])
            conn.execute(
                """
                insert into finding_occurrences(
                  finding_id, run_id, cell_id, path, start_line, end_line, imprecise
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    finding_id,
                    run_id,
                    cell_id,
                    finding.path,
                    finding.start_line,
                    finding.end_line,
                    int(finding.imprecise),
                ),
            )
            return finding_id

    def mark_finding(
        self, finding_id: str, state: FindingState, reason: str, metadata: dict[str, str]
    ) -> None:
        with self.connect() as conn:
            self._transition(conn, finding_id, state, reason, metadata)

    def list_open_findings(self, session_id: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    """
                    select * from findings
                    where session_id = ? and state = ?
                    order by path, finding_id
                    """,
                    (session_id, FindingState.OPEN),
                )
            )

    def _transition(
        self,
        conn: sqlite3.Connection,
        finding_id: str,
        state: FindingState,
        reason: str,
        metadata: dict[str, str],
    ) -> None:
        row = conn.execute(
            "select state from findings where finding_id = ?", (finding_id,)
        ).fetchone()
        if row is None:
            raise LookupError(f"unknown finding: {finding_id}")
        current = FindingState(str(row["state"]))
        assert_transition_allowed(current, state)
        conn.execute(
            "update findings set state = ? where finding_id = ?",
            (state, finding_id),
        )
        conn.execute(
            """
            insert into finding_events(finding_id, from_state, to_state, reason, metadata)
            values (?, ?, ?, ?, ?)
            """,
            (finding_id, current, state, reason, json.dumps(metadata, sort_keys=True)),
        )


def _next_finding_id(conn: sqlite3.Connection, session_id: str) -> str:
    del session_id
    rows = conn.execute(
        "select finding_id from findings where finding_id glob 'RGF-[0-9]*'"
    ).fetchall()
    max_numeric_id = 0
    for row in rows:
        suffix = str(row["finding_id"]).removeprefix("RGF-")
        if suffix.isdigit():
            max_numeric_id = max(max_numeric_id, int(suffix))
    return f"RGF-{max_numeric_id + 1:04d}"


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists sessions(
          session_id text primary key,
          metadata text not null,
          state text not null,
          created_at text not null default current_timestamp
        );
        create table if not exists runs(
          run_id integer primary key autoincrement,
          session_id text not null,
          target_digest text not null,
          created_at text not null default current_timestamp
        );
        create table if not exists review_cells(
          session_id text not null,
          cell_id text not null,
          file_path text not null,
          rule_id text not null,
          slice_id text not null,
          state text not null,
          content_digest text not null,
          primary key (session_id, cell_id)
        );
        create table if not exists findings(
          session_id text not null,
          finding_id text primary key,
          fingerprint text not null,
          state text not null,
          path text not null,
          rule_id text not null,
          content text not null,
          metadata text not null,
          unique(session_id, fingerprint)
        );
        create table if not exists finding_occurrences(
          occurrence_id integer primary key autoincrement,
          finding_id text not null,
          run_id integer not null,
          cell_id text not null,
          path text not null,
          start_line integer not null,
          end_line integer not null,
          imprecise integer not null
        );
        create table if not exists finding_events(
          event_id integer primary key autoincrement,
          finding_id text not null,
          from_state text not null,
          to_state text not null,
          reason text not null,
          metadata text not null,
          created_at text not null default current_timestamp
        );
        """
    )
