"""Component 1: input guard (rules only, no model call).

Ethics lecture: input guards (privacy/PII) before the LLM; AI Agents lecture: assume prompt injection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_CHARS = 2000

INJECTION_PATTERNS = [
    r"ignore (all |the |any )?(previous|prior|above|earlier) (instructions|rules|prompts?)",
    r"disregard (all |the |your )?(previous|prior|above|system) (instructions|rules|prompts?)",
    r"forget (all |your )?(previous |prior )?(instructions|rules)",
    r"(reveal|show|print|repeat) (me )?(your|the) (system )?(prompt|instructions)",
    r"you are now (a|an|in) ",
    r"\b(developer|dan|jailbreak|god) mode\b",
    r"act as (an? )?(unrestricted|unfiltered|admin|administrator|system)",
    r"pretend (that )?you (are|have) no (rules|restrictions)",
    r"(approve|set) (all|every) (leave )?requests?",
    r"\bsystem\s*:\s",
]

PII_PATTERNS = {
    "CARD": r"\b(?:\d[ -]?){13,19}\b",
    "IBAN": r"\bUA\d{2}[ ]?(?:\d[ ]?){25}\b",
    "PHONE": r"(?<!\d)\+?380[ -]?\(?\d{2}\)?[ -]?\d{3}[ -]?\d{2}[ -]?\d{2}(?!\d)",
    "EMAIL": r"\b[\w.+-]+@(?!lumora\.example)[\w-]+\.[\w.]+\b",
}


@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    text: str  # masked text passed downstream
    reason: str | None = None  # "too_long" | "prompt_injection" | None
    masked: tuple[str, ...] = ()


def check(message: str) -> GuardResult:
    text = message.strip()
    if len(text) > MAX_CHARS:
        return GuardResult(False, text[:MAX_CHARS], "too_long")
    lowered = text.lower()
    if any(re.search(p, lowered) for p in INJECTION_PATTERNS):
        return GuardResult(False, text, "prompt_injection")
    masked = []
    for label, pattern in PII_PATTERNS.items():
        if re.search(pattern, text):
            text = re.sub(pattern, f"[{label}]", text)
            masked.append(label)
    return GuardResult(True, text, None, tuple(masked))
