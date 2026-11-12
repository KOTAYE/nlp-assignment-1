"""Component 3: information collector.

The LLM decides which facts the answer depends on and extracts values stated in the conversation; code fills
profile facts from the identity provider (deterministic) and decides whether a clarifying question is needed.
"""

from __future__ import annotations

import re
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


_DURATION = re.compile(
    r"\b(\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten)\s+(working\s+)?(day|week|month)s?\b", re.I
)
_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
_UNIT_DAYS = {  # illness is counted in working days, stays abroad in calendar days
    "illness_duration_days": {"day": 1, "week": 5, "month": 21},
    "days_abroad": {"day": 1, "week": 7, "month": 30},
}


def extract_duration(fact: str, texts: list[str]) -> str | None:
    """Deterministic fallback for numeric facts the LLM left empty ("1 day", "two weeks", "3 months")."""
    for text in reversed(texts):  # most recent statement wins
        m = _DURATION.search(text)
        if m:
            n = int(m.group(1)) if m.group(1).isdigit() else _WORDS[m.group(1).lower()]
            return str(n * _UNIT_DAYS[fact][m.group(3).lower()])
    return None


_VAGUE = re.compile(r"\b(?:something|anything|stuff|this|that|these|those|it)\b", re.I)
_FRAME = set(
    [
        "can",
        "could",
        "i",
        "we",
        "get",
        "be",
        "is",
        "are",
        "will",
        "would",
        "do",
        "does",
        "me",
        "my",
        "the",
        "a",
        "an",
        "it",
        "for",
        "reimbursed",
        "reimburse",
        "expensed",
        "expense",
        "money",
        "back",
        "covered",
        "cover",
        "compensated",
        "paid",
        "pay",
        "company",
        "refund",
    ]
)


def names_an_item(question: str) -> bool:
    """Iteration 5, code fallback: the expense category is unknown only when the question refers to it vaguely
    ("this", "something I bought") or not at all ("Can I get reimbursed?"). A question that names the item
    ("Is a taxi to a client meeting reimbursed?") already states it, so no clarifying question is asked
    (the LLM left the value empty on such questions although its own follow-up question repeated the item)."""
    content = [w for w in re.findall(r"[a-z']+", question.lower()) if w not in _FRAME]
    return bool(content) and not _VAGUE.search(question)


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
        elif f.name in _UNIT_DAYS and (
            v := extract_duration(f.name, [m["content"] for m in history if m["role"] == "user"] + [question])
        ):
            facts[f.name] = v
        elif f.name == "expense_category" and names_an_item(question):
            facts[f.name] = "the item named in the question"
        else:
            missing.append(f.name)
    question_text = out.clarifying_question if missing else None
    if missing and not question_text:
        question_text = "Could you tell me " + " and ".join(m.replace("_", " ") for m in missing) + "?"
    return Collected(required, facts, missing, question_text)
