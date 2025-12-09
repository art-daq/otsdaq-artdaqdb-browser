"""
File: recreate_indexes.py
Purpose: Recreate indexes screen.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: pymongo, textual
Exports: RecreateIndexesScreen
Complexity: Medium | Lines: 476
"""

from datetime import datetime
from typing import Optional, List
from textual.app import ComposeResult
from textual.widgets import Static, TextArea, Button
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.worker import Worker
from ..base import BaseScreen
from ...mixins import OutputWindowMixin, DatabaseSelectorMixin
from ...constants import WidgetID
from ...trace import trace
from ...config import ConfigLoader, AppConfig, get_server_display_info
from ...data.indexes import RECOMMENDED_INDEXES, format_index_report


def _get_config() -> AppConfig:
    loader = ConfigLoader()
    (config, warnings) = loader.load()
    for warning in warnings:
        trace.warn("Config warning", tags=["database", "index"], warning=warning)
    return config


class RecreateIndexesScreen(OutputWindowMixin, DatabaseSelectorMixin, BaseScreen):
    OUTPUT_WIDGET_ID = WidgetID.OUTPUT_LOG
    DB_BUTTONS_CONTAINER_ID = "db_buttons_container"
    FALLBACK_FOCUS_WIDGET_ID = WidgetID.OUTPUT_LOG
    FOCUSABLE_CONTROLS = [WidgetID.OUTPUT_LOG]
    SECONDARY_ACTIONS = [("e", "recreate_indexes", "Recreate")]
    BINDINGS = [
        Binding("j", "select_next", "Next db", show=False, priority=True),
        Binding("k", "select_prev", "Prev db", show=False, priority=True),
        Binding("down", "select_next", "Next db", show=False, priority=True),
        Binding("up", "select_prev", "Prev db", show=False, priority=True),
        Binding("g", "scroll_top", "Top", show=False, priority=True),
        Binding("G", "scroll_bottom", "Bottom", show=False, priority=True),
        Binding("pagedown", "page_down", "Page Down", show=False, priority=True),
        Binding("pageup", "page_up", "Page Up", show=False, priority=True),
        Binding("h", "go_back", "Back", show=False, priority=True),
        Binding("left", "go_back", "Back", show=False, priority=True),
        Binding("escape", "go_back", "Back", show=False, priority=True),
        Binding("tab", "cycle_focus", "Focus", show=False),
        Binding("shift+tab", "cycle_focus_reverse", "Focus", show=False),
        Binding("r", "refresh_data", "Refresh", show=False, priority=True),
        Binding("e", "recreate_indexes", "Recreate", show=False, priority=True),
    ]

    def __init__(self):
        super().__init__()
        self._config: Optional[AppConfig] = None
        self.database = ""
        self.available_databases: List[str] = []
        self._is_running = False

    def get_focusable_controls(self) -> List[str]:
        controls = []
        if self.available_databases:
            for db_name in self.available_databases:
                controls.append(f"db_btn_{db_name}")
        controls.append(WidgetID.OUTPUT_LOG)
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
            yield Static("Recreate Indexes", classes="screen-title")
        with Horizontal(id="db_buttons_container", classes="db-buttons-row"):
            yield Static("Loading databases...", id="db_buttons_placeholder")
        yield Static("", classes="status-bar", id=WidgetID.STATUS_BAR)
        yield TextArea(id=WidgetID.OUTPUT_LOG, read_only=True)

    def on_mount(self) -> None:
        trace.info("RecreateIndexesScreen mounted", tags=["screen", "lifecycle"])
        _ = self.config
        trace.debug(
            "Mounted with config",
            tags=["database", "index", "lifecycle"],
            default_database=self.database,
            server=get_server_display_info(self.config),
        )
        self._show_initial_info()
        self._update_status("Discovering databases...")
        self.run_worker(self._fetch_databases(), name="fetch_databases")

    def _show_initial_info(self) -> None:
        text_area = self.query_one(f"#{WidgetID.OUTPUT_LOG}", TextArea)
        lines = []
        lines.append("MONGODB INDEX MANAGEMENT")
        lines.append("=" * 100)
        lines.append("")
        lines.append("This utility recreates recommended indexes on all collections in the selected database.")
        lines.append("")
        lines.append("WARNING: Selecting a database will:")
        lines.append("  1. DROP existing OTS Browser indexes (if they exist)")
        lines.append("  2. CREATE new indexes with current specifications")
        lines.append("")
        lines.append("Index creation runs in the background and may take time for large collections.")
        lines.append("")
        lines.append("-" * 100)
        lines.append("RECOMMENDED INDEXES")
        lines.append("-" * 100)
        lines.append("")
        for idx in RECOMMENDED_INDEXES:
            keys_str = ", ".join((f"{k}:{d}" for (k, d) in idx.keys))
            lines.append(f"  {idx.name}")
            lines.append(f"    Keys: {keys_str}")
            lines.append(f"    Purpose: {idx.description}")
            lines.append("")
        lines.append("-" * 100)
        lines.append("Select a database above to recreate indexes.")
        lines.append("")
        text_area.text = "\n".join(lines)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id.startswith("db_btn_") and (not self._is_running):
            db_name = self.handle_database_button_press(btn_id)
            if db_name:
                self._update_status(f"Selected: {db_name} - Press e to recreate indexes")

    def _update_status(self, status: str) -> None:
        status_bar = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        status_bar.update(status)

    def recreate_indexes(self) -> None:
        if self._is_running:
            self._update_status("Index operation already in progress...")
            return
        if not self.database:
            self.notify("Please select a database first", severity="warning")
            return
        self._is_running = True
        self._update_status(f"Recreating indexes on '{self.database}'...")
        text_area = self.query_one(f"#{WidgetID.OUTPUT_LOG}", TextArea)
        text_area.text = f"Connecting to database '{self.database}'...\n\nRecreating indexes, please wait..."
        text_area.focus()
        trace.info("Starting index recreation", tags=["database", "index", "lifecycle"], database=self.database)
        self.run_worker(self._do_recreate_indexes(), name="recreate_indexes", exclusive=True)

    async def _do_recreate_indexes(self) -> str:
        try:
            from pymongo import MongoClient
            from pymongo.errors import ConnectionFailure
            from ...config import parse_mongodb_uri
            from ...data.indexes import recreate_indexes_on_database, format_index_report

            mongo_config = self.config.data_source.mongodb
            auth_config = self.config.mongodb_auth
            (host, port, uri_database) = parse_mongodb_uri(mongo_config.uri)
            options = {
                "connectTimeoutMS": mongo_config.connect_timeout_ms,
                "serverSelectionTimeoutMS": mongo_config.server_selection_timeout_ms,
                "directConnection": mongo_config.direct_connection,
            }
            if mongo_config.socket_timeout_ms > 0:
                options["socketTimeoutMS"] = mongo_config.socket_timeout_ms
            if auth_config.type == "none":
                uri = f"mongodb://{host}:{port}/"
                if mongo_config.requires_tls:
                    options["tls"] = True
                client = MongoClient(uri, **options)
            elif auth_config.type == "x509":
                x509 = auth_config.x509
                cert_dir = x509.get_cert_dir_path()
                ca_cert = cert_dir / x509.ca_cert
                client_cert = cert_dir / x509.client_cert
                uri = f"mongodb://{host}:{port}/"
                options.update(
                    {
                        "tls": True,
                        "tlsCAFile": str(ca_cert),
                        "tlsCertificateKeyFile": str(client_cert),
                        "authMechanism": x509.auth_mechanism,
                        "authSource": x509.auth_source,
                    }
                )
                if x509.allow_invalid_certificates:
                    options["tlsAllowInvalidCertificates"] = True
                if x509.allow_invalid_hostnames:
                    options["tlsAllowInvalidHostnames"] = True
                client = MongoClient(uri, **options)
            elif auth_config.type == "userpass":
                userpass = auth_config.userpass
                uri = f"mongodb://{host}:{port}/"
                options.update(
                    {"username": userpass.user, "password": userpass.password, "authSource": userpass.auth_source}
                )
                if userpass.auth_mechanism != "DEFAULT":
                    options["authMechanism"] = userpass.auth_mechanism
                if mongo_config.requires_tls:
                    options["tls"] = True
                client = MongoClient(uri, **options)
            else:
                return f"Error: Unsupported authentication type: {auth_config.type}"
            try:
                client.admin.command("ping")
            except ConnectionFailure as e:
                return f"Error connecting to MongoDB:\n\n{str(e)}"
            db = client[self.database]
            trace.info("Connected, recreating indexes", tags=["database", "index", "lifecycle"], database=self.database)
            result = recreate_indexes_on_database(db, drop_existing=True)
            client.close()
            report = format_index_report(result, verbose=True)
            trace.debug(
                "Index recreation complete",
                tags=["database", "index", "lifecycle"],
                created=result.get("total_created", 0),
                dropped=result.get("total_dropped", 0),
                errors=result.get("total_errors", 0),
            )
            return report
        except ImportError as e:
            return f"Error: pymongo not installed.\n\n{str(e)}"
        except Exception as e:
            trace.error("Error recreating indexes", tags=["database", "error"], exception=e, database=self.database)
            return f"Error recreating indexes:\n\n{str(e)}"

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state.name == "SUCCESS":
            worker_name = event.worker.name
            if worker_name == "fetch_databases":
                self.available_databases = event.worker.result or []
                self._create_database_buttons()
                self.select_default_database(self.database)
                if not self.available_databases:
                    self._update_status("No databases available")
                else:
                    self._update_status(
                        f"Select a database to recreate indexes | {len(self.available_databases)} databases available"
                    )
                self.focus_first_control()
            elif worker_name == "recreate_indexes":
                self._is_running = False
                result = event.worker.result
                self._set_output_text(result, autoscroll=True)
                self._update_status(
                    f"Database: {self.database} | Completed: {datetime.now().strftime('%H:%M:%S')} | Press e to recreate again"
                )
                try:
                    if hasattr(self.app, "action_cache_clear"):
                        trace.info(
                            "Clearing pickle cache after index recreation",
                            tags=["screen", "indexes", "cache"],
                            database=self.database,
                        )
                        self.app.action_cache_clear()
                except Exception:
                    pass
        elif event.state.name == "ERROR":
            self._is_running = False
            error = str(event.worker.error) if event.worker.error else "Unknown error"
            self._update_status(f"Error: {error}")
            text_area = self.query_one(f"#{WidgetID.OUTPUT_LOG}", TextArea)
            text_area.text = f"Error during index recreation:\n\n{error}"

    def action_recreate_indexes(self) -> None:
        trace.debug(
            "Recreate indexes action triggered",
            tags=["screen", "indexes", "action"],
            is_running=self._is_running,
            database=self.database,
        )
        if self._is_running:
            return
        if self.database:
            self.recreate_indexes()
        else:
            self.notify("Please select a database first", severity="warning")

    def action_select_next(self) -> None:
        focused = self.focused
        if focused and hasattr(focused, "id") and (focused.id == WidgetID.OUTPUT_LOG):
            self.action_scroll_down()
            return
        if focused and hasattr(focused, "id") and focused.id and focused.id.startswith("db_btn_"):
            self._focus_next_db_button()

    def action_select_prev(self) -> None:
        focused = self.focused
        if focused and hasattr(focused, "id") and (focused.id == WidgetID.OUTPUT_LOG):
            self.action_scroll_up()
            return
        if focused and hasattr(focused, "id") and focused.id and focused.id.startswith("db_btn_"):
            self._focus_prev_db_button()

    def _focus_next_db_button(self) -> None:
        if not self.available_databases:
            return
        focused = self.focused
        if not focused or not focused.id:
            return
        current_db = focused.id.replace("db_btn_", "")
        try:
            idx = self.available_databases.index(current_db)
            next_idx = min(idx + 1, len(self.available_databases) - 1)
            next_btn_id = f"db_btn_{self.available_databases[next_idx]}"
            self.query_one(f"#{next_btn_id}", Button).focus()
        except (ValueError, Exception):
            pass

    def _focus_prev_db_button(self) -> None:
        if not self.available_databases:
            return
        focused = self.focused
        if not focused or not focused.id:
            return
        current_db = focused.id.replace("db_btn_", "")
        try:
            idx = self.available_databases.index(current_db)
            prev_idx = max(idx - 1, 0)
            prev_btn_id = f"db_btn_{self.available_databases[prev_idx]}"
            self.query_one(f"#{prev_btn_id}", Button).focus()
        except (ValueError, Exception):
            pass

    def action_go_back(self) -> None:
        if self._is_running:
            self.notify("Index recreation in progress", severity="warning")
            return
        trace.info(
            "Returning from RecreateIndexesScreen",
            tags=["screen", "navigation"],
            from_screen="RecreateIndexesScreen",
            reason="User pressed back (escape/h/left)",
        )
        self.app.pop_screen()
