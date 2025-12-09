"""
File: backup_screen.py
Purpose: Database backup screen.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: BackupScreen
Complexity: Medium | Lines: 462
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from textual.app import ComposeResult
from textual.widgets import Static, TextArea, Button
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.worker import Worker
from ..base import BaseScreen
from .directory_browser import DirectoryBrowserModal
from ...mixins import OutputWindowMixin, DatabaseSelectorMixin
from ...constants import WidgetID
from ...trace import trace
from ...config import ConfigLoader, AppConfig, build_mongodump_cmd, get_server_display_info


def _get_config() -> AppConfig:
    loader = ConfigLoader()
    (config, warnings) = loader.load()
    for warning in warnings:
        trace.warn("Config warning", tags=["config"], warning=warning)
    return config


class BackupScreen(OutputWindowMixin, DatabaseSelectorMixin, BaseScreen):
    OUTPUT_WIDGET_ID = WidgetID.OUTPUT_LOG
    DB_BUTTONS_CONTAINER_ID = "db_buttons_container"
    FALLBACK_FOCUS_WIDGET_ID = WidgetID.OUTPUT_LOG
    FOCUSABLE_CONTROLS = [WidgetID.OUTPUT_LOG]
    SECONDARY_ACTIONS = [("b", "browse_directory", "Browse"), ("e", "start_backup", "Backup")]
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
        Binding("b", "browse_directory", "Browse", show=False, priority=True),
        Binding("e", "start_backup", "Backup", show=False, priority=True),
    ]

    def __init__(self):
        super().__init__()
        self._config: Optional[AppConfig] = None
        self.backup_in_progress = False
        self.database = ""
        self.available_databases: List[str] = []
        self.backup_directory: Optional[str] = None

    def get_focusable_controls(self) -> List[str]:
        controls = []
        controls.append("browse_dir_btn")
        if self.available_databases:
            for db_name in self.available_databases:
                controls.append(f"db_btn_{db_name}")
        controls.append(WidgetID.OUTPUT_LOG)
        return controls

    def focus_first_control(self) -> None:
        try:
            browse_btn = self.query_one("#browse_dir_btn", Button)
            browse_btn.focus()
        except Exception:
            self.focus_database_selector_control()

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            self._config = _get_config()
            self.database = self._config.db_utilities.default_database
            self.backup_directory = self._config.backup.output_directory
        return self._config

    def _get_backup_dir(self) -> str:
        return self.backup_directory or self.config.backup.output_directory

    def compose_content(self) -> ComposeResult:
        with Vertical(classes="screen-header"):
            yield Static("Backup Database", classes="screen-title")
        with Horizontal(id="db_buttons_container", classes="db-buttons-row"):
            yield Static("Loading databases...", id="db_buttons_placeholder")
        with Horizontal(classes="restore-dir-row"):
            yield Button("Select Dir", id="browse_dir_btn", classes="browse-btn")
            yield Static("", id="backup_dir_info")
        with Horizontal(classes="restore-file-row"):
            yield Static("File:", classes="restore-file-label")
            yield Static("", id="backup_file_info", classes="backup-file-info")
        yield Static("", classes="status-bar", id=WidgetID.STATUS_BAR)
        yield TextArea(id=WidgetID.OUTPUT_LOG, read_only=True)

    def on_mount(self) -> None:
        trace.info("BackupScreen mounted", tags=["screen", "lifecycle"])
        _ = self.config
        trace.debug(
            "Mounted with config",
            tags=["screen", "backup", "lifecycle"],
            default_database=self.database,
            output_directory=self.config.backup.output_directory,
            server=get_server_display_info(self.config),
        )
        self._update_backup_dir_display()
        text_area = self.query_one(f"#{WidgetID.OUTPUT_LOG}", TextArea)
        server_info = get_server_display_info(self.config)
        text_area.text = f"Select a database to backup.\n\nServer: {server_info}\nBackup uses mongodump to create a .tgz archive.\n\nPress e to start backup."
        self._update_status("Discovering databases...")
        self.run_worker(self._fetch_databases(), name="fetch_databases")

    def _update_backup_dir_display(self) -> None:
        backup_dir = self._get_backup_dir()
        self.query_one("#backup_dir_info", Static).update(f"{backup_dir}")

    def _generate_backup_filename(self, database: str) -> str:
        backup_config = self.config.backup
        timestamp = datetime.now().strftime(backup_config.timestamp_format)
        filename = backup_config.filename_pattern.format(database=database, timestamp=timestamp)
        if not backup_config.compress and filename.endswith(".tgz"):
            filename = filename[:-4] + ".tar"
        return filename

    def _update_backup_file_info(self) -> None:
        if self.database:
            filename = self._generate_backup_filename(self.database)
            backup_dir = self._get_backup_dir()
            full_path = str(Path(backup_dir) / filename)
            self.query_one("#backup_file_info", Static).update(full_path)
        else:
            self.query_one("#backup_file_info", Static).update("")

    def _update_status(self, status: str) -> None:
        status_bar = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        status_bar.update(f"Status: {status}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id.startswith("db_btn_") and (not self.backup_in_progress):
            db_name = self.handle_database_button_press(btn_id)
            if db_name:
                self._update_backup_file_info()
                self._update_status(f"Selected: {db_name} - Press e to backup")
        elif btn_id == "browse_dir_btn":
            self._browse_directory()

    def _browse_directory(self) -> None:
        current_dir = self._get_backup_dir()
        trace.info(
            "Opening DirectoryBrowserModal",
            tags=["screen", "navigation"],
            from_screen="BackupScreen",
            to_screen="DirectoryBrowserModal",
            reason="User clicked Browse button to select backup directory",
        )
        self.app.push_screen(DirectoryBrowserModal(start_path=current_dir), self._on_directory_selected)

    def _on_directory_selected(self, selected_path: Optional[Path]) -> None:
        if selected_path:
            self.backup_directory = str(selected_path)
            self._update_backup_dir_display()
            self._update_backup_file_info()
            trace.debug("Backup directory changed", tags=["screen", "backup"], backup_directory=self.backup_directory)

    def action_browse_directory(self) -> None:
        trace.debug("Browse directory action triggered", tags=["screen", "backup", "action"])
        self._browse_directory()

    def action_start_backup(self) -> None:
        if self.backup_in_progress:
            return
        if self.database:
            self._start_backup()
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

    def _start_backup(self) -> None:
        if not self.database:
            self.notify("Please select a database", severity="warning")
            return
        filename = self._generate_backup_filename(self.database)
        backup_dir = self._get_backup_dir()
        output_path = str(Path(backup_dir) / filename)
        trace.info(
            "Starting backup", tags=["screen", "backup", "lifecycle"], database=self.database, output_path=output_path
        )
        self.backup_in_progress = True
        self._update_status("Running backup...")
        text_area = self.query_one(f"#{WidgetID.OUTPUT_LOG}", TextArea)
        text_area.text = f"Starting backup of database '{self.database}' to '{output_path}'...\n\n"
        text_area.focus()
        self.run_worker(self._run_backup(self.database, output_path), name="backup", exclusive=True)

    async def _run_backup(self, database: str, output_path: str) -> str:
        import tempfile
        import shutil

        output = []
        try:
            mongodump = self.config.tools.mongodump
            if not shutil.which(mongodump):
                return f"Error: {mongodump} not found.\n\nPlease install mongodb-database-tools package."
            temp_dir = tempfile.mkdtemp()
            output.append(f"Created temp directory: {temp_dir}")
            cmd = build_mongodump_cmd(
                self.config,
                database=database,
                output_dir=temp_dir,
                exclude_collections=self.config.backup.exclude_collections,
            )
            output.append(f"Running: {mongodump} --db={database} ...")
            output.append("")
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            (stdout, stderr) = await process.communicate()
            if stdout:
                output.append(stdout.decode())
            if stderr:
                output.append(stderr.decode())
            if process.returncode != 0:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return "\n".join(output) + f"\n\nBackup FAILED with exit code {process.returncode}"
            output.append(f"\nCreating archive: {output_path}")
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            import tarfile

            backup_config = self.config.backup
            if backup_config.compress:
                with tarfile.open(output_path, "w:gz", compresslevel=backup_config.compression_level) as tar:
                    tar.add(f"{temp_dir}/{database}", arcname=database)
            else:
                with tarfile.open(output_path, "w") as tar:
                    tar.add(f"{temp_dir}/{database}", arcname=database)
            file_size = Path(output_path).stat().st_size
            size_str = f"{file_size / 1048576:.2f} MB" if file_size >= 1048576 else f"{file_size / 1024:.1f} KB"
            shutil.rmtree(temp_dir, ignore_errors=True)
            output.append(f"\nBackup completed successfully!")
            output.append(f"  File: {output_path}")
            output.append(f"  Size: {size_str}")
            return "\n".join(output)
        except Exception as e:
            trace.error(
                "Backup process failed",
                tags=["database", "error"],
                exception=e,
                database=database,
                output_path=output_path,
            )
            return "\n".join(output) + f"\n\nError: {str(e)}"

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state.name == "SUCCESS":
            worker_name = event.worker.name
            if worker_name == "fetch_databases":
                self.available_databases = event.worker.result or []
                self._create_database_buttons()
                self.select_default_database(self.database)
                self._update_backup_file_info()
                if self.database:
                    self._update_status(f"Selected: {self.database} - Press e to backup")
                else:
                    self._update_status("No databases available")
                self.focus_first_control()
            elif worker_name == "backup":
                result = event.worker.result
                self._set_output_text(result, autoscroll=True)
                self.backup_in_progress = False
                if "successfully" in result:
                    self._update_status("Backup completed")
                else:
                    self._update_status("Backup failed")

    def action_go_back(self) -> None:
        if self.backup_in_progress:
            self.notify("Backup in progress", severity="warning")
            return
        trace.info(
            "Returning from BackupScreen",
            tags=["screen", "navigation"],
            from_screen="BackupScreen",
            reason="User pressed back (escape/h/left)",
        )
        self.app.pop_screen()
