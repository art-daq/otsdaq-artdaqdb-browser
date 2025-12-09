"""
File: database_stats.py
Purpose: Database statistics screen.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: DatabaseStatsScreen, REPORTS_DIR
Complexity: Medium | Lines: 410
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Static, TextArea, Button
from textual.containers import Vertical, Horizontal
from textual.worker import Worker
from ..base import BaseScreen, SCROLL_BINDINGS, BACK_BINDINGS, ACTIONS_PRIMARY_BINDINGS, FOCUS_BINDINGS
from ...mixins import OutputWindowMixin, DatabaseSelectorMixin
from ...constants import WidgetID
from ...trace import trace
from ...config import ConfigLoader, AppConfig, build_mongo_shell_cmd, get_server_display_info

REPORTS_DIR = Path.home() / "artdaqdb_reports"


def _get_config() -> AppConfig:
    loader = ConfigLoader()
    (config, warnings) = loader.load()
    for warning in warnings:
        trace.warn("Config warning", tags=["config"], warning=warning)
    return config


class DatabaseStatsScreen(OutputWindowMixin, DatabaseSelectorMixin, BaseScreen):
    OUTPUT_WIDGET_ID = WidgetID.STATS_CONTENT
    DB_BUTTONS_CONTAINER_ID = "db_buttons_container"
    FALLBACK_FOCUS_WIDGET_ID = WidgetID.STATS_CONTENT
    FOCUSABLE_CONTROLS = [WidgetID.STATS_CONTENT]
    SECONDARY_ACTIONS = [("s", "save_report", "Save")]
    BINDINGS = [
        *SCROLL_BINDINGS,
        *BACK_BINDINGS,
        Binding("escape", "go_back", "Back", show=False, priority=True),
        *ACTIONS_PRIMARY_BINDINGS,
        *FOCUS_BINDINGS,
        Binding("s", "save_report", "Save", show=False, priority=True),
    ]

    def __init__(self):
        super().__init__()
        self._config: Optional[AppConfig] = None
        self.database = ""
        self.available_databases: List[str] = []
        self._auto_refresh_timer = None

    def get_focusable_controls(self) -> List[str]:
        controls = []
        if self.available_databases:
            controls.append(f"db_btn_{self.available_databases[0]}")
        controls.append(WidgetID.STATS_CONTENT)
        return controls

    def focus_first_control(self) -> None:
        self.focus_database_selector_control()

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            self._config = _get_config()
            self.database = self._config.db_utilities.default_database
        return self._config

    def compose_content(self) -> ComposeResult:
        with Vertical(classes="screen-header"):
            yield Static("Database Statistics", classes="screen-title")
        with Horizontal(id="db_buttons_container", classes="db-buttons-row"):
            yield Static("Loading databases...", id="db_buttons_placeholder")
        yield Static("", classes="status-bar", id=WidgetID.STATUS_BAR)
        yield TextArea(id=WidgetID.STATS_CONTENT, read_only=True)

    def on_mount(self) -> None:
        trace.info(
            "DatabaseStatsScreen mounted",
            tags=["screen", "lifecycle"],
            default_database=self.database,
            server=get_server_display_info(self.config),
        )
        _ = self.config
        self._update_status("Discovering databases...")
        self.run_worker(self._fetch_databases(), name="fetch_databases")
        self._start_auto_refresh()

    def _start_auto_refresh(self) -> None:
        self._stop_auto_refresh()
        interval = self.config.db_utilities.auto_refresh_interval
        if interval > 0:
            trace.debug("Starting auto-refresh timer", tags=["screen", "lifecycle"], interval_seconds=interval)
            self._auto_refresh_timer = self.set_interval(float(interval), self._auto_refresh)

    def _stop_auto_refresh(self) -> None:
        if self._auto_refresh_timer is not None:
            self._auto_refresh_timer.stop()
            self._auto_refresh_timer = None

    def _auto_refresh(self) -> None:
        if self.database:
            trace.trace("Auto-refresh triggered", tags=["screen", "event"])
            self.load_stats()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        db_name = self.handle_database_button_press(btn_id)
        if db_name:
            self.load_stats()

    def _update_status(self, status: str) -> None:
        status_bar = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        status_bar.update(status)

    def load_stats(self) -> None:
        status_bar = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        status_bar.update(f"Loading statistics for '{self.database}'...")
        text_area = self.query_one(f"#{WidgetID.STATS_CONTENT}", TextArea)
        text_area.text = f"Connecting to database '{self.database}'..."
        trace.info("Starting stats fetch", tags=["screen", "stats", "query"], database=self.database)
        self.run_worker(self._fetch_stats(), exclusive=True)

    async def _fetch_stats(self) -> str:
        try:
            js_script = """
            (function() {
                var output = [];
                var dbStats = db.stats();

                output.push("DATABASE STATISTICS REPORT");
                output.push("=======================================================================================================")
                output.push("");
                output.push("  Database:         " + dbStats.db);
                output.push("  Collections:      " + dbStats.collections);
                output.push("  Total Documents:  " + Number(dbStats.objects));

                var dataSize = Number(dbStats.dataSize) || 0;
                var storageSize = Number(dbStats.storageSize) || 0;
                var indexSize = Number(dbStats.indexSize) || 0;
                var totalSize = Number(dbStats.totalSize) || (storageSize + indexSize);

                function humanSize(bytes) {
                    if (bytes < 1024) return bytes + " B";
                    if (bytes < 1048576) return (bytes/1024).toFixed(1) + " KB";
                    if (bytes < 1073741824) return (bytes/1048576).toFixed(1) + " MB";
                    return (bytes/1073741824).toFixed(2) + " GB";
                }

                output.push("  Data Size:        " + humanSize(dataSize));
                output.push("  Storage Size:     " + humanSize(storageSize));
                output.push("  Index Size:       " + humanSize(indexSize));
                output.push("  Total Size:       " + humanSize(totalSize));

                // Get per-collection hashes using dbHash command
                var collectionHashes = {};
                var dbHashMd5 = "N/A";
                try {
                    var hashResult = db.runCommand({dbHash: 1});
                    dbHashMd5 = hashResult.md5 || "N/A";
                    if (hashResult.collections) {
                        collectionHashes = hashResult.collections;
                    }
                } catch(e) {
                    // dbHash not available
                }
                output.push("  DB Hash:          " + dbHashMd5);

                output.push("");
                output.push("--------------------------------------------------------------------------------------------------------");
                output.push("COLLECTION DETAILS");
                output.push("--------------------------------------------------------------------------------------------------------");
                output.push("");

                var fmt = function(s, len) { return (s + "                                                                                ").substring(0, len); };
                output.push(fmt("Collection", 40) + fmt("Documents", 12) + fmt("Size", 12) + fmt("Indexes", 8) + "Hash");
                output.push(fmt("----------------------------------------", 40) + fmt("------------", 12) + fmt("------------", 12) + fmt("--------", 8) + "--------------------------------");

                var colls = db.getCollectionNames().sort();
                for (var i = 0; i < colls.length; i++) {
                    var colName = colls[i];
                    try {
                        var colStats = db.getCollection(colName).stats();
                        var docCount = Number(colStats.count) || 0;
                        var size = Number(colStats.size) || 0;
                        var indexes = Number(colStats.nindexes) || 0;
                        var hash = collectionHashes[colName] || "N/A";

                        var name = colName.length > 38 ? colName.substring(0, 36) + ".." : colName;
                        output.push(fmt(name, 40) + fmt(docCount.toString(), 12) + fmt(humanSize(size), 12) + fmt(indexes.toString(), 8) + hash);
                    } catch(e) {
                        output.push(fmt(colName, 40) + fmt("ERROR", 12) + fmt("-", 12) + fmt("-", 8) + "-");
                    }
                }

                output.push("");
                output.push("--------------------------------------------------------------------------------------------------------");
                output.push("Press 'r' to refresh");
                output.push("");

                print(output.join("\n"));
            })();
            """
            cmd = build_mongo_shell_cmd(self.config, database=self.database, quiet=True)
            cmd.extend(["--eval", js_script])
            trace.debug("Executing mongo command", tags=["screen", "stats"], database=self.database)
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            (stdout, stderr) = await process.communicate()
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                trace.error(
                    "MongoDB connection failed for database stats",
                    tags=["screen", "error"],
                    error=error_msg,
                    database=self.database,
                )
                return f"Error connecting to database '{self.database}':\n\n{error_msg}"
            trace.debug("Database stats fetched successfully", tags=["screen", "query"], database=self.database)
            return stdout.decode()
        except Exception as e:
            trace.error(
                "Error fetching database statistics", tags=["screen", "error"], exception=e, database=self.database
            )
            return f"Error fetching statistics:\n\n{str(e)}"

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state.name == "SUCCESS":
            worker_name = event.worker.name
            if worker_name == "fetch_databases":
                self.available_databases = event.worker.result or []
                self._create_database_buttons()
                self.select_default_database(self.database)
                if self.database:
                    self.load_stats()
                else:
                    self._update_status("No databases available")
                    text_area = self.query_one(f"#{WidgetID.STATS_CONTENT}", TextArea)
                    text_area.text = "No user databases found.\n\nSystem databases (admin, config, local) are excluded."
                self.focus_first_control()
            else:
                result = event.worker.result
                text_area = self.query_one(f"#{WidgetID.STATS_CONTENT}", TextArea)
                text_area.text = result
                status_bar = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
                status_bar.update(
                    f"Database: {self.database} | Last updated: {datetime.now().strftime('%H:%M:%S')} | Press Enter to reload"
                )

    def action_refresh_data(self) -> None:
        trace.debug("Refresh requested", tags=["screen", "stats", "mutation"])
        self.load_stats()

    def action_go_back(self) -> None:
        self._stop_auto_refresh()
        trace.info(
            "Returning from DatabaseStatsScreen",
            tags=["screen", "navigation"],
            from_screen="DatabaseStatsScreen",
            reason="User pressed back (escape/h/left)",
        )
        self.app.pop_screen()

    def action_save_report(self) -> None:
        text_area = self.query_one(f"#{WidgetID.STATS_CONTENT}", TextArea)
        content = text_area.text
        if not content or content.startswith("Connecting") or content.startswith("Loading"):
            self.notify("No report data to save", severity="warning")
            return
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            trace.error(
                "Failed to create reports directory", tags=["screen", "error"], path=str(REPORTS_DIR), exception=e
            )
            self.notify(f"Failed to create reports directory: {e}", severity="error")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_name = self.database or "unknown"
        filename = f"database_stats_{db_name}_{timestamp}.txt"
        filepath = REPORTS_DIR / filename
        try:
            filepath.write_text(content)
            trace.info(
                "Database stats report saved", tags=["screen", "event"], filepath=str(filepath), database=db_name
            )
            self.notify(f"Report saved: {filepath}")
        except OSError as e:
            trace.error("Failed to save report", tags=["screen", "error"], filepath=str(filepath), exception=e)
            self.notify(f"Failed to save report: {e}", severity="error")
