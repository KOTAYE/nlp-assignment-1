"""System-level QA evaluation over the QA set (brief metrics: answer correctness, source support, correct referral
to HR; plus retrieval inside the pipeline to locate the first failing stage).

Variants:
  pipeline (default): full pipeline.handle() per question (router -> collector -> rewriter -> hybrid retrieval ->
            reranker -> answerer -> referral).
  oracle:   answerer only, given the GOLD sections as evidence (upper bound for generation; separates retrieval
            errors from generation errors, RAG lecture: "measure retrieval and generation separately").
"""

from __future__ import annotations

import time

from evals.common import EVAL_DB_DIR, binary_report, load, save, split_arg
from evals.judge import VERDICT_SCORE, judge_correctness, judge_faithfulness
from hr_assistant import db
from hr_assistant.components import answerer
from hr_assistant.config import get_settings
from hr_assistant.directory import get_profile
from hr_assistant.pipeline import Session, handle
from hr_assistant.retrieval import load_chunks

PASS = {"fully_matches", "mostly_right"}


def _mean(xs: list[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def run_pipeline(rows: list[dict]) -> list[dict]:
    today = get_settings().today()
    EVAL_DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = db.reset_db(EVAL_DB_DIR / "qa.db")
    out = []
    for r in rows:
        profile = get_profile(r["employee_id"])
        session = Session(profile, conn, today)
        t0 = time.perf_counter()
        reply = handle(session, r["question"])
        latency = time.perf_counter() - t0
        evidence_ids = [e["id"] for e in reply.evidence]
        row = {
            "id": r["id"],
            "question": r["question"],
            "employee_id": r["employee_id"],
            "gold_outcome": r["gold_outcome"],
            "route": reply.route,
            "reply": reply.text,
            "citations": reply.citations,
            "gold_section_ids": r["gold_section_ids"],
            "evidence_ids": evidence_ids,
            "context_hit": bool(set(r["gold_section_ids"]) & set(evidence_ids))
            if r["gold_section_ids"]
            else None,
            "ticket_id": reply.ticket_id,
            "ticket_category": reply.details.get("category"),
            "gold_category": r["gold_category"],
            "tokens": reply.trace.tokens,
            "cost_usd": reply.trace.cost_usd,
            "latency_s": round(latency, 2),
        }
        if r["gold_outcome"] == "answer" and reply.route == "answer":
            v = judge_correctness(r["question"], r["gold_answer"], reply.text)
            ev_text = [e["text"] for e in reply.evidence]
            faith, claims = judge_faithfulness(reply.text, ev_text, str(profile.facts(today)))
            row.update(
                {
                    "verdict": v.verdict,
                    "verdict_reason": v.reason,
                    "faithfulness": faith,
                    "unsupported_claims": [c.claim for c in claims if not c.supported],
                    "citation_hit": bool(set(reply.citations) & set(r["gold_section_ids"])),
                }
            )
        out.append(row)
    return out


def run_oracle(rows: list[dict]) -> list[dict]:
    today = get_settings().today()
    chunks = {c.id: c for c in load_chunks()}
    out = []
    for r in rows:
        if r["gold_outcome"] != "answer":
            continue
        profile = get_profile(r["employee_id"])
        facts = profile.facts(today)
        evidence = [chunks[s] for s in r["gold_section_ids"]]
        ans = answerer.answer(r["question"], [], {}, facts, evidence)
        row = {
            "id": r["id"],
            "question": r["question"],
            "reply": ans.answer,
            "sufficient": ans.sufficient,
            "citations": ans.citations,
            "gold_section_ids": r["gold_section_ids"],
        }
        if ans.sufficient:
            v = judge_correctness(r["question"], r["gold_answer"], ans.answer)
            faith, claims = judge_faithfulness(ans.answer, [c.text for c in evidence], str(facts))
            row.update(
                {
                    "verdict": v.verdict,
                    "verdict_reason": v.reason,
                    "faithfulness": faith,
                    "unsupported_claims": [c.claim for c in claims if not c.supported],
                }
            )
        out.append(row)
    return out


def failing_stage(p: dict) -> str | None:
    """First stage that lost the answer (RAG lecture: find the first stage that loses required evidence)."""
    if p["gold_outcome"] == "hr_referral":
        if p["route"] == "hr_referral":
            return None
        return (
            "router/answerer (answered instead of referring)"
            if p["route"] == "answer"
            else f"route={p['route']}"
        )
    if p["route"] == "clarification":
        return "collector (unnecessary clarification)"
    if p["route"] != "answer":
        if p["route"] == "hr_referral" and not p["evidence_ids"]:
            return "router (referred directly)"
        if p["route"] == "hr_referral" and p.get("context_hit") is False:
            return "retrieval (gold section not in top-5) -> false referral"
        return f"{'answerer (abstained)' if p['route'] == 'hr_referral' else 'router'} -> {p['route']}"
    if p.get("verdict") in PASS:
        return None
    return "retrieval" if not p.get("context_hit") else "generation"


def main() -> None:
    args = split_arg("dev")
    rows = load("qa", args.split)
    if args.variant == "oracle":
        per_row = run_oracle(rows)
        answered = [p for p in per_row if p["sufficient"]]
        metrics = {
            "answer_rate_with_gold_context": round(len(answered) / len(per_row), 3),
            "correctness_mean_score": _mean([VERDICT_SCORE[p["verdict"]] for p in answered]),
            "correctness_pass_rate (of all)": round(
                sum(p.get("verdict") in PASS for p in per_row) / len(per_row), 3
            ),
            "faithfulness_mean": _mean([p["faithfulness"] for p in answered]),
            "verdicts": {v: sum(p.get("verdict") == v for p in per_row) for v in VERDICT_SCORE},
        }
        save(
            "qa",
            metrics,
            per_row,
            args.split,
            variant="oracle",
            prompts=("answerer", "judge_correctness", "judge_faithfulness"),
        )
        return

    per_row = run_pipeline(rows)
    for p in per_row:
        p["failing_stage"] = failing_stage(p)
    should_refer = [p["gold_outcome"] == "hr_referral" for p in per_row]
    referred = [p["route"] == "hr_referral" for p in per_row]
    ref = binary_report(should_refer, referred)
    ans_rows = [p for p in per_row if p["gold_outcome"] == "answer"]
    answered = [p for p in ans_rows if p["route"] == "answer"]
    correct_refs = [p for p in per_row if p["gold_outcome"] == "hr_referral" and p["route"] == "hr_referral"]
    metrics = {
        # answer correctness
        "answer_rate (answerable questions answered)": round(len(answered) / len(ans_rows), 3),
        "correctness_pass_rate (fully/mostly right, of answerable)": round(
            sum(p.get("verdict") in PASS for p in ans_rows) / len(ans_rows), 3
        ),
        "correctness_mean_score (answered)": _mean([VERDICT_SCORE[p["verdict"]] for p in answered]),
        "contradiction_rate (answered)": round(
            sum(p.get("verdict") == "contradicts" for p in answered) / max(1, len(answered)), 3
        ),
        # source support
        "faithfulness_mean (answered)": _mean([p["faithfulness"] for p in answered]),
        "citation_hit_rate (answered)": _mean([float(p["citation_hit"]) for p in answered]),
        "answers_with_citation": _mean([float(bool(p["citations"])) for p in answered]),
        # retrieval inside the pipeline
        "context_recall@5 (gold section in evidence)": _mean(
            [float(p["context_hit"]) for p in ans_rows if p["context_hit"] is not None]
        ),
        # referral to HR
        "referral_precision": ref["precision"],
        "referral_recall": ref["recall"],
        "referral_f1": ref["f1"],
        "referral_confusion": ref["confusion"],
        "ticket_category_accuracy": round(
            sum(p["ticket_category"] == p["gold_category"] for p in correct_refs) / len(correct_refs), 3
        )
        if correct_refs
        else None,
        # efficiency
        "avg_tokens_per_question": round(sum(p["tokens"] for p in per_row) / len(per_row)),
        "avg_cost_usd_per_question": round(sum(p["cost_usd"] or 0 for p in per_row) / len(per_row), 5),
        "avg_latency_s": round(sum(p["latency_s"] for p in per_row) / len(per_row), 2),
        "failing_stages": {
            s: sum(p["failing_stage"] == s for p in per_row)
            for s in {p["failing_stage"] for p in per_row}
            if s
        },
        "errors": [
            f"{p['id']} {p['question']!r}: route={p['route']} verdict={p.get('verdict')} stage={p['failing_stage']}"
            for p in per_row
            if p["failing_stage"]
        ],
    }
    save(
        "qa",
        metrics,
        per_row,
        args.split,
        variant="pipeline",
        prompts=(
            "router",
            "collector",
            "rewriter",
            "answerer",
            "referral",
            "judge_correctness",
            "judge_faithfulness",
        ),
    )


if __name__ == "__main__":
    main()
