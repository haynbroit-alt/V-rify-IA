"""
VERITY CORE — Python example
Executes code in the sandbox and independently verifies the Ed25519 proof.

Install: pip install requests cryptography
Run:     python examples/python_example.py
"""

import base64

import requests
from cryptography.hazmat.primitives.serialization import load_pem_public_key

API = "https://v-rify-ia.fly.dev"


def run():
    # 1. Execute code in the sandbox
    response = requests.post(
        f"{API}/v1/verify",
        json={
            "agent_id": "demo",
            "payload": "print(2**10)",
            "constraints": {"language": "python", "timeout": 5},
            "verification_rules": [
                {"rule_type": "exit_code", "value": 0},
                {"rule_type": "output_contains", "value": "1024"},
            ],
        },
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()

    print(f"Status    : {result['status']}")
    print(f"Output    : {result['execution']['stdout'].strip()}")
    print(f"Action ID : {result['action_id']}")
    print(f"Signature : {result['proof']['signature'][:40]}...")
    print(f"Key ID    : {result['proof']['key_id']}")

    # 2. Independently verify the Ed25519 proof — no server access needed
    pem = requests.get(f"{API}/v1/public-key", timeout=10).json()["public_key"]
    pub = load_pem_public_key(pem.encode())

    proof = result["proof"]
    message = (
        f"{proof['action_id']}:{proof['agent_id']}:"
        f"{proof['payload_hash']}:{proof['result_hash']}:{proof['timestamp']}"
    )
    sig = base64.urlsafe_b64decode(proof["signature"])
    pub.verify(sig, message.encode())
    print("Proof     : ✓ Ed25519 signature verified independently")

    # 3. Retrieve the stored proof later
    stored = requests.get(f"{API}/v1/proof/{result['action_id']}", timeout=10).json()
    print(f"Ledger    : ✓ proof retrieved from ledger (action_id={stored['proof']['action_id']})")


if __name__ == "__main__":
    run()
