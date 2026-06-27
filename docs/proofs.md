# Cryptographic Proofs

VERITY CORE signs every execution result with **Ed25519**. The signature is verifiable by anyone — no server access, no shared secret.

---

## How it works

When you call `POST /v1/verify`, the response includes a `proof` object:

```json
{
  "action_id": "5b73308c-e21d-42d2-9c8b-1fcde04d398b",
  "payload_hash": "bfd9381c...",
  "result_hash": "92c2b2d0...",
  "signature": "qx2zZrTp1E37...",
  "timestamp": 1782582144.1074,
  "agent_id": "my-agent",
  "key_id": "c8f3a73f7b8eb33f",
  "algorithm": "Ed25519"
}
```

**What each field covers:**

| Field | Content |
|---|---|
| `payload_hash` | SHA-256 of the code that was submitted |
| `result_hash` | SHA-256 of `{stdout, stderr, exit_code, status}` |
| `signature` | Ed25519 over the canonical message (see below) |
| `key_id` | First 16 hex chars of SHA-256(public_key) — for rotation tracking |

---

## The canonical message

The signed message is deterministic:

```
{action_id}:{agent_id}:{payload_hash}:{result_hash}:{timestamp}
```

This means the signature covers:
- **Which action** ran (`action_id`)
- **Which agent** submitted it (`agent_id`)
- **What code** was submitted (`payload_hash`)
- **What output** was produced (`result_hash`)
- **When** it happened (`timestamp`)

Changing any of these fields after signing will invalidate the signature.

---

## Verifying a proof independently (Python)

```python
import base64
import requests
from cryptography.hazmat.primitives.serialization import load_pem_public_key

API = "https://v-rify-ia.fly.dev"

# Fetch public key once (cache it — it changes only on key rotation)
pem = requests.get(f"{API}/v1/public-key").json()["public_key"]
pub = load_pem_public_key(pem.encode())

def verify_proof(proof: dict) -> bool:
    message = (
        f"{proof['action_id']}:{proof['agent_id']}:"
        f"{proof['payload_hash']}:{proof['result_hash']}:{proof['timestamp']}"
    )
    sig = base64.urlsafe_b64decode(proof["signature"])
    try:
        pub.verify(sig, message.encode())
        return True
    except Exception:
        return False

# Example
result = requests.post(f"{API}/v1/verify", json={
    "agent_id": "demo",
    "payload": "print(42)",
    "constraints": {"language": "python", "timeout": 5},
}).json()

print(verify_proof(result["proof"]))  # True
```

---

## Verifying a stored proof

Proofs are persisted in the ledger. Retrieve and re-verify at any time:

```bash
curl https://v-rify-ia.fly.dev/v1/proof/{action_id}
```

The response re-validates the signature server-side. If the ledger entry was tampered with, `status` is `REJECTED`.

---

## Key rotation

`key_id` is a 16-character fingerprint of the current public key. If the server rotates its signing key (e.g. key compromise), `key_id` changes. Old proofs remain verifiable with the old public key if you archived it.

To track rotation: compare `key_id` in the proof against the current `key_id` returned by `GET /v1/public-key` (derivable from the PEM).
