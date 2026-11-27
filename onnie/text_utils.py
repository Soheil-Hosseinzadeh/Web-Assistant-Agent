"""Pure text helpers: thinking extraction and chat-title cleanup."""

from __future__ import annotations

import re

THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_think_tags(text: str) -> str:
    return THINK_TAG_RE.sub("", text or "").strip()


def extract_thinking(memory_step) -> str:
    """Return what the model thought and did in this step as plain text:
    its reasoning, the thought/code it wrote, and what came back. No step
    numbers and no headings, so steps read as one continuous flow."""
    parts = []

    msg = getattr(memory_step, "model_output_message", None)
    reasoning = getattr(msg, "reasoning_content", None) if msg else None
    if reasoning:
        parts.append(str(reasoning).strip())

    model_output = getattr(memory_step, "model_output", None)
    if isinstance(model_output, list):
        model_output = " ".join(str(x) for x in model_output)
    if model_output:
        text = str(model_output)
        text = re.sub(r"</?think>", "", text, flags=re.IGNORECASE)
        text = text.replace("<end_code>", "").strip()
        if text:
            parts.append(text)

    observation = getattr(memory_step, "observations", None)
    if observation:
        parts.append(f"```text\n{str(observation).strip()[:4000]}\n```")

    error = getattr(memory_step, "error", None)
    if error:
        parts.append(f"```text\n{str(error).strip()[:2000]}\n```")

    return "\n\n".join(parts)


def join_thinking(chunks) -> str | None:
    return "\n\n".join(c for c in chunks if c).strip() or None


def clean_title(text: str) -> str:
    """Fallback title: the user's request, shortened."""
    text = re.sub(r"\s+", " ", text).strip()
    return (text[:34] + "…") if len(text) > 35 else (text or "New chat")


def clean_chat_name(raw: str, fallback: str) -> str:
    """Turn the agent's answer into a short sidebar title (max 5 words)."""
    text = strip_think_tags(raw or "")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    first = lines[0] if lines else ""
    first = first.strip().strip("\"'`*#.:;!?").strip()
    title = " ".join(first.split()[:5])
    return title or clean_title(fallback)
