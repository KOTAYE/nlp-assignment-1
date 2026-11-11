"""Rule-engine tests = the evaluation of the rule engine component (docs/architecture.md).

Every rule in docs/crisp-dm.md §1.4 has at least one test. The business date is fixed at 2026-11-12 (Thu).
"""

from __future__ import annotations

import datetime as dt
import re

import pytest

from hr_assistant import db
from hr_assistant.config import ROOT
from hr_assistant.rules import (
    COMPANY_HOLIDAYS,
    InvalidRequest,
    LeaveRequest,
    LeaveType,
    SpecialEvent,
    Status,
    annual_balance,
    annual_entitlement,
    carry_over,
    decide,
    working_days,
)

TODAY = dt.date(2026, 11, 12)
D = dt.date.fromisoformat


@pytest.fixture(scope="module")
def conn():
    c = db.connect(":memory:")
    db.init_db(c)
    return c


def run(conn, emp_id: str, leave_type: str, start: str, end: str, event=None, event_date=None):
    emp = db.get_employee(conn, emp_id)
    req = LeaveRequest(
        LeaveType(leave_type),
        D(start),
        D(end),
        SpecialEvent(event) if event else None,
        D(event_date) if event_date else None,
    )
    return decide(req, emp, db.leave_records(conn, emp_id), db.team_records(conn, emp.team, emp_id), TODAY)


# ---------------------------------------------------------------- calendar (leave-policy §6.1)


def test_working_days_skip_weekends_and_holidays():
    # 21-24 Dec (4) + 28-30 Dec (3); 25 and 31 Dec are company holidays
    assert len(working_days(D("2026-12-21"), D("2026-12-31"))) == 7


def test_holidays_match_policy_table():
    text = (ROOT / "data/policies/leave-policy.md").read_text(encoding="utf-8")
    section = text.split("### 6.1")[1].split("### 6.2")[0]
    in_policy = {D(m) for m in re.findall(r"\| (\d{4}-\d{2}-\d{2}) \|", section)}
    assert in_policy == set(COMPANY_HOLIDAYS)


# ---------------------------------------------------------------- entitlement (leave-policy §1.2, §2.1, §2.2)


@pytest.mark.parametrize(
    ("emp_id", "year", "expected"),
    [
        ("E003", 2026, 24),  # full year
        ("E007", 2026, 0),  # contractor
        ("E006", 2026, 8),  # started 1 Sep -> Sep..Dec
        ("E016", 2026, 4),  # started 15 Oct -> Nov..Dec
        ("E024", 2026, 8),  # started 3 Aug -> Sep..Dec
        ("E006", 2025, 0),  # before start
        ("E011", 2026, 24),  # part-time: same number of days (§1.3)
    ],
)
def test_annual_entitlement(conn, emp_id, year, expected):
    assert annual_entitlement(db.get_employee(conn, emp_id), year) == expected


def test_policy_examples_for_first_year():
    from hr_assistant.rules import Employee

    mk = lambda start: Employee("X", "X", "T", "employee", "full_time", "lviv", D(start))  # noqa: E731
    assert annual_entitlement(mk("2026-09-01"), 2026) == 8
    assert annual_entitlement(mk("2026-09-15"), 2026) == 6


# ---------------------------------------------------------------- carry-over (leave-policy §3.4)


@pytest.mark.parametrize(("emp_id", "expected"), [("E003", 5), ("E013", 0), ("E021", 2)])
def test_carry_over_into_2027(conn, emp_id, expected):
    emp = db.get_employee(conn, emp_id)
    assert carry_over(emp, db.leave_records(conn, emp_id), 2027) == expected


def test_balance_2027_includes_carry_over(conn):
    b = annual_balance(db.get_employee(conn, "E003"), db.leave_records(conn, "E003"), 2027, TODAY)
    assert (b.entitlement, b.carried_over, b.remaining_total) == (24, 5, 29)


def test_carry_over_usable_before_31_march(conn):
    # 4 Jan .. 5 Feb 2027 = 25 working days: 24 + 1 carried-over day
    assert run(conn, "E003", "annual", "2027-01-04", "2027-02-05").status == Status.APPROVED


def test_carry_over_not_usable_after_31_march(conn):
    # 5 Apr .. 10 May 2027 = 25 working days (3 May is a holiday) > 24
    d = run(conn, "E003", "annual", "2027-04-05", "2027-05-10")
    assert (d.status, d.code, d.working_days) == (Status.DECLINED, "insufficient_balance", 25)


# ---------------------------------------------------------------- annual decisions (leave-policy §3.2, §3.3)


def test_annual_approved(conn):
    d = run(conn, "E005", "annual", "2026-12-07", "2026-12-11")
    assert (d.status, d.code, d.working_days) == (Status.APPROVED, "annual_ok", 5)


def test_long_leave_needs_14_days_notice(conn):
    assert run(conn, "E005", "annual", "2026-11-23", "2026-11-27").code == "notice_too_short"


def test_short_leave_needs_2_working_days_notice(conn):
    assert (
        run(conn, "E005", "annual", "2026-11-16", "2026-11-16").code == "notice_too_short"
    )  # only Fri between
    assert run(conn, "E005", "annual", "2026-11-17", "2026-11-17").status == Status.APPROVED  # Fri + Mon


def test_insufficient_balance(conn):
    assert run(conn, "E021", "annual", "2026-12-07", "2026-12-09").code == "insufficient_balance"  # 3 > 2
    assert run(conn, "E021", "annual", "2026-12-07", "2026-12-08").status == Status.APPROVED
    assert run(conn, "E013", "annual", "2026-12-07", "2026-12-07").code == "insufficient_balance"


def test_team_overlap_goes_to_hr(conn):
    d = run(conn, "E010", "annual", "2026-12-28", "2026-12-30")  # E008 + E009 off on 29-30 Dec
    assert (d.status, d.code) == (Status.PENDING_HR, "team_overlap")
    assert run(conn, "E010", "annual", "2026-12-28", "2026-12-28").status == Status.APPROVED  # only E008


def test_overlap_with_own_request_declined(conn):
    assert run(conn, "E017", "annual", "2026-11-25", "2026-11-26").code == "overlaps_own_request"


def test_first_year_joiner_limited_balance(conn):
    assert run(conn, "E006", "annual", "2026-12-01", "2026-12-11").code == "insufficient_balance"  # 9 > 8
    assert run(conn, "E006", "annual", "2026-12-01", "2026-12-10").status == Status.APPROVED  # 8


# ---------------------------------------------------------------- eligibility (leave-policy §1.2, sick §1.1)


@pytest.mark.parametrize("leave_type", ["annual", "sick", "unpaid"])
def test_contractor_declined(conn, leave_type):
    start = "2026-11-13" if leave_type == "sick" else "2026-12-07"
    assert (
        run(conn, "E007", leave_type, start, "2026-12-08" if leave_type != "sick" else start).code
        == "contractor_not_eligible"
    )


# ---------------------------------------------------------------- sick leave (sick-leave-policy §2)


def test_sick_short_approved(conn):
    d = run(conn, "E005", "sick", "2026-11-12", "2026-11-13")
    assert (d.status, d.code) == (Status.APPROVED, "sick_ok")


def test_sick_long_needs_certificate(conn):
    assert run(conn, "E005", "sick", "2026-11-12", "2026-11-17").code == "sick_needs_certificate"


def test_sick_yearly_cap(conn):
    assert run(conn, "E010", "sick", "2026-11-16", "2026-11-18").code == "sick_over_yearly_paid"  # 8 + 3 > 10
    assert run(conn, "E010", "sick", "2026-11-16", "2026-11-17").status == Status.APPROVED  # 8 + 2


def test_sick_registration_window(conn):
    with pytest.raises(InvalidRequest) as e:
        run(conn, "E005", "sick", "2026-11-02", "2026-11-03")
    assert e.value.code == "sick_too_late"


def test_sick_never_declined_for_notice(conn):
    assert run(conn, "E005", "sick", "2026-11-11", "2026-11-11").status == Status.APPROVED


# ---------------------------------------------------------------- unpaid leave (leave-policy §5)


def test_unpaid_always_hr(conn):
    d = run(conn, "E004", "unpaid", "2027-02-01", "2027-02-05")
    assert (d.status, d.code) == (Status.PENDING_HR, "unpaid_needs_manager")


def test_unpaid_yearly_limit(conn):
    # E004 already has 5 pending unpaid days in 2026; 16 more = 21 > 20
    assert run(conn, "E004", "unpaid", "2026-11-16", "2026-12-07").code == "unpaid_over_limit"
    assert run(conn, "E004", "unpaid", "2026-11-16", "2026-12-04").status == Status.PENDING_HR  # 5 + 15 = 20


# ---------------------------------------------------------------- special leave (leave-policy §4)


def test_special_within_limit(conn):
    d = run(conn, "E018", "special", "2026-12-01", "2026-12-03", "wedding", "2026-12-05")
    assert (d.status, d.code) == (Status.APPROVED, "special_ok")


def test_special_over_limit(conn):
    assert (
        run(conn, "E018", "special", "2026-12-01", "2026-12-04", "wedding", "2026-12-05").code
        == "special_over_limit"
    )


def test_special_outside_event_window(conn):
    assert (
        run(conn, "E018", "special", "2026-12-14", "2026-12-15", "bereavement", "2026-10-01").code
        == "special_outside_window"
    )


# ---------------------------------------------------------------- invalid requests (instructive errors)


@pytest.mark.parametrize(
    ("args", "code"),
    [
        (("E005", "annual", "2026-12-30", "2027-01-05"), "spans_years"),
        (("E005", "annual", "2026-12-12", "2026-12-13"), "no_working_days"),
        (("E005", "annual", "2026-11-10", "2026-11-10"), "start_in_past"),
        (("E005", "annual", "2026-12-10", "2026-12-07"), "end_before_start"),
        (("E018", "special", "2026-12-01", "2026-12-02"), "special_missing_event"),
    ],
)
def test_invalid_requests(conn, args, code):
    with pytest.raises(InvalidRequest) as e:
        run(conn, *args)
    assert e.value.code == code and e.value.hint
