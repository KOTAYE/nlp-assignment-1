"""Recreate the demo database from the synthetic seed (setup utility, not used by the application).

Usage: python scripts/reset_db.py
"""

from hr_assistant.config import get_settings
from hr_assistant.db import reset_db

if __name__ == "__main__":
    path = get_settings().db_path
    reset_db(path).close()
    print(f"Database reset: {path}")
