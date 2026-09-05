"""Local durable job ledger, independent of MCP and external success labels.

This is a state/locking contract for a trusted local controller, not a scheduler
or authentication server. It never starts, discovers, signals or restarts a process.
An executor must supply verified process-exit evidence for terminal transitions.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


_TERMINAL = {'completed', 'failed', 'cancelled'}
_TRANSITIONS = {
    'queued': {'launching', 'cancelled'},
    'launching': {'running', 'reconciliation_required', 'cancel_requested', 'failed'},
    'running': {'completed', 'failed', 'cancel_requested', 'reconciliation_required'},
    'cancel_requested': {'cancelled', 'reconciliation_required', 'failed'},
    'reconciliation_required': {'running', 'cancel_requested', 'failed', 'cancelled'},
}


class JobLedger:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY, principal TEXT NOT NULL, project TEXT NOT NULL,
                    idem_key TEXT NOT NULL, digest TEXT NOT NULL, spec TEXT NOT NULL,
                    case_path TEXT NOT NULL, status TEXT NOT NULL, process_identity TEXT,
                    UNIQUE(principal, project, idem_key)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_case_writer ON jobs(case_path)
                    WHERE status NOT IN ('completed', 'failed', 'cancelled');
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
                    previous TEXT, status TEXT NOT NULL, detail TEXT NOT NULL,
                    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            ''')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _authorized(db, principal: str, project: str, job_id: str):
        row = db.execute('SELECT * FROM jobs WHERE job_id=? AND principal=? AND project=?',
                         (job_id, principal, project)).fetchone()
        if row is None:
            raise PermissionError('job is unavailable in this principal/project scope')
        return row

    def submit(self, principal: str, project: str, key: str, spec: dict) -> dict:
        if not all(isinstance(s, str) and s.strip() for s in (principal, project, key)):
            raise ValueError('principal, project and idempotency key are required')
        if not isinstance(spec.get('case_path'), str) or not spec.get('revision'):
            raise ValueError('case_path and immutable revision are required')
        normalized = {**spec, 'case_path': os.path.normcase(str(Path(spec['case_path']).resolve()))}
        encoded = json.dumps(normalized, sort_keys=True, separators=(',', ':'), allow_nan=False)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT * FROM jobs WHERE principal=? AND project=? AND idem_key=?',
                                  (principal, project, key)).fetchone()
            if existing:
                if existing['digest'] != digest:
                    raise ValueError('idempotency key already belongs to a different spec')
                return dict(existing)
            jid = uuid4().hex
            try:
                db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,NULL)',
                           (jid, principal, project, key, digest, encoded, normalized['case_path'], 'queued'))
            except sqlite3.IntegrityError as exc:
                raise ValueError('case already has a writer; reconcile its process before another submission') from exc
            db.execute('INSERT INTO events(job_id,previous,status,detail) VALUES (?,NULL,?,?)',
                       (jid, 'queued', 'submission persisted'))
            return dict(self._authorized(db, principal, project, jid))

    def get(self, principal: str, project: str, job_id: str) -> dict:
        with self._db() as db:
            return dict(self._authorized(db, principal, project, job_id))

    def list_active(self, principal: str, project: str) -> list[dict]:
        with self._db() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM jobs WHERE principal=? AND project=? AND status NOT IN "
                "('completed','failed','cancelled') ORDER BY rowid", (principal, project))]

    def request_cancel(self, principal: str, project: str, job_id: str) -> dict:
        row = self.get(principal, project, job_id)
        if row['status'] in _TERMINAL or row['status'] == 'cancel_requested':
            return row
        return self.transition(principal, project, job_id, expected=row['status'],
                               status='cancelled' if row['status'] == 'queued' else 'cancel_requested')

    def events(self, principal: str, project: str, job_id: str) -> list[dict]:
        with self._db() as db:
            self._authorized(db, principal, project, job_id)
            return [dict(row) for row in db.execute('SELECT * FROM events WHERE job_id=? ORDER BY sequence', (job_id,))]

    def transition(self, principal: str, project: str, job_id: str, *, expected: str,
                   status: str, process_identity: str | None = None,
                   exit_confirmed: bool = False, exit_code: int | None = None) -> dict:
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = self._authorized(db, principal, project, job_id)
            if row['status'] != expected or status not in _TRANSITIONS.get(expected, set()):
                raise ValueError('state conflict or invalid job transition')
            if status in _TERMINAL and expected != 'queued' and not exit_confirmed:
                raise ValueError('verified process exit is required; cancellation ACK is insufficient')
            if status == 'completed' and exit_code != 0:
                raise ValueError('completed requires a verified zero exit code')
            if status == 'running' and not (process_identity or row['process_identity']):
                raise ValueError('running requires process identity including a start token, not just a PID')
            db.execute('UPDATE jobs SET status=?, process_identity=COALESCE(?,process_identity) WHERE job_id=?',
                       (status, process_identity, job_id))
            db.execute('INSERT INTO events(job_id,previous,status,detail) VALUES (?,?,?,?)',
                       (job_id, expected, status, json.dumps({'exit_confirmed': exit_confirmed, 'exit_code': exit_code})))
            return dict(self._authorized(db, principal, project, job_id))
