"""The only place where the language model is called.

Every call is traced (component, prompt version, model, messages, output, tokens, cost, latency) into the
current trace and into `logs/traces/*.jsonl`. Tools record their calls through `trace_event` as well, so one
trace shows how a single input passes through the whole system.
"""

from __future__ import annotations

import contextvars
import datetime as dt
import json
import time
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from .config import get_settings

PROMPTS_DIR = Path(__file__).parent / "prompts"
T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------- tracing


@dataclass
class Trace:
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def llm_calls(self) -> list[dict[str, Any]]:
        return [e for e in self.events if e["kind"] == "llm"]

    @property
    def tokens(self) -> int:
        return sum(e.get("tokens_in", 0) + e.get("tokens_out", 0) for e in self.llm_calls)

    @property
    def cost_usd(self) -> float:
        return round(sum(e.get("cost_usd") or 0.0 for e in self.llm_calls), 6)


_current: contextvars.ContextVar[Trace | None] = contextvars.ContextVar("trace", default=None)


def start_trace() -> Trace:
    trace = Trace()
    _current.set(trace)
    return trace


def current_trace() -> Trace:
    trace = _current.get()
    if trace is None:
        trace = start_trace()
    return trace


def trace_event(kind: str, component: str, **data: Any) -> dict[str, Any]:
    event = {"ts": dt.datetime.now().isoformat(timespec="milliseconds"), "kind": kind, "component": component}
    event.update(data)
    trace = current_trace()
    event["trace_id"] = trace.trace_id
    trace.events.append(event)
    settings = get_settings()
    settings.traces_dir.mkdir(parents=True, exist_ok=True)
    with (settings.traces_dir / f"{dt.date.today().isoformat()}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
    return event


# ---------------------------------------------------------------- prompts


@lru_cache(maxsize=64)
def load_prompt(name: str) -> tuple[str, str]:
    """Return (version, text) of `prompts/<name>.md`. The first line must be `version: N`."""
    raw = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    first, _, body = raw.partition("\n")
    if not first.startswith("version:"):
        raise ValueError(f"Prompt {name} must start with 'version: N'")
    return first.split(":", 1)[1].strip(), body.strip()


# ---------------------------------------------------------------- client


@lru_cache(maxsize=1)
def client() -> OpenAI:
    s = get_settings()
    if not s.llm_api_key:
        raise RuntimeError("LLM_API_KEY is not set (see .env.example)")
    return OpenAI(api_key=s.llm_api_key, base_url=s.llm_base_url, timeout=60, max_retries=2)


def _usage(resp: Any) -> dict[str, Any]:
    u = getattr(resp, "usage", None)
    if u is None:
        return {}
    return {
        "tokens_in": getattr(u, "prompt_tokens", 0) or 0,
        "tokens_out": getattr(u, "completion_tokens", 0) or 0,
        "cost_usd": getattr(u, "cost", None),  # OpenRouter usage accounting
    }


def _create(component: str, prompt_version: str, model: str, messages: list[dict], **kwargs: Any) -> Any:
    t0 = time.perf_counter()
    error = None
    resp = None
    try:
        resp = client().chat.completions.create(
            model=model, messages=messages, extra_body={"usage": {"include": True}}, **kwargs
        )
        return resp
    except Exception as e:  # traced, then re-raised
        error = f"{type(e).__name__}: {e}"
        raise
    finally:
        msg = resp.choices[0].message if resp is not None else None
        trace_event(
            "llm",
            component,
            model=model,
            prompt_version=prompt_version,
            messages=messages,
            output=(msg.content if msg else None),
            tool_calls=[
                {"name": tc.function.name, "arguments": tc.function.arguments}
                for tc in (msg.tool_calls or [])
            ]
            if msg
            else [],
            latency_ms=round((time.perf_counter() - t0) * 1000),
            error=error,
            **(_usage(resp) if resp is not None else {}),
        )


def complete_json[T: BaseModel](
    component: str,
    prompt: str,
    user: str,
    schema: type[T],
    *,
    model: str | None = None,
    temperature: float = 0.0,
    history: list[dict] | None = None,
) -> T:
    """Call the LLM with the system prompt `prompts/<prompt>.md` and parse a structured output.

    The JSON schema is passed as `response_format`; the result is validated with Pydantic and retried once
    with the validation error if it does not match (instructive feedback instead of silent failure).
    """
    version, system = load_prompt(prompt)
    model = model or get_settings().llm_model
    messages: list[dict] = [
        {"role": "system", "content": system},
        *(history or []),
        {"role": "user", "content": user},
    ]
    response_format = {
        "type": "json_schema",
        "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema(), "strict": False},
    }
    for attempt in range(2):
        resp = _create(
            component, version, model, messages, temperature=temperature, response_format=response_format
        )
        content = resp.choices[0].message.content or ""
        try:
            return schema.model_validate_json(content)
        except ValidationError as e:
            if attempt == 1:
                raise
            messages = [
                *messages,
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": f"Your output did not match the schema: {e.errors()[:3]}. Return valid JSON only.",
                },
            ]
    raise AssertionError("unreachable")


def chat_with_tools(
    component: str,
    prompt_version: str,
    messages: list[dict],
    tools: list[dict],
    *,
    tool_choice: str | dict = "auto",
    model: str | None = None,
    temperature: float = 0.0,
) -> Any:
    """One step of an agent loop with native function calling. Returns the assistant message."""
    resp = _create(
        component,
        prompt_version,
        model or get_settings().llm_model,
        messages,
        tools=tools,
        tool_choice=tool_choice,
        temperature=temperature,
        parallel_tool_calls=False,
    )
    return resp.choices[0].message
