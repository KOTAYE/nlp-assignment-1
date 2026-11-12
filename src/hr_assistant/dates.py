"""Deterministic resolution of date expressions for the leave agent (iteration 3).

LLMs are unreliable at calendar arithmetic (weekday of a date, "next week", year of "1 February"), so the code
resolves the expressions it recognises and gives the agent ISO dates. Rules:
- explicit day + month without a year -> the next occurrence on or after (today - 14 days), so recent past dates
  (sick leave) stay in the current year;
- bare weekday -> the coming one (today counts); "last/since <weekday>" -> the most recent past one;
  "next week <weekday>" / "<weekday> next week" -> that weekday in the next calendar week;
- "the 20th" without a month -> the next date with that day of month.
"""

from __future__ import annotations

import datetime as dt
import re

MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ],
        1,
    )
}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
WEEKDAYS = {
    d: i for i, d in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])
}

_MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_DAY = r"(\d{1,2})(?:st|nd|rd|th)?"
_YEAR = r"(?:,?\s+(\d{4}))?"
# "7 December", "the 1st of February", "7 to 11 December", "December 7", "7-11 Dec 2027"
_WD = r"(?:(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\s+)?"  # optional weekday label before a day number
_DAY_MONTH = re.compile(
    rf"\b(?:the\s+)?{_DAY}(?:\s*(?:-|–|to|and|until|till)\s*{_WD}(?:the\s+)?{_DAY})?\s+(?:of\s+)?{_MON}\b{_YEAR}",
    re.I,
)
_MONTH_DAY = re.compile(rf"\b{_MON}\s+{_DAY}\b{_YEAR}", re.I)
_BARE_DAY = re.compile(rf"\bthe\s+{_DAY}\b(?!\s+(?:of\s+)?{_MON})", re.I)
_WEEKDAY = re.compile(
    r"\b(?:(next|last|since|this|coming)\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.I,
)


def _with_year(day: int, month: int, today: dt.date, year: int | None) -> dt.date | None:
    try:
        if year:
            return dt.date(year, month, day)
        d = dt.date(today.year, month, day)
        return d if d >= today - dt.timedelta(days=14) else dt.date(today.year + 1, month, day)
    except ValueError:
        return None


def resolve(text: str, today: dt.date) -> list[tuple[str, dt.date]]:
    """Return (expression, date) pairs for the date expressions found in `text`."""
    found: list[tuple[str, dt.date]] = []
    low = text.lower()
    for word, delta in (("today", 0), ("tomorrow", 1), ("yesterday", -1)):
        if re.search(rf"\b{word}\b", low):
            found.append((word, today + dt.timedelta(days=delta)))
    spans: list[tuple[int, int]] = []

    def inside(m: re.Match) -> bool:
        return any(a <= m.start() < b for a, b in spans)

    for m in _DAY_MONTH.finditer(text):
        spans.append(m.span())
        month = MONTHS[m.group(3).lower()[:3]]
        year = int(m.group(4)) if m.group(4) else None
        for g in (m.group(1), m.group(2)):
            if g and (d := _with_year(int(g), month, today, year)):
                found.append((m.group(0), d))
    for m in _MONTH_DAY.finditer(text):
        if inside(m):
            continue
        spans.append(m.span())
        month = MONTHS[m.group(1).lower()[:3]]
        if d := _with_year(int(m.group(2)), month, today, int(m.group(3)) if m.group(3) else None):
            found.append((m.group(0), d))
    for m in _BARE_DAY.finditer(text):
        if inside(m):
            continue
        day = int(m.group(1))
        cand = today
        for _ in range(62):
            if cand.day == day and cand >= today:
                found.append((m.group(0), cand))
                break
            cand += dt.timedelta(days=1)
    next_week = "next week" in low
    for m in _WEEKDAY.finditer(text):
        if inside(m) or re.match(r"\s+(?:the\s+)?\d", text[m.end() :]):
            continue  # weekday that only labels an explicit date ("Monday 7 December", "Friday the 20th")
        mod, wd = (m.group(1) or "").lower(), WEEKDAYS[m.group(2).lower()]
        if mod in ("last", "since"):
            back = (today.weekday() - wd) % 7 or 7
            found.append((m.group(0), today - dt.timedelta(days=back)))
        elif mod == "next" or next_week:
            monday_next = today + dt.timedelta(days=7 - today.weekday())
            found.append((m.group(0), monday_next + dt.timedelta(days=wd)))
        else:
            ahead = (wd - today.weekday()) % 7
            found.append((m.group(0), today + dt.timedelta(days=ahead)))
    # de-duplicate, keep order
    seen, out = set(), []
    for expr, d in found:
        if (expr.lower(), d) not in seen:
            seen.add((expr.lower(), d))
            out.append((expr, d))
    return out


def annotate(text: str, today: dt.date) -> str:
    """A note for the agent, or '' when no date expression was recognised."""
    pairs = resolve(text, today)
    if not pairs:
        return ""
    items = "; ".join(f"'{e}' = {d.strftime('%a')} {d.isoformat()}" for e, d in pairs)
    return f"[Dates resolved by the system calendar (trust these, do not recompute): {items}]"
