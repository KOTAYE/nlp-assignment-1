"""Lumora Tech HR assistant: Streamlit UI.

Run:  streamlit run app/streamlit_app.py

The UI never queries the leave database: everything about leave goes through the assistant (LLM tool calls),
as required by the brief ("access it via LLM only"). The trace panel shows how each message passed through the
system: guard -> router -> collector -> rewriter -> retrieval -> answerer / leave agent / HR referral.
"""

from __future__ import annotations

import json

import streamlit as st

from hr_assistant import db
from hr_assistant.config import get_settings
from hr_assistant.directory import all_profiles, get_profile
from hr_assistant.pipeline import Session, handle
from hr_assistant.retrieval import get_stack

st.set_page_config(page_title="Lumora HR Assistant", page_icon="🗂️", layout="wide")
settings = get_settings()


@st.cache_resource(show_spinner="Loading search models (first run only)...")
def warm_up():
    return get_stack()


@st.cache_resource
def connection():
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.connect(settings.db_path)
    db.init_db(conn)  # creates and seeds the database on first run (setup, not a data query)
    return conn


warm_up()
conn = connection()

# ---------------------------------------------------------------- sidebar: identity (SSO stand-in)
profiles = all_profiles()
labels = {p.employee.id: f"{p.employee.name} · {p.employee.team} · {p.employee.employment_type.replace('_', '-')}"
          f"{' · HR' if p.employee.role == 'hr' else ''}" for p in profiles}
with st.sidebar:
    st.header("Lumora Tech · HR")
    emp_id = st.selectbox("Log in as", list(labels), format_func=labels.get, index=4)
    profile = get_profile(emp_id)
    facts = profile.facts(settings.today())
    st.caption("Profile from the employee directory (identity provider):")
    st.markdown(
        f"- **Type:** {facts['employment_type']}\n- **Office:** {facts['office']}\n"
        f"- **Start:** {facts['start_date']}\n- **Probation passed:** {facts['probation_passed']}\n"
        f"- **Role:** {facts['role']}\n- **Business date:** {facts['today']}"
    )
    show_trace = st.toggle("Show trace (LLM & tool calls)", value=True)
    if st.button("New conversation"):
        st.session_state.pop("session", None)
        st.session_state.pop("messages", None)
    st.divider()
    st.caption("Try: *How many vacation days can I carry over?* · *Do I need a sick note?* · "
               "*Book annual leave 7–11 December* · *How many days do I have left?* · "
               "*What is the salary range for seniors?* · as HR: *Show pending requests*")

# ---------------------------------------------------------------- session state
if "session" not in st.session_state or st.session_state.session.profile.employee.id != emp_id:
    st.session_state.session = Session(profile, conn, settings.today())
    st.session_state.messages = []

session: Session = st.session_state.session

ROUTE_BADGE = {
    "answer": "📄 policy answer", "clarification": "❓ clarifying question", "hr_referral": "🧑‍💼 routed to HR",
    "leave_action": "🗓️ leave agent", "smalltalk": "💬 small talk", "unclear": "🤔 unclear", "blocked": "🛡️ blocked by guard",
}


def render_trace(reply_meta: dict) -> None:
    with st.expander(f"Trace · {reply_meta['llm_calls']} LLM calls · {reply_meta['tokens']} tokens · "
                     f"${reply_meta['cost']:.5f}", expanded=False):
        for e in reply_meta["events"]:
            kind, comp = e["kind"], e["component"]
            if kind == "llm":
                st.markdown(f"**LLM · {comp}** (prompt v{e.get('prompt_version')}, {e.get('model')}, "
                            f"{e.get('tokens_in', 0)}+{e.get('tokens_out', 0)} tok, {e.get('latency_ms')} ms)")
                if e.get("tool_calls"):
                    st.code(json.dumps(e["tool_calls"], indent=1, ensure_ascii=False), language="json")
                elif e.get("output"):
                    st.code(e["output"][:1500], language="json")
            elif kind == "tool":
                st.markdown(f"**TOOL · {e['tool']}** ← called by {comp} ({e.get('latency_ms')} ms)")
                st.code(json.dumps({"arguments": e["arguments"], "result": e["result"]}, indent=1,
                                   ensure_ascii=False, default=str)[:2000], language="json")
            elif kind == "retrieval":
                st.markdown(f"**RETRIEVAL** query: `{e['query']}`")
                st.write("hybrid top-20 → reranked top-5:", [f"{cid} ({s})" for cid, s in e["reranked"]])
            elif kind in ("guard", "router", "collector", "rewriter"):
                st.markdown(f"**{kind.upper()}** " + ", ".join(
                    f"{k}={v}" for k, v in e.items() if k not in ("ts", "kind", "component", "trace_id")))


for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m["role"] == "assistant":
            st.caption(ROUTE_BADGE.get(m["route"], m["route"]) + (f" · ticket #{m['ticket']}" if m.get("ticket") else ""))
            if m.get("evidence"):
                with st.expander("Sources"):
                    for ev in m["evidence"]:
                        mark = "✅ cited" if ev["id"] in m["citations"] else "retrieved"
                        st.markdown(f"**{ev['id']}** · {mark}")
                        st.caption(ev["text"])
            if show_trace and m.get("meta"):
                render_trace(m["meta"])

st.title("HR Assistant")
st.caption("Answers come only from Lumora Tech policies, with the exact section cited. "
           "Leave requests are handled through the assistant. Anything the policies don't cover goes to HR.")

if prompt := st.chat_input("Ask an HR question or manage your leave..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"), st.spinner("Thinking..."):
        reply = handle(session, prompt)
    meta = {"events": reply.trace.events, "llm_calls": len(reply.trace.llm_calls), "tokens": reply.trace.tokens,
            "cost": reply.trace.cost_usd}
    st.session_state.messages.append({"role": "assistant", "content": reply.text, "route": reply.route,
                                      "citations": reply.citations, "evidence": reply.evidence,
                                      "ticket": reply.ticket_id, "meta": meta})
    st.rerun()
