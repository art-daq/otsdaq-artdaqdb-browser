"""
File: trace_filter_row.py
Purpose: Unified filter header widget for trace log viewer.
Category: Widget
Author: ArtdaqDB Browser Team
Depends: textual
Exports: VimSelect, ClickableLabel, SourceFilterPopup, TimeFilterPopup, SeverityFilterPopup, ...
Complexity: High | Lines: 1452
"""

from datetime import datetime, timedelta
from typing import List, Optional, Set, Tuple, TypeVar
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Blur, Focus, Key
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Input, OptionList, RadioButton, RadioSet, Select, SelectionList, Static
from textual.widgets.selection_list import Selection
from ..constants import TraceColumnWidth
from ..models.trace_entry import DEFAULT_SEVERITIES, TraceEntry
from ..trace import trace
from .filter_input import fuzzy_match

SelectType = TypeVar("SelectType")


class VimSelect(Select[SelectType]):
    BINDINGS = [
        *Select.BINDINGS,
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def action_cursor_down(self) -> None:
        if not self.expanded:
            self.action_show_overlay()
        else:
            try:
                option_list = self.query_one(OptionList)
                option_list.action_cursor_down()
            except Exception:
                pass

    def action_cursor_up(self) -> None:
        if not self.expanded:
            self.action_show_overlay()
        else:
            try:
                option_list = self.query_one(OptionList)
                option_list.action_cursor_up()
            except Exception:
                pass

    def on_key(self, event: Key) -> None:
        if self.expanded and event.key in ("j", "k"):
            try:
                option_list = self.query_one(OptionList)
                if event.key == "j":
                    option_list.action_cursor_down()
                elif event.key == "k":
                    option_list.action_cursor_up()
                event.stop()
                event.prevent_default()
            except Exception:
                pass


class ClickableLabel(Static, can_focus=True):

    class Clicked(Message):

        def __init__(self, label: "ClickableLabel") -> None:
            self.label = label
            super().__init__()

    def _get_label_content(self) -> str:
        if hasattr(self, "renderable") and self.renderable is not None:
            return str(self.renderable)
        elif hasattr(self, "_renderable") and self._renderable is not None:
            return str(self._renderable)
        return ""

    def on_focus(self, event: Focus) -> None:
        content = self._get_label_content()
        trace.trace(
            "ClickableLabel focused",
            tags=["widget", "filter", "focus", "label"],
            widget_id=self.id,
            content=content[:20] if content else None,
        )

    def on_blur(self, event: Blur) -> None:
        trace.trace("ClickableLabel blurred", tags=["widget", "filter", "focus", "label"], widget_id=self.id)

    def on_click(self, event) -> None:
        trace.debug(
            "ClickableLabel clicked",
            tags=["widget", "filter", "event", "label"],
            widget_id=self.id,
            click_x=event.x,
            click_y=event.y,
        )
        self.post_message(self.Clicked(self))
        event.stop()

    def on_key(self, event) -> None:
        if event.key in ("enter", "space"):
            trace.debug(
                "ClickableLabel activated via key",
                tags=["widget", "filter", "event", "label"],
                widget_id=self.id,
                key=event.key,
            )
            self.post_message(self.Clicked(self))
            event.stop()


def _sanitize_id(name: str) -> str:
    return name.replace(".", "_").replace("-", "_").replace(" ", "_")


class SourceFilterPopup(ModalScreen[Set[str]]):
    DEFAULT_CSS = """
    SourceFilterPopup {
        align: center middle;
        background: transparent;
        border: none;
    }

    SourceFilterPopup > Vertical {
        width: 40;
        height: auto;
        max-height: 20;
        background: transparent;
        border: solid $primary;
        padding: 1;
    }

    SourceFilterPopup .popup-title {
        text-style: bold;
        color: $primary;
        background: transparent;
    }

    SourceFilterPopup .popup-help {
        color: $text-muted;
        background: transparent;
        margin-bottom: 1;
    }

    SourceFilterPopup SelectionList {
        height: auto;
        max-height: 12;
        background: transparent;
        border: none;
        padding: 0;
    }

    SourceFilterPopup SelectionList:focus {
        border: none;
        background: transparent;
    }

    SourceFilterPopup SelectionList > .selection-list--button {
        background: transparent;
        color: $text;
        padding: 0;
        height: 1;
    }

    SourceFilterPopup SelectionList > .selection-list--button-highlighted {
        background: $primary;
        color: $background;
    }

    SourceFilterPopup SelectionList > .selection-list--button-selected {
        color: $success;
    }

    SourceFilterPopup SelectionList > .selection-list--button-selected-highlighted {
        background: $primary;
        color: $background;
    }
    """
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("space", "toggle_selection", "Toggle", show=False),
        Binding("a", "select_all", "All", show=False),
        Binding("n", "select_none", "None", show=False),
        Binding("d", "done", "Done", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, available_classes: List[str], selected_classes: Set[str]):
        super().__init__()
        self.available_classes = available_classes
        self.selected_classes = selected_classes.copy()
        trace.debug(
            "SourceFilterPopup initialized",
            tags=["widget", "filter", "popup", "lifecycle"],
            available_count=len(available_classes),
            selected_count=len(selected_classes),
        )

    def compose(self) -> ComposeResult:
        trace.trace(
            "SourceFilterPopup composing",
            tags=["widget", "filter", "popup", "lifecycle"],
            class_count=len(self.available_classes),
        )
        with Vertical():
            yield Static("Select Sources", classes="popup-title")
            yield Static("j/k:Nav  Space:Toggle  a:All  n:None  d:Done  Esc:Cancel", classes="popup-help")
            selections = [
                Selection(class_name, class_name, class_name in self.selected_classes)
                for class_name in self.available_classes
            ]
            yield SelectionList[str](*selections, id="source_selection_list")

    def on_mount(self) -> None:
        trace.info(
            "POPUP OPENED - SourceFilterPopup mounted",
            tags=["widget", "filter", "popup", "lifecycle"],
            available_classes=len(self.available_classes),
            selected_classes=len(self.selected_classes),
        )
        try:
            selection_list = self.query_one("#source_selection_list", SelectionList)
            selection_list.focus()
            trace.info("POPUP OPENED - SelectionList focused", tags=["widget", "filter", "popup", "lifecycle"])
        except Exception as e:
            trace.error(
                "POPUP OPENED - Failed to focus SelectionList",
                tags=["widget", "filter", "popup", "error"],
                error=str(e),
            )

    def on_focus(self, event: Focus) -> None:
        trace.trace("SourceFilterPopup focused", tags=["widget", "filter", "popup", "focus"])

    def on_blur(self, event: Blur) -> None:
        trace.trace("SourceFilterPopup blurred", tags=["widget", "filter", "popup", "focus"])

    def _get_selected_classes(self) -> Set[str]:
        try:
            selection_list = self.query_one("#source_selection_list", SelectionList)
            return set(selection_list.selected)
        except Exception:
            return self.selected_classes

    def on_selection_list_selected_changed(self, event: SelectionList.SelectedChanged) -> None:
        self.selected_classes = set(event.selection_list.selected)
        trace.trace(
            "SelectionList selection changed",
            tags=["widget", "filter", "popup", "event"],
            selected_count=len(self.selected_classes),
        )
        event.stop()

    def action_select_all(self) -> None:
        trace.info("ACTION_SELECT_ALL called", tags=["widget", "filter", "popup", "action"])
        try:
            selection_list = self.query_one("#source_selection_list", SelectionList)
            trace.info(
                "ACTION_SELECT_ALL - before select_all()",
                tags=["widget", "filter", "popup", "action"],
                current_selected=len(selection_list.selected),
                available=len(self.available_classes),
            )
            selection_list.select_all()
            self.selected_classes = set(self.available_classes)
            trace.info(
                "ACTION_SELECT_ALL - after select_all()",
                tags=["widget", "filter", "popup", "action"],
                new_selected=len(selection_list.selected),
            )
            selection_list.focus()
        except Exception as e:
            trace.error("ACTION_SELECT_ALL failed", tags=["widget", "filter", "popup", "error"], error=str(e))

    def action_select_none(self) -> None:
        trace.info("ACTION_SELECT_NONE called", tags=["widget", "filter", "popup", "action"])
        try:
            selection_list = self.query_one("#source_selection_list", SelectionList)
            trace.info(
                "ACTION_SELECT_NONE - before deselect_all()",
                tags=["widget", "filter", "popup", "action"],
                current_selected=len(selection_list.selected),
            )
            selection_list.deselect_all()
            self.selected_classes = set()
            trace.info(
                "ACTION_SELECT_NONE - after deselect_all()",
                tags=["widget", "filter", "popup", "action"],
                new_selected=len(selection_list.selected),
            )
            selection_list.focus()
        except Exception as e:
            trace.error("ACTION_SELECT_NONE failed", tags=["widget", "filter", "popup", "error"], error=str(e))

    def action_done(self) -> None:
        trace.info("ACTION_DONE called", tags=["widget", "filter", "popup", "action"])
        self.selected_classes = self._get_selected_classes()
        trace.info(
            "ACTION_DONE - dismissing with selection",
            tags=["widget", "filter", "popup", "action"],
            final_count=len(self.selected_classes),
        )
        self.dismiss(self.selected_classes)

    def action_cancel(self) -> None:
        trace.info("ACTION_CANCEL called", tags=["widget", "filter", "popup", "action"])
        self.dismiss(None)

    def action_cursor_down(self) -> None:
        try:
            selection_list = self.query_one("#source_selection_list", SelectionList)
            selection_list.action_cursor_down()
        except Exception:
            pass

    def action_cursor_up(self) -> None:
        try:
            selection_list = self.query_one("#source_selection_list", SelectionList)
            selection_list.action_cursor_up()
        except Exception:
            pass

    def action_toggle_selection(self) -> None:
        try:
            selection_list = self.query_one("#source_selection_list", SelectionList)
            selection_list.action_select()
        except Exception:
            pass

    def on_key(self, event: Key) -> None:
        trace.trace("SourceFilterPopup key event", tags=["widget", "filter", "popup", "key"], key=event.key)
        if event.key == "j":
            self.action_cursor_down()
            event.stop()
            event.prevent_default()
        elif event.key == "k":
            self.action_cursor_up()
            event.stop()
            event.prevent_default()
        elif event.key == "space":
            self.action_toggle_selection()
            event.stop()
            event.prevent_default()
        elif event.key == "a":
            self.action_select_all()
            event.stop()
            event.prevent_default()
        elif event.key == "n":
            self.action_select_none()
            event.stop()
            event.prevent_default()
        elif event.key == "enter":
            self.action_done()
            event.stop()
            event.prevent_default()
        elif event.key == "escape":
            self.action_cancel()
            event.stop()
            event.prevent_default()


TIME_OPTIONS = [
    ("Time", "", "No filter - show all"),
    ("<1min", "1min", "Last 1 minute"),
    ("<5min", "5min", "Last 5 minutes"),
    ("<1h", "1h", "Last 1 hour"),
    ("<4h", "4h", "Last 4 hours"),
    ("today", "today", "Since midnight today"),
]


class TimeFilterPopup(ModalScreen[str]):
    DEFAULT_CSS = """
    TimeFilterPopup {
        align: center middle;
        background: transparent;
        border: none;
    }

    TimeFilterPopup > Vertical {
        width: 35;
        height: auto;
        max-height: 12;
        background: transparent;
        border: solid $primary;
        padding: 1;
    }

    TimeFilterPopup .popup-title {
        text-style: bold;
        color: $primary;
        background: transparent;
    }

    TimeFilterPopup .popup-help {
        color: $text-muted;
        background: transparent;
        margin-bottom: 1;
    }

    TimeFilterPopup RadioSet {
        background: transparent;
        border: none;
        padding: 0;
        height: auto;
    }

    TimeFilterPopup RadioSet:focus {
        background: transparent;
        border: none;
    }

    TimeFilterPopup RadioButton {
        background: transparent;
        padding: 0;
        height: 1;
    }
    """
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, current_value: str = ""):
        super().__init__()
        self.current_value = current_value
        trace.debug(
            "TimeFilterPopup initialized", tags=["widget", "filter", "popup", "lifecycle"], current_value=current_value
        )

    def compose(self) -> ComposeResult:
        trace.trace("TimeFilterPopup composing", tags=["widget", "filter", "popup", "lifecycle"])
        with Vertical():
            yield Static("Time Range", classes="popup-title")
            yield Static("j/k:Nav  Enter:Select  Esc:Cancel", classes="popup-help")
            with RadioSet(id="time_radio_set"):
                for label, value, description in TIME_OPTIONS:
                    is_selected = value == self.current_value
                    yield RadioButton(f"{label} - {description}", value=is_selected, id=f"time_{value or 'none'}")

    def on_mount(self) -> None:
        trace.info(
            "TIME POPUP OPENED", tags=["widget", "filter", "popup", "lifecycle"], current_value=self.current_value
        )
        try:
            radio_set = self.query_one("#time_radio_set", RadioSet)
            radio_set.focus()
        except Exception as e:
            trace.error("Failed to focus RadioSet", tags=["widget", "filter", "popup", "error"], error=str(e))

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.pressed:
            button_id = event.pressed.id or ""
            if button_id.startswith("time_"):
                value = button_id[5:]
                if value == "none":
                    value = ""
                trace.info("TIME SELECTED", tags=["widget", "filter", "popup", "action"], selected_value=value)
                self.dismiss(value)
        event.stop()

    def action_cancel(self) -> None:
        trace.info("TIME POPUP CANCELLED", tags=["widget", "filter", "popup", "action"])
        self.dismiss(None)

    def on_key(self, event: Key) -> None:
        if event.key == "j":
            try:
                radio_set = self.query_one("#time_radio_set", RadioSet)
                radio_set.focus()
                radio_set.action_next_button()
            except Exception:
                pass
            event.stop()
            event.prevent_default()
        elif event.key == "k":
            try:
                radio_set = self.query_one("#time_radio_set", RadioSet)
                radio_set.focus()
                radio_set.action_previous_button()
            except Exception:
                pass
            event.stop()
            event.prevent_default()
        elif event.key == "escape":
            self.action_cancel()
            event.stop()
            event.prevent_default()


SEVERITY_OPTIONS = [
    ("Sev", "", "No filter - show all"),
    ("≥TRC", "TRACE", "TRACE and above"),
    ("≥DBG", "DEBUG", "DEBUG and above"),
    ("≥INF", "INFO", "INFO and above"),
    ("≥WRN", "WARN", "WARN and above"),
    ("≥ERR", "ERROR", "ERROR and above"),
    ("≥CRT", "CRIT", "CRIT only"),
]


class SeverityFilterPopup(ModalScreen[str]):
    DEFAULT_CSS = """
    SeverityFilterPopup {
        align: center middle;
        background: transparent;
        border: none;
    }

    SeverityFilterPopup > Vertical {
        width: 35;
        height: auto;
        max-height: 15;
        background: transparent;
        border: solid $primary;
        padding: 1;
    }

    SeverityFilterPopup .popup-title {
        text-style: bold;
        color: $primary;
        background: transparent;
    }

    SeverityFilterPopup .popup-help {
        color: $text-muted;
        background: transparent;
        margin-bottom: 1;
    }

    SeverityFilterPopup RadioSet {
        background: transparent;
        border: none;
        padding: 0;
        height: auto;
    }

    SeverityFilterPopup RadioSet:focus {
        background: transparent;
        border: none;
    }

    SeverityFilterPopup RadioButton {
        background: transparent;
        padding: 0;
        height: 1;
    }
    """
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, current_value: str = ""):
        super().__init__()
        self.current_value = current_value
        trace.debug(
            "SeverityFilterPopup initialized",
            tags=["widget", "filter", "popup", "lifecycle"],
            current_value=current_value,
        )

    def compose(self) -> ComposeResult:
        trace.trace("SeverityFilterPopup composing", tags=["widget", "filter", "popup", "lifecycle"])
        with Vertical():
            yield Static("Severity Threshold", classes="popup-title")
            yield Static("j/k:Nav  Enter:Select  Esc:Cancel", classes="popup-help")
            with RadioSet(id="severity_radio_set"):
                for label, value, description in SEVERITY_OPTIONS:
                    is_selected = value == self.current_value
                    yield RadioButton(f"{label} - {description}", value=is_selected, id=f"sev_{value or 'none'}")

    def on_mount(self) -> None:
        trace.info(
            "SEVERITY POPUP OPENED", tags=["widget", "filter", "popup", "lifecycle"], current_value=self.current_value
        )
        try:
            radio_set = self.query_one("#severity_radio_set", RadioSet)
            radio_set.focus()
            trace.debug(
                "RadioSet focused",
                tags=["widget", "filter", "popup", "focus"],
                has_focus=radio_set.has_focus,
                _selected=radio_set._selected,
            )
        except Exception as e:
            trace.error("Failed to focus RadioSet", tags=["widget", "filter", "popup", "error"], error=str(e))

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.pressed:
            button_id = event.pressed.id or ""
            if button_id.startswith("sev_"):
                value = button_id[4:]
                if value == "none":
                    value = ""
                trace.info("SEVERITY SELECTED", tags=["widget", "filter", "popup", "action"], selected_value=value)
                self.dismiss(value)
        event.stop()

    def action_cancel(self) -> None:
        trace.info("SEVERITY POPUP CANCELLED", tags=["widget", "filter", "popup", "action"])
        self.dismiss(None)

    def on_key(self, event: Key) -> None:
        trace.debug("SEVERITY POPUP on_key", tags=["widget", "filter", "popup", "key"], key=event.key)
        if event.key == "j":
            try:
                radio_set = self.query_one("#severity_radio_set", RadioSet)
                radio_set.focus()
                radio_set.action_next_button()
                trace.debug("j key: called action_next_button", tags=["popup"])
            except Exception as e:
                trace.error("j key error", tags=["popup"], error=str(e))
            event.stop()
            event.prevent_default()
        elif event.key == "k":
            try:
                radio_set = self.query_one("#severity_radio_set", RadioSet)
                radio_set.focus()
                radio_set.action_previous_button()
                trace.debug("k key: called action_previous_button", tags=["popup"])
            except Exception as e:
                trace.error("k key error", tags=["popup"], error=str(e))
            event.stop()
            event.prevent_default()
        elif event.key == "escape":
            self.action_cancel()
            event.stop()
            event.prevent_default()


class TraceFilterRow(Widget, can_focus=True):
    BINDINGS = [
        Binding("tab", "focus_next_filter", "Next Filter", show=False),
        Binding("shift+tab", "focus_prev_filter", "Prev Filter", show=False),
        Binding("x", "clear_filters", "Clear Filters", show=False),
        Binding("escape", "close_popup", "Close", show=False),
    ]
    has_active_filters: reactive[bool] = reactive(False)

    class FilterChanged(Message):

        def __init__(
            self, time_preset: str, severity_threshold: str, selected_classes: Set[str], message_filter: str
        ) -> None:
            self.time_preset = time_preset
            self.severity_threshold = severity_threshold
            self.selected_classes = selected_classes
            self.message_filter = message_filter
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._available_classes: List[str] = []
        self._selected_classes: Set[str] = set()
        self._time_preset: str = ""
        self._severity_threshold: str = ""
        self._message_filter_value: str = ""
        self._popup_visible: bool = False
        self._initialized: bool = False
        self._filter_widgets: List[str] = ["filter_time", "filter_sev", "filter_source", "filter_message"]
        self._current_filter_index = 0
        trace.debug(
            "TraceFilterRow initialized",
            tags=["widget", "filter", "lifecycle"],
            filter_widgets=self._filter_widgets,
            initial_filter_index=self._current_filter_index,
        )

    def compose(self) -> ComposeResult:
        trace.debug(
            "TraceFilterRow composing",
            tags=["widget", "filter", "lifecycle"],
            default_time="",
            default_sev="",
            default_message="",
        )
        with Horizontal(classes="filter-row"):
            yield Static(" ", classes="filter-cursor-spacer")
            yield ClickableLabel("Time", id="filter_time", classes="filter-time")
            yield ClickableLabel("Sev", id="filter_sev", classes="filter-sev")
            yield ClickableLabel("Source", id="filter_source", classes="filter-source")
            yield Input(placeholder="Fuzzy search...", id="filter_message", classes="filter-message")

    def on_mount(self) -> None:
        msg_val = self.query_one("#filter_message", Input).value
        trace.debug(
            "TraceFilterRow mounted",
            tags=["widget", "filter", "lifecycle"],
            time_default=self._time_preset or "(empty)",
            sev_default=self._severity_threshold or "(empty)",
            message_default=msg_val or "(empty)",
            available_classes=len(self._available_classes),
            selected_classes=len(self._selected_classes),
            has_active_filters=self.has_active_filters,
        )
        self._initialized = True

    def on_focus(self, event: Focus) -> None:
        trace.debug(
            "TraceFilterRow focused",
            tags=["widget", "filter", "focus"],
            current_filter_index=self._current_filter_index,
        )

    def on_blur(self, event: Blur) -> None:
        trace.debug("TraceFilterRow blurred", tags=["widget", "filter", "focus"])

    def on_descendant_focus(self, event: Focus) -> None:
        widget_id = event.widget.id if event.widget.id else event.widget.__class__.__name__
        trace.trace(
            "Filter descendant focused",
            tags=["widget", "filter", "focus", "descendant"],
            widget_id=widget_id,
            widget_class=event.widget.__class__.__name__,
            parent_id=event.widget.parent.id if event.widget.parent and hasattr(event.widget.parent, "id") else None,
        )

    def on_descendant_blur(self, event: Blur) -> None:
        widget_id = event.widget.id if event.widget.id else event.widget.__class__.__name__
        trace.trace(
            "Filter descendant blurred",
            tags=["widget", "filter", "focus", "descendant"],
            widget_id=widget_id,
            widget_class=event.widget.__class__.__name__,
        )

    def _update_source_label(self) -> None:
        try:
            label = self.query_one("#filter_source", ClickableLabel)
        except Exception:
            return
        old_label = label._get_label_content()
        if not self._available_classes:
            new_label = "Source"
        elif len(self._selected_classes) == 0:
            new_label = "Src(0)"
        elif len(self._selected_classes) == len(self._available_classes):
            new_label = "Source"
        else:
            new_label = f"Src({len(self._selected_classes)})"
        label.update(new_label)
        trace.trace(
            "Source label updated",
            tags=["widget", "filter", "mutation"],
            old_label=old_label,
            new_label=new_label,
            selected=len(self._selected_classes),
            available=len(self._available_classes),
        )

    def _update_severity_label(self) -> None:
        try:
            label = self.query_one("#filter_sev", ClickableLabel)
        except Exception:
            return
        old_label = label._get_label_content()
        new_label = "Sev"
        for display_label, value, _desc in SEVERITY_OPTIONS:
            if value == self._severity_threshold:
                new_label = display_label
                break
        label.update(new_label)
        trace.trace(
            "Severity label updated",
            tags=["widget", "filter", "mutation"],
            old_label=old_label,
            new_label=new_label,
            threshold=self._severity_threshold,
        )

    def _update_time_label(self) -> None:
        try:
            label = self.query_one("#filter_time", ClickableLabel)
        except Exception:
            return
        old_label = label._get_label_content()
        new_label = "Time"
        for display_label, value, _desc in TIME_OPTIONS:
            if value == self._time_preset:
                new_label = display_label
                break
        label.update(new_label)
        trace.trace(
            "Time label updated",
            tags=["widget", "filter", "mutation"],
            old_label=old_label,
            new_label=new_label,
            preset=self._time_preset,
        )

    def set_available_classes(self, classes: List[str]) -> None:
        old_count = len(self._available_classes)
        self._available_classes = sorted(classes)
        self._selected_classes = set(self._available_classes)
        trace.debug(
            "Available classes set",
            tags=["widget", "filter", "mutation"],
            old_count=old_count,
            new_count=len(self._available_classes),
            classes_preview=self._available_classes[:5] if self._available_classes else [],
        )
        self._update_source_label()

    def set_available_tags(self, tags: List[str]) -> None:
        pass

    def get_filter_values(self) -> Tuple[str, str, Set[str], str]:
        message_filter = self.query_one("#filter_message", Input).value.strip()
        return (self._time_preset, self._severity_threshold, self._selected_classes.copy(), message_filter)

    def clear_filters(self) -> None:
        trace.debug(
            "Clearing all filters",
            tags=["widget", "filter", "mutation"],
            had_time_filter=bool(self._time_preset),
            had_sev_filter=bool(self._severity_threshold),
            had_source_filter=len(self._selected_classes) < len(self._available_classes),
            had_message_filter=bool(self.query_one("#filter_message", Input).value),
        )
        self._time_preset = ""
        self._severity_threshold = ""
        self._selected_classes = set(self._available_classes)
        self.query_one("#filter_message", Input).value = ""
        self._update_time_label()
        self._update_severity_label()
        self._update_source_label()
        self.has_active_filters = False
        self._post_filter_changed()

    def _calculate_time_cutoff(self, preset: str) -> Optional[datetime]:
        now = datetime.now()
        if preset == "1min":
            return now - timedelta(minutes=1)
        elif preset == "5min":
            return now - timedelta(minutes=5)
        elif preset == "1h":
            return now - timedelta(hours=1)
        elif preset == "4h":
            return now - timedelta(hours=4)
        elif preset == "today":
            return datetime.combine(now.date(), datetime.min.time())
        return None

    def filter_entries(self, entries: List[TraceEntry]) -> List[TraceEntry]:
        (time_preset, sev_threshold, selected_classes, message_filter) = self.get_filter_values()
        filtered = entries
        initial_count = len(entries)
        if time_preset:
            cutoff = self._calculate_time_cutoff(time_preset)
            if cutoff:
                filtered = [e for e in filtered if e.timestamp >= cutoff]
        if sev_threshold:
            threshold_level = DEFAULT_SEVERITIES.get(sev_threshold, {}).get("level", 0)
            filtered = [e for e in filtered if e.severity_level >= threshold_level]
        if selected_classes and len(selected_classes) < len(self._available_classes):
            filtered = [e for e in filtered if e.source_class in selected_classes]
        if message_filter:
            filtered = [e for e in filtered if fuzzy_match(message_filter, e.message)]
        trace.debug(
            "Filtered entries",
            tags=["widget", "filter", "query"],
            initial_count=initial_count,
            filtered_count=len(filtered),
            time_filter=time_preset or None,
            sev_filter=sev_threshold or None,
            source_filter=f"{len(selected_classes)}/{len(self._available_classes)}",
            message_filter=message_filter[:20] if message_filter else None,
        )
        return filtered

    def _has_any_filter(self) -> bool:
        (time_preset, sev_threshold, selected_classes, message_filter) = self.get_filter_values()
        return any(
            [
                time_preset,
                sev_threshold,
                len(selected_classes) < len(self._available_classes) if self._available_classes else False,
                message_filter,
            ]
        )

    def _post_filter_changed(self) -> None:
        if not self._initialized:
            trace.trace("Skipping FilterChanged - not yet initialized", tags=["widget", "filter", "event"])
            return
        (time_preset, sev_threshold, selected_classes, message_filter) = self.get_filter_values()
        self.has_active_filters = self._has_any_filter()
        self.post_message(self.FilterChanged(time_preset, sev_threshold, selected_classes, message_filter))

    def on_clickable_label_clicked(self, event: ClickableLabel.Clicked) -> None:
        trace.debug("Filter label clicked", tags=["widget", "filter", "event"], label_id=event.label.id)
        if event.label.id == "filter_time":
            self._show_time_popup()
            event.stop()
        elif event.label.id == "filter_sev":
            self._show_severity_popup()
            event.stop()
        elif event.label.id == "filter_source":
            self._show_source_popup()
            event.stop()

    def _show_source_popup(self) -> None:
        if self._popup_visible:
            return
        if not self._available_classes:
            self.notify("No source classes available", severity="warning")
            return
        trace.debug(
            "Opening source filter popup",
            tags=["widget", "filter", "event"],
            available_classes=len(self._available_classes),
            selected_classes=len(self._selected_classes),
        )
        self._popup_visible = True

        def handle_popup_result(result: Optional[Set[str]]) -> None:
            self._popup_visible = False
            if result is not None:
                trace.debug(
                    "Source selection confirmed",
                    tags=["widget", "filter", "event"],
                    selected_count=len(result),
                    available_count=len(self._available_classes),
                )
                self._selected_classes = result
                self._update_source_label()
                self._post_filter_changed()
            else:
                trace.debug("Source selection cancelled", tags=["widget", "filter", "event"])
            try:
                self.query_one("#filter_source", ClickableLabel).focus()
            except Exception:
                pass

        popup = SourceFilterPopup(self._available_classes, self._selected_classes)
        self.app.push_screen(popup, handle_popup_result)

    def _show_time_popup(self) -> None:
        if self._popup_visible:
            return
        trace.debug("Opening time filter popup", tags=["widget", "filter", "event"], current_preset=self._time_preset)
        self._popup_visible = True

        def handle_popup_result(result: Optional[str]) -> None:
            self._popup_visible = False
            if result is not None:
                trace.debug("Time preset confirmed", tags=["widget", "filter", "event"], new_preset=result)
                self._time_preset = result
                self._update_time_label()
                self._post_filter_changed()
            else:
                trace.debug("Time selection cancelled", tags=["widget", "filter", "event"])
            try:
                self.query_one("#filter_time", ClickableLabel).focus()
            except Exception:
                pass

        popup = TimeFilterPopup(self._time_preset)
        self.app.push_screen(popup, handle_popup_result)

    def _show_severity_popup(self) -> None:
        if self._popup_visible:
            return
        trace.debug(
            "Opening severity filter popup",
            tags=["widget", "filter", "event"],
            current_threshold=self._severity_threshold,
        )
        self._popup_visible = True

        def handle_popup_result(result: Optional[str]) -> None:
            self._popup_visible = False
            if result is not None:
                trace.debug("Severity threshold confirmed", tags=["widget", "filter", "event"], new_threshold=result)
                self._severity_threshold = result
                self._update_severity_label()
                self._post_filter_changed()
            else:
                trace.debug("Severity selection cancelled", tags=["widget", "filter", "event"])
            try:
                self.query_one("#filter_sev", ClickableLabel).focus()
            except Exception:
                pass

        popup = SeverityFilterPopup(self._severity_threshold)
        self.app.push_screen(popup, handle_popup_result)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "filter_message":
            trace.debug(
                "Message filter submitted",
                tags=["widget", "filter", "event"],
                filter_value=event.value[:50] if event.value else None,
            )
            self._post_filter_changed()
            event.stop()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter_message":
            if len(event.value) % 5 == 0 or not event.value:
                trace.trace("Message filter typing", tags=["widget", "filter", "event"], filter_length=len(event.value))
            self._post_filter_changed()
            event.stop()

    def action_focus_next_filter(self) -> None:
        old_index = self._current_filter_index
        self._current_filter_index = (self._current_filter_index + 1) % len(self._filter_widgets)
        trace.debug(
            "Focus next filter",
            tags=["widget", "filter", "navigation"],
            old_index=old_index,
            new_index=self._current_filter_index,
            target_widget=self._filter_widgets[self._current_filter_index],
        )
        self._focus_current_widget()

    def action_focus_prev_filter(self) -> None:
        old_index = self._current_filter_index
        self._current_filter_index = (self._current_filter_index - 1) % len(self._filter_widgets)
        trace.debug(
            "Focus prev filter",
            tags=["widget", "filter", "navigation"],
            old_index=old_index,
            new_index=self._current_filter_index,
            target_widget=self._filter_widgets[self._current_filter_index],
        )
        self._focus_current_widget()

    def _focus_current_widget(self) -> None:
        widget_id = self._filter_widgets[self._current_filter_index]
        try:
            widget = self.query_one(f"#{widget_id}")
            trace.trace(
                "Focusing widget",
                tags=["widget", "filter", "navigation"],
                widget_id=widget_id,
                widget_class=widget.__class__.__name__,
            )
            widget.focus()
        except Exception as e:
            trace.warn(
                "Failed to focus widget",
                tags=["widget", "filter", "navigation", "error"],
                widget_id=widget_id,
                error=str(e),
            )

    def action_close_popup(self) -> None:
        trace.debug("Close popup action", tags=["widget", "filter", "event"], popup_visible=self._popup_visible)
        pass

    def action_clear_filters(self) -> None:
        trace.debug("Clear filters action triggered", tags=["widget", "filter", "event"])
        self.clear_filters()
