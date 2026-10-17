"""SQLite audit ledger and idempotency state for the worker."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sender_hash(sender: str) -> str:
    return hashlib.sha256(sender.lower().encode()).hexdigest()


class AgentState:
    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        self.initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connection() as conn:
            conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS inbound_messages (
              gmail_message_id TEXT PRIMARY KEY,
              thread_id TEXT NOT NULL,
              sender_hash TEXT NOT NULL,
              subject TEXT NOT NULL,
              status TEXT NOT NULL,
              trace_id TEXT NOT NULL,
              gmail_draft_id TEXT,
              gmail_sent_id TEXT,
              ticket_id TEXT,
              error_code TEXT,
              error_detail TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
              run_id TEXT PRIMARY KEY,
              gmail_message_id TEXT NOT NULL,
              trace_id TEXT NOT NULL,
              state TEXT NOT NULL,
              model_provider TEXT,
              model_name TEXT,
              started_at TEXT NOT NULL,
              completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS audit_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              trace_id TEXT NOT NULL,
              gmail_message_id TEXT,
              event_type TEXT NOT NULL,
              data_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS thread_memory (
              thread_id TEXT PRIMARY KEY,
              summary TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reviewer_outcomes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              gmail_message_id TEXT NOT NULL,
              outcome TEXT NOT NULL CHECK(outcome IN ('correct','needs_correction','unsafe','missed_escalation')),
              notes TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_events_trace ON audit_events(trace_id);
            CREATE INDEX IF NOT EXISTS idx_messages_status ON inbound_messages(status);
            CREATE TABLE IF NOT EXISTS debug_artifacts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              trace_id TEXT NOT NULL,
              gmail_message_id TEXT NOT NULL,
              stage TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS planned_responses (
              gmail_message_id TEXT PRIMARY KEY,
              route TEXT NOT NULL,
              body TEXT NOT NULL,
              citation_ids_json TEXT NOT NULL,
              ticket_id TEXT,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS worker_locks (
              lock_name TEXT PRIMARY KEY,
              owner TEXT NOT NULL,
              expires_at TEXT NOT NULL
            );
            """)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(inbound_messages)")}
            if "error_detail" not in columns:
                conn.execute("ALTER TABLE inbound_messages ADD COLUMN error_detail TEXT")

    def acquire_lock(self, name: str, owner: str, lease_seconds: int = 300) -> bool:
        now = datetime.now(timezone.utc)
        expiry = datetime.fromtimestamp(now.timestamp() + lease_seconds, timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute("DELETE FROM worker_locks WHERE expires_at < ?", (now.isoformat(),))
            try:
                conn.execute("INSERT INTO worker_locks(lock_name, owner, expires_at) VALUES (?, ?, ?)", (name, owner, expiry))
            except sqlite3.IntegrityError:
                return False
        return True

    def release_lock(self, name: str, owner: str) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM worker_locks WHERE lock_name=? AND owner=?", (name, owner))

    def claim_message(self, message_id: str, thread_id: str, sender: str, subject: str, trace_id: str) -> bool:
        now = _now()
        with self.connection() as conn:
            try:
                conn.execute("""INSERT INTO inbound_messages
                    (gmail_message_id, thread_id, sender_hash, subject, status, trace_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'claimed', ?, ?, ?)""",
                    (message_id, thread_id, _sender_hash(sender), subject[:255], trace_id, now, now))
            except sqlite3.IntegrityError:
                row = conn.execute("SELECT status FROM inbound_messages WHERE gmail_message_id=?", (message_id,)).fetchone()
                if not row or row["status"] != "retry_requested":
                    return False
                conn.execute("""UPDATE inbound_messages SET status='claimed', trace_id=?, error_code=NULL,
                    error_detail=NULL, updated_at=? WHERE gmail_message_id=?""", (trace_id, now, message_id))
        return True

    def set_status(self, message_id: str, status: str, *, draft_id: str | None = None,
                   sent_id: str | None = None, ticket_id: str | None = None,
                   error_code: str | None = None, error_detail: str | None = None) -> None:
        with self.connection() as conn:
            conn.execute("""UPDATE inbound_messages SET status=?, gmail_draft_id=COALESCE(?, gmail_draft_id),
                gmail_sent_id=COALESCE(?, gmail_sent_id), ticket_id=COALESCE(?, ticket_id),
                error_code=COALESCE(?, error_code), error_detail=COALESCE(?, error_detail), updated_at=? WHERE gmail_message_id=?""",
                (status, draft_id, sent_id, ticket_id, error_code, error_detail, _now(), message_id))

    def record_event(self, trace_id: str, message_id: str | None, event_type: str, data: dict[str, Any]) -> None:
        # The caller supplies redacted operational metadata only; raw email text never enters this table.
        with self.connection() as conn:
            conn.execute("INSERT INTO audit_events (trace_id, gmail_message_id, event_type, data_json, created_at) VALUES (?, ?, ?, ?, ?)",
                         (trace_id, message_id, event_type, json.dumps(data, sort_keys=True, default=str), _now()))

    def start_run(self, run_id: str, message_id: str, trace_id: str, provider: str, model: str) -> None:
        with self.connection() as conn:
            conn.execute("""INSERT INTO runs(run_id, gmail_message_id, trace_id, state, model_provider, model_name, started_at)
                VALUES (?, ?, ?, 'started', ?, ?, ?)""", (run_id, message_id, trace_id, provider, model, _now()))

    def finish_run(self, run_id: str, state: str) -> None:
        with self.connection() as conn:
            conn.execute("UPDATE runs SET state=?, completed_at=? WHERE run_id=?", (state, _now(), run_id))

    def update_thread_summary(self, thread_id: str, summary: str) -> None:
        with self.connection() as conn:
            conn.execute("""INSERT INTO thread_memory(thread_id, summary, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET summary=excluded.summary, updated_at=excluded.updated_at""",
                         (thread_id, summary[:600], _now()))

    def record_debug_artifact(self, trace_id: str, message_id: str, stage: str, payload: dict[str, Any]) -> None:
        with self.connection() as conn:
            conn.execute("""INSERT INTO debug_artifacts(trace_id, gmail_message_id, stage, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)""", (trace_id, message_id, stage, json.dumps(payload, default=str), _now()))

    def record_response_plan(self, message_id: str, route: str, body: str, citation_ids: list[str], ticket_id: str | None) -> None:
        with self.connection() as conn:
            conn.execute("""INSERT INTO planned_responses(gmail_message_id, route, body, citation_ids_json, ticket_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(gmail_message_id) DO UPDATE SET route=excluded.route, body=excluded.body,
                citation_ids_json=excluded.citation_ids_json, ticket_id=excluded.ticket_id, created_at=excluded.created_at""",
                (message_id, route, body, json.dumps(citation_ids), ticket_id, _now()))

    def request_retry(self, message_id: str) -> bool:
        with self.connection() as conn:
            result = conn.execute("""UPDATE inbound_messages SET status='retry_requested', updated_at=?
                WHERE gmail_message_id=? AND status IN ('needs_review', 'ready_to_send')""", (_now(), message_id))
        return result.rowcount == 1

    def thread_summary(self, thread_id: str) -> str:
        with self.connection() as conn:
            row = conn.execute("SELECT summary FROM thread_memory WHERE thread_id=?", (thread_id,)).fetchone()
        return row["summary"] if row else ""

    def operator_rows(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute("""SELECT gmail_message_id, thread_id, subject, status, trace_id,
                gmail_draft_id, gmail_sent_id, ticket_id, error_code, error_detail, updated_at
                FROM inbound_messages ORDER BY updated_at DESC""").fetchall()
        return [dict(row) for row in rows]

    def response_route(self, message_id: str) -> str | None:
        with self.connection() as conn:
            row = conn.execute("""SELECT data_json FROM audit_events WHERE gmail_message_id=?
                AND event_type='response_planned' ORDER BY id DESC LIMIT 1""", (message_id,)).fetchone()
        return json.loads(row["data_json"]).get("route") if row else None

    def metrics(self) -> dict[str, int]:
        with self.connection() as conn:
            rows = conn.execute("SELECT status, COUNT(*) AS count FROM inbound_messages GROUP BY status").fetchall()
        return {row["status"]: row["count"] for row in rows}

    def export_debug_trace(self, message_id: str) -> dict[str, Any]:
        with self.connection() as conn:
            message = conn.execute("SELECT * FROM inbound_messages WHERE gmail_message_id=?", (message_id,)).fetchone()
            events = conn.execute("SELECT event_type, data_json, created_at FROM audit_events WHERE gmail_message_id=? ORDER BY id", (message_id,)).fetchall()
            artifacts = conn.execute("SELECT stage, payload_json, created_at FROM debug_artifacts WHERE gmail_message_id=? ORDER BY id", (message_id,)).fetchall()
            response = conn.execute("SELECT route, body, citation_ids_json, ticket_id, created_at FROM planned_responses WHERE gmail_message_id=?", (message_id,)).fetchone()
        if not message:
            raise KeyError(message_id)
        return {
            "message": dict(message),
            "events": [{**dict(event), "data": json.loads(event["data_json"])} for event in events],
            "debug_artifacts": [{**dict(item), "payload": json.loads(item["payload_json"])} for item in artifacts],
            "response": {**dict(response), "citation_ids": json.loads(response["citation_ids_json"])} if response else None,
        }
