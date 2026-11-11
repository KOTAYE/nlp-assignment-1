"""Tools: typed contracts the LLM can call, and their implementations.

This is the ONLY runtime path to the leave database (assignment brief: "access it via LLM only").
Design rules (AI Agents lecture): the description says when to use a tool, enums for closed sets, small return
objects, instructive errors (`error`, `message`, `hint`, `retryable`), least privilege (HR-only tools are not
even offered to employees), and the acting employee is injected by the harness, never taken from model arguments.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
import time
from dataclasses import dataclass

from . import db
from .directory import Profile
from .llm import trace_event
from .rules import (
    SICK_PAID_DAYS_PER_YEAR,
    UNPAID_DAYS_PER_YEAR,
    InvalidRequest,
    LeaveRequest,
    LeaveType,
    SpecialEvent,
    Status,
    annual_balance,
    decide,
    sick_days_used,
    unpaid_days_used,
)

TICKET_CATEGORIES = [
    "compensation",
    "career",
    "leave_and_absence",
    "benefits",
    "workplace_conduct",
    "relocation_and_abroad",
    "documents_and_data",
    "other",
]


@dataclass
class ToolContext:
    conn: sqlite3.Connection
    profile: Profile
    today: dt.date

    @property
    def employee(self):
        return self.profile.employee

    @property
    def is_hr(self) -> bool:
        return self.employee.role == "hr"

    def now(self) -> dt.datetime:
        return dt.datetime.combine(self.today, dt.datetime.now().time())


def _fn(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


DATE = {"type": "string", "format": "date", "description": "ISO date YYYY-MM-DD"}

EMPLOYEE_TOOLS = [
    _fn(
        "get_leave_balance",
        "Get the current employee's leave balances for a year: annual leave (entitlement, carried-over days, "
        "used/reserved, remaining), sick days used, unpaid days used. Use for any question about "
        "'how many days do I have'.",
        {"year": {"type": "integer", "description": "Calendar year; default is the current year."}},
        [],
    ),
    _fn(
        "list_my_leave_requests",
        "List the current employee's leave requests with their status. Use to check the status of a request "
        "or to find a request ID before cancelling.",
        {
            "status": {
                "type": "string",
                "enum": ["approved", "declined", "pending_hr", "cancelled", "any"],
                "default": "any",
            }
        },
        [],
    ),
    _fn(
        "submit_leave_request",
        "Submit a leave request for the current employee. The rule engine decides immediately: approved, "
        "declined or pending_hr (HR review). Call only when the leave type and both dates are known; for "
        "special leave also the event and event date. Do not guess dates: ask the employee.",
        {
            "leave_type": {"type": "string", "enum": [t.value for t in LeaveType]},
            "start_date": DATE,
            "end_date": DATE,
            "event": {
                "type": "string",
                "enum": [e.value for e in SpecialEvent],
                "description": "Only for special leave.",
            },
            "event_date": {**DATE, "description": "Only for special leave: date of the event."},
            "comment": {"type": "string", "description": "Optional note from the employee."},
        },
        ["leave_type", "start_date", "end_date"],
    ),
    _fn(
        "cancel_leave_request",
        "Cancel one of the current employee's own requests that is approved or pending and has not started yet.",
        {"request_id": {"type": "integer"}},
        ["request_id"],
    ),
]

HR_TOOLS = [
    _fn(
        "list_pending_requests",
        "HR only: list all leave requests waiting for HR review (status pending_hr), with the rule engine's reason.",
        {},
        [],
    ),
    _fn(
        "decide_leave_request",
        "HR only: approve or decline a pending request. This is irreversible: set confirmed=true only after the "
        "HR user has explicitly confirmed this exact decision in the conversation.",
        {
            "request_id": {"type": "integer"},
            "decision": {"type": "string", "enum": ["approved", "declined"]},
            "reason": {"type": "string", "description": "Short reason shown to the employee."},
            "confirmed": {"type": "boolean"},
        },
        ["request_id", "decision", "reason", "confirmed"],
    ),
]

REFERRAL_TOOLS = [
    _fn(
        "create_hr_ticket",
        "Create a ticket for the HR team when the company policies do not answer the employee's question, "
        "or the topic must be handled by a person (harassment, salary, disputes, individual cases).",
        {
            "category": {"type": "string", "enum": TICKET_CATEGORIES},
            "summary": {
                "type": "string",
                "description": "One or two sentences: what the employee needs, with key facts.",
            },
            "original_question": {"type": "string"},
        },
        ["category", "summary", "original_question"],
    ),
]


def tools_for(ctx: ToolContext) -> list[dict]:
    """Least privilege: HR tools are only offered to HR users."""
    return EMPLOYEE_TOOLS + (HR_TOOLS if ctx.is_hr else [])


# ---------------------------------------------------------------- implementations


def _err(error: str, message: str, hint: str = "", retryable: bool = True) -> dict:
    return {"error": error, "message": message, "hint": hint, "retryable": retryable}


def _request_view(r: dict) -> dict:
    keys = (
        "id",
        "leave_type",
        "event",
        "start_date",
        "end_date",
        "working_days",
        "status",
        "decision_message",
    )
    out = {k: r.get(k) for k in keys if r.get(k) is not None}
    if "employee_name" in r:
        out["employee"] = f"{r['employee_name']} ({r['employee_id']}, {r['team']})"
    return out


def _get_leave_balance(ctx: ToolContext, year: int | None = None) -> dict:
    year = year or ctx.today.year
    own = db.leave_records(ctx.conn, ctx.employee.id)
    if ctx.employee.is_contractor:
        return {
            "year": year,
            "note": "Contractors are not covered by the leave policies (leave-policy §1.2).",
        }
    b = annual_balance(ctx.employee, own, year, ctx.today)
    return {
        "year": year,
        "annual": {
            "entitlement": b.entitlement,
            "carried_over": b.carried_over,
            "carry_over_valid_until": b.carry_over_valid_until.isoformat(),
            "used_or_reserved": b.used_or_reserved,
            "remaining": b.remaining_total,
        },
        "sick_days_used": sick_days_used(own, year),
        "sick_paid_days_per_year": SICK_PAID_DAYS_PER_YEAR,
        "unpaid_days_used": unpaid_days_used(own, year),
        "unpaid_days_per_year": UNPAID_DAYS_PER_YEAR,
    }


def _list_my_leave_requests(ctx: ToolContext, status: str = "any") -> dict:
    where, params = "lr.employee_id = ?", (ctx.employee.id,)
    if status != "any":
        where, params = where + " AND lr.status = ?", (*params, status)
    rows = db.leave_rows(ctx.conn, where, params)
    return {"requests": [_request_view(r) for r in rows][-20:]}


def _parse_date(value: str, field: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError) as e:
        raise InvalidRequest(
            "invalid_date",
            f"`{field}` must be an ISO date YYYY-MM-DD (got {value!r}).",
            "Ask the employee for the exact date.",
        ) from e


def _submit_leave_request(
    ctx: ToolContext,
    leave_type: str,
    start_date: str,
    end_date: str,
    event: str | None = None,
    event_date: str | None = None,
    comment: str | None = None,
) -> dict:
    req = LeaveRequest(
        LeaveType(leave_type),
        _parse_date(start_date, "start_date"),
        _parse_date(end_date, "end_date"),
        SpecialEvent(event) if event else None,
        _parse_date(event_date, "event_date") if event_date else None,
    )
    own = db.leave_records(ctx.conn, ctx.employee.id)
    team = db.team_records(ctx.conn, ctx.employee.team, ctx.employee.id)
    decision = decide(req, ctx.employee, own, team, ctx.today)
    request_id = db.insert_leave(
        ctx.conn,
        ctx.employee.id,
        req.leave_type.value,
        req.start_date,
        req.end_date,
        decision.working_days,
        decision.status.value,
        decision.code,
        decision.message,
        comment,
        req.event.value if req.event else None,
        req.event_date,
        ctx.now(),
    )
    return {
        "request_id": request_id,
        "status": decision.status.value,
        "working_days": decision.working_days,
        "reason_code": decision.code,
        "explanation": decision.message,
    }


def _cancel_leave_request(ctx: ToolContext, request_id: int) -> dict:
    rows = db.leave_rows(ctx.conn, "lr.id = ?", (request_id,))
    if not rows or rows[0]["employee_id"] != ctx.employee.id:
        return _err(
            "not_found", f"You have no request #{request_id}.", "Call list_my_leave_requests to find the ID."
        )
    r = rows[0]
    if r["status"] not in (Status.APPROVED, Status.PENDING_HR):
        return _err(
            "not_cancellable",
            f"Request #{request_id} is {r['status']} and cannot be cancelled.",
            retryable=False,
        )
    if dt.date.fromisoformat(r["start_date"]) <= ctx.today:
        return _err(
            "already_started",
            "Leave that has already started cannot be cancelled here (leave-policy §3.5).",
            "Tell the employee to contact HR.",
            retryable=False,
        )
    db.update_leave_status(
        ctx.conn, request_id, Status.CANCELLED.value, "Cancelled by the employee.", ctx.employee.id, ctx.now()
    )
    return {"request_id": request_id, "status": "cancelled", "days_returned": r["working_days"]}


def _list_pending_requests(ctx: ToolContext) -> dict:
    rows = db.leave_rows(ctx.conn, "lr.status = 'pending_hr'")
    return {"pending": [_request_view(r) for r in rows]}


def _decide_leave_request(
    ctx: ToolContext, request_id: int, decision: str, reason: str, confirmed: bool
) -> dict:
    if not confirmed:
        return _err(
            "confirmation_required",
            "HR decisions are irreversible and need explicit confirmation.",
            f"Ask the HR user: 'Confirm: {decision} request #{request_id}?' and call again with confirmed=true.",
        )
    rows = db.leave_rows(ctx.conn, "lr.id = ?", (request_id,))
    if not rows:
        return _err("not_found", f"No request #{request_id}.", "Call list_pending_requests.")
    if rows[0]["status"] != Status.PENDING_HR:
        return _err(
            "not_pending", f"Request #{request_id} is {rows[0]['status']}, not pending.", retryable=False
        )
    db.update_leave_status(
        ctx.conn, request_id, decision, f"HR decision: {reason}", ctx.employee.id, ctx.now()
    )
    return {"request_id": request_id, "status": decision, "employee": rows[0]["employee_name"]}


def _create_hr_ticket(ctx: ToolContext, category: str, summary: str, original_question: str) -> dict:
    if category not in TICKET_CATEGORIES:
        return _err("invalid_category", f"Unknown category {category!r}.", f"Use one of {TICKET_CATEGORIES}.")
    ticket_id = db.insert_ticket(ctx.conn, ctx.employee.id, category, summary, original_question, ctx.now())
    return {"ticket_id": ticket_id, "status": "open", "sla": "HR replies within 2 working days"}


_IMPL = {
    "get_leave_balance": _get_leave_balance,
    "list_my_leave_requests": _list_my_leave_requests,
    "submit_leave_request": _submit_leave_request,
    "cancel_leave_request": _cancel_leave_request,
    "list_pending_requests": _list_pending_requests,
    "decide_leave_request": _decide_leave_request,
    "create_hr_ticket": _create_hr_ticket,
}
_HR_ONLY = {"list_pending_requests", "decide_leave_request"}


def execute(ctx: ToolContext, name: str, arguments: str | dict, component: str) -> dict:
    """Run a tool requested by the model. Never raises: errors are returned to the model as data."""
    t0 = time.perf_counter()
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else dict(arguments or {})
        if name not in _IMPL:
            result = _err("unknown_tool", f"No tool named {name}.", retryable=False)
        elif name in _HR_ONLY and not ctx.is_hr:
            result = _err("permission_denied", "This action is available to HR only.", retryable=False)
        else:
            result = _IMPL[name](ctx, **args)
    except InvalidRequest as e:
        result = _err(e.code, e.message, e.hint)
    except (TypeError, ValueError, json.JSONDecodeError) as e:
        result = _err("invalid_arguments", str(e), "Check the tool schema and call again.")
    trace_event(
        "tool",
        component,
        tool=name,
        arguments=arguments,
        result=result,
        latency_ms=round((time.perf_counter() - t0) * 1000),
    )
    return result
