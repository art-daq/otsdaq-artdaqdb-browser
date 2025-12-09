"""
File: db_browser_menu.py
Purpose: Database browser main menu screen.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: DatabaseBrowserScreen
Complexity: Low | Lines: 151
"""

from textual.app import ComposeResult
from textual.widgets import Static, DataTable
from textual.containers import Vertical, Container
from ..base import DataTableScreen, NAVIGATION_BINDINGS, SCREEN_NAV_BINDINGS, ACTIONS_PRIMARY_BINDINGS, FOCUS_BINDINGS
from ...constants import WidgetID, ScreenName
from ...trace import trace


class DatabaseBrowserScreen(DataTableScreen):
    TABLE_ID = WidgetID.BROWSER_MENU
    FOCUSABLE_CONTROLS = [WidgetID.BROWSER_MENU]
    SECONDARY_ACTIONS = []
    BINDINGS = [*NAVIGATION_BINDINGS, *SCREEN_NAV_BINDINGS, *ACTIONS_PRIMARY_BINDINGS, *FOCUS_BINDINGS]
    MENU_ITEMS = [
        ("Browse by Configuration", "browse_config", "Browse configurations and their collections"),
        ("Browse by Collection", "browse_collection", "Browse all collections directly"),
        ("Back to Home", "back", "Return to main menu"),
    ]

    def compose_content(self) -> ComposeResult:
        with Vertical(classes="screen-header"):
            yield Static("Browse Database", classes="screen-title")
        with Container(classes="utilities-menu-container"):
            yield DataTable(id=self.TABLE_ID, show_header=False)
        with Container(classes="utilities-info-container"):
            yield Static("", id="menu_description", classes="menu-description")

    def on_mount(self) -> None:
        trace.info("DatabaseBrowserScreen mounted", tags=["screen", "lifecycle"])
        table = self.get_table()
        table.cursor_type = "row"
        table.zebra_stripes = self.app.config.tables.zebra_stripes
        table.add_column("Option", key="option", width=30)
        for name, key, desc in self.MENU_ITEMS:
            table.add_row(name, key=key)
        self.focus_first_control()
        self._update_description()

    def on_screen_resume(self) -> None:
        super().on_screen_resume()
        self.focus_first_control()

    def on_key(self, event) -> None:

        def update_after():
            self._update_description()

        self.call_after_refresh(update_after)

    def _update_description(self) -> None:
        table = self.get_table()
        if table.cursor_row is not None and table.cursor_row < len(self.MENU_ITEMS):
            desc = self.MENU_ITEMS[table.cursor_row][2]
            self.query_one("#menu_description", Static).update(desc)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key:
            action_key = str(event.row_key.value)
            self._handle_menu_action(action_key)

    def _handle_menu_action(self, action_key: str) -> None:
        action_map = {
            "browse_config": (ScreenName.CONFIG_LIST, "Browse by Configuration"),
            "browse_collection": (ScreenName.COLLECTION_BROWSER, "Browse by Collection"),
        }
        if action_key == "back":
            trace.info(
                "Returning from DatabaseBrowserScreen",
                tags=["screen", "navigation"],
                from_screen="DatabaseBrowserScreen",
                reason="User selected 'Back to Home' from menu",
            )
            self.app.pop_screen()
            return
        if action_key in action_map:
            (target_screen, description) = action_map[action_key]
            trace.info(
                f"Navigating to {target_screen.value}",
                tags=["screen", "navigation"],
                from_screen="DatabaseBrowserScreen",
                to_screen=target_screen.value,
                reason=f"User selected '{description}' from menu",
            )
            self.app.state.clear_analyzer()
            self.app.push_screen(target_screen)

    def action_go_forward(self) -> None:
        table = self.get_table()
        if table.cursor_row is not None and table.cursor_row < len(self.MENU_ITEMS):
            action_key = self.MENU_ITEMS[table.cursor_row][1]
            self._handle_menu_action(action_key)

    def action_go_back(self) -> None:
        trace.info(
            "Returning from DatabaseBrowserScreen",
            tags=["screen", "navigation"],
            from_screen="DatabaseBrowserScreen",
            reason="User pressed back (escape/h/left)",
        )
        self.app.pop_screen()
