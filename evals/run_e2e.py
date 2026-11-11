"""End-to-end (extrinsic) evaluation: scripted multi-turn conversations through pipeline.handle().

Automatic checks per scenario: route sequence, citations, reply content, HR ticket creation, DB state.
Also checks tracer coverage: every LLM call in every turn is logged with tokens and latency, every tool call is
logged with its result.
"""

from __future__ import annotations

import time

from evals.common import EVAL_DB_DIR, load, save, split_arg
from hr_assistant import db
from hr_assistant.config import get_settings
from hr_assistant.directory import get_profile
from hr_assistant.pipeline import Session, handle

SEED_REQUESTS = len(db.LEAVE_HISTORY)


def run_scenario(s: dict) -> dict:
    today = get_settings().today()
    EVAL_DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = db.reset_db(EVAL_DB_DIR / "e2e.db")
    before = {r["id"]: r["status"] for r in db.leave_rows(conn)}
    session = Session(get_profile(s["employee_id"]), conn, today)
    routes, replies, cost, tokens, trace_ok = [], [], 0.0, 0, True
    last = None
    t0 = time.perf_counter()
    for turn in s["turns"]:
        last = handle(session, turn)
        routes.append(last.route)
        replies.append(last.text)
        cost += last.trace.cost_usd
        tokens += last.trace.tokens
        llm = last.trace.llm_calls
        tools = [e for e in last.trace.events if e["kind"] == "tool"]
        trace_ok &= all(e.get("tokens_in", 0) > 0 and e.get("latency_ms") is not None for e in llm)
        trace_ok &= all("result" in e for e in tools)
    latency = time.perf_counter() - t0
    rows = db.leave_rows(conn)
    new = [r for r in rows if r["id"] > SEED_REQUESTS]
    changes = {
        str(r["id"]): r["status"] for r in rows if r["id"] in before and before[r["id"]] != r["status"]
    }
    tickets = db.ticket_rows(conn)
    conn.close()

    c = s["checks"]
    results: dict[str, bool] = {}
    if "final_route" in c:
        results["route"] = routes[-1] == c["final_route"]
    if "routes" in c:
        results["route"] = routes == c["routes"]
    if "cite_any" in c:
        results["citation"] = bool(set(last.citations) & set(c["cite_any"]))
    if "reply_any" in c:
        results["reply"] = any(x.lower() in last.text.lower() for x in c["reply_any"])
    if "ticket" in c:
        results["ticket"] = bool(tickets) == c["ticket"]
    if "db_new" in c:
        results["db"] = [(r["leave_type"], r["status"]) for r in new] == [
            (n["type"], n["status"]) for n in c["db_new"]
        ]
    if "db_changes" in c:
        results["db"] = results.get("db", True) and changes == c["db_changes"]
    return {
        "id": s["id"],
        "label": s["label"],
        "turns": s["turns"],
        "routes": routes,
        "replies": replies,
        "citations": last.citations,
        "checks": results,
        "success": all(results.values()),
        "trace_complete": trace_ok,
        "cost_usd": round(cost, 6),
        "tokens": tokens,
        "latency_s": round(latency, 2),
    }


def main() -> None:
    args = split_arg("dev")
    per_row = [run_scenario(s) for s in load("e2e", args.split)]
    n = len(per_row)
    check_names = sorted({k for r in per_row for k in r["checks"]})
    metrics = {
        "scenario_success_rate": round(sum(r["success"] for r in per_row) / n, 3),
        "per_check_pass_rate": {
            k: round(
                sum(r["checks"][k] for r in per_row if k in r["checks"])
                / sum(k in r["checks"] for r in per_row),
                3,
            )
            for k in check_names
        },
        "success_by_label": {
            lab: f"{sum(r['success'] for r in per_row if r['label'] == lab)}/{sum(r['label'] == lab for r in per_row)}"
            for lab in sorted({r["label"] for r in per_row})
        },
        "tracer_coverage": round(sum(r["trace_complete"] for r in per_row) / n, 3),
        "avg_cost_usd_per_conversation": round(sum(r["cost_usd"] for r in per_row) / n, 5),
        "avg_latency_s_per_conversation": round(sum(r["latency_s"] for r in per_row) / n, 2),
        "failures": [
            f"{r['id']} {r['label']} {r['turns']}: routes={r['routes']} checks={r['checks']} last={r['replies'][-1][:150]!r}"
            for r in per_row
            if not r["success"]
        ],
    }
    save("e2e", metrics, per_row, args.split)


if __name__ == "__main__":
    main()
