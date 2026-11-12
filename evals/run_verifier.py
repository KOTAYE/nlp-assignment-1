"""Output guard (claim verifier) evaluation on controlled examples: supported vs unsupported main claims
(wrong facts, conclusions from silence, cases delegated to HR). The costly error is passing an unsupported
claim, so recall on 'unsupported' is the key metric."""

from __future__ import annotations

from evals.common import binary_report, load, save
from hr_assistant.components.verifier import verify
from hr_assistant.config import get_settings
from hr_assistant.directory import get_profile
from hr_assistant.retrieval import load_chunks


def main() -> None:
    chunks = {c.id: c for c in load_chunks()}
    today = get_settings().today()
    per_row = []
    for r in load("verifier"):
        v = verify(
            r["question"],
            r["answer"],
            [chunks[i] for i in r["evidence_ids"]],
            get_profile(r["employee_id"]).facts(today),
        )
        per_row.append(
            {
                "id": r["id"],
                "question": r["question"],
                "answer": r["answer"],
                "gold_supported": r["gold_supported"],
                "supported": v.supported,
                "reason": v.reason,
            }
        )
    rep = binary_report([not p["gold_supported"] for p in per_row], [not p["supported"] for p in per_row])
    save(
        "verifier",
        {
            "unsupported_recall (caught)": rep["recall"],
            "unsupported_precision": rep["precision"],
            "f1": rep["f1"],
            "accuracy": rep["accuracy"],
            "false_rejection_rate (supported flagged)": round(
                sum(p["gold_supported"] and not p["supported"] for p in per_row)
                / sum(p["gold_supported"] for p in per_row),
                3,
            ),
            "errors": [
                f"{p['id']} {p['answer']!r}: gold_supported={p['gold_supported']} pred={p['supported']}"
                for p in per_row
                if p["gold_supported"] != p["supported"]
            ],
        },
        per_row,
        "all",
        prompts=("verifier",),
    )


if __name__ == "__main__":
    main()
