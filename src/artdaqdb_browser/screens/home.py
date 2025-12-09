"""
File: home.py
Purpose: Home screen with main menu.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: HomeScreen
Complexity: Medium | Lines: 336
"""

import asyncio
from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Static, DataTable
from textual.binding import Binding
from textual.events import Click
from textual.worker import Worker
from .base import DataTableScreen, NAVIGATION_BINDINGS, SCREEN_NAV_BINDINGS, ACTIONS_PRIMARY_BINDINGS, FOCUS_BINDINGS
from ..widgets import LoadingProgress
from ..constants import WidgetID, ScreenName
from ..trace import trace
from ..config import ConfigLoader


class HomeScreen(DataTableScreen):
    TABLE_ID = WidgetID.MENU_TABLE
    FOCUSABLE_CONTROLS = [WidgetID.MENU_TABLE]
    BINDINGS = [
        *NAVIGATION_BINDINGS,
        *SCREEN_NAV_BINDINGS,
        *ACTIONS_PRIMARY_BINDINGS,
        *FOCUS_BINDINGS,
        Binding("q", "quit", "Quit", show=False),
    ]
    MENU_ITEMS = [
        ("Browse Database", "db_browser"),
        ("Database Doctor", "db_doctor"),
        ("Database Utilities", "db_utilities"),
        ("Configuration", "config_editor"),
        ("View Trace Log", "trace_log"),
        ("Cache Management", "cache_mgmt"),
        ("Quit", "quit"),
    ]

    def compose_content(self) -> ComposeResult:
        with Container(classes="top-half"):
            with Container(classes="menu-container"):
                yield Static("OTS Configuration Browser", classes="screen-title")
                yield DataTable(id=self.TABLE_ID, show_header=False)
        with Container(classes="bottom-half"):
            with Vertical(classes="summary-container"):
                yield Static("Database Summary", classes="summary-title")
                with Horizontal(classes="summary-row"):
                    yield Static("Backend:", classes="summary-label")
                    yield Static("Loading...", classes="summary-value", id=WidgetID.SUMMARY_CONFIGS)
                with Horizontal(classes="summary-row"):
                    yield Static("Connection:", classes="summary-label")
                    yield Static("Loading...", classes="summary-value", id=WidgetID.SUMMARY_DOCS)
                with Horizontal(classes="summary-row"):
                    yield Static("Collections:", classes="summary-label")
                    yield Static("Loading...", classes="summary-value", id=WidgetID.SUMMARY_COLLECTIONS)
                yield Static("", classes="summary-divider")
                with Horizontal(classes="summary-row"):
                    yield Static("Cache Status:", classes="summary-label")
                    yield Static("Loading...", classes="summary-value", id=WidgetID.SUMMARY_CACHE)
        yield LoadingProgress(id="loading_progress")

    def __init__(self):
        super().__init__()
        self._loading = False
        self._stats_loaded = False

    def on_mount(self) -> None:
        trace.info("HomeScreen mounted", tags=["screen", "lifecycle"])
        table = self.get_table()
        table.cursor_type = "row"
        table.zebra_stripes = self.app.config.tables.zebra_stripes
        table.add_column("Option", key="option")
        for name, key in self.MENU_ITEMS:
            table.add_row(name, key=key)
        self._start_loading_stats()
        self.focus_first_control()

    def on_screen_resume(self) -> None:
        self._apply_key_panel_visibility()
        self._update_footer()
        self.focus_first_control()
        if not self._loading:
            self._start_loading_stats()

    def refresh_data(self) -> None:
        if not self._loading:
            self._start_loading_stats()

    def on_click(self, event: Click) -> None:
        self.focus_first_control()

    def _start_loading_stats(self) -> None:
        if self._loading:
            return
        self._loading = True
        loading_progress = self.query_one("#loading_progress", LoadingProgress)
        loading_progress.start()
        self.run_worker(self._load_stats_async(), name="load_stats", exclusive=True)

    def _load_stats_sync(self) -> dict:
        result = {
            "backend_type": None,
            "connection_info": None,
            "collection_count": None,
            "cache_stats": None,
            "error": None,
        }
        try:
            loader = ConfigLoader()
            (config, _) = loader.load()
            result["backend_type"] = config.data_source.type
            if result["backend_type"] == "mongodb":
                mongo_cfg = config.data_source.mongodb
                uri = mongo_cfg.uri
                if uri.startswith("mongodb://"):
                    uri_part = uri.replace("mongodb://", "").split("?")[0]
                    result["connection_info"] = uri_part
                else:
                    result["connection_info"] = f"{mongo_cfg.database}"
            else:
                result["connection_info"] = config.data_source.filesystem.path
            backend = self.app.backend
            if backend:
                collections = backend.list_collections_optimized()
                result["collection_count"] = len(collections)
            if self.app.cache:
                result["cache_stats"] = self.app.cache.get_stats()
        except Exception as e:
            result["error"] = str(e)
        return result

    async def _load_stats_async(self) -> dict:
        trace.debug("Loading database summary in background", tags=["screen", "query"])
        return await asyncio.to_thread(self._load_stats_sync)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name != "load_stats":
            return
        if event.state.name not in ("SUCCESS", "ERROR", "CANCELLED"):
            return
        loading_progress = self.query_one("#loading_progress", LoadingProgress)
        loading_progress.stop()
        self._loading = False
        if event.state.name == "SUCCESS":
            result = event.worker.result
            self._apply_stats(result)
            self._stats_loaded = True
        elif event.state.name == "ERROR":
            error_msg = str(event.worker.error) if event.worker.error else "Unknown error"
            self._apply_error(error_msg)

    def _apply_stats(self, result: dict) -> None:
        if result.get("error"):
            self._apply_error(result["error"])
            return
        if result["backend_type"]:
            self.query_one(f"#{WidgetID.SUMMARY_CONFIGS}", Static).update(result["backend_type"])
        if result["connection_info"]:
            conn_info = result["connection_info"]
            if len(conn_info) > 35:
                if result["backend_type"] == "mongodb":
                    conn_info = conn_info[:32] + "..."
                else:
                    conn_info = "..." + conn_info[-32:]
            self.query_one(f"#{WidgetID.SUMMARY_DOCS}", Static).update(conn_info)
        if result["collection_count"] is not None:
            self.query_one(f"#{WidgetID.SUMMARY_COLLECTIONS}", Static).update(str(result["collection_count"]))
            trace.debug(
                "Database summary loaded successfully",
                tags=["screen", "query"],
                backend_type=result["backend_type"],
                collection_count=result["collection_count"],
            )
        else:
            self.query_one(f"#{WidgetID.SUMMARY_COLLECTIONS}", Static).update("N/A")
        if result["cache_stats"]:
            stats = result["cache_stats"]
            hit_rate = 0
            total = stats.get("hits", 0) + stats.get("misses", 0)
            if total > 0:
                hit_rate = stats.get("hits", 0) / total * 100
            cache_text = f"Enabled ({stats.get('size', 0)} entries, {hit_rate:.0f}% hit rate)"
            self.query_one(f"#{WidgetID.SUMMARY_CACHE}", Static).update(cache_text)
        else:
            self.query_one(f"#{WidgetID.SUMMARY_CACHE}", Static).update("Disabled")

    def _apply_error(self, error: str) -> None:
        trace.error("Failed to load database summary", tags=["screen", "error"], error=error)
        self.query_one(f"#{WidgetID.SUMMARY_CONFIGS}", Static).update("Error")
        self.query_one(f"#{WidgetID.SUMMARY_DOCS}", Static).update(error[:35])
        self.query_one(f"#{WidgetID.SUMMARY_COLLECTIONS}", Static).update("Error")
        self.query_one(f"#{WidgetID.SUMMARY_CACHE}", Static).update("Unknown")

    def update_stats(self) -> None:
        self._start_loading_stats()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key:
            action_key = str(event.row_key.value)
            self._handle_menu_action(action_key)

    def _handle_menu_action(self, action_key: str) -> None:
        action_map = {
            "db_browser": (ScreenName.DB_BROWSER, "Browse Database"),
            "db_doctor": (ScreenName.DB_DOCTOR, "Database Doctor"),
            "db_utilities": (ScreenName.DB_UTILITIES, "Database Utilities"),
            "config_editor": (ScreenName.CONFIG_EDITOR, "Configuration Editor"),
            "trace_log": (ScreenName.TRACE_VIEWER, "Trace Log Viewer"),
            "cache_mgmt": (ScreenName.CACHE_VIEWER, "Cache Management"),
        }
        if action_key == "quit":
            trace.info(
                "User requested application quit from menu",
                tags=["screen", "navigation", "lifecycle"],
                from_screen="HomeScreen",
                reason="User selected Quit from menu",
            )
            self.app.exit()
            return
        if action_key in action_map:
            (target_screen, description) = action_map[action_key]
            trace.info(
                f"Navigating to {target_screen.value}",
                tags=["screen", "navigation"],
                from_screen="HomeScreen",
                to_screen=target_screen.value,
                reason=f"User selected '{description}' from menu",
            )
            self.app.push_screen(target_screen)

    def action_quit(self) -> None:
        self.app.exit()

    def action_go_forward(self) -> None:
        table = self.get_table()
        if table.cursor_row is not None and table.cursor_row < len(self.MENU_ITEMS):
            action_key = self.MENU_ITEMS[table.cursor_row][1]
            self._handle_menu_action(action_key)

    def action_go_back(self) -> None:
        pass
