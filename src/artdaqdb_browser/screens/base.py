"""
File: base.py
Purpose: Base screen classes with common functionality.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: BaseScreen, DataTableScreen, FilterableTableScreen, create_secondary_bindings, NAVIGATION_BINDINGS, ...
Complexity: High | Lines: 797
"""

from typing import List, Tuple, Any, Optional, Callable, Dict, ClassVar
from textual.screen import Screen
from textual.widgets import DataTable, Static, Input
from textual.binding import Binding
from textual.widget import Widget
from ..widgets import FilterInput, FooterBar, fuzzy_match
from ..constants import WidgetID, StatusMessage, ScreenName, STANDARD_KEY_PANEL_BINDINGS, get_base_key_panel_bindings
from ..trace import trace

NAVIGATION_BINDINGS = [
    Binding("j", "cursor_down", "Down", show=False),
    Binding("k", "cursor_up", "Up", show=False),
    Binding("down", "cursor_down", "Down", show=False),
    Binding("up", "cursor_up", "Up", show=False),
    Binding("g", "scroll_top", "Top", show=False),
    Binding("G", "scroll_bottom", "Bottom", show=False),
    Binding("pagedown", "page_down", "Page Down", show=False),
    Binding("pageup", "page_up", "Page Up", show=False),
]
SCREEN_NAV_BINDINGS = [
    Binding("h", "go_back", "Back", show=False),
    Binding("left", "go_back", "Back", show=False),
    Binding("l", "go_forward", "Forward", show=False),
    Binding("right", "go_forward", "Forward", show=False),
    Binding("escape", "go_back", "Back", show=False),
]
ACTIONS_PRIMARY_BINDINGS = [
    Binding("enter", "select_item", "Select", show=False),
    Binding("space", "toggle_selection", "Toggle", show=False),
    Binding("r", "refresh_data", "Refresh", show=False, priority=True),
]
FOCUS_BINDINGS = [
    Binding("tab", "cycle_focus", "Focus", show=False),
    Binding("shift+tab", "cycle_focus_reverse", "Focus", show=False),
]
BACK_BINDINGS = [
    Binding("h", "go_back", "Back", show=False, priority=True),
    Binding("left", "go_back", "Back", show=False, priority=True),
]
SCROLL_BINDINGS = [
    Binding("j", "scroll_down", "Down", show=False, priority=True),
    Binding("k", "scroll_up", "Up", show=False, priority=True),
    Binding("down", "scroll_down", "Down", show=False, priority=True),
    Binding("up", "scroll_up", "Up", show=False, priority=True),
    Binding("g", "scroll_top", "Top", show=False, priority=True),
    Binding("G", "scroll_bottom", "Bottom", show=False, priority=True),
    Binding("pagedown", "page_down", "Page Down", show=False, priority=True),
    Binding("pageup", "page_up", "Page Up", show=False, priority=True),
]
DEFAULT_SECONDARY_ACTIONS: List[Tuple[str, str, str]] = [
    ("a", "action_add", "Add"),
    ("e", "action_edit", "Edit"),
    ("d", "action_delete", "Delete"),
    ("x", "action_execute", "Execute"),
    ("u", "action_undo", "Undo"),
]


def create_secondary_bindings(actions: List[Tuple[str, str, str]]) -> List[Binding]:
    return [Binding(key, action, desc, show=False, priority=True) for (key, action, desc) in actions]


class BaseScreen(Screen):
    FOCUSABLE_CONTROLS: List[str] = []
    SECONDARY_ACTIONS: ClassVar[List[Tuple[str, str, str]]] = []
    BINDINGS = [*NAVIGATION_BINDINGS, *SCREEN_NAV_BINDINGS, *ACTIONS_PRIMARY_BINDINGS, *FOCUS_BINDINGS]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.SECONDARY_ACTIONS:
            secondary_bindings = create_secondary_bindings(cls.SECONDARY_ACTIONS)
            existing_keys = {b.key for b in cls.BINDINGS if isinstance(b, Binding)}
            new_bindings = [b for b in secondary_bindings if b.key not in existing_keys]
            if new_bindings:
                cls.BINDINGS = [*cls.BINDINGS, *new_bindings]

    @classmethod
    def get_key_panel_bindings(cls) -> List[Tuple[str, str]]:
        return STANDARD_KEY_PANEL_BINDINGS

    def __init__(self):
        super().__init__()
        self._focus_index: int = 0

    def compose(self):
        from ..widgets import KeyPanel, FooterBar

        yield KeyPanel(extra_bindings=self.get_extra_key_bindings())
        yield from self.compose_content()
        yield FooterBar()

    def compose_content(self):
        return
        yield

    def get_extra_key_bindings(self) -> List[Tuple[str, str]]:
        return []

    def _update_footer(self) -> None:

        def do_update():
            try:
                footer_bar = self.query_one(FooterBar)
                footer_bar.update_actions(self.SECONDARY_ACTIONS)
            except Exception:
                pass

        self.call_after_refresh(do_update)

    def action_select_item(self) -> None:
        pass

    def action_toggle_selection(self) -> None:
        self.action_cycle_focus_from_primary()

    def action_refresh_data(self) -> None:
        if hasattr(self.app, "action_refresh"):
            self.app.action_refresh()

    def action_scroll_top(self) -> None:
        pass

    def action_scroll_bottom(self) -> None:
        pass

    def action_page_down(self) -> None:
        pass

    def action_page_up(self) -> None:
        pass

    def action_cycle_focus_reverse(self) -> None:
        controls = self.get_focusable_controls()
        if not controls:
            return
        current = self._get_current_focus_index()
        prev_index = (current - 1) % len(controls)
        widget_id = controls[prev_index]
        if self._focus_widget_by_id(widget_id):
            self._focus_index = prev_index

    def action_cycle_focus_from_primary(self) -> None:
        controls = self.get_focusable_controls()
        if not controls:
            return
        primary_widget = self._get_focusable_widget(controls[0])
        if primary_widget and primary_widget.has_focus:
            self.action_cycle_focus()

    def action_add(self) -> None:
        pass

    def action_edit(self) -> None:
        pass

    def action_delete(self) -> None:
        pass

    def action_execute(self) -> None:
        pass

    def action_undo(self) -> None:
        pass

    def on_show(self) -> None:
        self._apply_key_panel_visibility()
        self._update_footer()

    def on_screen_resume(self) -> None:
        self._apply_key_panel_visibility()
        self._update_footer()
        if hasattr(self, "load_data") and callable(getattr(self, "load_data")):
            trace.debug(
                "Reloading data on screen resume",
                tags=["screen", "lifecycle", "refresh"],
                screen=self.__class__.__name__,
            )
            self.load_data()

    def refresh_data(self) -> None:
        if hasattr(self, "load_data") and callable(getattr(self, "load_data")):
            self.load_data()

    def _apply_key_panel_visibility(self) -> None:
        if hasattr(self.app, "apply_key_panel_visibility"):
            self.call_after_refresh(self.app.apply_key_panel_visibility)

    def get_focusable_controls(self) -> List[str]:
        return self.FOCUSABLE_CONTROLS

    def _get_focusable_widget(self, widget_id: str) -> Optional[Widget]:
        try:
            widget = self.query_one(f"#{widget_id}")
            if isinstance(widget, FilterInput):
                return widget.query_one("#filter_input_field", Input)
            return widget
        except Exception:
            return None

    def _get_current_focus_index(self) -> int:
        controls = self.get_focusable_controls()
        for i, widget_id in enumerate(controls):
            widget = self._get_focusable_widget(widget_id)
            if widget and widget.has_focus:
                return i
        return 0

    def _focus_widget_by_id(self, widget_id: str) -> bool:
        try:
            widget = self.query_one(f"#{widget_id}")
            if isinstance(widget, FilterInput):
                widget.focus()
            else:
                widget.focus()
            return True
        except Exception:
            return False

    def _find_clicked_control(self, x: int, y: int) -> Optional[str]:
        controls = self.get_focusable_controls()
        for widget_id in controls:
            try:
                widget = self.query_one(f"#{widget_id}")
                if widget.region.contains(x, y):
                    return widget_id
            except Exception:
                continue
        return None

    def on_click(self, event) -> None:
        controls = self.get_focusable_controls()
        if not controls:
            return
        clicked_id = self._find_clicked_control(event.x, event.y)
        if clicked_id:
            self._focus_widget_by_id(clicked_id)
            try:
                self._focus_index = controls.index(clicked_id)
            except ValueError:
                pass

    def action_cycle_focus(self) -> None:
        controls = self.get_focusable_controls()
        if not controls:
            return
        current = self._get_current_focus_index()
        next_index = (current + 1) % len(controls)
        widget_id = controls[next_index]
        if self._focus_widget_by_id(widget_id):
            self._focus_index = next_index

    def focus_first_control(self) -> None:
        controls = self.get_focusable_controls()
        if controls:
            widget_id = controls[0]

            def _focus():
                self._focus_widget_by_id(widget_id)

            self.call_after_refresh(_focus)
            self._focus_index = 0

    def action_go_back(self) -> None:
        trace.info(
            f"Returning from {self.__class__.__name__}",
            tags=["screen", "navigation"],
            from_screen=self.__class__.__name__,
            reason="User pressed back (h/left/escape)",
        )
        self.app.pop_screen()

    def action_go_forward(self) -> None:
        pass


class DataTableScreen(BaseScreen):
    TABLE_ID: str = "data_table"
    FOCUSABLE_CONTROLS: List[str] = []

    def get_focusable_controls(self) -> List[str]:
        if self.FOCUSABLE_CONTROLS:
            return self.FOCUSABLE_CONTROLS
        return [self.TABLE_ID]

    def get_table(self) -> DataTable:
        return self.query_one(f"#{self.TABLE_ID}", DataTable)

    def setup_table(self, columns: List[Tuple[str, str, int]]) -> None:
        table = self.get_table()
        table.cursor_type = "row"
        table.zebra_stripes = self.app.config.tables.zebra_stripes
        for label, key, width in columns:
            table.add_column(label, key=key, width=width)

    def action_cursor_down(self) -> None:
        table = self.get_table()
        if table.has_focus:
            table.action_cursor_down()

    def action_cursor_up(self) -> None:
        table = self.get_table()
        if table.has_focus:
            table.action_cursor_up()

    def action_select_item(self) -> None:
        table = self.get_table()
        if table.has_focus:
            table.action_select_cursor()

    def focus_table(self) -> None:

        def _focus():
            self.get_table().focus()

        self.call_after_refresh(_focus)

    def navigate_on_row_select(
        self, event: DataTable.RowSelected, state_method: str, next_screen: ScreenName, trace_name: str, **state_kwargs
    ) -> bool:
        if not event.row_key:
            return False
        value = str(event.row_key.value)
        target_screen = next_screen.value if hasattr(next_screen, "value") else str(next_screen)
        trace.info(
            f"Navigating to {target_screen}",
            tags=["screen", "navigation"],
            from_screen=self.__class__.__name__,
            to_screen=target_screen,
            reason=f"User selected row: {value}",
            selected_value=value,
        )
        navigate_fn = getattr(self.app.state, state_method)
        navigate_fn(value, **state_kwargs)
        self.app.push_screen(next_screen)
        return True


class FilterableTableScreen(DataTableScreen):
    FOCUSABLE_CONTROLS: List[str] = []

    def get_focusable_controls(self) -> List[str]:
        if self.FOCUSABLE_CONTROLS:
            return self.FOCUSABLE_CONTROLS
        return [self.TABLE_ID, WidgetID.FILTER_INPUT]

    FILTER_BINDINGS = [
        Binding("slash", "focus_filter", "Filter", show=False, priority=True),
        Binding("c", "clear_filter", "Clear", show=False, priority=True),
    ]
    BINDINGS = [
        *NAVIGATION_BINDINGS,
        *SCREEN_NAV_BINDINGS,
        *ACTIONS_PRIMARY_BINDINGS,
        *FOCUS_BINDINGS,
        *FILTER_BINDINGS,
        Binding("escape", "handle_escape", "Back", show=False, priority=True),
    ]

    def get_extra_key_bindings(self) -> List[Tuple[str, str]]:
        return []

    def __init__(self):
        super().__init__()
        self.all_items: List[Any] = []
        self.filtered_items: List[Any] = []
        self.filter_text: str = ""

    def get_filter_input(self) -> FilterInput:
        return self.query_one(f"#{WidgetID.FILTER_INPUT}", FilterInput)

    def get_filter_text(self) -> str:
        return self.filter_text

    def get_item_name(self, item: Any) -> str:
        return getattr(item, "name", str(item))

    def filter_items(self, filter_text: str) -> None:
        self.filter_text = filter_text
        if not filter_text:
            self.filtered_items = self.all_items.copy()
        else:
            self.filtered_items = [
                item for item in self.all_items if fuzzy_match(filter_text, self.get_item_name(item))
            ]

    def apply_filters(self) -> None:
        self.filter_items(self.filter_text)
        self.update_table()
        self.update_status()

    def on_filter_input_changed(self, event: FilterInput.Changed) -> None:
        self.filter_text = event.value.lower().strip()
        self.apply_filters()

    def on_filter_input_submitted(self, event: FilterInput.Submitted) -> None:
        self.get_table().focus()

    def action_focus_filter(self) -> None:
        self.get_filter_input().focus()

    def action_clear_filter(self) -> None:
        self.get_filter_input().clear()
        self.filter_text = ""
        self.apply_filters()
        self.get_table().focus()

    def action_handle_escape(self) -> None:
        filter_input = self.get_filter_input()
        input_widget = filter_input.query_one(f"#{WidgetID.FILTER_INPUT_FIELD}", Input)
        if input_widget.has_focus:
            filter_input.blur()
            self.get_table().focus()
        else:
            trace.info(
                f"Returning from {self.__class__.__name__}",
                tags=["screen", "navigation"],
                from_screen=self.__class__.__name__,
                reason="User pressed escape to go back",
            )
            self.app.pop_screen()

    def update_table(self) -> None:
        raise NotImplementedError

    def update_status(self) -> None:
        raise NotImplementedError

    def _update_status_bar(self, text: str) -> None:
        self.query_one(f"#{WidgetID.STATUS_BAR}", Static).update(text)

    def update_status_with_filter(self, item_type: str) -> None:
        total = len(self.all_items)
        filtered = len(self.filtered_items)
        if self.filter_text:
            self._update_status_bar(
                StatusMessage.ITEMS_FILTERED.format(
                    filtered=filtered, total=total, item_type=item_type, filter_text=self.filter_text
                )
            )
        else:
            self._update_status_bar(StatusMessage.ITEMS_TOTAL.format(total=total, item_type=item_type))


from ..mixins import LoadableDataMixin, StateBasedDataMixin
