"""Input guard evaluation: attack block rate (recall), false-block rate on benign messages, PII masking accuracy."""

from __future__ import annotations

from evals.common import binary_report, load, save, split_arg
from hr_assistant.components.guard import check


def main() -> None:
    args = split_arg("all")
    rows = load("guard", args.split)
    per_row = []
    for r in rows:
        g = check(r["message"])
        per_row.append(
            {
                "id": r["id"],
                "message": r["message"],
                "gold_blocked": r["gold_blocked"],
                "blocked": not g.allowed,
                "gold_masked": r["gold_masked"],
                "masked": list(g.masked),
                "mask_ok": sorted(r["gold_masked"]) == sorted(g.masked) if not r["gold_blocked"] else None,
            }
        )
    rep = binary_report([p["gold_blocked"] for p in per_row], [p["blocked"] for p in per_row])
    benign = [p for p in per_row if not p["gold_blocked"]]
    metrics = {
        "attack_block_rate (recall)": rep["recall"],
        "block_precision": rep["precision"],
        "false_block_rate": round(sum(p["blocked"] for p in benign) / len(benign), 3),
        "f1": rep["f1"],
        "pii_masking_accuracy": round(sum(bool(p["mask_ok"]) for p in benign) / len(benign), 3),
        "confusion": rep["confusion"],
        "missed_attacks": [p["message"] for p in per_row if p["gold_blocked"] and not p["blocked"]],
        "false_blocks": [p["message"] for p in benign if p["blocked"]],
    }
    save("guard", metrics, per_row, args.split)


if __name__ == "__main__":
    main()
