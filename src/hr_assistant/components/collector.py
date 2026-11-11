"""Component 3: information collector.

The LLM decides which facts the answer depends on and extracts values stated in the conversation; code fills
profile facts from the identity provider (deterministic) and decides whether a clarifying question is needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..llm import complete_json
from ..schemas import PROFILE_FACTS, CollectorOutput


@dataclass
class Collected:
    required: list[str]  # fact names the answer depends on
    facts: dict[str, str] = field(default_factory=dict)  # name -> value (profile + conversation)
    missing: list[str] = field(default_factory=list)  # situational facts still unknown
    clarifying_question: str | None = None

    @property
    def needs_clarification(self) -> bool:
        return bool(self.missing)


def collect(question: str, history: list[dict], profile_facts: dict[str, str]) -> Collected:
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:]) or "(none)"
    user = f"Conversation so far:\n{convo}\n\nQuestion to answer:\n{question}"
    out = complete_json("collector", "collector", user, CollectorOutput)

    required: list[str] = []
    facts: dict[str, str] = {}
    missing: list[str] = []
    for f in out.required_facts:
        if f.name in required:
            continue
        required.append(f.name)
        if f.name in PROFILE_FACTS:
            facts[f.name] = profile_facts[f.name]  # identity provider is authoritative
        elif f.value not in (None, "", "null", "unknown"):
            facts[f.name] = f.value
        else:
            missing.append(f.name)
    question_text = out.clarifying_question if missing else None
    if missing and not question_text:
        question_text = "Could you tell me " + " and ".join(m.replace("_", " ") for m in missing) + "?"
    return Collected(required, facts, missing, question_text)
