"""Component 6: leave agent. A ReAct-style loop with native function calling over the leave tools.

Control policy (AI Agents lecture): step cap, repeated-call detection, explicit stop reason, HR decisions behind
a confirmation gate (enforced inside the tool).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..llm import chat_with_tools, load_prompt
from ..tools import ToolContext, execute, tools_for

MAX_STEPS = 6


@dataclass
class AgentResult:
    reply: str
    stop_reason: str  # "answered" | "max_steps" | "repeated_call"
    tool_calls: list[dict] = field(default_factory=list)
    steps: int = 0


def run(message: str, history: list[dict], ctx: ToolContext) -> AgentResult:
    version, template = load_prompt("leave_agent")
    profile = {k: v for k, v in ctx.profile.facts(ctx.today).items() if k != "today"}
    system = template.format(
        today=ctx.today.isoformat(),
        weekday=ctx.today.strftime("%A"),
        profile=json.dumps(profile, ensure_ascii=False),
    )
    messages: list[dict] = [
        {"role": "system", "content": system},
        *history[-8:],
        {"role": "user", "content": message},
    ]
    tools = tools_for(ctx)
    calls: list[dict] = []
    seen: dict[str, int] = {}

    for step in range(1, MAX_STEPS + 1):
        msg = chat_with_tools("leave_agent", version, messages, tools)
        if not msg.tool_calls:
            return AgentResult(msg.content or "", "answered", calls, step)
        messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            }
        )
        for tc in msg.tool_calls:
            key = f"{tc.function.name}:{tc.function.arguments}"
            seen[key] = seen.get(key, 0) + 1
            if seen[key] > 2:
                result = {
                    "error": "repeated_call",
                    "message": "Same call, same result. Change approach or answer.",
                    "retryable": False,
                }
            else:
                result = execute(ctx, tc.function.name, tc.function.arguments, "leave_agent")
            calls.append(
                {
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments or "{}"),
                    "result": result,
                }
            )
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, default=str)}
            )
    return AgentResult(
        "Sorry, I couldn't complete this request. Please try again or contact HR.",
        "max_steps",
        calls,
        MAX_STEPS,
    )
