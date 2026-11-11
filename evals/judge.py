"""LLM-as-judge (calibrated in run_judge_calibration.py). Uses JUDGE_MODEL (a different family than the generator)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from hr_assistant.config import get_settings
from hr_assistant.llm import complete_json

Verdict = Literal["fully_matches", "mostly_right", "mostly_wrong", "contradicts"]
VERDICT_SCORE = {"fully_matches": 1.0, "mostly_right": 2 / 3, "mostly_wrong": 1 / 3, "contradicts": 0.0}


class CorrectnessVerdict(BaseModel):
    reason: str
    verdict: Verdict


class Claim(BaseModel):
    claim: str
    supported: bool


class FaithfulnessVerdict(BaseModel):
    claims: list[Claim]


def judge_correctness(question: str, gold: str, candidate: str) -> CorrectnessVerdict:
    user = f"QUESTION: {question}\n\nGOLD answer: {gold}\n\nCANDIDATE answer: {candidate}"
    return complete_json(
        "judge_correctness", "judge_correctness", user, CorrectnessVerdict, model=get_settings().judge_model
    )


def judge_faithfulness(
    answer: str, evidence: list[str], profile: str = ""
) -> tuple[float | None, list[Claim]]:
    """Faithfulness = supported claims / total claims (RAGAS / DeepEval definition). None if no claims."""
    user = f"EMPLOYEE PROFILE: {profile}\n\nEVIDENCE:\n" + "\n\n".join(evidence) + f"\n\nANSWER: {answer}"
    out = complete_json(
        "judge_faithfulness",
        "judge_faithfulness",
        user,
        FaithfulnessVerdict,
        model=get_settings().judge_model,
    )
    if not out.claims:
        return None, []
    return sum(c.supported for c in out.claims) / len(out.claims), out.claims
