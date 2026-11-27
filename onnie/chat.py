"""Chat state shared by the GUI and the CLI.

Each chat owns:
  - its own agent (its own memory = the context fed to the model)
  - its own messages (with the thinking attached to each agent message)
  - a snapshot of the agent memory taken when the user leaves the chat

Everything is temporary: it lives in process memory only.
"""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from smolagents.memory import TaskStep
from smolagents import CodeAgent

from onnie.agent import StopStep, create_agent
from onnie.config import get_settings
from onnie.prompts import STOP_TEXT
from onnie.text_utils import join_thinking

MEMORY_FULL_WARNING = (
    "Memory is getting full. Onnie will lose some older conversation "
    "context as it makes room."
)


@dataclass(eq=False)
class Message:
    role: str  # "user" | "assistant"
    content: str
    thinking: str | None = None
    thinking_open: bool = False
    time: datetime = field(default_factory=datetime.now)


@dataclass(eq=False)  # identity comparison: chats are unique objects
class Chat:
    agent: CodeAgent
    queue: deque  # usage / warning events produced by the agent's step callback
    pending_thinking: list  # thinking of the run currently in progress
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "New chat"
    title_requested: bool = False
    created: datetime = field(default_factory=datetime.now)
    saved_steps: list = field(default_factory=list)  # agent memory while inactive
    messages: list[Message] = field(default_factory=list)
    tokens: int = 0
    warning: str = ""
    stop_requested: bool = False

    # ---------------- creation ----------------
    @classmethod
    def create(cls, verbosity: int = 2) -> "Chat":
        queue: deque = deque()
        pending_thinking: list = []
        agent = create_agent(queue, pending_thinking, verbosity=verbosity)
        return cls(agent=agent, queue=queue, pending_thinking=pending_thinking)

    # ---------------- messages ----------------
    def add_message(self, role: str, content: str, thinking: str | None = None) -> Message:
        message = Message(role=role, content=content, thinking=thinking)
        self.messages.append(message)
        return message

    @property
    def assistant_messages(self) -> list[Message]:
        return [m for m in self.messages if m.role == "assistant"]

    def thinking_text(self) -> str | None:
        """Thinking collected so far in the current run, joined as one text."""
        return join_thinking(self.pending_thinking)

    # ---------------- context isolation ----------------
    def save_context(self) -> None:
        """Snapshot the agent memory before leaving this chat."""
        self.saved_steps = list(self.agent.memory.steps)

    def load_context(self) -> None:
        """Load this chat's own saved context into ITS agent (and only its agent)."""
        self.agent.memory.steps = list(self.saved_steps)
        self.queue.clear()
        self.pending_thinking.clear()

    # ---------------- run lifecycle ----------------
    def consume_first_message(self) -> bool:
        """True exactly once: for the first user message of a chat (which is
        used to generate the chat title)."""
        is_first = not self.title_requested and not self.messages
        self.title_requested = True
        return is_first

    def begin_turn(self) -> None:
        self.pending_thinking.clear()
        self.stop_requested = False
        self.agent.interrupt_switch = False

    def end_turn(self) -> None:
        self.pending_thinking.clear()
        self.stop_requested = False

    def reset_after_naming(self) -> None:
        """Wipe the memory used for title generation so the real request starts clean."""
        self.agent.memory.reset()
        self.pending_thinking.clear()
        self.queue.clear()
        self.agent.interrupt_switch = False
        self.tokens = 0
        self.warning = ""

    # ---------------- stop ----------------
    def request_stop(self) -> bool:
        """Ask the agent to stop. Returns False if a stop was already requested."""
        if self.stop_requested:
            return False
        self.stop_requested = True
        self.agent.interrupt()  # smolagents stops at the next step boundary
        return True

    def remember_task(self, text: str) -> None:
        """Put a user request into the agent's memory without running it."""
        self.agent.memory.steps.append(TaskStep(task=text))

    def record_stop(self, thinking: str | None = None) -> None:
        """The stop is added to the agent's context as a user message, so the
        model knows it was interrupted when the chat continues."""
        self.agent.memory.steps.append(StopStep(task=STOP_TEXT))
        self.add_message("user", STOP_TEXT)
        self.add_message("assistant", "⏹ Stopped.", thinking=thinking)

    # ---------------- events ----------------
    def drain_events(self) -> list[str]:
        """Apply queued usage/warning events to this chat's state.

        Returns the *new* warnings (useful for the CLI, which prints them)."""
        trigger = get_settings().context_trigger
        new_warnings: list[str] = []
        while self.queue:
            event = self.queue.popleft()
            if event["type"] == "usage":
                self.tokens = event["tokens"]
                if event["tokens"] >= trigger and self.warning != MEMORY_FULL_WARNING:
                    self.warning = MEMORY_FULL_WARNING
                    new_warnings.append(MEMORY_FULL_WARNING)
            elif event["type"] == "warning":
                self.warning = event["message"]
                new_warnings.append(event["message"])
        return new_warnings
