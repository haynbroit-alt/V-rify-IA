// VERITY CORE — Node.js example
// Run: node examples/node_example.js  (Node 18+, no extra deps)

const API = "https://v-rify-ia.fly.dev";

async function run() {
  // 1. Execute code in the sandbox
  const res = await fetch(`${API}/v1/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      agent_id: "demo",
      payload: "print(2**10)",
      constraints: { language: "python", timeout: 5 },
      verification_rules: [
        { rule_type: "exit_code", value: 0 },
        { rule_type: "output_contains", value: "1024" },
      ],
    }),
  });

  const result = await res.json();

  console.log("Status    :", result.status);
  console.log("Output    :", result.execution.stdout.trim());
  console.log("Action ID :", result.action_id);
  console.log("Signature :", result.proof.signature.slice(0, 40) + "...");
  console.log("Key ID    :", result.proof.key_id);
  console.log("State     :", result.state);
  console.log("Transitions:");
  for (const t of result.transitions) {
    console.log(`  ${t.from_state} → ${t.to_state} (${t.duration_ms.toFixed(2)} ms)`);
  }

  // 2. Retrieve stored proof
  const proofRes = await fetch(`${API}/v1/proof/${result.action_id}`);
  const stored = await proofRes.json();
  console.log("Ledger    : ✓ proof retrieved (action_id =", stored.proof.action_id + ")");
}

run().catch(console.error);
