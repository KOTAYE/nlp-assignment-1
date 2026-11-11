"""Single source of configuration. Values come from `.env` / environment variables only."""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    judge_model: str
    db_path: Path
    policies_dir: Path
    traces_dir: Path
    today_override: dt.date | None

    def today(self) -> dt.date:
        """Business date used by the rule engine. Fixed via HR_TODAY for reproducible evals and demos."""
        return self.today_override or dt.date.today()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    today = os.getenv("HR_TODAY")
    return Settings(
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
        llm_model=os.getenv("LLM_MODEL", "openai/gpt-4o-mini"),
        judge_model=os.getenv(
            "JUDGE_MODEL", "google/gemini-2.5-flash"
        ),  # different family than the generator
        db_path=Path(os.getenv("HR_DB_PATH", ROOT / "data" / "hr.db")),
        policies_dir=ROOT / "data" / "policies",
        traces_dir=ROOT / "logs" / "traces",
        today_override=dt.date.fromisoformat(today) if today else None,
    )
