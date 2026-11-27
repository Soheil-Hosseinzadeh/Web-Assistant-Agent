"""Terminal rendering for the CLI (everything that prints with `rich`)."""

from __future__ import annotations

from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from onnie.chat import Chat, Message
from onnie.config import Settings
from onnie.prompts import INFO_TEXT

HELP_ROWS = [
    ("/new", "Create a new chat"),
    ("/chats", "List all chats"),
    ("/switch N", "Go to chat number N (its saved context is loaded)"),
    ("/think [N]", "Toggle the thinking of agent message N (default: last one)"),
    ("/history", "Redraw the current chat"),
    ("/context", "Show the context window usage"),
    ("/info", "About Onnie"),
    ("/help", "Show this help"),
    ("/quit", "Exit"),
    ("t  (while working)", "Show / hide the live 'thinking now' view"),
    ("s or Ctrl+C  (while working)", "Stop the agent right now"),
]


class Renderer:
    def __init__(self, settings: Settings, console: Console | None = None):
        self.settings = settings
        self.console = console or Console()

    # ---------------- small pieces ----------------
    def context_bar(self, tokens: int) -> str:
        limit = self.settings.context_length
        ratio = min(tokens / limit, 1.0) if limit else 0
        width = 22
        filled = int(ratio * width)
        color = "yellow" if ratio >= self.settings.context_threshold else "bright_cyan"
        return (
            f"[{color}]{'█' * filled}[/][grey37]{'░' * (width - filled)}[/] "
            f"{tokens:,} / {limit:,} tokens ({ratio * 100:.0f}%)"
        )

    def warning(self, text: str) -> None:
        self.console.print(Panel(text, border_style="yellow", box=box.ROUNDED))

    def message(self, text: str) -> None:
        self.console.print(text)

    # ---------------- panels ----------------
    def header(self, chat: Chat, number: int, total: int) -> None:
        body = (
            f"[bold]{escape(chat.title)}[/]  [dim]chat {number} of {total}[/]\n"
            f"{self.context_bar(chat.tokens)}"
        )
        self.console.print(
            Panel(
                body,
                title="[bold bright_cyan]✦ ONNIE · WEB ASSISTANT AGENT[/]",
                title_align="left",
                subtitle="[dim]/help for commands[/]",
                border_style="bright_cyan",
                box=box.ROUNDED,
            )
        )

    def user(self, content: str) -> None:
        self.console.print(
            Panel(
                Markdown(content),
                title="[bold #9ab5e9]You[/]",
                title_align="left",
                border_style="#29425f",
                box=box.ROUNDED,
            )
        )

    def thinking_panel(self, text: str, title: str = "THINKING") -> None:
        self.console.print(
            Panel(
                Markdown(text),
                title=f"[bold bright_magenta]{title}[/]",
                title_align="left",
                border_style="magenta",
                box=box.ROUNDED,
            )
        )

    def assistant(self, msg: Message, number: int) -> None:
        if msg.thinking and msg.thinking_open:
            self.thinking_panel(msg.thinking)
        if msg.thinking:
            arrow = "▾" if msg.thinking_open else "▸"
            title = (
                f"[bold bright_magenta]{arrow} thinking[/] [dim](/think {number})[/]"
                f"  [bold bright_cyan]ONNIE[/]"
            )
        else:
            title = "[bold bright_cyan]ONNIE[/]"
        self.console.print(
            Panel(
                Markdown(msg.content),
                title=title,
                title_align="left",
                border_style="cyan",
                box=box.ROUNDED,
            )
        )

    def chat(self, chat: Chat, number: int, total: int) -> None:
        """Clear the screen and redraw a whole chat."""
        self.console.clear()
        self.header(chat, number, total)
        if not chat.messages:
            self.console.print(
                "\n  [bold]What can I help you with?[/]\n"
                "  [dim]Ask Onnie to research, browse, analyze, or build something.[/]\n"
            )
        assistant_number = 0
        for msg in chat.messages:
            if msg.role == "user":
                self.user(msg.content)
            else:
                assistant_number += 1
                self.assistant(msg, assistant_number)
        if chat.warning:
            self.warning(chat.warning)

    def chat_list(self, chats: list[Chat], active: Chat | None) -> None:
        table = Table(box=box.SIMPLE_HEAVY, border_style="bright_cyan")
        table.add_column("#", justify="right")
        table.add_column("Chat")
        table.add_column("Created")
        table.add_column("Context", justify="right")
        for i, chat in enumerate(chats, start=1):
            marker = "[bold bright_cyan]▶[/] " if chat is active else "  "
            table.add_row(
                str(i),
                marker + escape(chat.title),
                chat.created.strftime("%H:%M"),
                f"{chat.tokens:,}/{self.settings.context_length:,}",
            )
        self.console.print(table)

    def help(self) -> None:
        table = Table(box=box.SIMPLE, show_header=False, border_style="bright_cyan")
        table.add_column(style="bold bright_cyan", no_wrap=True)
        table.add_column()
        for cmd, desc in HELP_ROWS:
            table.add_row(escape(cmd), desc)
        self.console.print(
            Panel(table, title="[bold]Commands[/]", border_style="bright_cyan", box=box.ROUNDED)
        )

    def info(self) -> None:
        self.console.print(
            Panel(
                Markdown(INFO_TEXT),
                title="[bold bright_cyan]✦ ABOUT ONNIE ✦[/]",
                subtitle="[bold bright_magenta]who I am and what I can do[/]",
                border_style="bright_magenta",
                box=box.DOUBLE,
                padding=(1, 3),
            )
        )
