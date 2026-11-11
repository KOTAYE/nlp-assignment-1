"""Structured outputs of the LLM components (validated with Pydantic)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Intent = Literal["policy_question", "leave_action", "hr_referral", "smalltalk", "unclear"]
INTENTS: tuple[str, ...] = ("policy_question", "leave_action", "hr_referral", "smalltalk", "unclear")


class RouteResult(BaseModel):
    intent: Intent
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(description="One short sentence explaining the choice.")


# Facts that policy answers can depend on. Profile facts come from the identity provider (directory);
# situational facts must come from the conversation.
PROFILE_FACTS: tuple[str, ...] = ("employment_type", "office", "probation_passed")
SITUATIONAL_FACTS: tuple[str, ...] = (
    "illness_duration_days",
    "has_medical_certificate",
    "days_abroad",
    "expense_category",
    "life_event",
    "document_type",
)
FactName = Literal[
    "employment_type",
    "office",
    "probation_passed",
    "illness_duration_days",
    "has_medical_certificate",
    "days_abroad",
    "expense_category",
    "life_event",
    "document_type",
]


class Fact(BaseModel):
    name: FactName
    value: str | None = Field(description="Value stated in the conversation, or null if not stated.")


class CollectorOutput(BaseModel):
    required_facts: list[Fact] = Field(description="Facts the correct answer depends on (may be empty).")
    clarifying_question: str | None = Field(
        description="One short question asking ONLY for the situational facts that are still missing; null if none."
    )


class RewriteResult(BaseModel):
    query: str = Field(description="Standalone search query.")


class Answer(BaseModel):
    answer: str
    citations: list[str] = Field(description="Section IDs used, exactly as given, e.g. 'leave-policy §3.4'.")
    sufficient: bool = Field(description="True only if the evidence fully supports the answer.")
    missing_info: str | None = Field(
        default=None, description="If not sufficient: what the policies do not cover."
    )
