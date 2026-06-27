# VERITY CORE 🔐

> Run AI-generated code safely. Get a cryptographic proof of execution.

**Live API**: https://v-rify-ia.fly.dev &nbsp;·&nbsp; **Docs**: https://v-rify-ia.fly.dev/docs &nbsp;·&nbsp; **Python SDK**: `pip install verity-core`

---

## Try it in 10 seconds

```bash
curl -X POST https://v-rify-ia.fly.dev/v1/verify \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"demo","payload":"print(2**10)","constraints":{"language":"python","timeout":5}}'
```

```json
{
  "status": "SUCCESS",
  "execution": { "stdout": "1024\n", "exit_code": 0, "execution_time_ms": 33 },
  "proof": { "signature": "qx2zZrTp...", "algorithm": "Ed25519", "key_id": "c8f3a73f7b8eb33f" },
  "state": "COMPLETED"
}
```

---

## Why

AI agents are executing code in production systems. But:

- You **cannot trust** what was actually executed
- You **cannot verify** results after the fact
- You **cannot audit** AI decisions without a tamper-proof record

VERITY CORE fixes this.

---

## Every execution returns

- ✅ **Output** — stdout, exit code, execution time
- 📜 **Full execution trace** — timestamped state transitions (PENDING → EXECUTING → COMPLETED)
- 🔐 **Cryptographic signature** — Ed25519, verifiable by anyone without server access

---

## Python SDK

```bash
pip install verity-core
```

```python
from verity import run

result = run("print(2**10)")

print(result.output)    # "1024\n"
print(result.verified)  # True
print(bool(result))     # True — success + verified
print(result.proof)     # {"signature": "...", "algorithm": "Ed25519", ...}
```

Or with the full client:

```python
from verity import VerityClient

client = VerityClient()
result = client.run(
    "import json; print(json.dumps({'ok': True}))",
    agent_id="my-agent",
    rules=[{"rule_type": "exit_code", "value": 0}],
)

if result:
    history = client.history("my-agent", limit=10)
```

---

## Examples

| File | Description |
|---|---|
| [`examples/curl_example.sh`](examples/curl_example.sh) | Shell one-liner |
| [`examples/python_example.py`](examples/python_example.py) | Execute + verify signature independently |
| [`examples/node_example.js`](examples/node_example.js) | Node.js fetch |

---

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/verify` | Execute + verify + sign |
| `GET` | `/v1/proof/{id}` | Retrieve and validate a stored proof |
| `GET` | `/v1/history/{agent_id}` | List all proofs for an agent |
| `GET` | `/v1/public-key` | Ed25519 public key (PEM) |

→ [Full API reference](docs/api.md) · [Security](docs/security.md) · [Proof verification](docs/proofs.md)

---

## Verify a proof without our server

```python
from cryptography.hazmat.primitives.serialization import load_pem_public_key
import base64, requests

pem = requests.get("https://v-rify-ia.fly.dev/v1/public-key").json()["public_key"]
pub = load_pem_public_key(pem.encode())

proof = ...  # your ProofRecord
msg = f"{proof['action_id']}:{proof['agent_id']}:{proof['payload_hash']}:{proof['result_hash']}:{proof['timestamp']}"
pub.verify(base64.urlsafe_b64decode(proof["signature"]), msg.encode())
# silent = valid. raises InvalidSignature if tampered.
```

---

## Self-host

```bash
git clone https://github.com/haynbroit-alt/V-rify-IA
cd V-rify-IA
pip install -e ".[dev]"
uvicorn app.main:app --port 8080
```

Docker required for full sandbox isolation. Push to `main` → auto-deploys to Fly.io.

---

## Built for

- AI agents that execute generated code
- Automation pipelines that need auditable results
- Secure code execution with verifiable output

---

## Status — v0.5

- [x] Docker sandbox (network-disabled, read-only FS, memory + CPU limits)
- [x] Ed25519 signatures with key rotation tracking
- [x] Full orchestrator state machine + transition timeline
- [x] Proof ledger (SQLite, verifiable offline)
- [x] Python SDK (`from verity import run`)
- [x] Rate limiting · Payload limit · Agent history
- [ ] Publish SDK to PyPI (`pip install verity-core`)
- [ ] Webhook callbacks
- [ ] Multi-language sandboxes (JS, Bash)
