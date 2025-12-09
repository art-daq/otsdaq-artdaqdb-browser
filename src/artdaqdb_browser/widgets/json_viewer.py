"""
File: json_viewer.py
Purpose: JSON viewer widget with syntax highlighting.
Category: Widget
Author: ArtdaqDB Browser Team
Depends: textual
Exports: JSONViewer
Complexity: Low | Lines: 73
"""

import json
from typing import Any, Dict
from textual.widgets import TextArea
from textual.events import Click, MouseScrollDown, MouseScrollUp


class JSONViewer(TextArea):
    can_focus = True
    SCROLL_LINES = 3
    DEFAULT_CSS = """
    JSONViewer {
        border: none;
        background: transparent;
        color: $text;
        padding: 0;
    }

    JSONViewer:focus {
        border: none;
    }
    """

    def __init__(self, data: Any = None, **kwargs):
        super().__init__(read_only=True, language="json", **kwargs)
        if data is not None:
            self.set_data(data)

    def on_click(self, event: Click) -> None:
        self.focus()

    def on_mouse_scroll_down(self, event: MouseScrollDown) -> None:
        self.scroll_relative(y=self.SCROLL_LINES)
        event.stop()

    def on_mouse_scroll_up(self, event: MouseScrollUp) -> None:
        self.scroll_relative(y=-self.SCROLL_LINES)
        event.stop()

    def set_data(self, data: Any) -> None:
        try:
            json_str = json.dumps(data, indent=2, default=str)
            self.load_text(json_str)
        except Exception as e:
            self.load_text(f"Error displaying JSON: {e}")

    def clear(self) -> None:
        self.load_text("")
