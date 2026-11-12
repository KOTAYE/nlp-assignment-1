"""HOLDOUT-3 (written after iteration 3 and BEFORE the iteration-4 fixes; never used for tuning).

Focus: topics the policies are silent about, privacy and "Can I ...?" rule questions, sensitive personal cases,
sections that delegate to HR; plus leave-agent sanity checks. Run: python -m evals.holdout3
"""

from __future__ import annotations

from evals.build_datasets import wd, write

HOLDOUT3_QA = [
    (
        "E003",
        "Will HR tell my team lead if I use the ethics hotline?",
        ["code-of-conduct §2.2"],
        "No: reports are handled confidentially (the hotline can be anonymous) and retaliation is forbidden.",
    ),
    (
        "E003",
        "Can the company see what I discussed with the psychologist?",
        ["benefits-policy §5.2"],
        "No, the company receives no information about who used the sessions or what was discussed.",
    ),
    (
        "E003",
        "Can I use a sick day for my mental health?",
        ["sick-leave-policy §3.4"],
        "Yes, mental health is treated like physical health; sick days apply under the same rules.",
    ),
    (
        "E003",
        "Can I split my annual leave into several parts?",
        ["leave-policy §2.3"],
        "Yes; at least one part per year should ideally be 5 consecutive working days (a recommendation).",
    ),
    (
        "E003",
        "Can I cancel my approved vacation before it starts?",
        ["leave-policy §3.5"],
        "Yes, an approved or pending request can be cancelled before the leave starts; the days return to the balance.",
    ),
    (
        "E003",
        "Can I work on a company holiday and take another day off instead?",
        ["leave-policy §6.2"],
        "Yes, with prior manager approval; you get another day off within 30 days.",
    ),
    (
        "E007",
        "Can I use the psychologist sessions?",
        ["benefits-policy §5.1"],
        "Contractors get the 24/7 support hotline, not the 6 paid sessions.",
    ),
    (
        "E003",
        "Is a taxi to a client meeting reimbursed?",
        ["expense-reimbursement-policy §4.2"],
        "Yes, in full.",
    ),
    (
        "E003",
        "Can I install software I downloaded from a torrent on my work laptop?",
        ["equipment-policy §4.1"],
        "No, installing pirated software is forbidden.",
    ),
    (
        "E003",
        "Can I work from a cafe on public Wi-Fi?",
        ["remote-work-policy §4.1"],
        "Only with the company VPN turned on.",
    ),
    (
        "E003",
        "Do I need approval before a business trip?",
        ["expense-reimbursement-policy §3.1"],
        "Yes, every business trip needs prior approval from the team lead.",
    ),
    (
        "E016",
        "By when do I have to complete the Code of Conduct training?",
        ["onboarding-policy §2.3"],
        "Within 30 calendar days of the start date.",
    ),
    (
        "E003",
        "Can I share customer data with a friend who is helping me with a task?",
        ["code-of-conduct §5.1"],
        "No, customer data must not be shared outside the company.",
    ),
    (
        "E003",
        "Does the company pay for my gym membership?",
        ["benefits-policy §1.1", "benefits-policy §3.1"],
        "Yes: sport compensation of 1,000 UAH per month after probation covers gym memberships.",
    ),
]
HOLDOUT3_REFER = [
    ("E003", "Does the company pay for contact lenses?", [], "benefits"),
    ("E003", "Is there a free lunch in the Kyiv office?", [], "benefits"),
    ("E003", "Can I get an allowance for cycling to work?", [], "benefits"),
    ("E003", "Will the company cover my mobile phone bill?", [], "benefits"),
    ("E003", "Do we get a wellness day off every quarter?", [], "leave_and_absence"),
    (
        "E003",
        "My father needs care after surgery. Can I take paid leave to look after him?",
        ["sick-leave-policy §3.3"],
        "leave_and_absence",
    ),
    (
        "E003",
        "I want to work remotely from Portugal for five months.",
        ["remote-work-policy §3.2"],
        "relocation_and_abroad",
    ),
    ("E003", "How does paternity leave work here?", ["leave-policy §7.1"], "leave_and_absence"),
    (
        "E003",
        "My team lead makes sexist jokes in meetings and I want to complain.",
        ["code-of-conduct §2.3"],
        "workplace_conduct",
    ),
    ("E003", "How much does my colleague Andrii earn?", [], "documents_and_data"),
]


def build_qa() -> list[dict]:
    rows = []
    for i, (emp, q, secs, ans) in enumerate(HOLDOUT3_QA, 1):
        rows.append(
            {
                "id": f"h3q{i:02d}",
                "employee_id": emp,
                "question": q,
                "gold_section_ids": secs,
                "gold_answer": ans,
                "gold_outcome": "answer",
                "gold_category": None,
                "origin": "manual",
                "split": "holdout3",
            }
        )
    for i, (emp, q, secs, cat) in enumerate(HOLDOUT3_REFER, 1):
        rows.append(
            {
                "id": f"h3u{i:02d}",
                "employee_id": emp,
                "question": q,
                "gold_section_ids": secs,
                "gold_answer": None,
                "gold_outcome": "hr_referral",
                "gold_category": cat,
                "origin": "manual",
                "split": "holdout3",
            }
        )
    return rows


def build_agent() -> list[dict]:
    S = []

    def add(emp, turns, label, new=(), required=(), reply_regex=None):
        S.append(
            {
                "id": f"h3a{len(S) + 1:02d}",
                "employee_id": emp,
                "turns": turns,
                "label": label,
                "split": "holdout3",
                "expect": {
                    "new": list(new),
                    "status_changes": {},
                    "tools_required": list(required),
                    "tools_forbidden": [],
                    "reply_any": [],
                    "reply_regex": reply_regex,
                },
            }
        )

    add(
        "E028",
        ["I'm sick today and tomorrow, please register it."],
        "submit",
        [{"type": "sick", "days": wd("2026-11-12", "2026-11-13"), "status": "approved"}],
        ["submit_leave_request"],
    )
    add(
        "E017",
        ["Book annual leave for next Thursday."],
        "submit",
        [{"type": "annual", "days": wd("2026-11-19", "2026-11-19"), "status": "approved"}],
        ["submit_leave_request"],
    )
    add(
        "E021",
        ["Book annual leave from Monday 30 November to Wednesday 2 December."],
        "submit",
        [{"type": "annual", "days": wd("2026-11-30", "2026-12-02"), "status": "declined"}],
        ["submit_leave_request"],
    )
    add(
        "E013",
        ["How many vacation days do I have left?"],
        "read",
        [],
        ["get_leave_balance"],
        reply_regex=r"\b(0|zero|no)\b",
    )
    return S


if __name__ == "__main__":
    write("qa_holdout3", build_qa(), None)
    write("agent_holdout3", build_agent(), None)
