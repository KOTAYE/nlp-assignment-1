"""SQLite storage: schema, synthetic seed, and low-level data access.

Only `hr_assistant.tools` may import this module at runtime: the application reaches the database
exclusively through tools that the LLM decides to call (assignment brief: "access it via LLM only").
Eval scripts may read it to check the final state.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path

from .rules import Employee, LeaveRecord, LeaveType, Status, working_days

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    team TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('employee', 'hr')),
    employment_type TEXT NOT NULL CHECK (employment_type IN ('full_time', 'part_time', 'contractor')),
    office TEXT NOT NULL CHECK (office IN ('lviv', 'kyiv', 'remote')),
    start_date TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS leave_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL REFERENCES employees(id),
    leave_type TEXT NOT NULL CHECK (leave_type IN ('annual', 'sick', 'unpaid', 'special')),
    event TEXT,
    event_date TEXT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    working_days INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('approved', 'declined', 'pending_hr', 'cancelled')),
    decision_code TEXT,
    decision_message TEXT,
    comment TEXT,
    created_at TEXT NOT NULL,
    decided_by TEXT,
    decided_at TEXT
);
CREATE TABLE IF NOT EXISTS hr_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL REFERENCES employees(id),
    category TEXT NOT NULL,
    summary TEXT NOT NULL,
    original_question TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);
"""

# Synthetic, fictional employees (data/README.md). Chosen to exercise every rule:
# contractors, part-timers, first-year joiners (pro-rated entitlement, probation), offices, teams.
EMPLOYEES: list[tuple[str, str, str, str, str, str, str]] = [
    ("E001", "Olena Hrytsenko", "People", "hr", "full_time", "lviv", "2021-03-01"),
    ("E002", "Iryna Bondar", "People", "hr", "full_time", "kyiv", "2023-05-15"),
    ("E003", "Andrii Koval", "Platform", "employee", "full_time", "lviv", "2020-06-15"),
    ("E004", "Sofiia Lysenko", "Platform", "employee", "full_time", "kyiv", "2022-01-10"),
    ("E005", "Maksym Tkachenko", "Platform", "employee", "full_time", "remote", "2023-04-03"),
    ("E006", "Daryna Shevchuk", "Platform", "employee", "full_time", "lviv", "2026-09-01"),
    ("E007", "Bohdan Kravets", "Platform", "employee", "contractor", "remote", "2024-02-01"),
    ("E008", "Kateryna Moroz", "Mobile", "employee", "full_time", "lviv", "2019-09-02"),
    ("E009", "Yurii Polishchuk", "Mobile", "employee", "full_time", "kyiv", "2021-11-15"),
    ("E010", "Nazar Savchenko", "Mobile", "employee", "full_time", "remote", "2022-05-16"),
    ("E011", "Anna Rudenko", "Mobile", "employee", "part_time", "lviv", "2023-08-01"),
    ("E012", "Ostap Hnatiuk", "Mobile", "employee", "contractor", "lviv", "2025-01-13"),
    ("E013", "Viktoriia Pavlenko", "Data", "employee", "full_time", "kyiv", "2020-02-03"),
    ("E014", "Dmytro Boiko", "Data", "employee", "full_time", "remote", "2024-10-01"),
    ("E015", "Mariia Zaitseva", "Data", "employee", "part_time", "remote", "2025-03-03"),
    ("E016", "Roman Kuzmenko", "Data", "employee", "full_time", "kyiv", "2026-10-15"),
    ("E017", "Yana Klymenko", "Design", "employee", "full_time", "lviv", "2022-07-01"),
    ("E018", "Artem Levchenko", "Design", "employee", "full_time", "remote", "2021-04-12"),
    ("E019", "Khrystyna Ostapenko", "Design", "employee", "part_time", "kyiv", "2024-06-03"),
    ("E020", "Ivan Marchenko", "Design", "employee", "contractor", "remote", "2023-09-01"),
    ("E021", "Oleksandr Romanenko", "Sales", "employee", "full_time", "kyiv", "2018-05-07"),
    ("E022", "Liliia Vasylenko", "Sales", "employee", "full_time", "lviv", "2023-01-16"),
    ("E023", "Serhii Bilyk", "Sales", "employee", "full_time", "remote", "2025-06-02"),
    ("E024", "Natalia Kostenko", "Sales", "employee", "full_time", "kyiv", "2026-08-03"),
    ("E025", "Pavlo Hordiienko", "QA", "employee", "full_time", "lviv", "2021-08-02"),
    ("E026", "Oksana Fedorenko", "QA", "employee", "full_time", "lviv", "2022-10-03"),
    ("E027", "Vitalii Danylenko", "QA", "employee", "full_time", "kyiv", "2024-01-08"),
    ("E028", "Halyna Prykhodko", "QA", "employee", "part_time", "remote", "2020-11-02"),
    ("E029", "Mykola Yatsenko", "QA", "employee", "contractor", "kyiv", "2025-09-01"),
    ("E030", "Tetiana Karpenko", "QA", "employee", "full_time", "remote", "2023-03-01"),
]

# (employee, type, start, end, status, event, event_date)
LEAVE_HISTORY: list[tuple[str, str, str, str, str, str | None, str | None]] = [
    # Mobile: two people already off over 28-30 Dec -> a third request there goes to HR (team_overlap)
    ("E008", "annual", "2026-12-28", "2026-12-30", "approved", None, None),
    ("E009", "annual", "2026-12-29", "2026-12-30", "approved", None, None),
    # E021: heavy user, only 2 annual days left in 2026
    ("E021", "annual", "2026-02-09", "2026-02-20", "approved", None, None),
    ("E021", "annual", "2026-07-06", "2026-07-21", "approved", None, None),
    # E013: entire 2026 entitlement used -> 0 left, nothing to carry over
    ("E013", "annual", "2026-04-06", "2026-04-17", "approved", None, None),
    ("E013", "annual", "2026-08-03", "2026-08-20", "approved", None, None),
    # E003: 10 days used -> 14 left; at most 5 can carry over into 2027
    ("E003", "annual", "2026-05-11", "2026-05-22", "approved", None, None),
    # E004: unpaid leave waiting for HR
    ("E004", "unpaid", "2026-12-14", "2026-12-18", "pending_hr", None, None),
    # E010: 8 sick days in 2026 -> 3 more would exceed the 10 paid days
    ("E010", "sick", "2026-03-02", "2026-03-04", "approved", None, None),
    ("E010", "sick", "2026-09-14", "2026-09-18", "pending_hr", None, None),
    # E017: future approved leave (can be cancelled)
    ("E017", "annual", "2026-11-23", "2026-11-27", "approved", None, None),
    # E022: declined request kept for tracking
    ("E022", "annual", "2026-10-05", "2026-10-09", "declined", None, None),
    # E005: special leave used earlier this year
    ("E005", "special", "2026-06-15", "2026-06-17", "approved", "wedding", "2026-06-13"),
    # QA: one person off in early January 2027
    ("E025", "annual", "2027-01-04", "2027-01-08", "approved", None, None),
]


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection, seed: bool = True) -> None:
    conn.executescript(SCHEMA)
    if seed and conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 0:
        conn.executemany("INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?, ?)", EMPLOYEES)
        for emp, ltype, start, end, status, event, event_date in LEAVE_HISTORY:
            n = len(working_days(dt.date.fromisoformat(start), dt.date.fromisoformat(end)))
            conn.execute(
                "INSERT INTO leave_requests (employee_id, leave_type, event, event_date, start_date, end_date,"
                " working_days, status, decision_code, decision_message, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'seed', 'Seeded history', '2026-01-01T00:00:00')",
                (emp, ltype, event, event_date, start, end, n, status),
            )
    conn.commit()


def reset_db(path: Path | str) -> sqlite3.Connection:
    """Fresh, seeded database (used by evals and the demo's reset button)."""
    p = Path(path)
    if p.exists():
        p.unlink()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(p)
    init_db(conn)
    return conn


# ---------------------------------------------------------------- row mapping


def _employee(row: sqlite3.Row) -> Employee:
    return Employee(
        row["id"],
        row["name"],
        row["team"],
        row["role"],
        row["employment_type"],
        row["office"],
        dt.date.fromisoformat(row["start_date"]),
    )


def _record(row: sqlite3.Row) -> LeaveRecord:
    return LeaveRecord(
        row["id"],
        row["employee_id"],
        LeaveType(row["leave_type"]),
        dt.date.fromisoformat(row["start_date"]),
        dt.date.fromisoformat(row["end_date"]),
        row["working_days"],
        Status(row["status"]),
    )


# ---------------------------------------------------------------- queries


def get_employee(conn: sqlite3.Connection, employee_id: str) -> Employee | None:
    row = conn.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
    return _employee(row) if row else None


def list_employees(conn: sqlite3.Connection) -> list[Employee]:
    return [_employee(r) for r in conn.execute("SELECT * FROM employees ORDER BY id")]


def leave_records(conn: sqlite3.Connection, employee_id: str) -> list[LeaveRecord]:
    rows = conn.execute(
        "SELECT * FROM leave_requests WHERE employee_id = ? ORDER BY start_date", (employee_id,)
    )
    return [_record(r) for r in rows]


def team_records(conn: sqlite3.Connection, team: str, exclude_employee: str) -> list[LeaveRecord]:
    rows = conn.execute(
        "SELECT lr.* FROM leave_requests lr JOIN employees e ON e.id = lr.employee_id"
        " WHERE e.team = ? AND lr.employee_id != ?",
        (team, exclude_employee),
    )
    return [_record(r) for r in rows]


def leave_rows(conn: sqlite3.Connection, where: str = "1=1", params: tuple = ()) -> list[dict]:
    rows = conn.execute(
        "SELECT lr.*, e.name AS employee_name, e.team AS team FROM leave_requests lr"
        f" JOIN employees e ON e.id = lr.employee_id WHERE {where} ORDER BY lr.start_date",
        params,
    )
    return [dict(r) for r in rows]


def insert_leave(
    conn: sqlite3.Connection,
    employee_id: str,
    leave_type: str,
    start: dt.date,
    end: dt.date,
    working_days_count: int,
    status: str,
    code: str,
    message: str,
    comment: str | None,
    event: str | None,
    event_date: dt.date | None,
    now: dt.datetime,
) -> int:
    cur = conn.execute(
        "INSERT INTO leave_requests (employee_id, leave_type, event, event_date, start_date, end_date,"
        " working_days, status, decision_code, decision_message, comment, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            employee_id,
            leave_type,
            event,
            event_date.isoformat() if event_date else None,
            start.isoformat(),
            end.isoformat(),
            working_days_count,
            status,
            code,
            message,
            comment,
            now.isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_leave_status(
    conn: sqlite3.Connection, request_id: int, status: str, message: str, decided_by: str, now: dt.datetime
) -> None:
    conn.execute(
        "UPDATE leave_requests SET status = ?, decision_message = ?, decided_by = ?, decided_at = ? WHERE id = ?",
        (status, message, decided_by, now.isoformat(timespec="seconds"), request_id),
    )
    conn.commit()


def insert_ticket(
    conn: sqlite3.Connection, employee_id: str, category: str, summary: str, question: str, now: dt.datetime
) -> int:
    cur = conn.execute(
        "INSERT INTO hr_tickets (employee_id, category, summary, original_question, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (employee_id, category, summary, question, now.isoformat(timespec="seconds")),
    )
    conn.commit()
    return int(cur.lastrowid)


def ticket_rows(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM hr_tickets ORDER BY id")]
