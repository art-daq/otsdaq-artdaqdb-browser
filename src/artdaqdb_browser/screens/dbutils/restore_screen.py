"""
File: restore_screen.py
Purpose: Database restore screen.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: NewDatabaseNameModal, RestoreConfirmModal, RestoreScreen
Complexity: High | Lines: 1027
"""

import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from textual.app import ComposeResult
from textual.widgets import Static, TextArea, Button, Select, Label
from textual.binding import Binding
from textual.containers import Vertical, Horizontal, Container
from textual.worker import Worker
from textual.screen import ModalScreen
from ..base import BaseScreen
from .directory_browser import DirectoryBrowserModal
from ...mixins import OutputWindowMixin, DatabaseSelectorMixin
from ...constants import WidgetID
from ...trace import trace
from ...config import (
    ConfigLoader,
    AppConfig,
    build_mongo_shell_cmd,
    build_mongorestore_cmd,
    get_server_display_info,
    parse_mongodb_uri,
)


def _get_config() -> AppConfig:
    loader = ConfigLoader()
    (config, warnings) = loader.load()
    for warning in warnings:
        trace.warn("Config warning", tags=["config"], warning=warning)
    return config


class NewDatabaseNameModal(ModalScreen[Optional[str]]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("enter", "confirm", "Confirm", priority=True),
    ]
    DEFAULT_CSS = """
    NewDatabaseNameModal {
        align: center middle;
    }
    NewDatabaseNameModal .modal-dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        border: thick $primary;
    }
    NewDatabaseNameModal .modal-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    NewDatabaseNameModal .modal-message {
        margin-bottom: 1;
    }
    NewDatabaseNameModal .modal-input {
        margin-bottom: 1;
    }
    NewDatabaseNameModal .modal-error {
        color: $error;
        margin-bottom: 1;
    }
    NewDatabaseNameModal .modal-buttons {
        height: 3;
        align: center middle;
    }
    NewDatabaseNameModal Button {
        margin: 0 1;
    }
    NewDatabaseNameModal Input {
        width: 100%;
    }
    """

    def __init__(self, existing_databases: List[str]):
        super().__init__()
        self.existing_databases = set(existing_databases)

    def compose(self) -> ComposeResult:
        from textual.widgets import Input

        with Container(classes="modal-dialog"):
            yield Label("Restore to New Database", classes="modal-title")
            yield Label(
                "Enter a name for the new database.\nThe name must end with '_db' and not already exist.",
                classes="modal-message",
            )
            yield Input(placeholder="my_new_database_db", id="db_name_input", classes="modal-input")
            yield Label("", id="error_label", classes="modal-error")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="cancel_btn", variant="default")
                yield Button("Restore", id="confirm_btn", variant="primary")

    def on_mount(self) -> None:
        from textual.widgets import Input

        self.query_one("#db_name_input", Input).focus()

    def _validate_name(self, name: str) -> Optional[str]:
        if not name:
            return "Database name is required"
        if not name.endswith("_db"):
            return "Database name must end with '_db'"
        if name in self.existing_databases:
            return f"Database '{name}' already exists"
        if not re.match("^[a-zA-Z0-9_]+$", name):
            return "Database name can only contain letters, numbers, and underscores"
        return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm_btn":
            self._try_confirm()
        else:
            self.dismiss(None)

    def _try_confirm(self) -> None:
        from textual.widgets import Input

        name_input = self.query_one("#db_name_input", Input)
        name = name_input.value.strip()
        error = self._validate_name(name)
        error_label = self.query_one("#error_label", Label)
        if error:
            error_label.update(error)
        else:
            self.dismiss(name)

    def action_confirm(self) -> None:
        self._try_confirm()

    def action_cancel(self) -> None:
        self.dismiss(None)


class RestoreConfirmModal(ModalScreen[bool]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("enter", "confirm", "Confirm", priority=True),
        Binding("y", "confirm", "Yes", show=False),
        Binding("n", "cancel", "No", show=False),
    ]
    DEFAULT_CSS = """
    RestoreConfirmModal {
        align: center middle;
    }
    RestoreConfirmModal .modal-dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        border: thick $primary;
    }
    RestoreConfirmModal .modal-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    RestoreConfirmModal .modal-message {
        margin-bottom: 1;
    }
    RestoreConfirmModal .modal-warning {
        text-style: bold;
        margin-bottom: 1;
    }
    RestoreConfirmModal .modal-buttons {
        height: 3;
        align: center middle;
    }
    RestoreConfirmModal Button {
        margin: 0 1;
    }
    """

    def __init__(self, database: str, backup_file: str, wipe_data: bool):
        super().__init__()
        self.database = database
        self.backup_file = backup_file
        self.wipe_data = wipe_data

    def compose(self) -> ComposeResult:
        with Container(classes="modal-dialog"):
            yield Label("Confirm Restore", classes="modal-title")
            yield Label(
                f"Restore backup to database '{self.database}'?\n\nBackup: {self.backup_file}", classes="modal-message"
            )
            if self.wipe_data:
                yield Label("WARNING: Existing data will be WIPED!", classes="modal-warning")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel [n]", id="cancel_btn", variant="default")
                yield Button("Restore [y]", id="confirm_btn", variant="warning")

    def on_mount(self) -> None:
        self.query_one("#cancel_btn", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm_btn":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class RestoreScreen(OutputWindowMixin, DatabaseSelectorMixin, BaseScreen):
    OUTPUT_WIDGET_ID = WidgetID.OUTPUT_LOG
    DB_BUTTONS_CONTAINER_ID = "db_buttons_container"
    FALLBACK_FOCUS_WIDGET_ID = WidgetID.OUTPUT_LOG
    FOCUSABLE_CONTROLS = [WidgetID.OUTPUT_LOG]
    SECONDARY_ACTIONS = [
        ("b", "browse_directory", "Browse"),
        ("s", "select_file", "File"),
        ("w", "toggle_wipe", "Wipe"),
        ("e", "start_restore", "Restore"),
        ("n", "restore_to_new", "NewDB"),
    ]
    BINDINGS = [
        Binding("j", "select_next", "Next file", show=False, priority=True),
        Binding("k", "select_prev", "Prev file", show=False, priority=True),
        Binding("down", "select_next", "Next file", show=False, priority=True),
        Binding("up", "select_prev", "Prev file", show=False, priority=True),
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
        Binding("s", "select_file", "File", show=False, priority=True),
        Binding("w", "toggle_wipe", "Wipe", show=False, priority=True),
        Binding("e", "start_restore", "Restore", show=False, priority=True),
        Binding("n", "restore_to_new", "NewDB", show=False, priority=True),
    ]

    def __init__(self):
        super().__init__()
        self._config: Optional[AppConfig] = None
        self.restore_in_progress = False
        self.database = ""
        self.available_databases: List[str] = []
        self.backup_files: List[Path] = []
        self.selected_backup: Optional[Path] = None
        self.wipe_data: Optional[bool] = None
        self.backup_directory: Optional[str] = None

    def get_focusable_controls(self) -> List[str]:
        controls = []
        controls.append("browse_dir_btn")
        controls.append("backup_file_select")
        controls.append("wipe_btn")
        if self.available_databases:
            for db_name in self.available_databases:
                controls.append(f"db_btn_{db_name}")
        controls.append(WidgetID.OUTPUT_LOG)
        return controls

    def focus_first_control(self) -> None:
        try:
            file_select = self.query_one("#backup_file_select", Select)
            file_select.focus()
        except Exception:
            try:
                text_area = self.query_one(f"#{WidgetID.OUTPUT_LOG}", TextArea)
                text_area.focus()
            except Exception:
                pass

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            self._config = _get_config()
            self.database = self._config.db_utilities.default_database
            self.wipe_data = self._config.restore.drop_existing
            self.backup_directory = self._config.backup.output_directory
        return self._config

    def _get_backup_dir(self) -> str:
        return self.backup_directory or self.config.backup.output_directory

    def compose_content(self) -> ComposeResult:
        with Vertical(classes="screen-header"):
            yield Static("Restore Database", classes="screen-title")
        with Horizontal(id="db_buttons_container", classes="db-buttons-row"):
            yield Static("Loading databases...", id="db_buttons_placeholder")
            yield Button("Wipe", id="wipe_btn", classes="wipe-btn")
        with Horizontal(classes="restore-dir-row"):
            yield Button("Select Dir", id="browse_dir_btn", classes="browse-btn")
            yield Static("", id="backup_dir_info")
        with Horizontal(classes="restore-file-row"):
            yield Static("File:", classes="restore-file-label")
            yield Select[str]([], id="backup_file_select", prompt="Select backup file", classes="backup-file-select")
        yield Static("", classes="status-bar", id=WidgetID.STATUS_BAR)
        yield TextArea(id=WidgetID.OUTPUT_LOG, read_only=True)

    def on_mount(self) -> None:
        trace.info("RestoreScreen mounted", tags=["screen", "lifecycle"])
        _ = self.config
        trace.debug(
            "Mounted with config",
            tags=["screen", "restore", "lifecycle"],
            default_database=self.database,
            drop_existing=self.wipe_data,
            server=get_server_display_info(self.config),
        )
        self._update_backup_dir_display()
        self._update_wipe_button()
        text_area = self.query_one(f"#{WidgetID.OUTPUT_LOG}", TextArea)
        server_info = get_server_display_info(self.config)
        text_area.text = f"Select a database and backup file to restore.\n\nServer: {server_info}\n\nWARNING: Restore will modify the target database!\n\nPress e to start restore."
        self._update_status("Discovering databases...")
        self.run_worker(self._fetch_databases(), name="fetch_databases")

    def _update_backup_dir_display(self) -> None:
        backup_dir = self._get_backup_dir()
        self.query_one("#backup_dir_info", Static).update(f"{backup_dir}")

    def _update_wipe_button(self) -> None:
        btn = self.query_one("#wipe_btn", Button)
        if self.wipe_data:
            btn.add_class("wipe-btn-active")
            btn.label = "Wipe: ON"
        else:
            btn.remove_class("wipe-btn-active")
            btn.label = "Wipe: OFF"

    def _find_backups_for_database(self, database: str) -> List[Path]:
        backup_dir = Path(self._get_backup_dir())
        if not backup_dir.exists():
            return []
        pattern = re.compile(f"^{re.escape(database)}-\\d{{8}}_\\d{{6}}\\.tgz$")
        backups = []
        for f in backup_dir.iterdir():
            if f.is_file() and pattern.match(f.name):
                backups.append(f)
        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return backups

    def _update_backup_list(self) -> None:
        select = self.query_one("#backup_file_select", Select)
        self.backup_files = self._find_backups_for_database(self.database) if self.database else []
        if not self.backup_files:
            self.selected_backup = None
            select.set_options([])
            return
        options = []
        for backup in self.backup_files:
            size = backup.stat().st_size
            size_str = f"{size / 1048576:.1f}MB" if size >= 1048576 else f"{size / 1024:.1f}KB"
            mtime = datetime.fromtimestamp(backup.stat().st_mtime).strftime("%m/%d %H:%M")
            label = f"{backup.name} ({size_str}, {mtime})"
            options.append((label, str(backup)))
        select.set_options(options)
        self.selected_backup = self.backup_files[0]
        select.value = str(self.selected_backup)

    def _create_database_buttons(self) -> None:
        container = self.query_one(f"#{self.DB_BUTTONS_CONTAINER_ID}", Horizontal)
        try:
            placeholder = container.query_one("#db_buttons_placeholder")
            placeholder.remove()
        except Exception:
            pass
        for btn in list(container.query(Button)):
            if btn.id and btn.id.startswith("db_btn_"):
                btn.remove()
        wipe_btn = container.query_one("#wipe_btn", Button)
        if not self.available_databases:
            container.mount(Static("No databases found", classes="db-no-databases"), before=wipe_btn)
            return
        for db_name in self.available_databases:
            is_selected = db_name == self.database
            btn = Button(
                db_name, id=f"db_btn_{db_name}", classes="db-select-btn" + (" db-btn-selected" if is_selected else "")
            )
            container.mount(btn, before=wipe_btn)

    def _update_status(self, status: str) -> None:
        status_bar = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        status_bar.update(f"Status: {status}")

    def _browse_directory(self) -> None:
        current_dir = self._get_backup_dir()
        trace.info(
            "Opening DirectoryBrowserModal",
            tags=["screen", "navigation"],
            from_screen="RestoreScreen",
            to_screen="DirectoryBrowserModal",
            reason="User clicked Browse button to select backup directory",
        )
        self.app.push_screen(DirectoryBrowserModal(start_path=current_dir), self._on_directory_selected)

    def _on_directory_selected(self, selected_path: Optional[Path]) -> None:
        if selected_path:
            self.backup_directory = str(selected_path)
            self._update_backup_dir_display()
            self._update_backup_list()
            trace.debug("Backup directory changed", tags=["screen", "restore"], backup_directory=self.backup_directory)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id.startswith("db_btn_") and (not self.restore_in_progress):
            db_name = btn_id.replace("db_btn_", "")
            if db_name == self.database and self.selected_backup:
                self.action_start_restore()
            else:
                self.handle_database_button_press(btn_id)
                self._update_backup_list()
                if self.selected_backup:
                    self._update_status(f"Selected: {db_name} - Press Enter or e to restore")
                else:
                    self._update_status(f"Selected: {db_name} - No backups available")
        elif btn_id == "browse_dir_btn":
            self._browse_directory()
        elif btn_id == "wipe_btn":
            self.wipe_data = not self.wipe_data
            self._update_wipe_button()
            trace.debug("Wipe data toggled", tags=["screen", "restore"], wipe_data=self.wipe_data)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "backup_file_select" and event.value != Select.BLANK:
            self.selected_backup = Path(str(event.value))
            trace.debug("Backup file selected", tags=["screen", "restore"], backup_file=str(self.selected_backup))

    def action_browse_directory(self) -> None:
        trace.debug("Browse directory action triggered", tags=["screen", "restore", "action"])
        self._browse_directory()

    def action_select_file(self) -> None:
        trace.debug("Select file action triggered", tags=["screen", "restore", "action"])
        try:
            file_select = self.query_one("#backup_file_select", Select)
            file_select.focus()
        except Exception as e:
            trace.error("Failed to focus file select", tags=["screen", "restore", "error"], exception=e)

    def action_toggle_wipe(self) -> None:
        trace.debug(
            "Toggle wipe action triggered", tags=["screen", "restore", "action"], current_wipe_data=self.wipe_data
        )
        self.wipe_data = not self.wipe_data
        self._update_wipe_button()
        trace.debug("Wipe data toggled", tags=["screen", "restore"], wipe_data=self.wipe_data)

    def action_start_restore(self) -> None:
        trace.debug(
            "Start restore action triggered",
            tags=["screen", "restore", "action"],
            restore_in_progress=self.restore_in_progress,
            database=self.database,
            selected_backup=str(self.selected_backup) if self.selected_backup else None,
        )
        if self.restore_in_progress:
            return
        if self.database and self.selected_backup:
            self._start_restore()
        elif not self.database:
            self.notify("Please select a database first", severity="warning")
        elif not self.selected_backup:
            self.notify("No backup file available", severity="warning")

    def action_restore_to_new(self) -> None:
        trace.debug(
            "Restore to new database action triggered",
            tags=["screen", "restore", "action"],
            restore_in_progress=self.restore_in_progress,
            selected_backup=str(self.selected_backup) if self.selected_backup else None,
        )
        if self.restore_in_progress:
            self.notify("Restore in progress", severity="warning")
            return
        if not self.selected_backup:
            self.notify("Please select a backup file first", severity="warning")
            return
        trace.info(
            "Opening NewDatabaseNameModal",
            tags=["screen", "navigation"],
            from_screen="RestoreScreen",
            to_screen="NewDatabaseNameModal",
            reason="User pressed 'n' to restore to new database",
        )

        def on_name_entered(new_db_name: Optional[str]) -> None:
            if new_db_name:
                self._restore_to_new_database(new_db_name)

        self.app.push_screen(NewDatabaseNameModal(existing_databases=self.available_databases), on_name_entered)

    def _restore_to_new_database(self, new_db_name: str) -> None:
        trace.info(
            "Starting restore to new database",
            tags=["screen", "restore", "lifecycle"],
            new_database=new_db_name,
            backup_file=str(self.selected_backup),
            wipe_data=self.wipe_data,
        )
        self.restore_in_progress = True
        self._update_status(f"Restoring to new database '{new_db_name}'...")
        text_area = self.query_one(f"#{WidgetID.OUTPUT_LOG}", TextArea)
        text_area.text = f"Starting restore from '{self.selected_backup.name}' to NEW database '{new_db_name}'...\n\n"
        text_area.focus()
        self.run_worker(
            self._run_restore(str(self.selected_backup), new_db_name, wipe_data=False), name="restore", exclusive=True
        )

    def action_select_next(self) -> None:
        focused = self.focused
        if focused and hasattr(focused, "id") and (focused.id == WidgetID.OUTPUT_LOG):
            self.action_scroll_down()
            return
        if focused and hasattr(focused, "id") and focused.id and focused.id.startswith("db_btn_"):
            self._focus_next_db_button()
            return
        try:
            select = self.query_one("#backup_file_select", Select)
            if not self.backup_files:
                return
            current_idx = -1
            if self.selected_backup:
                for i, backup in enumerate(self.backup_files):
                    if str(backup) == str(self.selected_backup):
                        current_idx = i
                        break
            next_idx = min(current_idx + 1, len(self.backup_files) - 1)
            if next_idx >= 0:
                self.selected_backup = self.backup_files[next_idx]
                select.value = str(self.selected_backup)
        except Exception:
            pass

    def action_select_prev(self) -> None:
        focused = self.focused
        if focused and hasattr(focused, "id") and (focused.id == WidgetID.OUTPUT_LOG):
            self.action_scroll_up()
            return
        if focused and hasattr(focused, "id") and focused.id and focused.id.startswith("db_btn_"):
            self._focus_prev_db_button()
            return
        try:
            select = self.query_one("#backup_file_select", Select)
            if not self.backup_files:
                return
            current_idx = len(self.backup_files)
            if self.selected_backup:
                for i, backup in enumerate(self.backup_files):
                    if str(backup) == str(self.selected_backup):
                        current_idx = i
                        break
            prev_idx = max(current_idx - 1, 0)
            self.selected_backup = self.backup_files[prev_idx]
            select.value = str(self.selected_backup)
        except Exception:
            pass

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

    def _start_restore(self) -> None:
        if not self.database:
            self.notify("Please select a database", severity="warning")
            return
        if not self.selected_backup or not self.selected_backup.exists():
            self.notify("Please select a backup file", severity="warning")
            return
        confirm_required = self.app.config.restore.require_confirmation
        if not confirm_required:
            self._perform_restore()
            return
        trace.debug(
            "Showing restore confirmation modal",
            tags=["screen", "restore", "modal"],
            database=self.database,
            backup_file=str(self.selected_backup),
            wipe_data=self.wipe_data,
        )
        database = self.database
        backup_path = str(self.selected_backup)
        wipe_data = self.wipe_data

        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                self._perform_restore()

        self.app.push_screen(
            RestoreConfirmModal(database=database, backup_file=self.selected_backup.name, wipe_data=wipe_data),
            on_confirm,
        )

    def _perform_restore(self) -> None:
        trace.info(
            "Starting restore",
            tags=["screen", "restore", "lifecycle"],
            database=self.database,
            backup_file=str(self.selected_backup),
            wipe_data=self.wipe_data,
        )
        self.restore_in_progress = True
        wipe_str = " (wiping existing data)" if self.wipe_data else ""
        self._update_status(f"Running restore{wipe_str}...")
        text_area = self.query_one(f"#{WidgetID.OUTPUT_LOG}", TextArea)
        text_area.text = (
            f"Starting restore from '{self.selected_backup.name}' to database '{self.database}'{wipe_str}...\n\n"
        )
        text_area.focus()
        self.run_worker(
            self._run_restore(str(self.selected_backup), self.database, self.wipe_data), name="restore", exclusive=True
        )

    async def _run_restore(self, input_path: str, database: str, wipe_data: bool) -> str:
        import tempfile
        import shutil

        output = []
        temp_dir = None
        try:
            mongorestore = self.config.tools.mongorestore
            if not shutil.which(mongorestore):
                return f"Error: {mongorestore} not found.\n\nPlease install mongodb-database-tools package."
            temp_dir = tempfile.mkdtemp()
            output.append(f"Extracting archive to: {temp_dir}")
            import tarfile

            with tarfile.open(input_path, "r:gz") as tar:
                tar.extractall(temp_dir)
            dump_dirs = [d for d in Path(temp_dir).iterdir() if d.is_dir()]
            if not dump_dirs:
                return "Error: Invalid archive - no database directory found"
            dump_dir = dump_dirs[0]
            output.append(f"Found dump directory: {dump_dir.name}")
            output.append("")
            if wipe_data:
                output.append("Wipe data option enabled - existing collections will be dropped")
                output.append("")
            restore_host = None
            restore_port = None
            if self.config.mongodb_auth.type == "x509":
                output.append("Discovering replica set primary...")
                discover_cmd = build_mongo_shell_cmd(self.config, database="admin", quiet=True)
                discover_cmd.extend(
                    [
                        "--eval",
                        "var status = rs.status(); if (status.ok === 1) { var p = status.members.find(function(m) { return m.stateStr === 'PRIMARY'; }); if (p) print('PRIMARY:' + p.name); }",
                    ]
                )
                process = await asyncio.create_subprocess_exec(
                    *discover_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                (stdout, stderr) = await process.communicate()
                if stdout:
                    for line in stdout.decode().split("\n"):
                        if line.startswith("PRIMARY:"):
                            primary = line.replace("PRIMARY:", "")
                            if ":" in primary:
                                restore_host = primary.split(":")[0]
                                restore_port = primary.split(":")[1]
                                output.append(f"Found primary: {restore_host}:{restore_port}")
            exclude_collections = self.config.restore.exclude_collections
            cmd = build_mongorestore_cmd(
                self.config,
                database=database,
                input_dir=str(dump_dir),
                host_override=restore_host,
                port_override=restore_port,
                drop_existing=wipe_data,
                exclude_collections=exclude_collections if exclude_collections else None,
            )
            exclude_info = f" (excluding: {', '.join(exclude_collections)})" if exclude_collections else ""
            output.append(
                f"\nRunning: {mongorestore} --db={database} {('--drop' if wipe_data else '')}{exclude_info} ..."
            )
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
                return "\n".join(output) + f"\n\nRestore FAILED with exit code {process.returncode}"
            (host, port, _) = parse_mongodb_uri(self.config.data_source.mongodb.uri)
            final_host = restore_host or host
            final_port = restore_port or port
            output.append(f"\nRestore completed successfully!")
            output.append(f"  Database: {database}")
            output.append(f"  Server: {final_host}:{final_port}")
            if wipe_data:
                output.append("  Existing data was wiped before restore")
            return "\n".join(output)
        except Exception as e:
            trace.error(
                "Restore process failed",
                tags=["database", "error"],
                exception=e,
                database=database,
                input_path=input_path,
            )
            return "\n".join(output) + f"\n\nError: {str(e)}"
        finally:
            if temp_dir:
                import shutil

                shutil.rmtree(temp_dir, ignore_errors=True)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state.name == "SUCCESS":
            worker_name = event.worker.name
            if worker_name == "fetch_databases":
                self.available_databases = event.worker.result or []
                self._create_database_buttons()
                self.select_default_database(self.database)
                self._update_backup_list()
                if self.database and self.selected_backup:
                    self._update_status(f"Selected: {self.database} - Press e to restore")
                elif self.database:
                    self._update_status(f"Selected: {self.database} - No backups available")
                else:
                    self._update_status("No databases available")
                self.focus_first_control()
            elif worker_name == "restore":
                result = event.worker.result
                self._set_output_text(result, autoscroll=True)
                self.restore_in_progress = False
                if "successfully" in result:
                    self._update_status("Restore completed")
                    try:
                        if hasattr(self.app, "action_cache_clear"):
                            trace.info(
                                "Clearing pickle cache after successful restore",
                                tags=["screen", "restore", "cache"],
                                database=self.database,
                            )
                            self.app.action_cache_clear()
                    except Exception:
                        pass
                else:
                    self._update_status("Restore failed")

    def action_go_back(self) -> None:
        if self.restore_in_progress:
            self.notify("Restore in progress", severity="warning")
            return
        trace.info(
            "Returning from RestoreScreen",
            tags=["screen", "navigation"],
            from_screen="RestoreScreen",
            reason="User pressed back (escape/h/left)",
        )
        self.app.pop_screen()
