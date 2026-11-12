"""HOLDOUT-4 (written after iteration 4 and BEFORE the iteration-5 fixes; never used for tuning).

Focus: answers that live in table rows, exceptions inside exclusion lists ("not reimbursed, except ..."),
"what should I do / whom do I contact" procedure questions (not personal incidents), named items the
policies are silent about (must go to HR, not to a clarifying question), plus leave-agent sanity checks.
Run: python -m evals.holdout4
"""

from __future__ import annotations

from evals.build_datasets import wd, write

HOLDOUT4_QA = [
    (
        "E028",
        "What is my education budget?",
        ["benefits-policy §1.1"],
        "As a part-time employee: 300 USD per year after probation.",
    ),
    (
        "E003",
        "How much sport compensation does a part-time employee get?",
        ["benefits-policy §1.1"],
        "500 UAH per month after probation.",
    ),
    (
        "E003",
        "Can I expense the wine we ordered at an approved lunch with a client?",
        ["expense-reimbursement-policy §1.3", "expense-reimbursement-policy §5.1"],
        "Yes: alcohol is reimbursed at approved client meals (within the 40 USD per person limit).",
    ),
    (
        "E003",
        "Will the company pay my parking fine from a business trip?",
        ["expense-reimbursement-policy §1.3"],
        "No, fines are not reimbursed.",
    ),
    (
        "E003",
        "My work laptop was stolen from my car. What do I need to do?",
        ["equipment-policy §2.1"],
        "Report it to IT within 24 hours so IT can lock the device remotely.",
    ),
    (
        "E003",
        "Who should I tell if I see a colleague being bullied?",
        ["code-of-conduct §2.2"],
        "Report it to HR at hr@lumora.example or anonymously via the ethics hotline in the HR portal.",
    ),
    (
        "E003",
        "Does our health insurance include dental treatment?",
        ["benefits-policy §2.1"],
        "Yes, dental treatment is covered up to 10,000 UAH per year.",
    ),
    (
        "E003",
        "A partner sent me a 30 USD gift card. Is it OK to keep it?",
        ["code-of-conduct §4.1"],
        "Yes, gifts up to 50 USD may be accepted.",
    ),
    (
        "E007",
        "Can I join the English lessons?",
        ["benefits-policy §6.1"],
        "Yes, contractors can join the free group English lessons (after a placement test).",
    ),
    (
        "E003",
        "I accidentally cracked my laptop screen. Do I have to pay for the repair?",
        ["equipment-policy §2.2"],
        "No, accidental damage is repaired at the company's cost.",
    ),
    (
        "E003",
        "Can I buy running shoes with my sport compensation?",
        ["benefits-policy §3.1"],
        "No, sport equipment purchases are not covered.",
    ),
    (
        "E003",
        "How much do I get per day on a business trip?",
        ["expense-reimbursement-policy §3.2"],
        "A per diem of 50 USD per day, plus accommodation up to 120 USD per night.",
    ),
]

HOLDOUT4_REFER = [
    ("E003", "Will the company pay for my home internet?", [], "benefits"),
    ("E003", "Is there a fuel allowance for driving to the office?", [], "benefits"),
    ("E003", "Do we get a year-end bonus?", [], "compensation"),
    ("E003", "Can I bring my dog to the Lviv office?", [], "other"),
    ("E003", "Does the company help pay for kindergarten?", [], "benefits"),
    (
        "E003",
        "My manager keeps shouting at me in front of the team. I can't take it anymore.",
        ["code-of-conduct §2.3"],
        "workplace_conduct",
    ),
]


def build_qa() -> list[dict]:
    rows = []
    for i, (emp, q, secs, ans) in enumerate(HOLDOUT4_QA, 1):
        rows.append(
            {
                "id": f"h4q{i:02d}",
                "employee_id": emp,
                "question": q,
                "gold_section_ids": secs,
                "gold_answer": ans,
                "gold_outcome": "answer",
                "gold_category": None,
                "origin": "manual",
                "split": "holdout4",
            }
        )
    for i, (emp, q, secs, cat) in enumerate(HOLDOUT4_REFER, 1):
        rows.append(
            {
                "id": f"h4u{i:02d}",
                "employee_id": emp,
                "question": q,
                "gold_section_ids": secs,
                "gold_answer": None,
                "gold_outcome": "hr_referral",
                "gold_category": cat,
                "origin": "manual",
                "split": "holdout4",
            }
        )
    return rows


def build_agent() -> list[dict]:
    S = []

    def add(emp, turns, label, new=(), required=(), reply_regex=None):
        S.append(
            {
                "id": f"h4a{len(S) + 1:02d}",
                "employee_id": emp,
                "turns": turns,
                "label": label,
                "split": "holdout4",
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
        ["I forgot to register yesterday, I was sick. Please add it."],
        "submit",
        [{"type": "sick", "days": wd("2026-11-11", "2026-11-11"), "status": "approved"}],
        ["submit_leave_request"],
    )
    add(
        "E017",
        ["Please book me a day off on Friday 4 December."],
        "submit",
        [{"type": "annual", "days": wd("2026-12-04", "2026-12-04"), "status": "approved"}],
        ["submit_leave_request"],
    )
    add(
        "E017",
        ["Book annual leave on 25 November."],
        "submit",
        [{"type": "annual", "days": wd("2026-11-25", "2026-11-25"), "status": "declined"}],
        ["submit_leave_request"],
        reply_regex=r"(?i)(overlap|already|declined|existing)",
    )
    return S


if __name__ == "__main__":
    write("qa_holdout4", build_qa(), None)
    write("agent_holdout4", build_agent(), None)
