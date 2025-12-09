"""
File: server_stats.py
Purpose: Server statistics screen.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: ServerStatsScreen, REPORTS_DIR
Complexity: Medium | Lines: 453
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional
from textual.app import ComposeResult
from textual.widgets import Static, TextArea
from textual.containers import Vertical
from textual.worker import Worker
from textual.binding import Binding
from ..base import BaseScreen, SCROLL_BINDINGS, BACK_BINDINGS, ACTIONS_PRIMARY_BINDINGS, FOCUS_BINDINGS
from ...mixins import OutputWindowMixin
from ...constants import WidgetID
from ...trace import trace
from ...config import ConfigLoader, AppConfig, build_mongo_shell_cmd, get_server_display_info

REPORTS_DIR = Path.home() / "artdaqdb_reports"


def _get_config() -> AppConfig:
    loader = ConfigLoader()
    (config, warnings) = loader.load()
    for warning in warnings:
        trace.warn("Configuration warning", tags=["config"], warning=warning)
    return config


class ServerStatsScreen(OutputWindowMixin, BaseScreen):
    OUTPUT_WIDGET_ID = WidgetID.STATS_CONTENT
    FOCUSABLE_CONTROLS = [WidgetID.STATS_CONTENT]
    SECONDARY_ACTIONS = [("a", "toggle_extended", "Extended"), ("s", "save_report", "Save")]
    BINDINGS = [
        *SCROLL_BINDINGS,
        *BACK_BINDINGS,
        Binding("escape", "go_back", "Back", show=False, priority=True),
        *ACTIONS_PRIMARY_BINDINGS,
        *FOCUS_BINDINGS,
        Binding("a", "toggle_extended", "Extended", show=False, priority=True),
        Binding("s", "save_report", "Save", show=False, priority=True),
    ]

    def __init__(self):
        super().__init__()
        self._config: Optional[AppConfig] = None
        self.show_extended = False
        self.stats_content = ""
        self._auto_refresh_timer = None

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            self._config = _get_config()
            self.show_extended = self._config.db_utilities.extended_stats
        return self._config

    def compose_content(self) -> ComposeResult:
        with Vertical(classes="screen-header"):
            yield Static("Server Statistics", classes="screen-title")
        yield Static("", classes="status-bar", id=WidgetID.STATUS_BAR)
        yield TextArea(id=WidgetID.STATS_CONTENT, read_only=True)

    def on_mount(self) -> None:
        trace.info(
            "ServerStatsScreen mounted",
            tags=["screen", "lifecycle"],
            server=get_server_display_info(self.config),
            extended_stats=self.show_extended,
        )
        self.load_stats()
        self.focus_first_control()
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
        trace.trace("Auto-refresh triggered", tags=["screen", "event"])
        self.load_stats()

    def load_stats(self) -> None:
        status_bar = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        status_bar.update("Loading server statistics...")
        text_area = self.query_one(f"#{WidgetID.STATS_CONTENT}", TextArea)
        server_info = get_server_display_info(self.config)
        text_area.text = f"Connecting to MongoDB server ({server_info})..."
        trace.debug("Starting server stats fetch", tags=["screen", "query"], extended=self.show_extended)
        self.run_worker(self._fetch_stats(), exclusive=True)

    async def _fetch_stats(self) -> str:
        try:
            show_all = "true" if self.show_extended else "false"
            js_script = f"""\n            (function() {{\n                var showAll = {show_all};\n                var output = [];\n                var status = db.serverStatus();\n\n                output.push("SERVER STATISTICS REPORT");\n                output.push("================================================================================");\n                output.push("");\n                output.push("SERVER INFORMATION");\n                output.push("  Host:              " + (status.host || "N/A"));\n                output.push("  MongoDB Version:   " + (status.version || "N/A"));\n                output.push("  Storage Engine:    " + ((status.storageEngine && status.storageEngine.name) || "N/A"));\n                output.push("  Process ID:        " + (status.pid || "N/A"));\n\n                var uptime = Number(status.uptime) || 0;\n                var days = Math.floor(uptime / 86400);\n                var hours = Math.floor((uptime % 86400) / 3600);\n                var mins = Math.floor((uptime % 3600) / 60);\n                var uptimeStr = days > 0 ? days + "d " + hours + "h " + mins + "m" : hours + "h " + mins + "m";\n                output.push("  Uptime:            " + uptimeStr);\n                output.push("  Server Time:       " + (status.localTime ? status.localTime.toISOString() : "N/A"));\n                output.push("");\n\n                output.push("--------------------------------------------------------------------------------");\n                output.push("REPLICA SET");\n                try {{\n                    var rsStatus = rs.status();\n                    if (rsStatus.ok === 1) {{\n                        output.push("  Replica Set:       " + (rsStatus.set || "N/A"));\n                        var primary = rsStatus.members.find(function(m) {{ return m.stateStr === "PRIMARY"; }});\n                        output.push("  Primary:           " + (primary ? primary.name : "N/A"));\n                        output.push("");\n                        output.push("  Member                        State        Health");\n                        output.push("  --------------------------    ----------   ------");\n                        rsStatus.members.forEach(function(m) {{\n                            var health = m.health === 1 ? "OK" : "DOWN";\n                            var name = (m.name + "                              ").substring(0, 28);\n                            var state = (m.stateStr + "          ").substring(0, 12);\n                            output.push("  " + name + state + health);\n                        }});\n                    }}\n                }} catch(e) {{\n                    output.push("  Status:            Standalone (not a replica set)");\n                }}\n                output.push("");\n\n                output.push("--------------------------------------------------------------------------------");\n                output.push("CONNECTIONS");\n                output.push("  Current:           " + (status.connections.current || 0));\n                output.push("  Active:            " + (status.connections.active || 0));\n                output.push("  Available:         " + (status.connections.available || 0));\n                output.push("  Total Created:     " + (status.connections.totalCreated || 0));\n                output.push("");\n\n                output.push("--------------------------------------------------------------------------------");\n                output.push("MEMORY USAGE");\n                if (status.mem) {{\n                    output.push("  Resident:          " + (status.mem.resident || 0) + " MB");\n                    output.push("  Virtual:           " + (status.mem.virtual || 0) + " MB");\n                }}\n                output.push("");\n\n                output.push("--------------------------------------------------------------------------------");\n                output.push("OPERATIONS (since startup)");\n                if (status.opcounters) {{\n                    output.push("  Insert:            " + (status.opcounters.insert || 0));\n                    output.push("  Query:             " + (status.opcounters.query || 0));\n                    output.push("  Update:            " + (status.opcounters.update || 0));\n                    output.push("  Delete:            " + (status.opcounters.delete || 0));\n                    output.push("  Command:           " + (status.opcounters.command || 0));\n                }}\n                output.push("");\n\n                output.push("--------------------------------------------------------------------------------");\n                output.push("NETWORK");\n                if (status.network) {{\n                    var bytesIn = Number(status.network.bytesIn) || 0;\n                    var bytesOut = Number(status.network.bytesOut) || 0;\n                    output.push("  Bytes In:          " + (bytesIn / 1048576).toFixed(1) + " MB");\n                    output.push("  Bytes Out:         " + (bytesOut / 1048576).toFixed(1) + " MB");\n                    output.push("  Total Requests:    " + (status.network.numRequests || 0));\n                }}\n                output.push("");\n\n                if (showAll) {{\n                    output.push("--------------------------------------------------------------------------------");\n                    output.push("WIREDTIGER CACHE");\n                    if (status.wiredTiger && status.wiredTiger.cache) {{\n                        var cache = status.wiredTiger.cache;\n                        var maxBytes = Number(cache["maximum bytes configured"]) || 0;\n                        var currentBytes = Number(cache["bytes currently in the cache"]) || 0;\n                        output.push("  Max Cache Size:    " + (maxBytes / 1073741824).toFixed(2) + " GB");\n                        output.push("  Bytes In Cache:    " + (currentBytes / 1073741824).toFixed(2) + " GB");\n                        if (maxBytes > 0) {{\n                            output.push("  Cache Usage:       " + ((currentBytes / maxBytes) * 100).toFixed(1) + "%");\n                        }}\n                        output.push("  Pages Read:        " + (cache["pages read into cache"] || 0));\n                        output.push("  Pages Written:     " + (cache["pages written from cache"] || 0));\n                    }}\n                    output.push("");\n\n                    output.push("--------------------------------------------------------------------------------");\n                    output.push("GLOBAL LOCKS");\n                    if (status.globalLock && status.globalLock.currentQueue) {{\n                        output.push("  Queue Readers:     " + (status.globalLock.currentQueue.readers || 0));\n                        output.push("  Queue Writers:     " + (status.globalLock.currentQueue.writers || 0));\n                    }}\n                    if (status.globalLock && status.globalLock.activeClients) {{\n                        output.push("  Active Readers:    " + (status.globalLock.activeClients.readers || 0));\n                        output.push("  Active Writers:    " + (status.globalLock.activeClients.writers || 0));\n                    }}\n                    output.push("");\n                }}\n\n                output.push("--------------------------------------------------------------------------------");\n                if (showAll) {{\n                    output.push("Press 'a' to toggle extended statistics off");\n                }} else {{\n                    output.push("Press 'a' for extended statistics | Press 'r' to refresh");\n                }}\n                output.push("");\n\n                print(output.join("\\n"));\n            }})();\n            """
            cmd = build_mongo_shell_cmd(self.config, database="admin", quiet=True)
            cmd.extend(["--eval", js_script])
            trace.trace("Executing mongo shell command", tags=["screen", "query"], cmd_length=len(cmd))
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            (stdout, stderr) = await process.communicate()
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                server_info = get_server_display_info(self.config)
                if "not authorized" in error_msg or "unauthorized" in error_msg.lower():
                    trace.warn("User lacks permissions for server stats", tags=["screen", "auth"], error=error_msg)
                    return f"""PERMISSION DENIED\n================================================================================\n\nYour MongoDB user does not have permission to view server statistics.\n\nThe 'serverStatus' command requires the 'clusterMonitor' role on the 'admin'\ndatabase, which is typically reserved for database administrators.\n\n--------------------------------------------------------------------------------\nTO GRANT ACCESS (requires admin privileges):\n\n  Connect to MongoDB as an admin user and run:\n\n    use admin\n    db.grantRolesToUser("<your_username>", [\n      {{ role: "clusterMonitor", db: "admin" }}\n    ])\n\n--------------------------------------------------------------------------------\nALTERNATIVE:\n\n  Contact your database administrator to request the 'clusterMonitor' role,\n  or use 'Database Info' from the utilities menu for basic database metrics\n  that don't require admin privileges.\n\nServer: {server_info}\n"""
                trace.error("MongoDB connection failed for server stats", tags=["screen", "error"], error=error_msg)
                return f"Error connecting to MongoDB:\n\n{error_msg}\n\nServer: {server_info}\n\nMake sure:\n1. MongoDB server is accessible\n2. Authentication is configured correctly in appconfig.yml\n3. mongosh or mongo client is installed"
            trace.debug("Server stats fetched successfully", tags=["screen", "query"])
            return stdout.decode()
        except FileNotFoundError:
            trace.error("MongoDB client not found", tags=["screen", "error"], error="mongosh/mongo not found")
            return "Error: mongosh/mongo client not found.\n\nPlease install MongoDB client tools."
        except Exception as e:
            trace.error("Error fetching server statistics", tags=["screen", "error"], exception=e)
            return f"Error fetching statistics:\n\n{str(e)}"

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state.name == "SUCCESS":
            result = event.worker.result
            text_area = self.query_one(f"#{WidgetID.STATS_CONTENT}", TextArea)
            text_area.text = result
            status_bar = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
            mode = "Extended" if self.show_extended else "Basic"
            status_bar.update(f"{mode} statistics | Last updated: {datetime.now().strftime('%H:%M:%S')}")

    def action_refresh_data(self) -> None:
        trace.debug("Refresh server stats requested", tags=["screen", "event"])
        self.load_stats()

    def action_toggle_extended(self) -> None:
        self.show_extended = not self.show_extended
        trace.debug("Extended stats display toggled", tags=["screen", "event"], extended=self.show_extended)
        self.load_stats()

    def action_go_back(self) -> None:
        self._stop_auto_refresh()
        trace.info(
            "Returning from ServerStatsScreen",
            tags=["screen", "navigation"],
            from_screen="ServerStatsScreen",
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
        mode = "extended" if self.show_extended else "basic"
        filename = f"server_stats_{mode}_{timestamp}.txt"
        filepath = REPORTS_DIR / filename
        try:
            filepath.write_text(content)
            trace.info("Server stats report saved", tags=["screen", "event"], filepath=str(filepath), mode=mode)
            self.notify(f"Report saved: {filepath}")
        except OSError as e:
            trace.error("Failed to save report", tags=["screen", "error"], filepath=str(filepath), exception=e)
            self.notify(f"Failed to save report: {e}", severity="error")
