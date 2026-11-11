"""Employee directory = the identity provider (like SSO claims).

It tells the application *who is logged in* and their profile (employment type, office, start date, role).
It is deliberately separate from the leave database: the leave database is reached only through LLM tool
calls (assignment brief: "use a database ... and access it via LLM only"), while the directory is the
session's identity source, used for login and for pre-filling profile facts in information collection.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .db import EMPLOYEES
from .rules import Employee

PROBATION_MONTHS = 3  # onboarding-policy §3.1


def _add_months(day: dt.date, months: int) -> dt.date:
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    return dt.date(year, month, min(day.day, 28))


@dataclass(frozen=True)
class Profile:
    employee: Employee
    probation_end: dt.date | None

    def probation_passed(self, today: dt.date) -> bool | None:
        """None for contractors (no probation, onboarding-policy §3.1)."""
        if self.probation_end is None:
            return None
        return today >= self.probation_end

    def facts(self, today: dt.date) -> dict[str, str]:
        e = self.employee
        passed = self.probation_passed(today)
        return {
            "employee_id": e.id,
            "name": e.name,
            "team": e.team,
            "role": e.role,
            "employment_type": e.employment_type,
            "office": e.office,
            "start_date": e.start_date.isoformat(),
            "probation_passed": "not applicable (contractor)"
            if passed is None
            else ("yes" if passed else "no"),
            "today": today.isoformat(),
        }


def all_profiles() -> list[Profile]:
    out = []
    for eid, name, team, role, etype, office, start in EMPLOYEES:
        emp = Employee(eid, name, team, role, etype, office, dt.date.fromisoformat(start))
        end = None if etype == "contractor" else _add_months(emp.start_date, PROBATION_MONTHS)
        out.append(Profile(emp, end))
    return out


def get_profile(employee_id: str) -> Profile:
    for p in all_profiles():
        if p.employee.id == employee_id:
            return p
    raise KeyError(employee_id)
