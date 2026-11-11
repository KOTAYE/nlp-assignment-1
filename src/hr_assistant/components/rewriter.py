"""Component 4a: query rewriter (conversation turn -> standalone search query)."""

from __future__ import annotations

from ..llm import complete_json
from ..schemas import RewriteResult


def rewrite(question: str, history: list[dict], facts: dict[str, str]) -> str:
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:]) or "(none)"
    known = ", ".join(f"{k}={v}" for k, v in facts.items()) or "(none)"
    user = f"Conversation so far:\n{convo}\n\nKnown facts: {known}\n\nLatest question:\n{question}"
    return complete_json("rewriter", "rewriter", user, RewriteResult).query
