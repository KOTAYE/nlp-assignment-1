"""Shared helpers for eval scripts: datasets, results files, metrics."""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any

os.environ.setdefault("HR_TODAY", "2026-11-12")  # reproducible business date for all evals

from hr_assistant.config import get_settings
from hr_assistant.llm import load_prompt

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "evals" / "datasets"
RESULTS = ROOT / "evals" / "results"
EVAL_DB_DIR = ROOT / "logs" / "eval_dbs"


HOLDOUT_FILES = {"qa": "qa_holdout", "leave_agent": "agent_holdout"}
HOLDOUT2_FILES = {"qa": "qa_holdout2", "leave_agent": "agent_holdout2"}
HOLDOUT3_FILES = {"qa": "qa_holdout3", "leave_agent": "agent_holdout3"}
HOLDOUT4_FILES = {"qa": "qa_holdout4", "leave_agent": "agent_holdout4"}


def load(name: str, split: str | None = None) -> list[dict]:
    if split == "holdout":
        name = HOLDOUT_FILES[name]
    elif split == "holdout2":
        name = HOLDOUT2_FILES[name]
    elif split == "holdout3":
        name = HOLDOUT3_FILES[name]
    elif split == "holdout4":
        name = HOLDOUT4_FILES[name]
    rows = [
        json.loads(line) for line in (DATASETS / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    if split and split != "all":
        rows = [r for r in rows if r.get("split") == split]
    return rows


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def prompt_versions(*names: str) -> dict[str, str]:
    return {n: load_prompt(n)[0] for n in names}


def save(
    component: str,
    metrics: dict,
    per_row: list[dict],
    split: str,
    variant: str | None = None,
    prompts: tuple[str, ...] = (),
    extra: dict | None = None,
) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    s = get_settings()
    out = {
        "component": component,
        "variant": variant,
        "split": split,
        "n": len(per_row),
        "metrics": metrics,
        "model": s.llm_model,
        "judge_model": s.judge_model,
        "prompt_versions": prompt_versions(*prompts),
        "business_date": os.environ.get("HR_TODAY"),
        "date": dt.datetime.now().isoformat(timespec="seconds"),
        "git_commit": git_commit(),
        **(extra or {}),
        "per_row": per_row,
    }
    name = f"{component}__{variant}__{split}" if variant else f"{component}__{split}"
    path = RESULTS / f"{name}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n== {name}  (n={len(per_row)})")
    for k, v in metrics.items():
        if not isinstance(v, (dict, list)):
            print(f"  {k:32s} {v}")
    print(f"  -> {path.relative_to(ROOT)}")
    return path


# ---------------------------------------------------------------- metrics


def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)}


def binary_report(gold: list[bool], pred: list[bool]) -> dict[str, Any]:
    tp = sum(g and p for g, p in zip(gold, pred, strict=True))
    fp = sum((not g) and p for g, p in zip(gold, pred, strict=True))
    fn = sum(g and (not p) for g, p in zip(gold, pred, strict=True))
    tn = sum((not g) and (not p) for g, p in zip(gold, pred, strict=True))
    denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = (tp * tn - fp * fn) / denom if denom else 0.0
    return {
        **prf(tp, fp, fn),
        "accuracy": round((tp + tn) / len(gold), 3) if gold else 0.0,
        "mcc": round(mcc, 3),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


def multiclass_report(gold: list[str], pred: list[str], labels: list[str]) -> dict[str, Any]:
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        matthews_corrcoef,
        precision_recall_fscore_support,
    )

    p, r, f, s = precision_recall_fscore_support(gold, pred, labels=labels, zero_division=0)
    return {
        "accuracy": round(accuracy_score(gold, pred), 3),
        "macro_f1": round(f1_score(gold, pred, labels=labels, average="macro", zero_division=0), 3),
        "mcc": round(matthews_corrcoef(gold, pred), 3),
        "per_class": {
            lab: {
                "precision": round(p[i], 3),
                "recall": round(r[i], 3),
                "f1": round(f[i], 3),
                "support": int(s[i]),
            }
            for i, lab in enumerate(labels)
        },
        "confusion_matrix": {
            "labels": labels,
            "rows_gold_cols_pred": confusion_matrix(gold, pred, labels=labels).tolist(),
        },
    }


def ranking_metrics(ranked: list[str], gold: set[str], ks: tuple[int, ...] = (1, 3, 5)) -> dict[str, float]:
    out: dict[str, float] = {}
    for k in ks:
        top = ranked[:k]
        out[f"hit@{k}"] = float(any(x in gold for x in top))
        out[f"recall@{k}"] = len(gold & set(top)) / len(gold)
    rr = 0.0
    for i, x in enumerate(ranked[:10], 1):
        if x in gold:
            rr = 1 / i
            break
    out["mrr@10"] = rr
    dcg = sum(1 / math.log2(i + 1) for i, x in enumerate(ranked[:5], 1) if x in gold)
    idcg = sum(1 / math.log2(i + 1) for i in range(1, min(len(gold), 5) + 1))
    out["ndcg@5"] = dcg / idcg if idcg else 0.0
    return out


def mean_dicts(rows: list[dict[str, float]]) -> dict[str, float]:
    if not rows:
        return {}
    return {k: round(sum(r[k] for r in rows) / len(rows), 3) for k in rows[0]}


def split_arg(default: str = "dev"):
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--split",
        default=default,
        choices=["dev", "test", "all", "holdout", "holdout2", "holdout3", "holdout4"],
    )
    ap.add_argument("--variant", default=None)
    ap.add_argument("--k", type=int, default=1, help="repetitions for pass^k (agent evals)")
    return ap.parse_args()
