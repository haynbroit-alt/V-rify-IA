import hashlib
import hmac
import json
import os
import sqlite3
import time
import uuid
import logging
from pathlib import Path

from app.models import ExecutionResult, ProofRecord

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("VERITY_DB_PATH", "/tmp/verity_ledger.db"))

# Secret key for HMAC-SHA256 signatures (in prod: load from HSM / env secret)
_SIGNING_KEY = os.getenv("VERITY_SIGNING_KEY", "verity-dev-key-change-in-production").encode()


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS proof_ledger (
            action_id     TEXT PRIMARY KEY,
            agent_id      TEXT NOT NULL,
            payload_hash  TEXT NOT NULL,
            result_hash   TEXT NOT NULL,
            signature     TEXT NOT NULL,
            timestamp     REAL NOT NULL
        )
        """
    )
    conn.commit()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    _init_db(conn)
    return conn


class ProofLedger:
    """
    Immutable audit trail. Every executed action gets a signed proof entry.
    Uses HMAC-SHA256 over (payload_hash + result_hash + timestamp + agent_id).
    """

    def record(
        self,
        action_id: str,
        agent_id: str,
        raw_payload: str,
        result: ExecutionResult,
    ) -> ProofRecord:
        payload_hash = self._hash(raw_payload)
        result_digest = json.dumps(
            {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
                "status": result.status,
            },
            sort_keys=True,
        )
        result_hash = self._hash(result_digest)
        ts = time.time()

        signature = self._sign(
            f"{action_id}:{agent_id}:{payload_hash}:{result_hash}:{ts}"
        )

        record = ProofRecord(
            action_id=action_id,
            payload_hash=payload_hash,
            result_hash=result_hash,
            signature=signature,
            timestamp=ts,
            agent_id=agent_id,
        )

        self._persist(record)
        return record

    def get(self, action_id: str) -> ProofRecord | None:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT action_id, agent_id, payload_hash, result_hash, signature, timestamp "
                "FROM proof_ledger WHERE action_id = ?",
                (action_id,),
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            return None
        return ProofRecord(
            action_id=row[0],
            agent_id=row[1],
            payload_hash=row[2],
            result_hash=row[3],
            signature=row[4],
            timestamp=row[5],
        )

    def verify_signature(self, record: ProofRecord) -> bool:
        expected = self._sign(
            f"{record.action_id}:{record.agent_id}:{record.payload_hash}"
            f":{record.result_hash}:{record.timestamp}"
        )
        return hmac.compare_digest(expected, record.signature)

    def _persist(self, record: ProofRecord) -> None:
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO proof_ledger VALUES (?,?,?,?,?,?)",
                (
                    record.action_id,
                    record.agent_id,
                    record.payload_hash,
                    record.result_hash,
                    record.signature,
                    record.timestamp,
                ),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Ledger persistence error: {e}")
        finally:
            conn.close()

    @staticmethod
    def _hash(data: str) -> str:
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def _sign(message: str) -> str:
        return hmac.new(_SIGNING_KEY, message.encode(), hashlib.sha256).hexdigest()
