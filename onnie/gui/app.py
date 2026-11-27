"""NiceGUI web interface for Onnie.

One :class:`ChatPage` is created per browser session. All chat state is
temporary (kept in memory only) and strictly isolated per chat.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nicegui import run, ui

from onnie.chat import Chat, Message
from onnie.config import get_settings
from onnie.gui.theme import CSS, FONTS_HTML, LOGO_HTML
from onnie.prompts import INFO_TEXT, TITLE_PROMPT
from onnie.text_utils import clean_chat_name, clean_title


@dataclass
class LiveBlock:
    """The temporary 'Thinking now…' block shown while the agent is working."""

    active: bool = False
    open: bool = False
    last: str | None = None
    md: Any = None
    box: Any = None
    btn: Any = None

    def start(self) -> None:
        self.active, self.open, self.last = True, False, ""
        self.md = self.box = self.btn = None

    def end(self) -> None:
        self.active, self.last = False, None
        self.md = self.box = self.btn = None


def _apply_toggle_state(button, box, is_open: bool) -> None:
    """Show/hide a thinking box and highlight its button accordingly."""
    box.set_visibility(is_open)
    if is_open:
        button.classes(add="think-active")
    else:
        button.classes(remove="think-active")


class ChatPage:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.chats: dict[str, Chat] = {}
        self.active_id: str | None = None
        self.running = False
        self.live = LiveBlock()

        # Widgets (assigned while building the layout)
        self.message_area = None
        self.chat_list = None
        self.context_label = None
        self.context_bar = None
        self.context_warning = None
        self.composer = None
        self.send_button = None
        self.stop_button = None
        self.status_label = None
        self.info_dialog = None

    @property
    def active(self) -> Chat | None:
        return self.chats.get(self.active_id)

    # ==================================================================
    # Layout
    # ==================================================================
    def build(self) -> None:
        self._build_info_dialog()
        with ui.row().classes("app-shell w-full no-wrap"):
            self._build_sidebar()
            with ui.column().classes("main-panel"):
                self._build_topbar()
                with ui.row().classes("toolbar w-full items-center justify-between"):
                    ui.label("Conversation").classes("text-lg font-semibold text-slate-100")
                self.message_area = ui.column().classes("conversation w-full")
                self._build_composer()

        # A timer drains step callbacks while the blocking agent runs in a worker thread.
        ui.timer(0.25, self.process_events)
        self.new_chat()

    def _build_info_dialog(self) -> None:
        with ui.dialog() as self.info_dialog:
            with ui.card().classes("neon-card"):
                with ui.column().classes("neon-head w-full gap-1"):
                    ui.label("ABOUT ONNIE").classes("neon-title")
                    ui.label("who I am and what I can do").classes("neon-sub")
                with ui.column().classes("neon-body w-full"):
                    ui.markdown(INFO_TEXT).classes("message-content")
                with ui.row().classes("neon-foot w-full justify-end"):
                    ui.button("CLOSE", on_click=self.info_dialog.close).props(
                        "flat no-caps"
                    ).classes("neon-close")

    def _build_sidebar(self) -> None:
        with ui.column().classes("sidebar"):
            with ui.row().classes("items-center gap-3 px-5 pt-6 pb-7"):
                ui.html(LOGO_HTML)
                with ui.column().classes("gap-0"):
                    ui.label("ONNIE").classes("brand-title")
            ui.button("New chat", icon="add", on_click=self.new_chat).props(
                "unelevated"
            ).classes("new-chat-btn mx-4 mb-5")
            ui.label("YOUR CHATS").classes("sidebar-heading px-5")
            self.chat_list = ui.column().classes("w-full px-3 gap-1")
            ui.element("div").classes("flex-1")
            with ui.column().classes("px-5 pb-5 gap-2"):
                ui.label("LOCAL SESSION").classes("sidebar-heading")
                ui.label("Chats stay in this running app session.").classes(
                    "text-xs text-slate-500 leading-relaxed"
                )

    def _build_topbar(self) -> None:
        limit = self.settings.context_length
        with ui.row().classes("topbar w-full items-center justify-between"):
            ui.label("WEB ASSISTANT AGENT").classes("topbar-heading")

            with ui.row().classes("items-center gap-3"):
                self.status_label = ui.label("Ready").classes("status-pill")

                with ui.column().classes("context-card gap-2"):
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label("CONTEXT WINDOW").classes("context-title")
                        self.context_label = ui.label(f"0 / {limit:,} tokens").classes(
                            "context-value"
                        )
                    with ui.element("div").classes("context-track"):
                        self.context_bar = (
                            ui.element("div").classes("context-fill").style("width:0%")
                        )
                    self.context_warning = ui.label("").classes("context-warning")
                    self.context_warning.set_visibility(False)

                ui.button(icon="info", on_click=self.info_dialog.open).props(
                    "flat round"
                ).classes("top-icon").tooltip("About Onnie")

    def _build_composer(self) -> None:
        with ui.column().classes("composer-wrap w-full"):
            with ui.row().classes("composer w-full items-center"):
                self.composer = (
                    ui.textarea(placeholder="Message Onnie…")
                    .props("autogrow rows=1")
                    .classes("composer-input")
                )
                self.send_button = (
                    ui.button(icon="send", on_click=lambda: self.send_message())
                    .props("round unelevated")
                    .classes("send-btn")
                )
                self.stop_button = (
                    ui.button(icon="stop", on_click=self.stop_agent)
                    .props("round unelevated")
                    .classes("stop-btn")
                    .tooltip("Stop")
                )
                self.stop_button.set_visibility(False)
            ui.label(
                "Onnie can make mistakes. Review important information and actions."
            ).classes("composer-note")

    # ==================================================================
    # Chat management
    # ==================================================================
    def new_chat(self) -> None:
        if self.running:
            ui.notify(
                "Wait for the current response to finish before opening a new chat.",
                type="warning",
            )
            return
        self._leave_current_chat()
        chat = Chat.create(verbosity=2)
        self.chats[chat.id] = chat
        self.active_id = chat.id
        self.render_chat_list()
        self.render_messages()
        self.update_context(0, "")
        self.status_label.set_text("Ready")

    def switch_chat(self, chat_id: str) -> None:
        if self.running:
            ui.notify(
                "Wait for the current response to finish before switching chats.",
                type="warning",
            )
            return
        if chat_id == self.active_id or chat_id not in self.chats:
            return
        # 1) save chat A's context, 2) load chat B's context into B's agent.
        # A's agent is never touched again until the user returns to A.
        self._leave_current_chat()
        self.active_id = chat_id
        chat = self.active
        chat.load_context()
        self.render_chat_list()
        self.render_messages()
        self.update_context(chat.tokens, chat.warning)
        self.status_label.set_text("Ready")

    def _leave_current_chat(self) -> None:
        if self.active:
            self.active.save_context()

    def add_message(self, chat: Chat, role: str, content: str, thinking: str | None = None) -> None:
        self.live.end()
        chat.add_message(role, content, thinking=thinking)
        if chat.id == self.active_id:
            self.render_messages()

    # ==================================================================
    # Rendering
    # ==================================================================
    def render_chat_list(self) -> None:
        if self.chat_list is None:
            return
        self.chat_list.clear()
        with self.chat_list:
            for chat_id, chat in reversed(list(self.chats.items())):
                selected = chat_id == self.active_id
                with ui.row().classes(
                    "sidebar-chat selected-chat" if selected else "sidebar-chat"
                ).on("click", lambda cid=chat_id: self.switch_chat(cid)):
                    ui.icon("chat_bubble_outline").classes("text-slate-400")
                    with ui.column().classes("min-w-0 flex-1 gap-0"):
                        ui.label(chat.title).classes(
                            "chat-title text-sm text-slate-200"
                        )
                        ui.label(chat.created.strftime("%H:%M")).classes(
                            "text-xs text-slate-500"
                        )
                    if selected:
                        ui.icon("circle").classes("text-cyan-400 text-xs")

    def render_messages(self) -> None:
        if self.message_area is None:
            return
        self.message_area.clear()
        chat = self.active
        if not chat:
            return
        with self.message_area:
            if not chat.messages:
                self._render_empty_state()
            for msg in chat.messages:
                is_user = msg.role == "user"
                with ui.row().classes("w-full justify-end" if is_user else "w-full justify-start"):
                    if is_user:
                        with ui.column().classes("message-bubble user-bubble"):
                            ui.label("You").classes("message-author")
                            ui.markdown(msg.content).classes("message-content")
                    else:
                        self._render_assistant_message(msg)
            if self.live.active:
                self._render_live_block()
        ui.run_javascript(
            "const c=document.querySelector('.conversation');"
            "if(c){c.scrollTo({top:c.scrollHeight,behavior:'smooth'});}"
        )

    @staticmethod
    def _render_empty_state() -> None:
        with ui.column().classes("w-full items-center justify-center py-16 gap-3"):
            ui.html('<div class="empty-orb">✦</div>')
            ui.label("What can I help you with?").classes("text-2xl font-semibold text-slate-100")
            ui.label("Ask Onnie to research, browse, analyze, or build something.").classes(
                "text-sm text-slate-400"
            )

    @staticmethod
    def _render_assistant_message(msg: Message) -> None:
        with ui.column().classes("assistant-wrap"):
            if msg.thinking:
                think_btn = (
                    ui.button("Thinking", icon="psychology")
                    .props("flat dense no-caps")
                    .classes("think-btn")
                )
                with ui.column().classes("message-bubble thinking-bubble") as thinking_box:
                    ui.label("THINKING").classes("message-author")
                    ui.markdown(msg.thinking).classes("message-content")
                _apply_toggle_state(think_btn, thinking_box, msg.thinking_open)

                def toggle(m=msg, box=thinking_box, btn=think_btn):
                    m.thinking_open = not m.thinking_open
                    _apply_toggle_state(btn, box, m.thinking_open)

                think_btn.on("click", toggle)

            with ui.column().classes("message-bubble assistant-bubble"):
                ui.label("ONNIE").classes("message-author")
                ui.markdown(msg.content).classes("message-content")

    def _render_live_block(self) -> None:
        """Temporary agent box shown while the agent works. A centered
        'Thinking now…' button toggles the live thinking text."""
        live = self.live
        with ui.column().classes("assistant-wrap"):
            with ui.row().classes("w-full justify-center"):
                btn = (
                    ui.button("Thinking now…", icon="psychology")
                    .props("flat dense no-caps")
                    .classes("think-btn think-live")
                )
            with ui.column().classes("message-bubble thinking-bubble") as box:
                ui.label("THINKING NOW").classes("message-author")
                md = ui.markdown(live.last or "Waiting for the model…").classes("message-content")
            _apply_toggle_state(btn, box, live.open)

            def toggle():
                live.open = not live.open
                _apply_toggle_state(btn, box, live.open)

            btn.on("click", toggle)
            with ui.column().classes("message-bubble assistant-bubble"):
                ui.label("ONNIE").classes("message-author")
                ui.label("Working on it…").classes("live-working")
        live.md, live.box, live.btn = md, box, btn

    def update_context(self, tokens: int, warning: str) -> None:
        chat = self.active
        if chat:
            chat.tokens = tokens
            chat.warning = warning
        s = self.settings
        ratio = min(tokens / s.context_length, 1.0) if s.context_length else 0
        self.context_label.set_text(f"{tokens:,} / {s.context_length:,} tokens")
        self.context_bar.style(f"width: {ratio * 100:.1f}%")
        self.context_bar.classes(
            replace="context-fill" + (" context-danger" if ratio >= s.context_threshold else "")
        )
        self.context_warning.set_text(warning)
        self.context_warning.set_visibility(bool(warning))

    def set_running_ui(self, running: bool) -> None:
        self.running = running
        self.send_button.set_visibility(not running)
        self.stop_button.set_visibility(running)
        self.stop_button.enable()
        if running:
            self.composer.disable()
        else:
            self.composer.enable()

    # ==================================================================
    # Events / actions
    # ==================================================================
    async def process_events(self) -> None:
        chat = self.active
        if not chat:
            return
        # Drain events for the active chat only.
        if chat.queue:
            chat.drain_events()
            self.update_context(chat.tokens, chat.warning)

        live = self.live
        if live.active and live.md is not None:
            text = chat.thinking_text() or ""
            if text != live.last:
                live.last = text
                live.md.set_content(text or "Waiting for the model…")
                if live.open and live.box is not None:
                    ui.run_javascript(
                        f"const e=document.getElementById('c{live.box.id}');"
                        "if(e){e.scrollTop=e.scrollHeight;}"
                    )

    async def send_message(self, text: str | None = None) -> None:
        if self.running:
            return
        value = (text if text is not None else self.composer.value or "").strip()
        if not value:
            return
        chat = self.active
        if not chat:
            return

        is_first_message = chat.consume_first_message()
        self.composer.value = ""
        self.add_message(chat, "user", value)
        chat.begin_turn()
        self.set_running_ui(True)
        self.live.start()
        self.render_messages()
        try:
            # First message of a new chat: ask the agent for a short topic,
            # use it as the chat name, then wipe the agent's memory so the
            # real interaction starts clean with the user's first request.
            if is_first_message:
                await self._name_chat(chat, value)
                if chat.stop_requested:
                    # Stop was pressed while naming: do not start the real run.
                    chat.remember_task(value)
                    chat.record_stop()
                    self.status_label.set_text("Stopped")
                    return
            await self._run_request(chat, value)
        finally:
            if self.live.active:
                self.live.end()
                self.render_messages()
            chat.end_turn()
            self.set_running_ui(False)
            self.composer.run_method("focus")
            await self.process_events()

    async def _name_chat(self, chat: Chat, value: str) -> None:
        self.status_label.set_text("Naming chat…")
        try:
            title_result = await run.io_bound(
                chat.agent.run,
                TITLE_PROMPT.replace("{user_request}", value),
                reset=True,
            )
            chat.title = clean_chat_name(str(title_result), value)
        except Exception:  # noqa: BLE001
            chat.title = clean_title(value)
        self.render_chat_list()
        chat.reset_after_naming()
        self.update_context(0, "")

    async def _run_request(self, chat: Chat, value: str) -> None:
        self.status_label.set_text("Onnie is working…")
        try:
            result = await run.io_bound(chat.agent.run, value, reset=False)
            self.add_message(chat, "assistant", str(result), thinking=chat.thinking_text())
            self.status_label.set_text("Completed")
        except Exception as exc:  # noqa: BLE001
            thinking = chat.thinking_text()
            if chat.stop_requested:
                chat.record_stop(thinking)
                self.status_label.set_text("Stopped")
            else:
                self.add_message(
                    chat,
                    "assistant",
                    f"**Something went wrong:** `{type(exc).__name__}: {exc}`",
                    thinking=thinking,
                )
                self.status_label.set_text("Error")

    async def stop_agent(self) -> None:
        chat = self.active
        if not chat or not self.running:
            return
        chat.request_stop()
        self.stop_button.disable()
        self.status_label.set_text("Stopping…")


def index() -> None:
    """Page builder: called once per browser session."""
    ui.add_head_html(FONTS_HTML)
    ui.add_css(CSS)
    ChatPage().build()


def run_gui() -> None:
    settings = get_settings()
    ui.page("/")(index)
    ui.run(
        title="Onnie",
        favicon="✦",
        dark=True,
        reload=False,
        show=False,
        port=settings.port,
        host=settings.host,
    )
