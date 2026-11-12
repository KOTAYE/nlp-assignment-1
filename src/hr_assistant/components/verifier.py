"""Component 5b: output guard. Runs after the answerer, before the reply is shown.

1. Delegation rule (code, iteration 3): if a cited section says the case is handled / decided by HR, refer to HR.
2. Claim verifier (LLM + code, iteration 3 → 4): the LLM names the asked item and must QUOTE the evidence sentence
   that explicitly talks about it. Code then checks that the quote is really in the evidence (verbatim). No quote,
   or an invented quote, means the answer would rely on the policies being silent, so the question goes to HR
   (Ethics lecture: hallucination guard; "assertions beat judges": the decisive check is in code).
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from ..llm import complete_json
from ..retrieval import Chunk

DELEGATION = re.compile(
    r"handled by HR (?:directly|individually)|decided by HR individually|processed by HR directly|"
    r"always forwarded to HR",
    re.I,
)


class VerifierOutput(BaseModel):
    asked_item: str
    item_quote: str | None
    supported: bool
    reason: str


class VerifierResult(BaseModel):
    asked_item: str
    item_quote: str | None
    quote_found: bool
    supported: bool  # final decision: LLM judgement AND a verbatim quote that exists in the evidence
    reason: str


def delegating_sections(chunks: list[Chunk]) -> list[str]:
    return [c.id for c in chunks if DELEGATION.search(c.body)]


def _norm(text: str) -> str:
    return re.sub(r"[\s*_`>|]+", " ", text).strip().lower()


def quote_in_evidence(quote: str | None, evidence: list[Chunk]) -> bool:
    """Verbatim check (whitespace / markdown-insensitive). A quote shorter than 3 words does not count.

    A quoted TABLE ROW may skip columns ("Sport compensation | 500 UAH / month after probation"): then every
    quoted cell must appear verbatim in one and the same table row of the evidence."""
    if not quote or len(quote.split()) < 3:
        return False
    q = _norm(quote).rstrip(".")
    if any(q in _norm(c.text) for c in evidence):
        return True
    cells = [_norm(x) for x in quote.split("|") if _norm(x)]
    if len(cells) < 2:
        return False
    rows = [ln for c in evidence for ln in c.text.splitlines() if ln.lstrip().startswith("|")]
    return any(all(cell in _norm(row) for cell in cells) for row in rows)


def verify(
    question: str,
    answer: str,
    evidence: list[Chunk],
    profile_facts: dict[str, str],
    facts: dict[str, str] | None = None,
) -> VerifierResult:
    """`facts` are the situational facts collected in the conversation (iteration 5: after a clarification the
    question alone is vague, e.g. "something I bought for work" + expense_category=taxi)."""
    profile = ", ".join(f"{k}={v}" for k, v in profile_facts.items() if k != "employee_id")
    stated = ", ".join(f"{k}={v}" for k, v in (facts or {}).items() if k not in profile_facts) or "(none)"
    sections = "\n\n".join(c.text for c in evidence)
    user = (
        f"Employee profile: {profile}\nFacts the employee gave in the conversation: {stated}\n\n"
        f"Question: {question}\n\nAnswer: {answer}\n\nEvidence:\n{sections}"
    )
    out = complete_json("verifier", "verifier", user, VerifierOutput)
    found = quote_in_evidence(out.item_quote, evidence)
    reason = out.reason if found else f"no evidence sentence explicitly covers '{out.asked_item}'"
    return VerifierResult(
        asked_item=out.asked_item,
        item_quote=out.item_quote,
        quote_found=found,
        supported=out.supported and found,
        reason=reason,
    )
