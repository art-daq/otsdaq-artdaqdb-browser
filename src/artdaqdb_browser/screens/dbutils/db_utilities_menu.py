"""
File: db_utilities_menu.py
Purpose: Database utilities main menu screen.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: DatabaseUtilitiesScreen
Complexity: Low | Lines: 196
"""

from typing import Optional
from textual.app import ComposeResult
from textual.widgets import Static, DataTable
from textual.binding import Binding
from textual.containers import Vertical, Container
from ..base import DataTableScreen, NAVIGATION_BINDINGS, SCREEN_NAV_BINDINGS, ACTIONS_PRIMARY_BINDINGS, FOCUS_BINDINGS
from ...constants import WidgetID, ScreenName
from ...trace import trace
from ...config import ConfigLoader, AppConfig, get_server_display_info


def _get_config() -> AppConfig:
    loader = ConfigLoader()
    (config, warnings) = loader.load()
    for warning in warnings:
        trace.warn("Configuration warning", tags=["config"], warning=warning)
    return config


class DatabaseUtilitiesScreen(DataTableScreen):
    TABLE_ID = WidgetID.UTILITIES_MENU
    FOCUSABLE_CONTROLS = [WidgetID.UTILITIES_MENU]
    SECONDARY_ACTIONS = []
    BINDINGS = [*NAVIGATION_BINDINGS, *SCREEN_NAV_BINDINGS, *ACTIONS_PRIMARY_BINDINGS, *FOCUS_BINDINGS]
    MENU_ITEMS = [
        ("Server Statistics", "server_stats", "View MongoDB server status and metrics"),
        ("Database Statistics", "db_stats", "View database and collection statistics"),
        ("Cache Viewer", "cache_viewer", "View and manage application cache entries"),
        ("Recreate Indexes", "recreate_indexes", "Drop and recreate OTS Browser indexes for optimal performance"),
        ("Backup Database", "backup", "Create backup archive of a database"),
        ("Restore Database", "restore", "Restore database from backup archive"),
        ("Back to Home", "back", "Return to main menu"),
    ]

    def __init__(self):
        super().__init__()
        self._config: Optional[AppConfig] = None

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            self._config = _get_config()
        return self._config

    def compose_content(self) -> ComposeResult:
        with Vertical(classes="screen-header"):
            yield Static("Database Utilities", classes="screen-title")
        with Container(classes="utilities-menu-container"):
            yield DataTable(id=self.TABLE_ID, show_header=False)
        with Container(classes="utilities-info-container"):
            yield Static("", id="menu_description", classes="menu-description")
            yield Static("", id="server_info", classes="server-info")

    def on_mount(self) -> None:
        trace.info("DatabaseUtilitiesScreen mounted", tags=["screen", "lifecycle"])
        server_info = get_server_display_info(self.config)
        self.query_one("#server_info", Static).update(f"Server: {server_info}")
        trace.debug(
            "Loaded server configuration",
            tags=["screen", "query"],
            server_info=server_info,
            auth_type=self.config.mongodb_auth.type,
        )
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
            "server_stats": (ScreenName.SERVER_STATS, "Server Statistics"),
            "db_stats": (ScreenName.DATABASE_STATS, "Database Statistics"),
            "cache_viewer": (ScreenName.CACHE_VIEWER, "Cache Viewer"),
            "recreate_indexes": (ScreenName.RECREATE_INDEXES, "Recreate Indexes"),
            "backup": (ScreenName.DB_BACKUP, "Backup Database"),
            "restore": (ScreenName.DB_RESTORE, "Restore Database"),
        }
        if action_key == "back":
            trace.info(
                "Returning from DatabaseUtilitiesScreen",
                tags=["screen", "navigation"],
                from_screen="DatabaseUtilitiesScreen",
                reason="User selected 'Back to Home' from menu",
            )
            self.app.pop_screen()
            return
        if action_key in action_map:
            (target_screen, description) = action_map[action_key]
            trace.info(
                f"Navigating to {target_screen.value}",
                tags=["screen", "navigation"],
                from_screen="DatabaseUtilitiesScreen",
                to_screen=target_screen.value,
                reason=f"User selected '{description}' from menu",
            )
            self.app.push_screen(target_screen)

    def action_go_forward(self) -> None:
        table = self.get_table()
        if table.cursor_row is not None and table.cursor_row < len(self.MENU_ITEMS):
            action_key = self.MENU_ITEMS[table.cursor_row][1]
            self._handle_menu_action(action_key)

    def action_go_back(self) -> None:
        trace.info(
            "Returning from DatabaseUtilitiesScreen",
            tags=["screen", "navigation"],
            from_screen="DatabaseUtilitiesScreen",
            reason="User pressed back (escape/h/left)",
        )
        self.app.pop_screen()
