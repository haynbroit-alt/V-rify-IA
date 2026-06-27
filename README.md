# VERITY CORE 🔐

> Run AI-generated code safely — get a cryptographic proof of execution.

VERITY CORE executes untrusted code in an isolated sandbox and returns a signed, verifiable proof of what happened. Built for AI agents, automation pipelines, and any system where you need to trust — but verify — generated code.

**Live API**: https://v-rify-ia.fly.dev — **Docs**: https://v-rify-ia.fly.dev/docs

---

## Try it in 10 seconds

```bash
curl -X POST https://v-rify-ia.fly.dev/v1/verify \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "demo",
    "payload": "print(2**10)",
    "constraints": {"language": "python", "timeout": 5}
  }'
```

You get back:
- ✅ The execution output (`1024`)
- 🔐 An Ed25519 signature over the result
- 📜 A full timestamped trace of the execution pipeline

```json
{
  "status": "SUCCESS",
  "execution": { "stdout": "1024\n", "exit_code": 0, "execution_time_ms": 33 },
  "proof": {
    "signature": "qx2zZrTp1E37Vk...",
    "algorithm": "Ed25519",
    "key_id": "c8f3a73f7b8eb33f"
  },
  "state": "COMPLETED",
  "transitions": [
    { "from_state": "PENDING",   "to_state": "EXECUTING",  "duration_ms": 0.08 },
    { "from_state": "EXECUTING", "to_state": "VERIFYING",  "duration_ms": 33.6 },
    { "from_state": "SIGNING",   "to_state": "COMPLETED",  "duration_ms": 1.4  }
  ]
}
```

The `proof.signature` is verifiable by anyone holding the public key — no server access required.

---

## Why this exists

AI agents execute code. That creates real risks:

| Problem | VERITY CORE's answer |
|---|---|
| Untrusted code runs on your host | Isolated sandbox, no network, read-only FS |
| No record of what actually ran | Ed25519-signed proof per execution |
| Hard to audit AI agent decisions | Full state trace with timestamps |
| Code could exfiltrate data | Static security scan on every payload |

---

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/verify` | Execute + verify + sign |
| `GET` | `/v1/proof/{id}` | Retrieve and validate a stored proof |
| `GET` | `/v1/history/{agent_id}` | List all proofs for an agent |
| `GET` | `/v1/public-key` | Ed25519 public key (PEM) |
| `GET` | `/health` | Health check |

→ [Full API reference](docs/api.md)

---

## Examples

```
examples/
├── curl_example.sh       # One-liner shell test
├── python_example.py     # Execute + verify signature independently
└── node_example.js       # Node.js fetch
```

---

## Pipeline

Every request passes through a deterministic 7-stage pipeline:

```
PENDING → VALIDATING_REQUEST → EXECUTING → VERIFYING → SIGNING → PERSISTING → COMPLETED
```

Each stage is timed and recorded in `transitions[]`. Failures produce a `FAILED_*` state with a reason — never silent errors.

---

## Security

- **Sandbox**: network disabled, read-only filesystem, 128 MB RAM, 50% CPU cap, PID limit
- **Static analysis**: blocks `eval`, `exec`, subprocess calls, raw sockets, sensitive paths
- **Signatures**: Ed25519 — verifiable by third parties without the private key
- **Rate limit**: 60 req/min per IP
- **Payload limit**: 10 KB max

→ [Full security documentation](docs/security.md)

---

## Verify a proof independently

```python
from cryptography.hazmat.primitives.serialization import load_pem_public_key
import base64, requests

pem = requests.get("https://v-rify-ia.fly.dev/v1/public-key").json()["public_key"]
pub = load_pem_public_key(pem.encode())

proof = ...  # your ProofRecord from /v1/verify
msg = f"{proof['action_id']}:{proof['agent_id']}:{proof['payload_hash']}:{proof['result_hash']}:{proof['timestamp']}"
pub.verify(base64.urlsafe_b64decode(proof["signature"]), msg.encode())
# raises InvalidSignature if tampered — otherwise silent success
```

→ [Full verification guide](docs/proofs.md)

---

## Self-host

```bash
git clone https://github.com/haynbroit-alt/V-rify-IA
cd V-rify-IA
pip install -e .
uvicorn app.main:app --port 8080
```

Docker required for full sandbox isolation. Without Docker, set `VERITY_ALLOW_SUBPROCESS_FALLBACK=true` (dev only).

**Deploy to Fly.io**: push to `main` — GitHub Actions deploys automatically.

---

## Status

**v0.5** — production-ready MVP, live at https://v-rify-ia.fly.dev

- [x] Docker sandbox (network-disabled, read-only FS, memory + CPU limits)
- [x] Ed25519 signatures with key rotation tracking (`key_id`)
- [x] Orchestrator state machine with full transition timeline
- [x] Proof ledger (SQLite, verifiable offline)
- [x] Rate limiting · Payload size limit · Agent history
- [ ] SDK (`pip install verity-core`)
- [ ] Webhook callbacks on execution result
- [ ] Multi-language sandboxes (JS, Bash)
