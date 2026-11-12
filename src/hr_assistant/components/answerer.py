"""Component 5: grounded answerer with citations and a sufficiency flag."""

from __future__ import annotations

import re

from ..llm import complete_json
from ..retrieval import Chunk
from ..schemas import Answer

_REF = re.compile(r"([a-z]+(?:-[a-z]+)+)\W{0,3}?(\d+\.\d+)")


def _ref_key(text: str) -> tuple[str, str] | None:
    m = _REF.search(text.lower())
    return (m.group(1), m.group(2)) if m else None


def resolve_citations(cited: list[str], answer_text: str, evidence: list[Chunk]) -> list[str]:
    """Map model citations to evidence IDs by (doc_id, section number), tolerant of a garbled "§" sign.

    Exact IDs are kept first; then IDs referenced inline in the answer text ("[code-of-conduct §4.1]") are
    added, which recovers a citation the model wrote correctly in the text but garbled in the list.
    Only IDs that exist in the evidence survive (no invented sources)."""
    by_key = {_ref_key(c.id): c.id for c in evidence}
    out: list[str] = []
    candidates = [*cited, *re.findall(r"\[([^\]]+)\]", answer_text)]
    for raw in candidates:
        for part in raw.split(","):
            cid = part.strip() if part.strip() in by_key.values() else by_key.get(_ref_key(part))
            if cid and cid not in out:
                out.append(cid)
    return out


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
    result.citations = resolve_citations(result.citations, result.answer, evidence)
    if result.sufficient and not result.citations:
        result.sufficient = False
        result.missing_info = result.missing_info or "The answer could not be linked to a policy section."
    return result
