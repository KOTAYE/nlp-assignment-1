"""Component 7: HR referral. The LLM summarises the case and calls the `create_hr_ticket` tool (the database is
reached only through this LLM tool call)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from ..llm import chat_with_tools, load_prompt
from ..tools import REFERRAL_TOOLS, ToolContext, execute


@dataclass
class Referral:
    ticket_id: int | None
    category: str | None
    summary: str | None
    reply: str


def refer(question: str, reason: str, ctx: ToolContext, profile_facts: dict[str, str]) -> Referral:
    version, template = load_prompt("referral")
    system = template.format(
        today=ctx.today.isoformat(), reason=reason, profile=json.dumps(profile_facts, ensure_ascii=False)
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]
    msg = chat_with_tools(
        "referral",
        version,
        messages,
        REFERRAL_TOOLS,
        tool_choice={"type": "function", "function": {"name": "create_hr_ticket"}},
    )
    for call in msg.tool_calls or []:
        result = execute(ctx, call.function.name, call.function.arguments, "referral")
        if "ticket_id" in result:
            args = json.loads(call.function.arguments)
            reply = (
                f"The company policies don't fully cover this, so I've passed your question to the HR team: "
                f"ticket #{result['ticket_id']} ({args['category'].replace('_', ' ')}). "
                f"HR replies within 2 working days, or you can write to hr@lumora.example."
            )
            return Referral(result["ticket_id"], args["category"], args["summary"], reply)
    return Referral(
        None, None, None, "I couldn't create an HR ticket automatically. Please write to hr@lumora.example."
    )
