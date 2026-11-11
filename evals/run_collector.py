"""Information collector evaluation (brief: "report metrics for information collection").

- required situational facts: micro precision / recall / F1 (facts in gold_optional are ignored)
- value extraction accuracy for facts stated in the conversation
- clarification decision ("asked iff needed"): precision / recall / F1 / accuracy
"""

from __future__ import annotations

import re

from evals.common import binary_report, load, prf, save, split_arg
from hr_assistant.components.collector import collect
from hr_assistant.config import get_settings
from hr_assistant.directory import get_profile
from hr_assistant.schemas import SITUATIONAL_FACTS


def _value_ok(fact: str, gold: str, pred: str | None) -> bool:
    if pred is None:
        return False
    g, p = gold.lower(), pred.lower()
    if fact in ("illness_duration_days", "days_abroad"):
        nums = [int(x) for x in re.findall(r"\d+", p)]
        weeks = "week" in p
        return int(g) in nums or (weeks and any(n * 7 == int(g) for n in nums))
    if fact == "has_medical_certificate":
        return p in ("yes", "true", "y") or "yes" in p or "has" in p
    return g in p or p in g


def main() -> None:
    args = split_arg("dev")
    rows = load("collector", args.split)
    today = get_settings().today()
    tp = fp = fn = 0
    values_total = values_ok = 0
    per_row = []
    for r in rows:
        prof = get_profile(r["employee_id"]).facts(today)
        col = collect(r["question"], r["history"], prof)
        pred = {f for f in col.required if f in SITUATIONAL_FACTS} - set(r["gold_optional"])
        gold = set(r["gold_required"])
        tp += len(pred & gold)
        fp += len(pred - gold)
        fn += len(gold - pred)
        vals = {}
        for fact, gval in r["gold_values"].items():
            ok = _value_ok(fact, gval, col.facts.get(fact))
            values_total += 1
            values_ok += ok
            vals[fact] = {"gold": gval, "pred": col.facts.get(fact), "ok": ok}
        per_row.append(
            {
                "id": r["id"],
                "question": r["question"],
                "gold_required": sorted(gold),
                "pred_required": sorted(pred),
                "values": vals,
                "gold_ask": r["gold_needs_clarification"],
                "pred_ask": col.needs_clarification,
                "clarifying_question": col.clarifying_question,
            }
        )
    ask = binary_report([p["gold_ask"] for p in per_row], [p["pred_ask"] for p in per_row])
    metrics = {
        "facts_precision": prf(tp, fp, fn)["precision"],
        "facts_recall": prf(tp, fp, fn)["recall"],
        "facts_f1": prf(tp, fp, fn)["f1"],
        "value_extraction_accuracy": round(values_ok / values_total, 3) if values_total else None,
        "clarification_precision": ask["precision"],
        "clarification_recall": ask["recall"],
        "clarification_f1": ask["f1"],
        "clarification_accuracy": ask["accuracy"],
        "clarification_confusion": ask["confusion"],
        "errors": [
            f"{p['question']!r}: gold={p['gold_required']} pred={p['pred_required']} ask {p['gold_ask']}->{p['pred_ask']}"
            for p in per_row
            if p["gold_ask"] != p["pred_ask"] or set(p["gold_required"]) != set(p["pred_required"])
        ],
    }
    save("collector", metrics, per_row, args.split, prompts=("collector",))


if __name__ == "__main__":
    main()
