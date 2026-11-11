"""Router evaluation: LLM router vs classical baseline (TF-IDF + LogReg trained on dev).

Metrics: accuracy, macro-F1, MCC, per-class P/R/F1, confusion matrix. Key business metric: recall of hr_referral.
"""

from __future__ import annotations

from evals.common import load, multiclass_report, save, split_arg
from hr_assistant.components.router import TfidfLogRegRouter, route
from hr_assistant.schemas import INTENTS


def main() -> None:
    args = split_arg("dev")
    rows = load("router", args.split)
    labels = list(INTENTS)

    # LLM router
    per_row = []
    for r in rows:
        res = route(r["message"], r["history"])
        per_row.append(
            {
                "id": r["id"],
                "message": r["message"],
                "gold": r["gold_intent"],
                "pred": res.intent,
                "confidence": res.confidence,
                "reason": res.reason,
            }
        )
    rep = multiclass_report([p["gold"] for p in per_row], [p["pred"] for p in per_row], labels)
    rep["hr_referral_recall"] = rep["per_class"]["hr_referral"]["recall"]
    rep["errors"] = [
        f"{p['message']!r}: {p['gold']} -> {p['pred']}" for p in per_row if p["gold"] != p["pred"]
    ]
    save("router", rep, per_row, args.split, variant="llm", prompts=("router",))

    # Classical baseline: trained on dev, so it is only meaningful on test
    if args.split == "test":
        train = load("router", "dev")
        base = TfidfLogRegRouter().fit([r["message"] for r in train], [r["gold_intent"] for r in train])
        preds = base.predict([r["message"] for r in rows])
        b_rows = [
            {"id": r["id"], "message": r["message"], "gold": r["gold_intent"], "pred": p}
            for r, p in zip(rows, preds, strict=True)
        ]
        b = multiclass_report([p["gold"] for p in b_rows], [p["pred"] for p in b_rows], labels)
        b["hr_referral_recall"] = b["per_class"]["hr_referral"]["recall"]
        save("router", b, b_rows, args.split, variant="tfidf_logreg_baseline")


if __name__ == "__main__":
    main()
