"""Component 5: grounded answerer with citations and a sufficiency flag."""

from __future__ import annotations

from ..llm import complete_json
from ..retrieval import Chunk
from ..schemas import Answer


def answer(
    question: str,
    history: list[dict],
    facts: dict[str, str],
    profile_facts: dict[str, str],
    evidence: list[Chunk],
) -> Answer:
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:]) or "(none)"
    profile = ", ".join(f"{k}={v}" for k, v in profile_facts.items() if k not in ("employee_id",))
    known = ", ".join(f"{k}={v}" for k, v in facts.items()) or "(none)"
    sections = "\n\n".join(c.text for c in evidence)
    user = (
        f"Employee profile: {profile}\nFacts relevant to this question: {known}\n\n"
        f"Conversation so far:\n{convo}\n\nQuestion: {question}\n\nEvidence (policy sections):\n{sections}"
    )
    result = complete_json("answerer", "answerer", user, Answer)
    # Citation validation: keep only IDs that were actually in the evidence (no invented sources).
    allowed = {c.id for c in evidence}
    result.citations = [c for c in dict.fromkeys(result.citations) if c in allowed]
    if result.sufficient and not result.citations:
        result.sufficient = False
        result.missing_info = result.missing_info or "The answer could not be linked to a policy section."
    return result
