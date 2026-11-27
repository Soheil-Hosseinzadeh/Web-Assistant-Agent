"""Terminal interface for Onnie.

Chats are kept in memory only. While the agent works, a spinner is shown and
single keys are read without Enter: ``t`` toggles the live thinking view,
``s`` (or Ctrl+C) stops the agent.
"""

from __future__ import annotations

import threading

from rich.markup import escape

from onnie.chat import Chat
from onnie.cli.keyreader import KeyReader
from onnie.cli.render import Renderer
from onnie.config import get_settings
from onnie.prompts import TITLE_PROMPT
from onnie.text_utils import clean_chat_name, clean_title, join_thinking


class CliApp:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.view = Renderer(self.settings)
        self.console = self.view.console
        self.chats: list[Chat] = []  # creation order; displayed number = index + 1
        self.active: Chat | None = None
        self._commands = {
            "help": self.cmd_help, "h": self.cmd_help, "?": self.cmd_help,
            "new": self.cmd_new,
            "chats": self.cmd_chats, "list": self.cmd_chats, "ls": self.cmd_chats,
            "switch": self.cmd_switch, "open": self.cmd_switch, "go": self.cmd_switch,
            "think": self.cmd_think, "thinking": self.cmd_think,
            "history": self.cmd_history, "redraw": self.cmd_history, "clear": self.cmd_history,
            "context": self.cmd_context, "ctx": self.cmd_context,
            "info": self.cmd_info,
        }

    # ==================================================================
    # Main loop
    # ==================================================================
    def run(self) -> None:
        self.cmd_new()
        while True:
            chat = self.active
            prompt = (
                f"[bold bright_cyan]{escape(chat.title[:30])}[/] [dim]·[/] "
                f"[dim]{chat.tokens:,}/{self.settings.context_length:,}[/] "
                f"[bold bright_magenta]❯[/] "
            )
            try:
                line = self.console.input(prompt).strip()
            except EOFError:
                break
            except KeyboardInterrupt:
                self.console.print("\n[dim]Type /quit to exit.[/]")
                continue
            if not line:
                continue
            if line.startswith("/"):
                if not self.handle_command(line):
                    break
            else:
                self.handle_message(chat, line)
        self.console.print("[dim]Bye![/]")

    # ==================================================================
    # Commands
    # ==================================================================
    def handle_command(self, line: str) -> bool:
        """Returns False when the app should exit."""
        parts = line[1:].split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""
        if cmd in ("quit", "exit", "q"):
            return False
        handler = self._commands.get(cmd)
        if handler is None:
            self.console.print(f"[yellow]Unknown command '/{escape(cmd)}'. Type /help.[/]")
        else:
            handler(arg)
        return True

    def cmd_help(self, arg: str = "") -> None:
        self.view.help()

    def cmd_info(self, arg: str = "") -> None:
        self.view.info()

    def cmd_chats(self, arg: str = "") -> None:
        self.view.chat_list(self.chats, self.active)

    def cmd_history(self, arg: str = "") -> None:
        self.redraw(self.active)

    def cmd_context(self, arg: str = "") -> None:
        chat = self.active
        self.console.print(f"  {self.view.context_bar(chat.tokens)}")
        if chat.warning:
            self.view.warning(chat.warning)

    def cmd_new(self, arg: str = "") -> None:
        self._leave_current_chat()
        chat = Chat.create(verbosity=-1)
        self.chats.append(chat)
        self.active = chat
        self.redraw(chat)

    def cmd_switch(self, arg: str = "") -> None:
        if not arg.isdigit() or not 1 <= int(arg) <= len(self.chats):
            self.console.print(
                f"[yellow]Usage: /switch N  (N between 1 and {len(self.chats)}, see /chats)[/]"
            )
            return
        target = self.chats[int(arg) - 1]
        if target is self.active:
            self.console.print("[dim]Already in that chat.[/]")
            return
        # Save chat A's context, then load only chat B's context into B's agent.
        self._leave_current_chat()
        self.active = target
        target.load_context()
        self.redraw(target)

    def cmd_think(self, arg: str = "") -> None:
        chat = self.active
        assistants = chat.assistant_messages
        if not assistants:
            self.console.print("[yellow]There is no agent message in this chat yet.[/]")
            return
        if arg:
            if not arg.isdigit() or not 1 <= int(arg) <= len(assistants):
                self.console.print(f"[yellow]Choose a number between 1 and {len(assistants)}.[/]")
                return
            msg = assistants[int(arg) - 1]
        else:
            msg = assistants[-1]
        if not msg.thinking:
            self.console.print("[yellow]That message has no recorded thinking.[/]")
            return
        msg.thinking_open = not msg.thinking_open
        self.redraw(chat)

    # ==================================================================
    # Helpers
    # ==================================================================
    def _leave_current_chat(self) -> None:
        if self.active:
            self.active.save_context()

    def redraw(self, chat: Chat) -> None:
        self.view.chat(chat, self.chats.index(chat) + 1, len(self.chats))

    def _print_last_assistant(self, chat: Chat) -> None:
        self.view.assistant(chat.messages[-1], len(chat.assistant_messages))

    def _request_stop(self, chat: Chat) -> None:
        if chat.request_stop():
            self.console.print("[bold red]⏹ Stop requested — stopping the agent…[/]")

    def _show_new_warnings(self, chat: Chat) -> None:
        for warning in chat.drain_events():
            self.view.warning(warning)

    def _record_stop(self, chat: Chat, thinking: str | None) -> None:
        chat.record_stop(thinking)
        self.view.user(chat.messages[-2].content)
        self._print_last_assistant(chat)

    # ==================================================================
    # Sending messages
    # ==================================================================
    def handle_message(self, chat: Chat, value: str) -> None:
        is_first = chat.consume_first_message()
        chat.add_message("user", value)
        self.view.user(value)
        chat.begin_turn()
        agent = chat.agent

        try:
            # First message: ask the agent for a topic, name the chat with it,
            # wipe the agent's memory, then run the real request cleanly.
            if is_first:
                result = self.run_background(
                    chat,
                    lambda: agent.run(TITLE_PROMPT.replace("{user_request}", value), reset=True),
                    "Naming chat",
                    live_enabled=False,
                )
                if "error" in result:
                    chat.title = clean_title(value)
                else:
                    chat.title = clean_chat_name(str(result["value"]), value)
                chat.reset_after_naming()
                self.console.print(f"[dim]Chat named:[/] [bold]{escape(chat.title)}[/]")

                if chat.stop_requested:
                    chat.remember_task(value)
                    self._record_stop(chat, None)
                    return

            result = self.run_background(
                chat, lambda: agent.run(value, reset=False), "Onnie is working", live_enabled=True
            )
            thinking = chat.thinking_text()
            if "error" in result:
                exc = result["error"]
                if chat.stop_requested:
                    self._record_stop(chat, thinking)
                else:
                    chat.add_message(
                        "assistant",
                        f"**Something went wrong:** `{type(exc).__name__}: {exc}`",
                        thinking=thinking,
                    )
                    self._print_last_assistant(chat)
            else:
                chat.add_message("assistant", str(result["value"]), thinking=thinking)
                self._print_last_assistant(chat)
        finally:
            chat.end_turn()
            self.console.print(f"  {self.view.context_bar(chat.tokens)}\n")

    def run_background(self, chat: Chat, fn, label: str, live_enabled: bool) -> dict:
        """Run fn in a worker thread while showing a spinner. `t` toggles the
        live thinking view, `s` / Ctrl+C stops the agent."""
        result: dict = {}

        def worker():
            try:
                result["value"] = fn()
            except Exception as exc:  # noqa: BLE001
                result["error"] = exc

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        live = {"open": False, "printed": 0}
        hint = (
            "  [dim]\\[t] thinking now · \\[s] stop[/]"
            if live_enabled
            else "  [dim]\\[s] stop[/]"
        )
        limit = self.settings.context_length

        with self.console.status(f"[bright_cyan]{label}…[/]{hint}", spinner="dots") as status:
            with KeyReader() as keys:
                while True:
                    try:
                        if not thread.is_alive():
                            break
                        key = keys.poll(0.15)
                        if key in ("s", "S"):
                            self._request_stop(chat)
                        elif key in ("t", "T") and live_enabled:
                            live["open"] = not live["open"]
                            if live["open"]:
                                live["printed"] = 0
                                self.console.print("[dim magenta]— live thinking on —[/]")
                            else:
                                self.console.print("[dim magenta]— live thinking hidden —[/]")
                        self._show_new_warnings(chat)
                        if live["open"]:
                            chunks = list(chat.pending_thinking)
                            if len(chunks) > live["printed"]:
                                text = join_thinking(chunks[live["printed"]:])
                                live["printed"] = len(chunks)
                                if text:
                                    self.view.thinking_panel(text, "THINKING NOW")
                        status.update(
                            f"[bright_cyan]{'Stopping' if chat.stop_requested else label}…[/]"
                            f"{hint}  [dim]{chat.tokens:,}/{limit:,} tokens[/]"
                        )
                    except KeyboardInterrupt:
                        self._request_stop(chat)
        thread.join()
        self._show_new_warnings(chat)
        return result


def run_cli() -> None:
    CliApp().run()
