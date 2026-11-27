"""Custom smolagents memory steps."""

from smolagents.memory import TaskStep
from smolagents.models import ChatMessage, MessageRole


class StopStep(TaskStep):
    """A memory step that reaches the model as a plain *user* message
    (no 'New task:' prefix), used when the user presses the stop button."""

    def to_messages(self, summary_mode: bool = False):
        return [
            ChatMessage(
                role=MessageRole.USER,
                content=[{"type": "text", "text": self.task}],
            )
        ]
