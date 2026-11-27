"""Builds the LLM model and one independent CodeAgent per chat."""

from __future__ import annotations

from collections import deque
from functools import lru_cache

from smolagents import CodeAgent, LiteLLMModel

from onnie.config import get_settings
from onnie.text_utils import extract_thinking
from onnie.tools import attach_requested_screenshots, default_tools

# Python modules the agent's generated code is allowed to import.
AUTHORIZED_IMPORTS = [
    "requests",
    "bs4",
    "PIL",
    "json",
    "datetime",
    "re",
    "numpy",
    "pandas",
    "urllib",
    "httpx",
]


@lru_cache(maxsize=1)
def get_model() -> LiteLLMModel:
    """The model is stateless, so one instance is shared by every chat."""
    s = get_settings()
    return LiteLLMModel(
        model_id=s.model,
        api_base=s.base_url,
        api_key=s.api_key,
        num_ctx=s.context_length,
        temperature=s.temperature,
        flatten_messages_as_text=False,
    )


def _trim_memory(agent: CodeAgent, event_queue: deque) -> None:
    """Keep only the newest part of the agent's history and tell the UI."""
    keep_ratio = get_settings().keep_ratio
    steps = agent.memory.steps
    old_count = len(steps)
    keep_count = max(1, int(old_count * keep_ratio))
    agent.memory.steps = steps[-keep_count:]
    event_queue.append(
        {
            "type": "warning",
            "message": (
                f"Memory is getting full. Onnie has trimmed older history "
                f"and kept the newest {keep_count} of {old_count} steps "
                f"to make room for the next request."
            ),
        }
    )


def _make_step_callback(event_queue: deque, thinking_sink: list):
    settings = get_settings()

    def on_step(memory_step, agent):
        usage = getattr(memory_step, "token_usage", None)
        input_tokens = getattr(usage, "input_tokens", None) if usage else None

        if input_tokens is not None:
            event_queue.append(
                {
                    "type": "usage",
                    "tokens": int(input_tokens),
                    "limit": settings.context_length,
                    "threshold": settings.context_threshold,
                }
            )

        thinking = extract_thinking(memory_step)
        if thinking:
            thinking_sink.append(thinking)

        # When a request's input context reaches the threshold, retain the
        # newest part of this agent's history.
        if input_tokens is not None and input_tokens >= settings.context_trigger:
            _trim_memory(agent, event_queue)

    return on_step


def create_agent(event_queue: deque, thinking_sink: list, verbosity: int = 2) -> CodeAgent:
    """Create an independent agent/memory for one chat.

    event_queue   -> usage / warning events for the UI
    thinking_sink -> list that collects the thinking of every step of the
                     current run (owned by exactly one chat)
    """
    settings = get_settings()
    return CodeAgent(
        tools=default_tools(include_vision=settings.enable_vision_tools),
        model=get_model(),
        max_steps=settings.max_steps,
        verbosity_level=verbosity,
        instructions=settings.instructions,
        step_callbacks=[
            attach_requested_screenshots,
            _make_step_callback(event_queue, thinking_sink),
        ],
        executor_kwargs={"timeout_seconds": settings.executor_timeout},
        additional_authorized_imports=AUTHORIZED_IMPORTS,
    )
