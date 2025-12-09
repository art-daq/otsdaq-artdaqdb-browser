"""
File: key_panel.py
Purpose: Key bindings help panel widget.
Category: Widget
Author: ArtdaqDB Browser Team
Depends: textual
Exports: KeyPanel
Complexity: Low | Lines: 132
"""

from typing import List, Tuple, Optional
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static
from ..constants import STANDARD_KEY_PANEL_BINDINGS


class KeyPanel(Vertical):
    DEFAULT_CSS = """
    KeyPanel {
        dock: right;
        width: 16;
        height: 100%;
        background: transparent;
        border-left: solid $border;
        padding: 0;
        overflow-y: hidden;
        scrollbar-size: 0 0;
    }

    KeyPanel.hidden {
        display: none;
        width: 0;
        border: none;
        padding: 0;
        margin: 0;
    }

    KeyPanel .key-panel-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        background: transparent;
        margin-bottom: 0;
        padding-bottom: 0;
        border-bottom: solid $border;
    }

    KeyPanel .key-item {
        height: 1;
        margin-bottom: 0;
        padding: 0;
        layout: horizontal;
        background: transparent;
    }

    KeyPanel .key-binding {
        width: 5;
        text-style: bold;
        color: $accent;
        text-align: right;
        padding-right: 1;
        background: transparent;
    }

    KeyPanel .key-description {
        width: 1fr;
        color: $text-muted;
        background: transparent;
    }
    """

    def __init__(
        self,
        bindings: Optional[List[Tuple[str, str]]] = None,
        extra_bindings: Optional[List[Tuple[str, str]]] = None,
        use_standard: bool = True,
        **kwargs
    ):
        super().__init__(**kwargs)
        if bindings is not None:
            self._bindings = list(bindings)
        elif use_standard:
            self._bindings = STANDARD_KEY_PANEL_BINDINGS.copy()
            if extra_bindings:
                self._bindings.extend(extra_bindings)
        else:
            self._bindings = []

    @property
    def bindings(self) -> List[Tuple[str, str]]:
        return self._bindings

    def compose(self) -> ComposeResult:
        yield Static("Keys", classes="key-panel-title")
        for key, description in self._bindings:
            with Horizontal(classes="key-item"):
                yield Static(key, classes="key-binding")
                yield Static(description, classes="key-description")
