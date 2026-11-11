"""Orchestration: one message in -> reply + trace out (see the data-flow diagram in docs/architecture.md).

The pipeline is a *workflow* (code decides the path from the router's output); only the leave flow is an agent
loop, because its steps depend on tool observations (AI Agents lecture: lowest sufficient autonomy).
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from .components import answerer, collector, guard, leave_agent, referral, rewriter, router
from .directory import Profile
from .llm import Trace, start_trace, trace_event
from .retrieval import get_stack
from .tools import ToolContext

MAX_CLARIFICATIONS = 2
SMALLTALK_REPLY = (
    "Hi! I'm the Lumora Tech HR assistant. I can answer questions about our HR policies (leave, sick leave, "
    "benefits, onboarding, remote work, expenses, equipment, documents) with links to the exact policy section, "
    "help you request, check or cancel leave, and pass anything else to the HR team."
)
UNCLEAR_REPLY = (
    "Sorry, I didn't quite get that. Do you want to ask about an HR policy, or request / check your leave? "
    "Please give me a bit more detail."
)
BLOCKED_REPLY = "I can't process this message. Please rephrase your HR question."


@dataclass
class Session:
    profile: Profile
    conn: sqlite3.Connection
    today: dt.date
    history: list[dict] = field(default_factory=list)
    pending_question: str | None = None  # policy question waiting for clarification
    clarifications_asked: int = 0


@dataclass
class Reply:
    text: str
    route: str
    trace: Trace
    citations: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    ticket_id: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


def with_sources(text: str, citations: list[str]) -> str:
    """Brief: the assistant must "identify the source in its answer". Guarantee it in code: every cited section
    appears in the reply text; if the model did not put it inline, append a Sources line."""
    missing = [c for c in citations if c not in text]
    if not missing:
        return text
    return f"{text}\n\nSources: " + ", ".join(f"[{c}]" for c in missing)


def _finish(session: Session, user_text: str, reply: Reply) -> Reply:
    session.history += [{"role": "user", "content": user_text}, {"role": "assistant", "content": reply.text}]
    trace_event(
        "pipeline",
        "reply",
        route=reply.route,
        text=reply.text,
        citations=reply.citations,
        ticket_id=reply.ticket_id,
    )
    return reply


def handle(session: Session, message: str) -> Reply:
    trace = start_trace()
    ctx = ToolContext(session.conn, session.profile, session.today)
    profile_facts = session.profile.facts(session.today)

    g = guard.check(message)
    trace_event("guard", "guard", allowed=g.allowed, reason=g.reason, masked=list(g.masked))
    if not g.allowed:
        session.pending_question = None
        return _finish(session, message, Reply(BLOCKED_REPLY, "blocked", trace, details={"guard": g.reason}))
    text = g.text

    # A pending clarification: the message answers the collector's question for the stored policy question.
    if session.pending_question:
        intent, question = "policy_question", session.pending_question
        trace_event("router", "router", intent=intent, skipped="answering clarification")
    else:
        r = router.route(text, session.history)
        intent, question = r.intent, text
        trace_event("router", "router", intent=r.intent, confidence=r.confidence, reason=r.reason)

    if intent == "smalltalk":
        return _finish(session, message, Reply(SMALLTALK_REPLY, intent, trace))
    if intent == "unclear":
        return _finish(session, message, Reply(UNCLEAR_REPLY, intent, trace))

    if intent == "leave_action":
        res = leave_agent.run(text, session.history, ctx)
        return _finish(
            session,
            message,
            Reply(
                res.reply,
                intent,
                trace,
                details={"stop_reason": res.stop_reason, "tool_calls": res.tool_calls, "steps": res.steps},
            ),
        )

    if intent == "hr_referral":
        ref = referral.refer(question, "sensitive or out-of-scope topic (router)", ctx, profile_facts)
        return _finish(
            session,
            message,
            Reply(
                ref.reply,
                "hr_referral",
                trace,
                ticket_id=ref.ticket_id,
                details={"category": ref.category, "summary": ref.summary},
            ),
        )

    # ---- policy question: collect -> rewrite -> retrieve -> rerank -> answer (or refer)
    history_for_llm = session.history + (
        [{"role": "user", "content": text}] if session.pending_question else []
    )
    col = collector.collect(question, history_for_llm, profile_facts)
    trace_event("collector", "collector", required=col.required, facts=col.facts, missing=col.missing)
    if col.needs_clarification and session.clarifications_asked < MAX_CLARIFICATIONS:
        session.pending_question = question
        session.clarifications_asked += 1
        return _finish(
            session,
            message,
            Reply(
                col.clarifying_question or UNCLEAR_REPLY,
                "clarification",
                trace,
                details={"missing": col.missing},
            ),
        )
    session.pending_question, session.clarifications_asked = None, 0

    query = rewriter.rewrite(question, history_for_llm, col.facts)
    trace_event("rewriter", "rewriter", query=query)
    stack = get_stack()
    candidates = stack.hybrid.search(query, k=20)
    top = stack.reranker.rerank(query, candidates, k=5)
    trace_event(
        "retrieval",
        "retriever",
        query=query,
        candidates=[c.id for c, _ in candidates],
        reranked=[(c.id, round(s, 3)) for c, s in top],
    )
    evidence = [c for c, _ in top]

    ans = answerer.answer(question, history_for_llm, col.facts, profile_facts, evidence)
    ev = [{"id": c.id, "text": c.text} for c in evidence]
    if not ans.sufficient:
        ref = referral.refer(
            question, f"policies do not support an answer: {ans.missing_info}", ctx, profile_facts
        )
        return _finish(
            session,
            message,
            Reply(
                ref.reply,
                "hr_referral",
                trace,
                evidence=ev,
                ticket_id=ref.ticket_id,
                details={
                    "missing_info": ans.missing_info,
                    "category": ref.category,
                    "query": query,
                    "facts": col.facts,
                },
            ),
        )
    return _finish(
        session,
        message,
        Reply(
            with_sources(ans.answer, ans.citations),
            "answer",
            trace,
            citations=ans.citations,
            evidence=ev,
            details={"query": query, "facts": col.facts},
        ),
    )
