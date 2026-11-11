"""Leave agent evaluation: evaluate the trajectory, not just the answer (AI Agents lecture).

Per scenario (fresh seeded DB each run): outcome = final DB state matches (new requests: type + working days +
status; status changes), process = required tools called, safety = no forbidden tool / no unexpected write,
communication = reply contains the expected information. Efficiency: steps, tokens, cost. Consistency: pass^k.
"""

from __future__ import annotations

import datetime as dt
import re

from evals.common import EVAL_DB_DIR, load, save, split_arg
from hr_assistant import db
from hr_assistant.components import leave_agent
from hr_assistant.config import get_settings
from hr_assistant.directory import get_profile
from hr_assistant.llm import start_trace
from hr_assistant.rules import working_days
from hr_assistant.tools import ToolContext

SEED_REQUESTS = len(db.LEAVE_HISTORY)


def run_scenario(s: dict) -> dict:
    today = get_settings().today()
    EVAL_DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = db.reset_db(EVAL_DB_DIR / "agent.db")
    before = {r["id"]: r["status"] for r in db.leave_rows(conn)}
    ctx = ToolContext(conn, get_profile(s["employee_id"]), today)
    trace = start_trace()
    history: list[dict] = []
    calls: list[dict] = []
    stop_reasons, steps, reply = [], 0, ""
    for turn in s["turns"]:
        res = leave_agent.run(turn, history, ctx)
        history += [{"role": "user", "content": turn}, {"role": "assistant", "content": res.reply}]
        calls += res.tool_calls
        stop_reasons.append(res.stop_reason)
        steps += res.steps
        reply = res.reply
    rows = db.leave_rows(conn)
    new = [r for r in rows if r["id"] > SEED_REQUESTS]
    changes = {
        str(r["id"]): r["status"] for r in rows if r["id"] in before and before[r["id"]] != r["status"]
    }
    conn.close()

    exp = s["expect"]
    # outcome: union of working days per expected status/type must match the newly created requests
    new_days = sorted(
        d.isoformat()
        for r in new
        for d in working_days(dt.date.fromisoformat(r["start_date"]), dt.date.fromisoformat(r["end_date"]))
    )
    exp_days = sorted(d for n in exp["new"] for d in n["days"])
    new_ok = (
        (
            new_days == exp_days
            and all(
                r["status"] == n["status"] and r["leave_type"] == n["type"] for r in new for n in exp["new"]
            )
        )
        if exp["new"]
        else not new
    )
    if (
        s["label"] == "submit_or_refuse" and not new
    ):  # refusing a contractor without submitting is also correct
        new_ok = "contractor" in reply.lower()
    changes_ok = changes == {k: v for k, v in exp["status_changes"].items()}
    names = [c["name"] for c in calls]
    process_ok = all(t in names for t in exp["tools_required"])
    safety_ok = not any(t in names for t in exp["tools_forbidden"])
    text = reply.lower()
    comm_ok = (not exp["reply_any"] or any(x.lower() in text for x in exp["reply_any"])) and (
        not exp.get("reply_regex") or re.search(exp["reply_regex"], text) is not None
    )
    return {
        "id": s["id"],
        "label": s["label"],
        "turns": s["turns"],
        "reply": reply,
        "tool_calls": names,
        "new_requests": [{k: r[k] for k in ("leave_type", "start_date", "end_date", "status")} for r in new],
        "status_changes": changes,
        "outcome_ok": new_ok and changes_ok,
        "process_ok": process_ok,
        "safety_ok": safety_ok,
        "communication_ok": comm_ok,
        "success": new_ok and changes_ok and process_ok and safety_ok and comm_ok,
        "steps": steps,
        "stop_reasons": stop_reasons,
        "tokens": trace.tokens,
        "cost_usd": trace.cost_usd,
    }


def main() -> None:
    args = split_arg("dev")
    scenarios = load("leave_agent", args.split)
    runs: list[list[dict]] = [[run_scenario(s) for s in scenarios] for _ in range(args.k)]
    first = runs[0]
    n = len(first)

    def rate(key: str) -> float:
        return round(sum(r[key] for r in first) / n, 3)

    metrics = {
        "success_rate (all checks, run 1)": rate("success"),
        "outcome_db_state_accuracy": rate("outcome_ok"),
        "process_required_tools": rate("process_ok"),
        "safety_no_forbidden_tools": rate("safety_ok"),
        "communication_reply_check": rate("communication_ok"),
        f"pass^{args.k} (all {args.k} runs succeed)": round(
            sum(all(run[i]["success"] for run in runs) for i in range(n)) / n, 3
        ),
        "pass@1 averaged over runs": round(sum(r["success"] for run in runs for r in run) / (n * args.k), 3),
        "avg_steps": round(sum(r["steps"] for r in first) / n, 2),
        "avg_tokens_per_task": round(sum(r["tokens"] for r in first) / n),
        "avg_cost_usd_per_task": round(sum(r["cost_usd"] or 0 for r in first) / n, 5),
        "stop_reasons": {sr: sum(sr in r["stop_reasons"] for r in first) for sr in ("answered", "max_steps")},
        "failures": [
            f"{r['id']} {r['label']} {r['turns'][-1]!r}: outcome={r['outcome_ok']} process={r['process_ok']} "
            f"safety={r['safety_ok']} comm={r['communication_ok']} new={r['new_requests']} reply={r['reply'][:120]!r}"
            for run in runs
            for r in run
            if not r["success"]
        ],
    }
    save(
        "leave_agent",
        metrics,
        [r for run in runs for r in run],
        args.split,
        variant=f"k{args.k}",
        prompts=("leave_agent",),
    )


if __name__ == "__main__":
    main()
