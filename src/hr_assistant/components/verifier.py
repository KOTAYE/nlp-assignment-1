"""Component 5b: output guard (iteration 3). Runs after the answerer, before the reply is shown.

1. Delegation rule (code): if a cited section says the case is handled / decided by HR, the question goes to HR.
2. Claim verifier (LLM): the answer's main claim must be stated in the evidence; answers that rely on the policies
   being silent ("not covered", "not eligible" without a rule) go to HR (Ethics lecture: hallucination guard).
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


class VerifierResult(BaseModel):
    main_claim: str
    supported: bool
    reason: str


def delegating_sections(chunks: list[Chunk]) -> list[str]:
    return [c.id for c in chunks if DELEGATION.search(c.body)]


def verify(
    question: str, answer: str, evidence: list[Chunk], profile_facts: dict[str, str]
) -> VerifierResult:
    profile = ", ".join(f"{k}={v}" for k, v in profile_facts.items() if k != "employee_id")
    sections = "\n\n".join(c.text for c in evidence)
    user = f"Employee profile: {profile}\n\nQuestion: {question}\n\nAnswer: {answer}\n\nEvidence:\n{sections}"
    return complete_json("verifier", "verifier", user, VerifierResult)
