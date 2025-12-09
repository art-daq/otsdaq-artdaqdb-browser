"""
File: footer_bar.py
Purpose: Dynamic footer bar widget for displaying secondary actions.
Category: Widget
Author: ArtdaqDB Browser Team
Depends: textual
Exports: FooterBar, format_key_display
Complexity: Low | Lines: 162
"""

from typing import List, Tuple
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static
from textual.reactive import reactive

FOOTER_APP_KEYS: List[Tuple[str, str, str]] = [("?", "action_help", "Help"), ("q", "action_quit", "Quit")]


def format_key_display(key: str) -> str:
    if key == "slash":
        return "/"
    if key == "escape":
        return "Esc"
    if key == "enter":
        return "Enter"
    if key == "space":
        return "Space"
    if key == "tab":
        return "Tab"
    if key == "pageup":
        return "PgUp"
    if key == "pagedown":
        return "PgDn"
    if key.startswith("ctrl+") or key.startswith("ctrl-"):
        return "^" + key[5:]
    if key.startswith("shift+") or key.startswith("shift-"):
        return "S-" + key[6:]
    if key.startswith("alt+") or key.startswith("alt-"):
        return "M-" + key[4:]
    return key


class FooterBar(Horizontal):
    DEFAULT_CSS = """
    FooterBar {
        dock: bottom;
        width: 100%;
        height: 1;
        background: $footer-background;
        color: $text-muted;
        align: right middle;
    }

    FooterBar > .footer-key {
        width: auto;
        color: $accent;
        text-style: bold;
        padding: 0 1;
        background: transparent;
        height: 1;
    }

    FooterBar > .footer-description {
        width: auto;
        color: $text;
        padding: 0 1 0 0;
        background: transparent;
        height: 1;
    }
    """
    _bindings_key: reactive[str] = reactive("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._actions: List[Tuple[str, str, str]] = []

    def compose(self) -> ComposeResult:
        for key, _action, description in FOOTER_APP_KEYS:
            display_key = format_key_display(key)
            yield Static(display_key, classes="footer-key")
            yield Static(description, classes="footer-description")

    def update_actions(self, actions: List[Tuple[str, str, str]]) -> None:
        self._actions = actions
        self.remove_children()
        for key, _action, description in actions:
            display_key = format_key_display(key)
            self.mount(Static(display_key, classes="footer-key"))
            self.mount(Static(description, classes="footer-description"))
        for key, _action, description in FOOTER_APP_KEYS:
            display_key = format_key_display(key)
            self.mount(Static(display_key, classes="footer-key"))
            self.mount(Static(description, classes="footer-description"))
        self._bindings_key = "|".join((f"{k}:{d}" for (k, _, d) in actions))

    def clear_actions(self) -> None:
        self.update_actions([])
