# VERITY CORE

**Trust infrastructure for AI agent actions — execute, verify, prove.**

AI agents generate code and take actions. VERITY CORE ensures every action is:

- **Executed** in an isolated sandbox (no direct host access)
- **Verified** against declared rules and a security policy
- **Proven** with a cryptographic signature for full auditability

---

## Architecture

```
AI Agent (any LLM)
        ↓
VERITY CORE Gateway  POST /v1/verify
        ↓
┌─────────────────────────┐
│  Execution Kernel        │  ← Docker sandbox, network-disabled
│  (kernel.py)             │
├─────────────────────────┤
│  Verification Engine     │  ← Rules + security pattern scan
│  (engine.py)             │
├─────────────────────────┤
│  Proof Ledger            │  ← HMAC-SHA256 signed, SQLite-backed
│  (ledger.py)             │
└─────────────────────────┘
        ↓
  Signed VerityResponse
```

---

## Quickstart

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Send an action:

```bash
curl -X POST http://localhost:8000/v1/verify \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-agent-v1",
    "payload": "print(2 ** 10)",
    "constraints": {"language": "python", "timeout": 5},
    "verification_rules": [
      {"rule_type": "exit_code", "value": 0},
      {"rule_type": "output_contains", "value": "1024"}
    ]
  }'
```

Response:

```json
{
  "action_id": "550e8400-...",
  "status": "SUCCESS",
  "execution": { "stdout": "1024\n", "exit_code": 0, "execution_time_ms": 142 },
  "verification": { "passed": true, "rules_evaluated": 2, "rules_passed": 2, "security_flags": [] },
  "proof": { "payload_hash": "...", "result_hash": "...", "signature": "..." }
}
```

---

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Service health check |
| `POST` | `/v1/verify` | Submit an AI action for execution + verification |
| `GET`  | `/v1/proof/{action_id}` | Retrieve and validate a proof record |

---

## Components

### Execution Kernel (`app/kernel.py`)
Runs submitted code inside a Docker container with:
- Network disabled
- Memory limit enforced
- Configurable timeout
- Automatic container cleanup

Falls back to subprocess if Docker is unavailable (dev/test mode).

### Verification Engine (`app/engine.py`)
After execution, validates:
- **User-defined rules**: `exit_code`, `output_contains`, `output_not_contains`, `max_execution_ms`, `stderr_empty`
- **Security scan**: static analysis for dangerous patterns (`eval`, `subprocess`, raw sockets, sensitive filesystem paths, network calls)

### Proof Ledger (`app/ledger.py`)
Every action — success or failure — is recorded with:
- SHA-256 hash of the payload
- SHA-256 hash of the execution result
- HMAC-SHA256 signature over (action_id, agent_id, payload_hash, result_hash, timestamp)
- Persisted to SQLite (production: swap for an append-only store)

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Docker Deployment

```bash
# Requires Docker socket access for the sandbox
VERITY_SIGNING_KEY=your-secret docker compose up
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VERITY_DB_PATH` | `/tmp/verity_ledger.db` | SQLite ledger path |
| `VERITY_SIGNING_KEY` | `verity-dev-key-...` | HMAC signing key — **change in production** |

---

## Roadmap

- [x] Execution Kernel (Docker sandbox)
- [x] Verification Engine (rules + security scan)
- [x] Proof Ledger (HMAC-signed, SQLite)
- [x] REST Gateway (FastAPI)
- [ ] Multi-language sandboxes (JS, Bash, Go)
- [ ] Multi-agent coordination (DAG of verified actions)
- [ ] Webhook callbacks on verification result
- [ ] Prometheus metrics endpoint
- [ ] Append-only ledger (IPFS / Merkle DAG)
