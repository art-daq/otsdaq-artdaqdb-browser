"""
File: filter_input.py
Purpose: Filter input widget with fuzzy search capabilities.
Category: Widget
Author: ArtdaqDB Browser Team
Depends: textual
Exports: FilterInput, fuzzy_match
Complexity: Medium | Lines: 229
"""

import asyncio
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input
from textual.message import Message

_search_config_cache = None


def _get_search_config():
    global _search_config_cache
    if _search_config_cache is None:
        try:
            from ..config import ConfigLoader

            loader = ConfigLoader()
            (config, _) = loader.load()
            _search_config_cache = {
                "fuzzy_match": config.search.fuzzy_match,
                "min_search_chars": config.search.min_search_chars,
                "case_insensitive": config.search.case_insensitive,
                "debounce_ms": config.search.debounce_ms,
            }
        except Exception:
            _search_config_cache = {
                "fuzzy_match": True,
                "min_search_chars": 1,
                "case_insensitive": True,
                "debounce_ms": 100,
            }
    return _search_config_cache


class FilterInput(Horizontal):

    class Changed(Message):

        def __init__(self, value: str) -> None:
            self.value = value
            super().__init__()

    class Cleared(Message):
        pass

    class Submitted(Message):
        pass

    DEFAULT_CSS = """
    FilterInput {
        height: 3;
        background: transparent;
        align: left middle;
        padding: 0 1;
    }

    FilterInput > Input {
        width: 1fr;
        height: 3;
        border: solid $border;
        background: $background;
        color: $text;
        text-style: bold;
        padding: 0 1;
        margin: 0;
    }

    FilterInput > Input:focus {
        border: solid $primary;
        background: $background;
        color: $text;
        text-style: bold;
    }

    FilterInput > Input > .input--cursor {
        color: $background;
        background: $foreground;
        text-style: bold;
    }

    FilterInput > Input > .input--placeholder {
        color: $text-muted;
    }
    """

    def __init__(self, placeholder: str = "Filter...", **kwargs):
        super().__init__(**kwargs)
        self.placeholder = placeholder
        self._debounce_timer = None
        self._pending_value = None
        config = _get_search_config()
        self._debounce_ms = config.get("debounce_ms", 100)

    def compose(self) -> ComposeResult:
        yield Input(placeholder=self.placeholder, id="filter_input_field")

    def _emit_changed(self) -> None:
        if self._pending_value is not None:
            self.post_message(self.Changed(self._pending_value))
            self._pending_value = None

    def _has_event_loop(self) -> bool:
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter_input_field":
            self._pending_value = event.value
            if self._debounce_timer is not None:
                self._debounce_timer.stop()
            if self._debounce_ms <= 0:
                self._emit_changed()
            elif not self._has_event_loop():
                self._emit_changed()
            else:
                self._debounce_timer = self.set_timer(self._debounce_ms / 1000.0, self._emit_changed)
            event.stop()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "filter_input_field":
            self.post_message(self.Submitted())

    def get_value(self) -> str:
        input_widget = self.query_one("#filter_input_field", Input)
        return input_widget.value

    def set_value(self, value: str) -> None:
        input_widget = self.query_one("#filter_input_field", Input)
        input_widget.value = value

    def clear(self) -> None:
        input_widget = self.query_one("#filter_input_field", Input)
        input_widget.value = ""
        self.post_message(self.Cleared())

    def focus(self) -> None:
        input_widget = self.query_one("#filter_input_field", Input)
        input_widget.focus()

    def blur(self) -> None:
        input_widget = self.query_one("#filter_input_field", Input)
        input_widget.blur()


def fuzzy_match(query: str, text: str) -> bool:
    if not query:
        return True
    config = _get_search_config()
    if len(query) < config["min_search_chars"]:
        return True
    if config["case_insensitive"]:
        query = query.lower()
        text = text.lower()
    if query in text:
        return True
    if not config["fuzzy_match"]:
        return False
    query_idx = 0
    text_idx = 0
    while query_idx < len(query) and text_idx < len(text):
        if query[query_idx] == text[text_idx]:
            query_idx += 1
        text_idx += 1
    return query_idx == len(query)
