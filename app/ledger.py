import base64
import hashlib
import json
import logging
import os
import sqlite3
import time
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.config import get_settings
from app.models import ExecutionResult, ProofRecord

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("VERITY_DB_PATH", get_settings().db_path))

# Ed25519 keypair — load from 32-byte hex seed or generate ephemeral.
# In production: inject VERITY_PRIVATE_KEY_HEX from a secret manager.
_PRIVATE_KEY_HEX = os.getenv("VERITY_PRIVATE_KEY_HEX", "")
if _PRIVATE_KEY_HEX:
    _private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(_PRIVATE_KEY_HEX))
else:
    _private_key = Ed25519PrivateKey.generate()
    logger.warning(
        "No VERITY_PRIVATE_KEY_HEX set — using ephemeral key (proofs wont survive restart)"
    )

_public_key = _private_key.public_key()


def get_public_key_pem() -> str:
    """Return the Ed25519 public key in PEM format for independent signature verification."""
    return _public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


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


def _canonical_message(
    action_id: str, agent_id: str, payload_hash: str, result_hash: str, ts: float
) -> bytes:
    """Deterministic byte string that is signed and verified."""
    return f"{action_id}:{agent_id}:{payload_hash}:{result_hash}:{ts}".encode()


class ProofLedger:
    """
    Immutable audit trail with Ed25519 signatures.
    Anyone holding the public key can verify a proof without access to the server.
    """

    def record(
        self, action_id: str, agent_id: str, raw_payload: str, result: ExecutionResult
    ) -> ProofRecord:
        payload_hash = _sha256(raw_payload)
        result_digest = json.dumps(
            {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
                "status": result.status,
            },
            sort_keys=True,
        )
        result_hash = _sha256(result_digest)
        ts = time.time()

        message = _canonical_message(action_id, agent_id, payload_hash, result_hash, ts)
        sig_bytes = _private_key.sign(message)
        signature = base64.urlsafe_b64encode(sig_bytes).decode()

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
        try:
            message = _canonical_message(
                record.action_id,
                record.agent_id,
                record.payload_hash,
                record.result_hash,
                record.timestamp,
            )
            sig_bytes = base64.urlsafe_b64decode(record.signature.encode())
            _public_key.verify(sig_bytes, message)
            return True
        except (InvalidSignature, Exception):
            return False

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
            logger.error("ledger.persist_error", extra={"error": str(e)})
        finally:
            conn.close()


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()
