"""
File: trace_viewer.py
Purpose: Trace log viewer screen with v3 format support.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: TraceViewerScreen
Complexity: High | Lines: 725
"""

import json
import re
from pathlib import Path
from typing import List, Optional
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Input, Static, TextArea
from ..base import BaseScreen, BACK_BINDINGS, FOCUS_BINDINGS, SCROLL_BINDINGS
from ...constants import TraceColumnWidth, WidgetID
from ...models.trace_entry import DEFAULT_SEVERITIES, TraceEntry, TraceParser
from ...trace import trace, clear_trace_log, get_trace_file_path
from ...widgets import TraceFilterRow


class TraceViewerScreen(BaseScreen):
    CSS = """
    TraceViewerScreen {
        layers: below default above overlay;
    }
    """
    SECONDARY_ACTIONS = [
        ("slash", "start_search", "Find"),
        ("f", "toggle_filters", "Filters"),
        ("t", "toggle_view", "View"),
        ("x", "clear_all_filters", "Reset"),
        ("a", "autoscroll", "Tail"),
        ("r", "refresh_log", "Reload"),
        ("c", "clear_log", "Clear"),
    ]
    BINDINGS = [
        Binding("escape", "handle_escape", "Back", show=False, priority=True),
        *BACK_BINDINGS,
        Binding("n", "search_next", "Next Match", show=False, priority=True),
        Binding("N", "search_prev", "Prev Match", show=False, priority=True),
        Binding("tab", "focus_next", "Next Pane", show=False, priority=True),
        Binding("shift+tab", "focus_prev", "Prev Pane", show=False, priority=True),
        Binding("ctrl+r", "refresh_log", "Reload", show=False, priority=True),
        *SCROLL_BINDINGS,
        *FOCUS_BINDINGS,
        Binding("slash", "start_search", "Find", show=False, priority=True),
        Binding("f", "toggle_filters", "Filters", show=False, priority=True),
        Binding("t", "toggle_view", "View", show=False, priority=True),
        Binding("x", "clear_all_filters", "Reset", show=False, priority=True),
        Binding("a", "autoscroll", "Tail", show=False, priority=True),
        Binding("r", "refresh_log", "Reload", show=False, priority=True),
        Binding("c", "clear_log", "Clear", show=False, priority=True),
    ]

    def __init__(self):
        super().__init__()
        self.search_mode = False
        self.search_term = ""
        self.match_positions = []
        self.current_match = -1
        self.log_content = ""
        self.show_filters = True
        self.show_table_view = True
        self.auto_scroll = False
        self.selected_entry: Optional[TraceEntry] = None
        self.current_entry_index = 0
        self.parser = TraceParser()
        self.all_entries: List[TraceEntry] = []
        self.filtered_entries: List[TraceEntry] = []

    def compose_content(self) -> ComposeResult:
        with Horizontal(classes="screen-header"):
            yield Static("Trace Log Viewer", classes="screen-title")
        yield TraceFilterRow(id="trace_filter_row")
        with Vertical(classes="trace-main-content"):
            with Vertical(classes="trace-list-pane"):
                yield DataTable(id="trace_table", cursor_type="row")
                yield TextArea(id="trace_content", read_only=True)
            with Vertical(classes="trace-detail-pane"):
                yield Static("", id="entry_status", classes="entry-status-bar")
                yield TextArea(id="trace_detail", read_only=True)
        with Horizontal(classes="search-container", id="search_container"):
            yield Input(placeholder="/search...", id="search_input")
        yield Static("", classes="status-bar", id=WidgetID.STATUS_BAR)

    def on_mount(self) -> None:
        table = self.query_one("#trace_table", DataTable)
        table.show_header = False
        for label, width in TraceColumnWidth.get_table_columns():
            if width:
                table.add_column(label, width=width)
            else:
                table.add_column(label)
        self._update_view_visibility()
        self.load_log()
        if self.show_table_view:
            self.query_one("#trace_table", DataTable).focus()
        else:
            self.query_one("#trace_content", TextArea).focus()

    def _update_view_visibility(self) -> None:
        filter_row = self.query_one("#trace_filter_row", TraceFilterRow)
        table = self.query_one("#trace_table", DataTable)
        text_area = self.query_one("#trace_content", TextArea)
        if self.show_filters:
            filter_row.remove_class("hidden")
        else:
            filter_row.add_class("hidden")
        if self.show_table_view:
            table.remove_class("hidden")
            text_area.add_class("hidden")
        else:
            table.add_class("hidden")
            text_area.remove_class("hidden")

    def load_log(self) -> None:
        text_area = self.query_one("#trace_content", TextArea)
        status_bar = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        trace_path = get_trace_file_path()
        if not trace_path.exists():
            self.log_content = (
                "(No trace log file found)\n\nRun the application and perform some actions to generate trace output."
            )
            text_area.text = self.log_content
            self.all_entries = []
            self.filtered_entries = []
            status_bar.update("No log file")
            self._update_table()
            self._update_detail_pane(None)
            return
        try:
            self.log_content = trace_path.read_text()
            lines = self.log_content.count("\n")
            size = trace_path.stat().st_size
            self.all_entries = self.parser.parse(self.log_content)
            self.filtered_entries = self.all_entries.copy()
            filter_row = self.query_one("#trace_filter_row", TraceFilterRow)
            classes = sorted(set((e.source_class for e in self.all_entries if e.source_class)))
            filter_row.set_available_classes(classes)
            text_area.text = self.log_content
            self._update_table()
            if self.filtered_entries:
                self.selected_entry = self.filtered_entries[0]
                self._update_detail_pane(self.selected_entry)
            text_area.scroll_end(animate=False)
        except Exception as e:
            self.log_content = f"Error reading log file: {e}"
            text_area.text = self.log_content
            self.all_entries = []
            self.filtered_entries = []
            status_bar.update("Error loading log")
            self._update_table()
            self._update_detail_pane(None)

    def _update_table(self) -> None:
        table = self.query_one("#trace_table", DataTable)
        table.clear()
        for entry in self.filtered_entries:
            (time_str, sev, source, message) = entry.to_display_tuple()
            table.add_row(time_str, sev, source, message)

    def _update_text_view(self) -> None:
        text_area = self.query_one("#trace_content", TextArea)
        if not self.filtered_entries:
            text_area.text = "(No matching entries)"
            return
        lines = []
        for entry in self.filtered_entries:
            lines.append(entry.to_full_text())
            lines.append("")
        text_area.text = "\n".join(lines)

    def _update_detail_pane(self, entry: Optional[TraceEntry]) -> None:
        detail = self.query_one("#trace_detail", TextArea)
        status_bar = self.query_one("#entry_status", Static)
        if entry is None:
            status_bar.update("No entry selected")
            detail.text = "(No entry selected)"
            return
        filtered = len(self.filtered_entries)
        total = len(self.all_entries)
        status_parts = [f"Entry {self.current_entry_index + 1}/{filtered}"]
        if filtered < total:
            status_parts.append(f"({total} total)")
        status_parts.append(entry.severity)
        status_parts.append(entry.source)
        status_bar.update(" | ".join(status_parts))
        lines = [
            f"TIMESTAMP:  {entry.timestamp_str}",
            f"SEVERITY:   {entry.severity} ({entry.severity_level})",
            f"SOURCE:     {entry.source}",
            f"TAGS:       {(', '.join(entry.tags) if entry.tags else '(none)')}",
            "",
            "MESSAGE:",
            f"  {entry.message}",
            "",
        ]
        if entry.data:
            lines.append("DATA:")
            for key, value in entry.data.items():
                if isinstance(value, dict):
                    lines.append(f"  {key}:")
                    for k, v in value.items():
                        lines.append(f"    {k} = {v}")
                else:
                    lines.append(f"  {key} = {value}")
            lines.append("")
        if entry.continuations:
            lines.append("CONTINUATIONS:")
            for key, value in entry.continuations.items():
                if isinstance(value, dict):
                    lines.append(f"  {key}: {json.dumps(value, indent=2)}")
                elif isinstance(value, list):
                    lines.append(f"  {key}:")
                    for item in value:
                        lines.append(f"    - {item}")
                else:
                    lines.append(f"  {key}: {value}")
            lines.append("")
        if entry.exception_type:
            lines.append("EXCEPTION:")
            lines.append(f"  Type:    {entry.exception_type}")
            if entry.exception_message:
                lines.append(f"  Message: {entry.exception_message}")
            if entry.stack_trace:
                lines.append("  Stack:")
                for frame in entry.stack_trace:
                    lines.append(f"    {frame}")
            lines.append("")
        if entry.trace_id or entry.span_id:
            lines.append("TRACE CONTEXT:")
            if entry.trace_id:
                lines.append(f"  trace_id:       {entry.trace_id}")
            if entry.span_id:
                lines.append(f"  span_id:        {entry.span_id}")
            if entry.parent_span_id:
                lines.append(f"  parent_span_id: {entry.parent_span_id}")
            lines.append("")
        detail.text = "\n".join(lines)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key is not None:
            row_index = event.cursor_row
            if 0 <= row_index < len(self.filtered_entries):
                self.current_entry_index = row_index
                self.selected_entry = self.filtered_entries[row_index]
                self._update_detail_pane(self.selected_entry)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is not None:
            row_index = event.cursor_row
            if 0 <= row_index < len(self.filtered_entries):
                self.current_entry_index = row_index
                self.selected_entry = self.filtered_entries[row_index]
                self._update_detail_pane(self.selected_entry)

    def action_toggle_filters(self) -> None:
        self.show_filters = not self.show_filters
        self._update_view_visibility()
        self.notify(f"Filters {('shown' if self.show_filters else 'hidden')}", timeout=1)

    def action_toggle_view(self) -> None:
        self.show_table_view = not self.show_table_view
        self._update_view_visibility()
        if self.show_table_view:
            self.query_one("#trace_table", DataTable).focus()
        else:
            self.query_one("#trace_content", TextArea).focus()
        self.notify(f"{('Table' if self.show_table_view else 'Raw')} view", timeout=1)

    def action_clear_all_filters(self) -> None:
        filter_row = self.query_one("#trace_filter_row", TraceFilterRow)
        filter_row.clear_filters()
        self.notify("Filters cleared", timeout=1)

    def action_focus_next(self) -> None:
        filter_row = self.query_one("#trace_filter_row", TraceFilterRow)
        table = self.query_one("#trace_table", DataTable)
        text_area = self.query_one("#trace_content", TextArea)
        detail = self.query_one("#trace_detail", TextArea)
        filter_focused = filter_row.has_focus or any((w.has_focus for w in filter_row.query("Input, Static")))
        if filter_focused:
            if filter_row._current_filter_index < len(filter_row._filter_widgets) - 1:
                filter_row.action_focus_next_filter()
            else:
                filter_row._current_filter_index = 0
                if self.show_table_view:
                    table.focus()
                else:
                    text_area.focus()
        elif table.has_focus or text_area.has_focus:
            detail.focus()
        elif self.show_filters:
            try:
                filter_row.query_one("#filter_time").focus()
            except Exception:
                filter_row.focus()
        elif self.show_table_view:
            table.focus()
        else:
            text_area.focus()

    def action_focus_prev(self) -> None:
        filter_row = self.query_one("#trace_filter_row", TraceFilterRow)
        table = self.query_one("#trace_table", DataTable)
        text_area = self.query_one("#trace_content", TextArea)
        detail = self.query_one("#trace_detail", TextArea)
        filter_focused = filter_row.has_focus or any((w.has_focus for w in filter_row.query("Input, Static")))
        if filter_focused:
            if filter_row._current_filter_index > 0:
                filter_row.action_focus_prev_filter()
            else:
                filter_row._current_filter_index = len(filter_row._filter_widgets) - 1
                detail.focus()
        elif table.has_focus or text_area.has_focus:
            if self.show_filters:
                filter_row._current_filter_index = len(filter_row._filter_widgets) - 1
                try:
                    filter_row.query_one("#filter_message").focus()
                except Exception:
                    filter_row.focus()
            else:
                detail.focus()
        elif self.show_table_view:
            table.focus()
        else:
            text_area.focus()

    def on_trace_filter_row_filter_changed(self, event: TraceFilterRow.FilterChanged) -> None:
        filter_row = self.query_one("#trace_filter_row", TraceFilterRow)
        self.filtered_entries = filter_row.filter_entries(self.all_entries)
        self.current_entry_index = 0
        self._update_table()
        self._update_text_view()
        if self.filtered_entries:
            if self.auto_scroll:
                self._scroll_to_latest()
            else:
                self.selected_entry = self.filtered_entries[0]
                self._update_detail_pane(self.selected_entry)
        else:
            self._update_detail_pane(None)

    def action_start_search(self) -> None:
        if self.search_mode:
            return
        self.search_mode = True
        search_container = self.query_one("#search_container")
        search_container.add_class("visible")
        search_input = self.query_one("#search_input", Input)
        search_input.value = self.search_term
        search_input.focus()

    def action_handle_escape(self) -> None:
        if self.search_mode:
            self.exit_search_mode()
        else:
            trace.info(
                "Returning from TraceViewerScreen",
                tags=["screen", "navigation"],
                from_screen="TraceViewerScreen",
                reason="User pressed escape to go back",
            )
            self.app.pop_screen()

    def action_go_back(self) -> None:
        trace.info(
            "Returning from TraceViewerScreen",
            tags=["screen", "navigation"],
            from_screen="TraceViewerScreen",
            reason="User pressed back (h/left)",
        )
        self.app.pop_screen()

    def exit_search_mode(self) -> None:
        self.search_mode = False
        search_container = self.query_one("#search_container")
        search_container.remove_class("visible")
        if self.show_table_view:
            self.query_one("#trace_table", DataTable).focus()
        else:
            self.query_one("#trace_content", TextArea).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search_input":
            self.search_term = event.value.strip()
            self.perform_search()
            self.exit_search_mode()

    def perform_search(self) -> None:
        self.match_positions = []
        self.current_match = -1
        if not self.search_term:
            return
        if self.show_table_view:
            pattern = re.compile(re.escape(self.search_term), re.IGNORECASE)
            for i, entry in enumerate(self.filtered_entries):
                search_text = f"{entry.timestamp_str} {entry.severity} {entry.source} {entry.tags_str} {entry.message}"
                if entry.data:
                    search_text += " " + json.dumps(entry.data)
                if pattern.search(search_text):
                    self.match_positions.append(i)
            if self.match_positions:
                self.current_match = 0
                self.goto_match(0)
        else:
            text_area = self.query_one("#trace_content", TextArea)
            lines = text_area.text.split("\n")
            pattern = re.compile(re.escape(self.search_term), re.IGNORECASE)
            for i, line in enumerate(lines):
                if pattern.search(line):
                    self.match_positions.append(i)
            if self.match_positions:
                self.current_match = 0
                self.goto_match(0)

    def goto_match(self, match_index: int) -> None:
        if not self.match_positions:
            return
        if self.show_table_view:
            table = self.query_one("#trace_table", DataTable)
            row_index = self.match_positions[match_index]
            if row_index < table.row_count:
                table.move_cursor(row=row_index)
        else:
            line_num = self.match_positions[match_index]
            text_area = self.query_one("#trace_content", TextArea)
            text_area.cursor_location = (line_num, 0)
            text_area.scroll_cursor_visible()

    def action_search_next(self) -> None:
        if not self.match_positions:
            return
        self.current_match = (self.current_match + 1) % len(self.match_positions)
        self.goto_match(self.current_match)

    def action_search_prev(self) -> None:
        if not self.match_positions:
            return
        self.current_match = (self.current_match - 1) % len(self.match_positions)
        self.goto_match(self.current_match)

    def action_autoscroll(self) -> None:
        self.auto_scroll = not self.auto_scroll
        if self.auto_scroll:
            self._scroll_to_latest()
            self.notify("Auto-scroll ON", timeout=1)
        else:
            self.notify("Auto-scroll OFF", timeout=1)

    def _scroll_to_latest(self) -> None:
        if not self.filtered_entries:
            return
        last_index = len(self.filtered_entries) - 1
        self.current_entry_index = last_index
        self.selected_entry = self.filtered_entries[last_index]
        if self.show_table_view:
            table = self.query_one("#trace_table", DataTable)
            if table.row_count > 0:
                table.move_cursor(row=table.row_count - 1)
        else:
            text_area = self.query_one("#trace_content", TextArea)
            text_area.scroll_end(animate=False)
        self._update_detail_pane(self.selected_entry)

    def action_refresh_log(self) -> None:
        self.load_log()
        if self.search_term:
            self.perform_search()
        if self.auto_scroll:
            self._scroll_to_latest()
        self.notify("Log refreshed", timeout=1)

    def action_clear_log(self) -> None:
        try:
            clear_trace_log()
            self.search_term = ""
            self.match_positions = []
            self.current_match = -1
            self.load_log()
            self.notify("Log cleared", timeout=1)
        except Exception as e:
            self.notify(f"Error clearing log: {e}", severity="error")

    def _is_filter_widget_focused(self) -> bool:
        filter_row = self.query_one("#trace_filter_row", TraceFilterRow)
        for widget in filter_row.query("Input, Static"):
            if widget.has_focus:
                return True
        return False

    def action_scroll_down(self) -> None:
        if self._is_filter_widget_focused():
            return
        if self.show_table_view:
            table = self.query_one("#trace_table", DataTable)
            table.action_cursor_down()
        else:
            text_area = self.query_one("#trace_content", TextArea)
            text_area.scroll_relative(y=1)

    def action_scroll_up(self) -> None:
        if self._is_filter_widget_focused():
            return
        if self.show_table_view:
            table = self.query_one("#trace_table", DataTable)
            table.action_cursor_up()
        else:
            text_area = self.query_one("#trace_content", TextArea)
            text_area.scroll_relative(y=-1)

    def action_scroll_top(self) -> None:
        if self._is_filter_widget_focused():
            return
        if self.show_table_view:
            table = self.query_one("#trace_table", DataTable)
            table.move_cursor(row=0)
        else:
            text_area = self.query_one("#trace_content", TextArea)
            text_area.scroll_home(animate=False)

    def action_scroll_bottom(self) -> None:
        if self._is_filter_widget_focused():
            return
        if self.show_table_view:
            table = self.query_one("#trace_table", DataTable)
            if table.row_count > 0:
                table.move_cursor(row=table.row_count - 1)
        else:
            text_area = self.query_one("#trace_content", TextArea)
            text_area.scroll_end(animate=False)
