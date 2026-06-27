# API Reference

Base URL: `https://v-rify-ia.fly.dev`  
Interactive docs: `https://v-rify-ia.fly.dev/docs`

---

## POST /v1/verify

Execute code in the sandbox, verify it against rules, and return a signed proof.

**Rate limit**: 60 requests per minute per IP.  
**Payload limit**: 10 KB.

### Request

```json
{
  "agent_id": "string",
  "payload": "string (code, max 10 KB)",
  "constraints": {
    "language": "python | javascript | bash",
    "timeout": 5,
    "memory": "128m",
    "network_disabled": true
  },
  "verification_rules": [
    { "rule_type": "exit_code",        "value": 0 },
    { "rule_type": "output_contains",  "value": "expected string" },
    { "rule_type": "output_not_contains", "value": "error" },
    { "rule_type": "max_execution_ms", "value": 2000 },
    { "rule_type": "stderr_empty",     "value": true }
  ]
}
```

### Response

```json
{
  "action_id": "uuid",
  "state": "COMPLETED | FAILED_EXECUTION | FAILED_PERSISTENCE",
  "status": "SUCCESS | FAILURE | REJECTED | TIMEOUT",
  "execution": {
    "stdout": "1024\n",
    "stderr": "",
    "exit_code": 0,
    "execution_time_ms": 33.5,
    "status": "SUCCESS"
  },
  "verification": {
    "passed": true,
    "rules_evaluated": 2,
    "rules_passed": 2,
    "violations": [],
    "security_flags": []
  },
  "proof": {
    "action_id": "uuid",
    "payload_hash": "sha256hex",
    "result_hash": "sha256hex",
    "signature": "base64url Ed25519 signature",
    "timestamp": 1782582144.1,
    "agent_id": "string",
    "key_id": "16-char fingerprint",
    "algorithm": "Ed25519"
  },
  "transitions": [
    {
      "from_state": "PENDING",
      "to_state": "VALIDATING_REQUEST",
      "timestamp": 1782582144.07,
      "duration_ms": 0,
      "reason": null
    }
  ],
  "message": "Verified and signed."
}
```

---

## GET /v1/proof/{action_id}

Retrieve a stored proof and re-validate its signature.

Returns `status: REJECTED` if the signature does not match (tampered record).

---

## GET /v1/history/{agent_id}

List the most recent proof records for a given agent, newest first.

Query params:
- `limit` (int, 1–100, default 50)

```json
{
  "agent_id": "my-agent",
  "count": 3,
  "records": [ ...ProofRecord... ]
}
```

---

## GET /v1/public-key

Returns the Ed25519 public key in PEM format. Use this to verify signatures independently.

```json
{ "public_key": "-----BEGIN PUBLIC KEY-----\n..." }
```

---

## GET /health

```json
{ "status": "ok", "service": "verity-core", "version": "0.5.0" }
```

---

## State machine

| State | Meaning |
|---|---|
| `PENDING` | Request received |
| `VALIDATING_REQUEST` | Payload and constraints checked |
| `EXECUTING` | Code running in sandbox |
| `VERIFYING` | Rules + security scan applied |
| `SIGNING` | Ed25519 signature computed |
| `PERSISTING` | Proof written to ledger |
| `COMPLETED` | Full pipeline success |
| `FAILED_EXECUTION` | Sandbox crash (kernel error) |
| `FAILED_PERSISTENCE` | Ledger write error |

`status` is the code execution result (`SUCCESS`, `FAILURE`, `REJECTED`, `TIMEOUT`).  
`state` is the pipeline health. Both are always present in the response.
