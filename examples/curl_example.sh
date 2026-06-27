#!/usr/bin/env bash
# VERITY CORE — curl example
# Run: bash examples/curl_example.sh

API="https://v-rify-ia.fly.dev"

echo "==> Submitting code for sandboxed execution..."
curl -s -X POST "$API/v1/verify" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "demo",
    "payload": "print(2**10)",
    "constraints": {"language": "python", "timeout": 5},
    "verification_rules": [
      {"rule_type": "exit_code", "value": 0},
      {"rule_type": "output_contains", "value": "1024"}
    ]
  }' | python3 -m json.tool
