"""SIOS Streamlit UI — chat interface with verified execution badges."""

from __future__ import annotations

import requests
import streamlit as st

API_URL = "http://localhost:8001"

st.set_page_config(
    page_title="SIOS — Scientific Intelligence",
    page_icon="🔬",
    layout="wide",
)

st.title("🔬 SIOS — Scientific Intelligence Open System")
st.caption(
    "Multi-agent AI · Claude · Every execution cryptographically verified by VERITY CORE"
)

# ---- session state ----
if "messages" not in st.session_state:
    st.session_state.messages = []
if "proofs" not in st.session_state:
    st.session_state.proofs = []

# ---- sidebar ----
with st.sidebar:
    st.header("Session")
    if st.button("New session", use_container_width=True):
        try:
            requests.delete(f"{API_URL}/v1/session", timeout=5)
        except Exception:
            pass
        st.session_state.messages = []
        st.session_state.proofs = []
        st.rerun()

    st.divider()
    st.subheader("Verified Proofs")
    if not st.session_state.proofs:
        st.caption("No executions yet.")
    for proof in reversed(st.session_state.proofs):
        aid = proof.get("action_id", "")[:8]
        verified = proof.get("verified", False)
        icon = "✅" if verified else "❌"
        with st.expander(f"{icon} {aid}..."):
            st.json(proof)

    st.divider()
    st.subheader("Examples")
    examples = [
        "Integrate x² from 0 to 3 analytically and verify numerically",
        "Implement merge sort and benchmark it on 10 000 random integers",
        "Generate a synthetic dataset and run a linear regression",
        "Solve the Fibonacci sequence iteratively vs recursively and compare speed",
        "Compute the eigenvalues of a random 5×5 matrix",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True, key=ex):
            st.session_state["_prefill"] = ex
            st.rerun()

# ---- chat history ----
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("code"):
            with st.expander("Code executed in VERITY CORE sandbox"):
                st.code(msg["code"], language="python")
        if msg.get("output"):
            with st.expander("Execution output"):
                st.text(msg["output"])
        if msg.get("category"):
            st.caption(f"Category: {msg['category']} · Iterations: {msg.get('iterations', '?')}")

# ---- input ----
prefill = st.session_state.pop("_prefill", None)
query = st.chat_input("Ask a scientific question or coding task...") or prefill

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("*Thinking and executing…*")
        try:
            resp = requests.post(
                f"{API_URL}/v1/ask",
                json={"query": query},
                timeout=180,
            )
            resp.raise_for_status()
            data = resp.json()

            placeholder.markdown(data["answer"])

            col1, col2, col3 = st.columns(3)
            col1.metric("Category", data["category"].capitalize())
            col2.metric("Verified", "Yes" if data["verified"] else "No")
            col3.metric("Iterations", data["iterations"])

            if data.get("code"):
                with st.expander("Code executed in VERITY CORE sandbox"):
                    st.code(data["code"], language="python")
            if data.get("output"):
                with st.expander("Execution output"):
                    st.text(data["output"])

            for proof in data.get("proofs", []):
                st.session_state.proofs.append(proof)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": data["answer"],
                    "code": data.get("code", ""),
                    "output": data.get("output", ""),
                    "category": data.get("category", ""),
                    "iterations": data.get("iterations", 0),
                }
            )
        except requests.exceptions.ConnectionError:
            placeholder.error(
                f"Cannot connect to SIOS API at {API_URL}. "
                "Start it with: `uvicorn sios.api.main:app --port 8001`"
            )
        except Exception as exc:
            placeholder.error(f"Error: {exc}")
