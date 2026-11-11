"""Deterministic leave rule engine.

This module encodes the leave rules from the policy corpus. The policy text is the source of truth:
- leave-policy §1.2 (eligibility), §2.1-2.2 (entitlement), §3.1-3.4 (requests, notice, decisions,
  carry-over), §4 (special leave), §5 (unpaid leave), §6.1 (company holidays)
- sick-leave-policy §1.1, §2.1-2.4

The functions are pure: they receive all the data they need and never touch the database or an LLM.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum


class LeaveType(StrEnum):
    ANNUAL = "annual"
    SICK = "sick"
    UNPAID = "unpaid"
    SPECIAL = "special"


class SpecialEvent(StrEnum):
    WEDDING = "wedding"
    BEREAVEMENT = "bereavement"
    CHILDBIRTH = "childbirth"


class Status(StrEnum):
    APPROVED = "approved"
    DECLINED = "declined"
    PENDING_HR = "pending_hr"
    CANCELLED = "cancelled"


ACTIVE_STATUSES = (Status.APPROVED, Status.PENDING_HR)  # statuses that reserve days

# leave-policy §6.1
COMPANY_HOLIDAYS: frozenset[dt.date] = frozenset(
    dt.date.fromisoformat(d)
    for d in (
        "2026-12-25",
        "2026-12-31",
        "2027-01-01",
        "2027-03-08",
        "2027-05-03",
        "2027-06-28",
        "2027-08-24",
        "2027-10-14",
        "2027-12-24",
    )
)

ANNUAL_DAYS_PER_YEAR = 24  # leave-policy §2.1
FIRST_YEAR_DAYS_PER_MONTH = 2  # leave-policy §2.2
CARRY_OVER_MAX = 5  # leave-policy §3.4
CARRY_OVER_DEADLINE = (3, 31)  # 31 March, leave-policy §3.4
LONG_LEAVE_THRESHOLD = 3  # working days, leave-policy §3.2
LONG_LEAVE_NOTICE_CAL_DAYS = 14  # leave-policy §3.2
SHORT_LEAVE_NOTICE_WORK_DAYS = 2  # leave-policy §3.2
TEAM_OVERLAP_LIMIT = 2  # leave-policy §3.3
SPECIAL_DAYS_PER_EVENT = 3  # leave-policy §4.1
SPECIAL_EVENT_WINDOW_DAYS = 30  # leave-policy §4.2
UNPAID_DAYS_PER_YEAR = 20  # leave-policy §5.1
SICK_NO_CERT_MAX = 3  # sick-leave-policy §2.2
SICK_PAID_DAYS_PER_YEAR = 10  # sick-leave-policy §2.1
SICK_REGISTRATION_WINDOW = 7  # calendar days, sick-leave-policy §2.2


@dataclass(frozen=True)
class Employee:
    id: str
    name: str
    team: str
    role: str  # "employee" | "hr"
    employment_type: str  # "full_time" | "part_time" | "contractor"
    office: str  # "lviv" | "kyiv" | "remote"
    start_date: dt.date

    @property
    def is_contractor(self) -> bool:
        return self.employment_type == "contractor"


@dataclass(frozen=True)
class LeaveRecord:
    """An existing leave request, as stored in the database."""

    id: int
    employee_id: str
    leave_type: LeaveType
    start_date: dt.date
    end_date: dt.date
    working_days: int
    status: Status


@dataclass(frozen=True)
class LeaveRequest:
    """A new request to be decided."""

    leave_type: LeaveType
    start_date: dt.date
    end_date: dt.date
    event: SpecialEvent | None = None
    event_date: dt.date | None = None


@dataclass(frozen=True)
class Decision:
    status: Status
    code: str  # machine-readable reason, used in evals
    message: str  # human-readable explanation with the policy reference
    working_days: int


class InvalidRequest(ValueError):
    """The request is malformed and cannot be decided (the LLM should fix the arguments)."""

    def __init__(self, code: str, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.code, self.message, self.hint = code, message, hint


# ---------------------------------------------------------------- calendar helpers


def is_working_day(day: dt.date) -> bool:
    return day.weekday() < 5 and day not in COMPANY_HOLIDAYS


def daterange(start: dt.date, end: dt.date):
    day = start
    while day <= end:
        yield day
        day += dt.timedelta(days=1)


def working_days(start: dt.date, end: dt.date) -> list[dt.date]:
    return [d for d in daterange(start, end) if is_working_day(d)]


def working_days_strictly_between(a: dt.date, b: dt.date) -> int:
    """Number of working days d with a < d < b."""
    if b <= a:
        return 0
    return len(working_days(a + dt.timedelta(days=1), b - dt.timedelta(days=1)))


# ---------------------------------------------------------------- balances


def annual_entitlement(employee: Employee, year: int) -> int:
    """leave-policy §1.2, §2.1, §2.2."""
    if employee.is_contractor or employee.start_date.year > year:
        return 0
    if employee.start_date.year < year:
        return ANNUAL_DAYS_PER_YEAR
    start = employee.start_date
    first_full_month = start.month if start.day == 1 else start.month + 1
    full_months = max(0, 12 - first_full_month + 1)
    return min(ANNUAL_DAYS_PER_YEAR, FIRST_YEAR_DAYS_PER_MONTH * full_months)


def _active(records: list[LeaveRecord], leave_type: LeaveType) -> list[LeaveRecord]:
    return [r for r in records if r.leave_type == leave_type and r.status in ACTIVE_STATUSES]


def _days_in_year(records: list[LeaveRecord], year: int) -> list[dt.date]:
    days: list[dt.date] = []
    for r in records:
        days += [d for d in working_days(r.start_date, r.end_date) if d.year == year]
    return days


FIRST_TRACKED_YEAR = 2026  # leave history in the system starts in 2026; nothing is carried into it


def carry_over(employee: Employee, own: list[LeaveRecord], year: int) -> int:
    """Unused annual days of the previous year that may be carried over (leave-policy §3.4)."""
    if year <= FIRST_TRACKED_YEAR:
        return 0
    prev = year - 1
    used_prev = len(_days_in_year(_active(own, LeaveType.ANNUAL), prev))
    available_prev = annual_entitlement(employee, prev) + carry_over(employee, own, prev)
    return max(0, min(CARRY_OVER_MAX, available_prev - used_prev))


@dataclass(frozen=True)
class AnnualBalance:
    year: int
    entitlement: int
    carried_over: int
    carry_over_valid_until: dt.date
    used_or_reserved: int
    carry_left: int  # carried-over days still unused (usable only for days <= the deadline)
    main_left: int  # days of this year's entitlement still unused
    remaining_total: int  # what the employee can still book from `today`


def annual_balance(employee: Employee, own: list[LeaveRecord], year: int, today: dt.date) -> AnnualBalance:
    """Carried-over days are consumed first by leave taken on or before 31 March (leave-policy §3.4)."""
    entitlement = annual_entitlement(employee, year)
    carried = carry_over(employee, own, year)
    deadline = dt.date(year, *CARRY_OVER_DEADLINE)
    used_days = _days_in_year(_active(own, LeaveType.ANNUAL), year)
    carry_consumed = min(carried, sum(1 for d in used_days if d <= deadline))
    carry_left = carried - carry_consumed
    main_left = max(0, entitlement - (len(used_days) - carry_consumed))
    return AnnualBalance(
        year=year,
        entitlement=entitlement,
        carried_over=carried,
        carry_over_valid_until=deadline,
        used_or_reserved=len(used_days),
        carry_left=carry_left,
        main_left=main_left,
        remaining_total=main_left + (carry_left if today <= deadline else 0),
    )


def sick_days_used(own: list[LeaveRecord], year: int) -> int:
    return len(_days_in_year(_active(own, LeaveType.SICK), year))


def unpaid_days_used(own: list[LeaveRecord], year: int) -> int:
    return len(_days_in_year(_active(own, LeaveType.UNPAID), year))


# ---------------------------------------------------------------- decision


def _validate(req: LeaveRequest, today: dt.date) -> list[dt.date]:
    if req.end_date < req.start_date:
        raise InvalidRequest(
            "end_before_start",
            "The end date is before the start date.",
            "Ask the employee to confirm the dates.",
        )
    if req.start_date.year != req.end_date.year:
        raise InvalidRequest(
            "spans_years",
            "A single request cannot span two calendar years (leave-policy §3.1).",
            f"Submit two requests: {req.start_date}..{req.start_date.year}-12-31 and "
            f"{req.end_date.year}-01-01..{req.end_date}.",
        )
    days = working_days(req.start_date, req.end_date)
    if not days:
        raise InvalidRequest(
            "no_working_days",
            "The requested period contains no working days.",
            "Weekends and company holidays are already days off (leave-policy §6.1).",
        )
    if req.leave_type == LeaveType.SICK:
        if req.start_date < today - dt.timedelta(days=SICK_REGISTRATION_WINDOW):
            raise InvalidRequest(
                "sick_too_late",
                "Sick days must be registered within 7 days of the first day of illness "
                "(sick-leave-policy §2.2).",
                "Contact HR directly.",
            )
    elif req.start_date <= today:
        raise InvalidRequest(
            "start_in_past",
            "Leave must start after today.",
            "Ask for a future start date, or contact HR for leave that has already started.",
        )
    if req.leave_type == LeaveType.SPECIAL and (req.event is None or req.event_date is None):
        raise InvalidRequest(
            "special_missing_event",
            "Special leave needs the event type and the event date.",
            "Ask which event (wedding, bereavement, childbirth) and when it happens.",
        )
    return days


def _overlaps(a_start: dt.date, a_end: dt.date, b_start: dt.date, b_end: dt.date) -> bool:
    return a_start <= b_end and b_start <= a_end


def decide(
    req: LeaveRequest,
    employee: Employee,
    own: list[LeaveRecord],
    teammates: list[LeaveRecord],
    today: dt.date,
) -> Decision:
    """Decide a leave request. `own` are the employee's existing requests; `teammates` are the
    existing requests of other members of the same team."""
    days = _validate(req, today)
    n = len(days)

    def d(status: Status, code: str, message: str) -> Decision:
        return Decision(status, code, message, n)

    if employee.is_contractor:
        return d(
            Status.DECLINED,
            "contractor_not_eligible",
            "Contractors are not covered by the leave policies; agree on time off with your manager "
            "under your service agreement (leave-policy §1.2, sick-leave-policy §1.1).",
        )

    clash = [
        r
        for r in own
        if r.status in ACTIVE_STATUSES and _overlaps(r.start_date, r.end_date, req.start_date, req.end_date)
    ]
    if clash:
        return d(
            Status.DECLINED,
            "overlaps_own_request",
            f"These dates overlap with your existing request #{clash[0].id} "
            f"({clash[0].start_date}..{clash[0].end_date}) (leave-policy §3.3).",
        )

    year = req.start_date.year

    if req.leave_type == LeaveType.SICK:
        used = sick_days_used(own, year)
        if n > SICK_NO_CERT_MAX:
            return d(
                Status.PENDING_HR,
                "sick_needs_certificate",
                f"Sick leave longer than {SICK_NO_CERT_MAX} working days needs a medical certificate; "
                "HR will review it (sick-leave-policy §2.3).",
            )
        if used + n > SICK_PAID_DAYS_PER_YEAR:
            return d(
                Status.PENDING_HR,
                "sick_over_yearly_paid",
                f"This would bring your sick days to {used + n}, above the {SICK_PAID_DAYS_PER_YEAR} "
                "paid days per year; HR will review it (sick-leave-policy §2.1, §2.4).",
            )
        return d(
            Status.APPROVED,
            "sick_ok",
            f"Sick leave registered for {n} working day(s); no certificate needed (sick-leave-policy §2.2).",
        )

    if req.leave_type == LeaveType.UNPAID:
        used = unpaid_days_used(own, year)
        if used + n > UNPAID_DAYS_PER_YEAR:
            return d(
                Status.DECLINED,
                "unpaid_over_limit",
                f"This would bring your unpaid leave to {used + n} working days, above the "
                f"{UNPAID_DAYS_PER_YEAR}-day yearly limit (leave-policy §5.1, §5.2).",
            )
        return d(
            Status.PENDING_HR,
            "unpaid_needs_manager",
            "Unpaid leave always needs manager approval; HR will review it (leave-policy §5.2).",
        )

    if req.leave_type == LeaveType.SPECIAL:
        assert req.event_date is not None
        if abs((req.start_date - req.event_date).days) > SPECIAL_EVENT_WINDOW_DAYS:
            return d(
                Status.PENDING_HR,
                "special_outside_window",
                "Special leave should be taken within 30 days of the event; HR will review it "
                "(leave-policy §4.2).",
            )
        if n > SPECIAL_DAYS_PER_EVENT:
            return d(
                Status.PENDING_HR,
                "special_over_limit",
                f"Special leave is {SPECIAL_DAYS_PER_EVENT} working days per event; the extra days "
                "need HR review (leave-policy §4.1, §4.2).",
            )
        return d(
            Status.APPROVED,
            "special_ok",
            f"Special leave ({req.event}) approved for {n} working day(s) (leave-policy §4.1).",
        )

    # annual leave
    balance = annual_balance(employee, own, year, today)
    days_before_deadline = sum(1 for x in days if x <= balance.carry_over_valid_until)
    usable_carry = min(balance.carry_left, days_before_deadline)
    needed_from_main = n - usable_carry
    if needed_from_main > balance.main_left:
        return d(
            Status.DECLINED,
            "insufficient_balance",
            f"You requested {n} working days but have {balance.remaining_total} annual leave days "
            f"available for {year} (leave-policy §2.1, §3.3).",
        )

    if n > LONG_LEAVE_THRESHOLD:
        if (req.start_date - today).days < LONG_LEAVE_NOTICE_CAL_DAYS:
            return d(
                Status.DECLINED,
                "notice_too_short",
                f"Leave of more than {LONG_LEAVE_THRESHOLD} working days must be requested at least "
                f"{LONG_LEAVE_NOTICE_CAL_DAYS} calendar days in advance (leave-policy §3.2).",
            )
    elif working_days_strictly_between(today, req.start_date) < SHORT_LEAVE_NOTICE_WORK_DAYS:
        return d(
            Status.DECLINED,
            "notice_too_short",
            f"Leave of up to {LONG_LEAVE_THRESHOLD} working days must be requested at least "
            f"{SHORT_LEAVE_NOTICE_WORK_DAYS} working days in advance (leave-policy §3.2).",
        )

    approved_team = [r for r in teammates if r.status == Status.APPROVED]
    for day in days:
        off = {r.employee_id for r in approved_team if r.start_date <= day <= r.end_date}
        if len(off) >= TEAM_OVERLAP_LIMIT:
            return d(
                Status.PENDING_HR,
                "team_overlap",
                f"{len(off)} members of your team already have approved leave on {day}; HR will "
                "confirm with your team lead within 3 working days (leave-policy §3.3).",
            )

    return d(
        Status.APPROVED,
        "annual_ok",
        f"Annual leave approved for {n} working day(s); {balance.remaining_total - n} day(s) remain "
        f"for {year} (leave-policy §3.3).",
    )
