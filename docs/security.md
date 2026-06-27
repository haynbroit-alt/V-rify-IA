# Security

VERITY CORE's security model is built around one principle: **no AI-generated code ever runs directly on the host**.

---

## Sandbox isolation

Every payload runs inside a Docker container with:

| Constraint | Value |
|---|---|
| Network | Disabled (`--network none`) |
| Filesystem | Read-only (`--read-only`) |
| Memory | 128 MB hard cap |
| CPU | 50% of one core (`cpu_quota=50000`) |
| PID limit | 64 processes |
| Capabilities | All dropped (`--cap-drop ALL`) |
| Privilege escalation | Blocked (`no-new-privileges:true`) |
| User | Non-root (`uid=1000`) |
| Writable `/tmp` | `noexec,nosuid,size=64m` |

A container is created fresh per request and destroyed immediately after execution. No state persists between executions.

---

## Static security scan

Before execution, every payload is scanned for dangerous patterns:

- `eval(`, `exec(` — dynamic code execution
- `subprocess`, `os.system`, `os.popen` — shell spawning
- `socket.`, `urllib`, `requests`, `http` — network calls
- `/etc/passwd`, `/etc/shadow`, `/proc/` — sensitive filesystem paths
- `__import__`, `importlib` — dynamic imports

Detected patterns are reported in `verification.security_flags[]`. The payload still executes — the flags are surfaced for the caller to act on.

---

## Cryptographic proofs

Proofs use **Ed25519** (not HMAC-SHA256), which means:

- The private key stays on the server
- Anyone with the public key (`GET /v1/public-key`) can verify a proof **without any server access**
- Tamper-detection is cryptographically guaranteed

The signed message is a deterministic canonical string:

```
{action_id}:{agent_id}:{payload_hash}:{result_hash}:{timestamp}
```

`payload_hash` and `result_hash` are SHA-256 digests, so the signature covers the exact code that ran and the exact output produced.

---

## Subprocess fallback

In production, Docker must be available. If Docker is unavailable, the API raises an error unless `VERITY_ALLOW_SUBPROCESS_FALLBACK=true` is set.

**Never set `VERITY_ALLOW_SUBPROCESS_FALLBACK=true` in production.** This env var bypasses all sandbox isolation and runs code directly in the host process.

---

## Rate limiting

`POST /v1/verify` is rate-limited to **60 requests per minute per IP** using `slowapi`. Exceeded requests receive HTTP 429.

---

## Payload size

Payloads are hard-capped at **10 KB**. Requests exceeding this limit receive HTTP 422 before any execution occurs.
