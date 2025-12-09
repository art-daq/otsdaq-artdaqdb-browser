"""
File: config_editor.py
Purpose: Configuration editor screen.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: DisplayMode, ConfigEditorScreen, DISPLAY_MODE_LABELS, TREE_VIEW_SECTIONS
Complexity: High | Lines: 1706
"""

import copy
import os
import re
import shutil
import yaml
from enum import Enum
from pathlib import Path
from typing import Optional, Any, List, Tuple, Dict, Set
from textual.app import ComposeResult
from textual.widgets import Static, Tree, Button, Input, RadioSet, RadioButton
from textual.binding import Binding
from textual.containers import Vertical, Horizontal, Container
from textual.widgets.tree import TreeNode
from ..base import BaseScreen, FOCUS_BINDINGS, BACK_BINDINGS
from ...constants import WidgetID
from ...config import AppConfig, ConfigLoader, ConfigError
from ...trace import trace
from ...utils import truncate_text


def _escape_markup(text: str) -> str:
    return text.replace("[", "\\[").replace("]", "\\]")


DISCRETE_FIELDS: Dict[Tuple[str, ...], List[Tuple[str, str]]] = {
    ("data_source", "type"): [("filesystem", "Filesystem"), ("mongodb", "MongoDB")],
    ("data_source", "mongodb", "tls"): [("false", "Disabled"), ("true", "Enabled")],
    ("data_source", "mongodb", "direct_connection"): [
        ("false", "Disabled (Replica Set)"),
        ("true", "Enabled (Single Server)"),
    ],
    ("mongodb_auth", "type"): [
        ("none", "None (No Auth)"),
        ("userpass", "Username/Password"),
        ("x509", "X.509 Certificate"),
    ],
    ("mongodb_auth", "userpass", "auth_mechanism"): [
        ("DEFAULT", "Default (Auto)"),
        ("SCRAM-SHA-1", "SCRAM-SHA-1"),
        ("SCRAM-SHA-256", "SCRAM-SHA-256"),
    ],
    ("mongodb_auth", "x509", "allow_invalid_certificates"): [
        ("false", "Validate Certificates"),
        ("true", "Skip Validation (INSECURE)"),
    ],
    ("mongodb_auth", "x509", "allow_invalid_hostnames"): [
        ("false", "Validate Hostnames"),
        ("true", "Skip Validation (INSECURE)"),
    ],
    ("ui", "theme"): [
        ("catppuccin-mocha", "Catppuccin Mocha (Dark)"),
        ("textual-dark", "Textual Dark"),
        ("textual-ansi", "Textual ANSI"),
        ("dracula", "Dracula (Dark)"),
        ("flexoki", "Flexoki (Dark)"),
        ("gruvbox", "Gruvbox (Dark)"),
        ("monokai", "Monokai (Dark)"),
        ("nord", "Nord (Dark)"),
        ("tokyo-night", "Tokyo Night (Dark)"),
        ("catppuccin-latte", "Catppuccin Latte (Light)"),
        ("textual-light", "Textual Light"),
        ("solarized-light", "Solarized Light"),
    ],
    ("tables", "default_sort_order"): [("asc", "Ascending"), ("desc", "Descending")],
    ("logging", "level"): [("debug", "Debug"), ("info", "Info"), ("warning", "Warning"), ("error", "Error")],
    ("app", "debug"): [("false", "Disabled"), ("true", "Enabled")],
    ("cache", "enabled"): [("true", "Enabled"), ("false", "Disabled")],
    ("cache", "auto_purge"): [("true", "Enabled"), ("false", "Disabled")],
    ("ui", "show_deleted"): [("false", "Hidden"), ("true", "Shown")],
    ("ui", "mouse_support"): [("true", "Enabled"), ("false", "Disabled")],
    ("ui", "show_key_hints"): [("true", "Shown"), ("false", "Hidden")],
    ("tables", "zebra_stripes"): [("false", "Disabled"), ("true", "Enabled")],
    ("logging", "trace_enabled"): [("true", "Enabled"), ("false", "Disabled")],
    ("backup", "compress"): [("true", "Enabled"), ("false", "Disabled")],
    ("restore", "require_confirmation"): [("true", "Required"), ("false", "Not Required")],
    ("restore", "drop_existing"): [("false", "Keep Existing"), ("true", "Drop Existing")],
    ("db_utilities", "extended_stats"): [("false", "Basic"), ("true", "Extended")],
    ("documents", "soft_delete"): [("true", "Soft Delete"), ("false", "Hard Delete")],
    ("documents", "confirm_hard_delete"): [("true", "Required"), ("false", "Not Required")],
    ("search", "fuzzy_match"): [("true", "Enabled"), ("false", "Disabled")],
    ("search", "case_insensitive"): [("true", "Case Insensitive"), ("false", "Case Sensitive")],
}
DIRECTORY_FIELDS: List[Tuple[str, ...]] = [
    ("data_source", "filesystem", "path"),
    ("mongodb_auth", "x509", "cert_dir"),
    ("cache", "directory"),
    ("backup", "output_directory"),
]
FILE_FIELDS: List[Tuple[str, ...]] = [
    ("logging", "trace_file"),
    ("mongodb_auth", "x509", "ca_cert"),
    ("mongodb_auth", "x509", "client_cert"),
]
EXECUTABLE_FIELDS: List[Tuple[str, ...]] = [("tools", "mongo_shell"), ("tools", "mongodump"), ("tools", "mongorestore")]


class DisplayMode(Enum):
    ALL = "all"
    DATA_SOURCE = "data_source"
    TREE_VIEW = "tree_view"


DISPLAY_MODE_LABELS = {
    DisplayMode.ALL: "All Parameters",
    DisplayMode.DATA_SOURCE: "Data Source Only",
    DisplayMode.TREE_VIEW: "Core Settings",
}
TREE_VIEW_SECTIONS = ["data_source", "mongodb_auth", "logging", "backup", "restore"]


class ConfigEditorScreen(BaseScreen):
    FOCUSABLE_CONTROLS = [WidgetID.CONFIG_TREE, WidgetID.CONFIG_VALUE_INPUT, "config_radio_set", "validate_path_btn"]
    SECONDARY_ACTIONS = [
        ("s", "save_config", "Save"),
        ("r", "reset_config", "Reset"),
        ("v", "validate_config", "Validate"),
        ("m", "cycle_mode", "Mode"),
        ("w", "toggle_modified", "Modified"),
        ("u", "undo_changes", "Undo"),
    ]
    BINDINGS = [
        Binding("escape", "go_back", "Back", show=False),
        *BACK_BINDINGS,
        Binding("l", "edit_field", "Edit", show=False),
        Binding("right", "edit_field", "Edit", show=False),
        Binding("enter", "edit_field", "Edit", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("g", "goto_first", "First", show=False),
        Binding("G", "goto_last", "Last", show=False),
        *FOCUS_BINDINGS,
        Binding("s", "save_config", "Save", show=False, priority=True),
        Binding("r", "reset_config", "Reset", show=False, priority=True),
        Binding("v", "validate_config", "Validate", show=False, priority=True),
        Binding("m", "cycle_mode", "Mode", show=False, priority=True),
        Binding("w", "toggle_modified", "Modified", show=False, priority=True),
        Binding("u", "undo_changes", "Undo", show=False, priority=True),
    ]

    def __init__(self):
        super().__init__()
        self.config_loader: Optional[ConfigLoader] = None
        self.current_config: Optional[AppConfig] = None
        self._original_config: Optional[AppConfig] = None
        self.modified = False
        self.selected_path: List[str] = []
        self._current_field_type: str = "input"
        self._applying_value: bool = False
        self._display_mode: DisplayMode = DisplayMode.DATA_SOURCE
        self._show_modified_only: bool = False
        self._modified_paths: Set[Tuple[str, ...]] = set()
        self._invalid_paths: Set[Tuple[str, ...]] = set()
        self._validation_errors: Dict[Tuple[str, ...], str] = {}
        self._tree_expanded_paths: Set[Tuple[str, ...]] = set()
        self._tree_selected_path: Optional[Tuple[str, ...]] = None

    def _is_input_focused(self) -> bool:
        try:
            input_field = self.query_one(f"#{WidgetID.CONFIG_VALUE_INPUT}", Input)
            return input_field.has_focus and (not input_field.disabled)
        except Exception:
            return False

    def check_action(self, action: str, parameters: tuple) -> bool:
        if self._is_input_focused():
            allowed_when_typing = {"focus_next", "focus_previous"}
            if action in allowed_when_typing:
                return True
            return False
        return True

    def get_focusable_controls(self) -> List[str]:
        all_controls = [WidgetID.CONFIG_TREE, WidgetID.CONFIG_VALUE_INPUT, "config_radio_set", "validate_path_btn"]
        visible_controls = []
        for control_id in all_controls:
            try:
                widget = self.query_one(f"#{control_id}")
                if widget.has_class("hidden"):
                    continue
                if hasattr(widget, "disabled") and widget.disabled:
                    continue
                visible_controls.append(control_id)
            except Exception:
                continue
        return visible_controls

    def compose_content(self) -> ComposeResult:
        with Vertical(classes="screen-header"):
            yield Static("Configuration Editor", classes="screen-title")
        with Horizontal(classes="config-main-content"):
            with Container(classes="config-tree-pane"):
                yield Static("Settings", classes="pane-title")
                yield Tree("Configuration", id=WidgetID.CONFIG_TREE)
            with Container(classes="config-editor-pane"):
                yield Static("", id="selected_path", classes="selected-path")
                yield Static("", id="field_description", classes="field-description")
                yield Static("", id="validation_status", classes="validation-status")
                yield Input(id=WidgetID.CONFIG_VALUE_INPUT, placeholder="Select a setting...")
                yield RadioSet(id="config_radio_set", classes="config-radio-set hidden")
                with Horizontal(classes="editor-buttons"):
                    yield Button("Validate Path", id="validate_path_btn", variant="default", classes="hidden")
        yield Static("", classes="status-bar", id=WidgetID.STATUS_BAR)

    def on_mount(self) -> None:
        trace.info("ConfigEditorScreen mounted", tags=["screen", "lifecycle"])
        self.config_loader = ConfigLoader()
        self.load_config()
        self.build_tree()
        self.focus_first_control()
        self._update_status("Ready")

    def load_config(self) -> None:
        try:
            (self.current_config, warnings) = self.config_loader.load()
            for warning in warnings:
                self.notify(warning, severity="warning")
        except ConfigError as e:
            self.notify(f"Error loading config: {_escape_markup(str(e))}", severity="error")
            self.current_config = AppConfig()
        self._original_config = copy.deepcopy(self.current_config)
        self._modified_paths.clear()

    def build_tree(self) -> None:
        tree = self.query_one(f"#{WidgetID.CONFIG_TREE}", Tree)
        if tree.root.children:
            self._save_tree_state()
        tree.clear()
        config_dict = self.current_config.model_dump()
        if self._display_mode == DisplayMode.DATA_SOURCE:
            filtered_dict = {k: v for (k, v) in config_dict.items() if k in ["data_source", "mongodb_auth"]}
        elif self._display_mode == DisplayMode.TREE_VIEW:
            filtered_dict = {k: v for (k, v) in config_dict.items() if k in TREE_VIEW_SECTIONS}
        else:
            filtered_dict = config_dict
        self._add_dict_to_tree(tree.root, filtered_dict, [])
        tree.root.expand()
        self._restore_tree_state()

    def _add_dict_to_tree(self, parent: TreeNode, data: dict, path: List[str]) -> None:
        for key, value in data.items():
            current_path = path + [key]
            path_tuple = tuple(current_path)
            node_data = {"path": current_path, "value": value, "key": key}
            is_modified = self._is_path_modified(path_tuple)
            if self._show_modified_only and (not is_modified):
                continue
            is_invalid = path_tuple in self._invalid_paths
            is_field_modified = path_tuple in self._modified_paths
            if is_invalid:
                marker = "[red]✗[/] "
            elif is_field_modified:
                marker = "[yellow]●[/] "
            else:
                marker = ""
            if isinstance(value, dict):
                section_modified = (
                    any(
                        (
                            mp[0] == key if len(mp) > 0 else False
                            for mp in self._modified_paths
                            if mp[: len(current_path)] == path_tuple
                        )
                    )
                    or path_tuple in self._modified_paths
                )
                section_invalid = any((ip[: len(current_path)] == path_tuple for ip in self._invalid_paths))
                if section_invalid:
                    section_marker = "[red]✗[/] "
                elif section_modified:
                    section_marker = "[yellow]●[/] "
                else:
                    section_marker = ""
                node = parent.add(f"{section_marker}[bold]{key}[/]", data=node_data)
                self._add_dict_to_tree(node, value, current_path)
            elif isinstance(value, list):
                display = f"{marker}{key}: [{len(value)} items]"
                parent.add(display, data=node_data, allow_expand=False)
            else:
                display_value = str(value) if value is not None else "null"
                display_value = truncate_text(display_value, max_length=30)
                display = f"{marker}{key}: {display_value}"
                parent.add(display, data=node_data, allow_expand=False)

    def _is_path_modified(self, path_tuple: Tuple[str, ...]) -> bool:
        if path_tuple in self._modified_paths:
            return True
        for mp in self._modified_paths:
            if len(mp) >= len(path_tuple) and mp[: len(path_tuple)] == path_tuple:
                return True
        return False

    def _validate_field_value(self, path: List[str], value: Any) -> Tuple[bool, Optional[str]]:
        path_tuple = tuple(path)
        if value is None or value == "" or value == "null":
            return (True, None)
        str_value = str(value) if not isinstance(value, str) else value
        if path_tuple in DIRECTORY_FIELDS:
            expanded = Path(str_value).expanduser()
            if not expanded.exists():
                return (False, f"Directory does not exist: {str_value}")
            if not expanded.is_dir():
                return (False, f"Path is not a directory: {str_value}")
            return (True, None)
        if path_tuple in FILE_FIELDS:
            if path_tuple in [("mongodb_auth", "x509", "ca_cert"), ("mongodb_auth", "x509", "client_cert")]:
                if self.current_config:
                    cert_dir = Path(self.current_config.mongodb_auth.x509.cert_dir).expanduser()
                    full_path = cert_dir / str_value
                    if not full_path.exists():
                        return (False, f"Certificate file not found: {full_path}")
            else:
                expanded = Path(str_value).expanduser()
                if not expanded.parent.exists():
                    return (False, f"Parent directory does not exist: {expanded.parent}")
            return (True, None)
        if path_tuple in EXECUTABLE_FIELDS:
            exe_path = shutil.which(str_value)
            if not exe_path:
                expanded = Path(str_value).expanduser()
                if not (expanded.exists() and os.access(expanded, os.X_OK)):
                    return (False, f"Executable not found: {str_value}")
            return (True, None)
        numeric_fields = [
            ("data_source", "mongodb", "connect_timeout_ms"),
            ("data_source", "mongodb", "server_selection_timeout_ms"),
            ("data_source", "mongodb", "socket_timeout_ms"),
            ("cache", "ttl"),
            ("cache", "max_entries"),
            ("cache", "max_size_mb"),
            ("search", "min_search_chars"),
            ("search", "debounce_ms"),
            ("ui", "max_list_items"),
            ("ui", "max_text_length"),
            ("logging", "max_trace_size_mb"),
            ("logging", "trace_backup_count"),
            ("backup", "compression_level"),
        ]
        if path_tuple in numeric_fields:
            try:
                num_val = int(value) if isinstance(value, str) else value
                if num_val < 0:
                    return (False, "Value must be non-negative")
            except (ValueError, TypeError):
                return (False, "Value must be a number")
            return (True, None)
        if path_tuple == ("data_source", "mongodb", "uri"):
            if not str_value.startswith(("mongodb://", "mongodb+srv://")):
                return (False, "URI must start with mongodb:// or mongodb+srv://")
            return (True, None)
        return (True, None)

    def _mark_field_invalid(self, path: List[str], error: str) -> None:
        path_tuple = tuple(path)
        self._invalid_paths.add(path_tuple)
        self._validation_errors[path_tuple] = error
        trace.debug("Field marked as invalid", tags=["config", "validation"], path=".".join(path), error=error)

    def _mark_field_valid(self, path: List[str]) -> None:
        path_tuple = tuple(path)
        self._invalid_paths.discard(path_tuple)
        self._validation_errors.pop(path_tuple, None)

    def _is_discrete_field(self, path: List[str]) -> bool:
        return tuple(path) in DISCRETE_FIELDS

    def _is_directory_field(self, path: List[str]) -> bool:
        return tuple(path) in DIRECTORY_FIELDS

    def _is_file_field(self, path: List[str]) -> bool:
        return tuple(path) in FILE_FIELDS

    def _is_executable_field(self, path: List[str]) -> bool:
        return tuple(path) in EXECUTABLE_FIELDS

    def _is_path_field(self, path: List[str]) -> bool:
        return self._is_directory_field(path) or self._is_file_field(path) or self._is_executable_field(path)

    def _get_discrete_options(self, path: List[str]) -> List[Tuple[str, str]]:
        return DISCRETE_FIELDS.get(tuple(path), [])

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        if node.data and "path" in node.data:
            self.selected_path = node.data["path"]
            value = node.data.get("value")
            path_str = " > ".join(self.selected_path)
            self.query_one("#selected_path", Static).update(f"Path: {path_str}")
            description = self._get_field_description(self.selected_path)
            self.query_one("#field_description", Static).update(description)
            self.query_one("#validation_status", Static).update("")
            input_field = self.query_one(f"#{WidgetID.CONFIG_VALUE_INPUT}", Input)
            radio_set = self.query_one("#config_radio_set", RadioSet)
            validate_btn = self.query_one("#validate_path_btn", Button)
            if isinstance(value, (dict, list)):
                self._current_field_type = "readonly"
                input_field.remove_class("hidden")
                radio_set.add_class("hidden")
                validate_btn.add_class("hidden")
                input_field.value = yaml.dump(value, default_flow_style=True).strip()
                input_field.disabled = True
            elif self._is_discrete_field(self.selected_path):
                self._current_field_type = "select"
                input_field.add_class("hidden")
                radio_set.remove_class("hidden")
                validate_btn.add_class("hidden")
                input_field.disabled = False
                options = self._get_discrete_options(self.selected_path)
                if isinstance(value, bool):
                    str_value = "true" if value else "false"
                elif value is None:
                    str_value = "null"
                else:
                    str_value = str(value)
                self._rebuild_radio_buttons(radio_set, options, str_value)
            else:
                self._current_field_type = "input"
                input_field.remove_class("hidden")
                radio_set.add_class("hidden")
                input_field.disabled = False
                if value is None:
                    input_field.value = "null"
                else:
                    input_field.value = str(value)
                if self._is_path_field(self.selected_path):
                    validate_btn.remove_class("hidden")
                    self._validate_current_path()
                else:
                    validate_btn.add_class("hidden")

    def _get_field_description(self, path: List[str]) -> str:
        descriptions = {
            ("app", "name"): "Application name displayed in the header",
            ("app", "debug"): "Enable debug mode with verbose logging",
            ("data_source", "type"): "Backend type: 'filesystem' or 'mongodb'",
            ("data_source", "filesystem", "path"): "Path to directory containing JSON files",
            ("data_source", "mongodb", "uri"): "MongoDB connection URI (must start with mongodb:// or mongodb+srv://)",
            ("data_source", "mongodb", "database"): "MongoDB database name",
            (
                "data_source",
                "mongodb",
                "connect_timeout_ms",
            ): "How long to wait for initial connection (ms, 1000-120000)",
            (
                "data_source",
                "mongodb",
                "server_selection_timeout_ms",
            ): "How long to wait for server selection (ms, 1000-120000)",
            (
                "data_source",
                "mongodb",
                "socket_timeout_ms",
            ): "How long to wait for socket operations (ms, 0=no timeout)",
            ("data_source", "mongodb", "tls"): "Enable TLS/SSL encrypted connection to MongoDB",
            ("data_source", "mongodb", "direct_connection"): "Connect directly to single server (bypass replica set)",
            ("mongodb_auth", "type"): "Authentication type: 'userpass', 'x509', or 'none'",
            ("mongodb_auth", "userpass", "user"): "MongoDB username for authentication",
            ("mongodb_auth", "userpass", "password"): "MongoDB password for authentication",
            ("mongodb_auth", "userpass", "auth_source"): "Database to authenticate against (default: admin)",
            ("mongodb_auth", "userpass", "auth_mechanism"): "SCRAM authentication mechanism (DEFAULT auto-selects)",
            ("mongodb_auth", "x509", "cert_dir"): "Directory containing certificate files",
            ("mongodb_auth", "x509", "ca_cert"): "CA certificate filename for server verification",
            ("mongodb_auth", "x509", "client_cert"): "Client certificate with private key for authentication",
            ("mongodb_auth", "x509", "auth_mechanism"): "Must be MONGODB-X509 for certificate auth",
            ("mongodb_auth", "x509", "auth_source"): "Must be $external for X.509 authentication",
            (
                "mongodb_auth",
                "x509",
                "allow_invalid_certificates",
            ): "Skip certificate validation (INSECURE - testing only)",
            ("mongodb_auth", "x509", "allow_invalid_hostnames"): "Skip hostname validation (INSECURE - testing only)",
            ("cache", "enabled"): "Enable disk caching for performance",
            ("cache", "directory"): "Cache storage directory path",
            ("cache", "ttl"): "Cache time-to-live in seconds (0 = no expiration)",
            ("cache", "max_entries"): "Maximum number of cached entries",
            ("cache", "max_size_mb"): "Maximum cache size in megabytes",
            ("cache", "auto_purge"): "Automatically purge expired entries on startup",
            ("ui", "theme"): "Color theme for the application",
            ("ui", "show_deleted"): "Show deleted documents by default",
            ("ui", "mouse_support"): "Enable mouse interaction",
            ("ui", "show_key_hints"): "Show keyboard shortcuts panel",
            ("ui", "datetime_format"): "Date/time display format (strftime)",
            ("ui", "date_format"): "Date-only display format",
            ("ui", "timezone"): "Timezone for display (null = local)",
            ("ui", "max_list_items"): "Maximum items to display in lists",
            ("ui", "max_text_length"): "Truncate text after N characters",
            ("tables", "zebra_stripes"): "Enable alternating row colors",
            ("tables", "default_sort_order"): "Default sort order for tables",
            ("logging", "trace_enabled"): "Enable trace logging for debugging",
            ("logging", "trace_file"): "Trace log file path",
            ("logging", "level"): "Logging verbosity level",
            ("logging", "max_trace_size_mb"): "Maximum trace file size in MB",
            ("logging", "trace_backup_count"): "Number of backup logs to keep",
            ("backup", "output_directory"): "Default output directory for backups",
            ("backup", "filename_pattern"): "Backup filename pattern with placeholders",
            ("backup", "timestamp_format"): "Timestamp format for backup filenames",
            ("backup", "compress"): "Compress backup archives",
            ("backup", "compression_level"): "Compression level (1-9)",
            ("restore", "require_confirmation"): "Require confirmation before restore",
            ("restore", "drop_existing"): "Drop existing collections before restore",
            ("search", "fuzzy_match"): "Enable fuzzy matching in filters",
            ("search", "min_search_chars"): "Minimum characters before search starts",
            ("search", "debounce_ms"): "Search debounce delay in milliseconds",
            ("search", "case_insensitive"): "Case sensitivity for search",
            ("tools", "mongo_shell"): "MongoDB shell command (null = auto-detect)",
            ("tools", "mongodump"): "mongodump executable path",
            ("tools", "mongorestore"): "mongorestore executable path",
        }
        return descriptions.get(tuple(path), "No description available")

    def _validate_current_path(self) -> None:
        if not self.selected_path:
            return
        input_field = self.query_one(f"#{WidgetID.CONFIG_VALUE_INPUT}", Input)
        value = input_field.value
        status_widget = self.query_one("#validation_status", Static)
        if value == "null" or value == "":
            if self._is_executable_field(self.selected_path):
                status_widget.update("[yellow]null = auto-detect[/]")
            else:
                status_widget.update("[yellow]Path not set[/]")
            return
        expanded_path = Path(value).expanduser()
        if self._is_directory_field(self.selected_path):
            if expanded_path.exists():
                if expanded_path.is_dir():
                    status_widget.update(f"[green]Directory exists[/]")
                else:
                    status_widget.update(f"[red]Path exists but is not a directory[/]")
            else:
                status_widget.update(f"[yellow]Directory does not exist - will offer to create[/]")
        elif self._is_file_field(self.selected_path):
            if tuple(self.selected_path) in [
                ("mongodb_auth", "x509", "ca_cert"),
                ("mongodb_auth", "x509", "client_cert"),
            ]:
                cert_dir = Path(self.current_config.mongodb_auth.x509.cert_dir).expanduser()
                full_path = cert_dir / value
                if full_path.exists():
                    status_widget.update(f"[green]File exists: {full_path}[/]")
                else:
                    status_widget.update(f"[red]File not found: {full_path}[/]")
            elif expanded_path.exists():
                status_widget.update(f"[green]File exists[/]")
            elif expanded_path.parent.exists():
                status_widget.update(f"[yellow]File will be created[/]")
            else:
                status_widget.update(f"[red]Parent directory does not exist[/]")
        elif self._is_executable_field(self.selected_path):
            exe_path = shutil.which(value)
            if exe_path:
                status_widget.update(f"[green]Found: {exe_path}[/]")
            elif expanded_path.exists() and os.access(expanded_path, os.X_OK):
                status_widget.update(f"[green]Executable exists[/]")
            else:
                status_widget.update(f"[red]Executable not found in PATH[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "validate_path_btn":
            self._validate_and_fix_path()

    def _rebuild_radio_buttons(self, radio_set: RadioSet, options: List[Tuple[str, str]], current_value: str) -> None:
        self._applying_value = True
        try:
            for child in list(radio_set.children):
                child.remove()
            radio_set._pressed_button = None
            for idx, (opt_value, opt_label) in enumerate(options):
                is_selected = opt_value == current_value
                btn = RadioButton(opt_label, value=is_selected)
                btn.data = {"value": opt_value}
                radio_set.mount(btn)
                if is_selected:
                    radio_set._pressed_button = btn
        finally:

            def clear_guard():
                self._applying_value = False

            self.call_later(clear_guard)

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if self._current_field_type != "select" or self._applying_value:
            return
        if event.pressed and hasattr(event.pressed, "data"):
            value = event.pressed.data.get("value")
            if value:
                self._apply_radio_value(value)

    def _apply_radio_value(self, value: str) -> None:
        if not self.selected_path:
            return
        self._applying_value = True
        try:
            if value.lower() == "true":
                typed_value = True
            elif value.lower() == "false":
                typed_value = False
            else:
                typed_value = value
            (is_valid, error_msg) = self._validate_field_value(self.selected_path, typed_value)
            self._set_config_value(self.selected_path, typed_value)
            self.modified = True
            if is_valid:
                self._mark_field_valid(self.selected_path)
            else:
                self._mark_field_invalid(self.selected_path, error_msg)
            try:
                self.build_tree()
                self._update_status("Modified (unsaved)")
            except Exception:
                pass
            trace.debug(
                "Applied configuration value",
                tags=["config", "mutation"],
                path=".".join(self.selected_path),
                value=str(typed_value),
                is_valid=is_valid,
            )
            self._focus_tree()
        except Exception as e:
            self._mark_field_invalid(self.selected_path, str(e))
            try:
                self.build_tree()
            except Exception:
                pass
            self.notify(f"Invalid value: {_escape_markup(str(e))}", severity="error")
            trace.error(
                "Failed to apply radio value", tags=["config", "error"], path=".".join(self.selected_path), exception=e
            )
        finally:

            def clear_guard():
                self._applying_value = False

            self.call_later(clear_guard)

    def _focus_tree(self) -> None:
        try:
            tree = self.query_one(f"#{WidgetID.CONFIG_TREE}", Tree)
            tree.focus()
        except Exception:
            pass

    def _save_tree_state(self) -> None:
        try:
            tree = self.query_one(f"#{WidgetID.CONFIG_TREE}", Tree)
            self._tree_expanded_paths.clear()
            self._collect_expanded_paths(tree.root, [])
            if tree.cursor_node and tree.cursor_node.data:
                path = tree.cursor_node.data.get("path", [])
                self._tree_selected_path = tuple(path) if path else None
            else:
                self._tree_selected_path = None
            trace.debug(
                "Tree state saved",
                tags=["config", "tree"],
                expanded_count=len(self._tree_expanded_paths),
                selected_path=".".join(self._tree_selected_path) if self._tree_selected_path else None,
            )
        except Exception as e:
            trace.debug("Could not save tree state", tags=["config", "tree"], exception=e)

    def _collect_expanded_paths(self, node: TreeNode, path: List[str]) -> None:
        if node.is_expanded and path:
            self._tree_expanded_paths.add(tuple(path))
        for child in node.children:
            if child.data and "key" in child.data:
                child_path = path + [child.data["key"]]
                self._collect_expanded_paths(child, child_path)

    def _restore_tree_state(self) -> None:
        try:
            tree = self.query_one(f"#{WidgetID.CONFIG_TREE}", Tree)
            self._restore_expanded_paths(tree.root, [])
            if self._tree_selected_path:
                self._select_node_by_path(tree, list(self._tree_selected_path))
            trace.debug(
                "Tree state restored",
                tags=["config", "tree"],
                expanded_count=len(self._tree_expanded_paths),
                selected_path=".".join(self._tree_selected_path) if self._tree_selected_path else None,
            )
        except Exception as e:
            trace.debug("Could not restore tree state", tags=["config", "tree"], exception=e)

    def _restore_expanded_paths(self, node: TreeNode, path: List[str]) -> None:
        path_tuple = tuple(path)
        if path_tuple in self._tree_expanded_paths:
            node.expand()
        for child in node.children:
            if child.data and "key" in child.data:
                child_path = path + [child.data["key"]]
                self._restore_expanded_paths(child, child_path)

    def _select_node_by_path(self, tree: Tree, path: List[str]) -> None:
        current_node = tree.root
        for key in path:
            found = False
            for child in current_node.children:
                if child.data and child.data.get("key") == key:
                    current_node = child
                    found = True
                    break
            if not found:
                return
        tree.select_node(current_node)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == WidgetID.CONFIG_VALUE_INPUT:
            self._apply_value(return_focus=True)
            event.stop()

    def on_key(self, event) -> None:
        if event.key == "escape" and self._is_input_focused():
            self._apply_value(return_focus=True)
            event.stop()
            event.prevent_default()

    def watch_focused(self, old_widget, new_widget) -> None:
        if old_widget is not None:
            if isinstance(old_widget, Tree):
                self._save_tree_state()
            elif isinstance(old_widget, Input) and old_widget.id == WidgetID.CONFIG_VALUE_INPUT:
                if not old_widget.disabled and self._current_field_type == "input":
                    self._apply_value(return_focus=False)
        if new_widget is None:
            return
        if isinstance(new_widget, Tree):
            self._restore_tree_state()
        elif isinstance(new_widget, Input) and new_widget.id == WidgetID.CONFIG_VALUE_INPUT:
            if not new_widget.disabled:
                new_widget.selection = (0, len(new_widget.value))

    def _apply_value(self, return_focus: bool = False) -> None:
        if not self.selected_path:
            self.notify("No setting selected", severity="warning")
            return
        if self._current_field_type == "readonly":
            self.notify("This field cannot be edited directly", severity="warning")
            return
        if self._current_field_type == "select":
            return
        input_field = self.query_one(f"#{WidgetID.CONFIG_VALUE_INPUT}", Input)
        new_value = input_field.value
        try:
            if new_value.lower() == "true":
                typed_value = True
            elif new_value.lower() == "false":
                typed_value = False
            elif new_value.lower() == "null" or new_value == "":
                typed_value = None
            elif new_value.isdigit():
                typed_value = int(new_value)
            elif new_value.lstrip("-").replace(".", "", 1).isdigit():
                typed_value = float(new_value)
            elif new_value.startswith("[") or new_value.startswith("{"):
                typed_value = yaml.safe_load(new_value)
            else:
                typed_value = new_value
            (is_valid, error_msg) = self._validate_field_value(self.selected_path, typed_value)
            self._set_config_value(self.selected_path, typed_value)
            self.modified = True
            if is_valid:
                self._mark_field_valid(self.selected_path)
                self.notify("Value applied", timeout=1)
            else:
                self._mark_field_invalid(self.selected_path, error_msg)
                self.notify(f"Value applied (invalid: {_escape_markup(error_msg)})", severity="warning", timeout=3)
            self.build_tree()
            self._update_status("Modified (unsaved)")
            trace.debug(
                "Applied input value to configuration",
                tags=["config", "mutation"],
                path=".".join(self.selected_path),
                value=str(typed_value)[:50],
                is_valid=is_valid,
            )
            if self._is_path_field(self.selected_path):
                self._validate_current_path()
            if return_focus:
                self._focus_tree()
        except Exception as e:
            self._mark_field_invalid(self.selected_path, str(e))
            self.build_tree()
            self.notify(f"Invalid value: {_escape_markup(str(e))}", severity="error")
            trace.error(
                "Failed to apply value", tags=["config", "error"], path=".".join(self.selected_path), exception=e
            )

    def _check_path_value(self, value: str) -> Tuple[bool, str]:
        if value == "null" or value == "":
            return (True, "")
        expanded_path = Path(value).expanduser()
        if self._is_executable_field(self.selected_path):
            exe_path = shutil.which(value)
            if not exe_path and (not (expanded_path.exists() and os.access(expanded_path, os.X_OK))):
                return (True, "")
        return (True, "")

    def _validate_and_fix_path(self) -> None:
        if not self.selected_path:
            return
        input_field = self.query_one(f"#{WidgetID.CONFIG_VALUE_INPUT}", Input)
        value = input_field.value
        if value == "null" or value == "":
            self.notify("No path specified", severity="warning")
            return
        expanded_path = Path(value).expanduser()
        if self._is_directory_field(self.selected_path):
            if not expanded_path.exists():
                self._offer_create_directory(expanded_path)
            elif not expanded_path.is_dir():
                self.notify(f"Path exists but is not a directory: {expanded_path}", severity="error")
            else:
                self.notify(f"Directory exists: {expanded_path}", timeout=2)
        elif self._is_executable_field(self.selected_path):
            exe_path = shutil.which(value)
            if exe_path:
                self.notify(f"Executable found: {exe_path}", timeout=2)
            elif expanded_path.exists() and os.access(expanded_path, os.X_OK):
                self.notify(f"Executable exists: {expanded_path}", timeout=2)
            else:
                self.notify(
                    f"Executable not found: {value}\nMake sure it's installed and in your PATH", severity="error"
                )
        else:
            self._validate_current_path()

    def _offer_create_directory(self, path: Path) -> None:
        try:
            path.mkdir(parents=True, exist_ok=True)
            self.notify(f"Created directory: {path}", timeout=2)
            self._validate_current_path()
        except PermissionError:
            self.notify(f"Permission denied: Cannot create {path}", severity="error")
        except Exception as e:
            self.notify(f"Failed to create directory: {_escape_markup(str(e))}", severity="error")

    def _set_config_value(self, path: List[str], value: Any) -> None:
        config_dict = self.current_config.model_dump()
        current = config_dict
        for key in path[:-1]:
            current = current[key]
        current[path[-1]] = value
        self.current_config = AppConfig(**config_dict)
        path_tuple = tuple(path)
        original_value = self._get_original_value(path)
        if value != original_value:
            self._modified_paths.add(path_tuple)
        else:
            self._modified_paths.discard(path_tuple)

    def _get_original_value(self, path: List[str]) -> Any:
        if not self._original_config:
            return None
        original_dict = self._original_config.model_dump()
        current = original_dict
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current

    def _reset_value(self) -> None:
        if not self.selected_path:
            return
        default_config = AppConfig()
        default_dict = default_config.model_dump()
        current = default_dict
        for key in self.selected_path:
            current = current.get(key)
            if current is None:
                break
        if self._current_field_type == "select":
            radio_set = self.query_one("#config_radio_set", RadioSet)
            if isinstance(current, bool):
                str_value = "true" if current else "false"
            elif current is None:
                str_value = "null"
            else:
                str_value = str(current)
            options = self._get_discrete_options(self.selected_path)
            self._rebuild_radio_buttons(radio_set, options, str_value)
        else:
            input_field = self.query_one(f"#{WidgetID.CONFIG_VALUE_INPUT}", Input)
            if current is None:
                input_field.value = "null"
            elif isinstance(current, (dict, list)):
                input_field.value = yaml.dump(current, default_flow_style=True).strip()
            else:
                input_field.value = str(current)
        self.notify("Field reset to default", timeout=1)

    def action_save_config(self) -> None:
        if self._invalid_paths:
            invalid_count = len(self._invalid_paths)
            first_invalid = next(iter(self._invalid_paths))
            error_msg = self._validation_errors.get(first_invalid, "Invalid value")
            self.notify(
                f"Cannot save: {invalid_count} invalid value(s). Fix them first.\nFirst invalid: {' > '.join(first_invalid)} - {_escape_markup(error_msg)}",
                severity="error",
                timeout=5,
            )
            trace.warning(
                "Save blocked due to invalid values",
                tags=["config", "validation"],
                invalid_count=invalid_count,
                invalid_paths=[".".join(p) for p in self._invalid_paths],
            )
            return
        old_theme = self.app.config.ui.theme
        try:
            self.config_loader.save(self.current_config)
            self.modified = False
            self._modified_paths.clear()
            self._update_status("Saved")
            self.app.config = self.current_config
            new_theme = self.current_config.ui.theme
            if old_theme != new_theme:
                if new_theme in self.app.available_themes:
                    self.app.theme = new_theme
                    trace.info(
                        "Theme changed and applied", tags=["theme", "config"], old_theme=old_theme, new_theme=new_theme
                    )
                    self.notify(f"Theme changed to {new_theme}", timeout=3)
                else:
                    trace.error(
                        "Theme not available",
                        tags=["theme", "config", "error"],
                        theme=new_theme,
                        available=list(self.app.available_themes.keys()),
                    )
                    self.notify(f"Warning: Theme '{new_theme}' not available", severity="error", timeout=5)
            else:
                self.notify("Configuration saved successfully", timeout=2)
            self._original_config = copy.deepcopy(self.current_config)
            try:
                self.build_tree()
            except Exception:
                pass
            trace.info("Configuration saved to file", tags=["config", "mutation"])
        except ConfigError as e:
            self.notify(f"Error saving: {_escape_markup(str(e))}", severity="error")

    def action_refresh_data(self) -> None:
        trace.info(
            "action_refresh_data called (should not happen, 'r' should call reset_config)",
            tags=["config", "action", "unexpected"],
        )

    def action_reset_config(self) -> None:
        trace.info("action_reset_config called", tags=["config", "action"])
        self.current_config = AppConfig()
        self.modified = True
        self._modified_paths.clear()
        self.build_tree()
        self._update_status("Reset to defaults (unsaved)")
        self.notify("Configuration reset to defaults", timeout=2)

    def action_validate_config(self) -> None:
        config_dict = self.current_config.model_dump()
        self._invalid_paths.clear()
        self._validation_errors.clear()
        self._validate_all_fields(config_dict)
        (is_valid, errors) = self.config_loader.validate(config_dict)
        if self._invalid_paths:
            first_invalid = next(iter(self._invalid_paths))
            error_msg = self._validation_errors.get(first_invalid, "Invalid value")
            self.build_tree()
            self._expand_and_select_path(list(first_invalid))
            invalid_count = len(self._invalid_paths)
            self.notify(
                f"Found {invalid_count} invalid value(s). First: {' > '.join(first_invalid)}",
                severity="error",
                timeout=5,
            )
            trace.info(
                "Validation found invalid values",
                tags=["config", "validation"],
                invalid_count=invalid_count,
                first_invalid=".".join(first_invalid),
            )
        elif not is_valid:
            error_msg = "\n".join(errors[:5])
            self.notify(f"Validation issues:\n{_escape_markup(error_msg)}", severity="error", timeout=5)
        else:
            try:
                self.build_tree()
            except Exception:
                pass
            self.notify("Configuration is valid ✓", timeout=2)
            trace.info("Configuration validated successfully", tags=["config", "validation"])

    def _validate_all_fields(self, data: dict, path: List[str] = None) -> None:
        if path is None:
            path = []
        for key, value in data.items():
            current_path = path + [key]
            if isinstance(value, dict):
                self._validate_all_fields(value, current_path)
            elif not isinstance(value, list):
                (is_valid, error_msg) = self._validate_field_value(current_path, value)
                if not is_valid:
                    self._mark_field_invalid(current_path, error_msg)

    def _expand_and_select_path(self, path: List[str]) -> None:
        try:
            tree = self.query_one(f"#{WidgetID.CONFIG_TREE}", Tree)
            current_node = tree.root
            for i, key in enumerate(path):
                current_node.expand()
                found = False
                for child in current_node.children:
                    if child.data and child.data.get("key") == key:
                        current_node = child
                        found = True
                        break
                if not found:
                    trace.warning(
                        "Could not find tree node for path",
                        tags=["config", "tree"],
                        path=".".join(path),
                        missing_key=key,
                    )
                    break
            current_node.expand()
            tree.select_node(current_node)

            def _move_to_node():
                tree.scroll_to_node(current_node)

            self.call_after_refresh(_move_to_node)
            trace.debug("Expanded and selected tree path", tags=["config", "tree"], path=".".join(path))
        except Exception as e:
            trace.error(
                "Failed to expand tree to path", tags=["config", "tree", "error"], path=".".join(path), exception=e
            )

    def _get_value_by_path(self, data: dict, path: Tuple[str, ...]) -> Any:
        current = data
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current

    def _update_status(self, status: str) -> None:
        status_bar = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        config_file = self.config_loader.find_config_file()
        if config_file:
            file_info = str(config_file.resolve())
        else:
            file_info = "No file (using defaults)"
        parts = [status]
        mode_label = DISPLAY_MODE_LABELS.get(self._display_mode, "Unknown")
        parts.append(f"Mode: {mode_label}")
        if self._modified_paths:
            parts.append(f"Modified: {len(self._modified_paths)}")
        if self._invalid_paths:
            parts.append(f"[red]Invalid: {len(self._invalid_paths)}[/]")
        if self._show_modified_only:
            parts.append("[filter: modified only]")
        parts.append(f"File: {file_info}")
        status_bar.update(" | ".join(parts))

    def action_cursor_down(self) -> None:
        tree = self.query_one(f"#{WidgetID.CONFIG_TREE}", Tree)
        tree.action_cursor_down()

    def action_cursor_up(self) -> None:
        tree = self.query_one(f"#{WidgetID.CONFIG_TREE}", Tree)
        tree.action_cursor_up()

    def action_goto_first(self) -> None:
        tree = self.query_one(f"#{WidgetID.CONFIG_TREE}", Tree)
        tree.action_scroll_home()

    def action_goto_last(self) -> None:
        tree = self.query_one(f"#{WidgetID.CONFIG_TREE}", Tree)
        tree.action_scroll_end()

    def action_edit_field(self) -> None:
        tree = self.query_one(f"#{WidgetID.CONFIG_TREE}", Tree)
        if not tree.has_focus:
            return
        if not self.selected_path:
            return
        if self._current_field_type == "readonly":
            self.notify("This field cannot be edited directly", severity="warning")
            return
        if self._current_field_type == "select":
            radio_set = self.query_one("#config_radio_set", RadioSet)
            radio_set.focus()
        else:
            input_field = self.query_one(f"#{WidgetID.CONFIG_VALUE_INPUT}", Input)
            input_field.focus()

    def action_go_back(self) -> None:
        if self.modified:
            self.notify("Unsaved changes will be lost", severity="warning", timeout=2)
        trace.info(
            "Returning from ConfigEditorScreen",
            tags=["screen", "navigation"],
            from_screen="ConfigEditorScreen",
            reason="User pressed back (escape/h/left)",
        )
        self.app.pop_screen()

    def action_cycle_mode(self) -> None:
        trace.info("action_cycle_mode called", tags=["config", "action"])
        if not self.current_config:
            self.notify("Configuration not loaded", severity="warning")
            return
        modes = [DisplayMode.ALL, DisplayMode.DATA_SOURCE, DisplayMode.TREE_VIEW]
        current_idx = modes.index(self._display_mode)
        next_idx = (current_idx + 1) % len(modes)
        self._display_mode = modes[next_idx]
        trace.debug("Display mode changed", tags=["config", "ui"], new_mode=self._display_mode.value)
        self.build_tree()
        mode_label = DISPLAY_MODE_LABELS.get(self._display_mode, "Unknown")
        self._update_status("Ready")
        self.notify(f"Mode: {mode_label}", timeout=1)

    def action_toggle_modified(self) -> None:
        trace.info("action_toggle_modified called", tags=["config", "action"])
        if not self.current_config:
            self.notify("Configuration not loaded", severity="warning")
            return
        self._show_modified_only = not self._show_modified_only
        trace.debug(
            "Modified-only filter toggled",
            tags=["config", "ui"],
            show_modified_only=self._show_modified_only,
            modified_count=len(self._modified_paths),
        )
        if self._show_modified_only and (not self._modified_paths):
            self.notify("No modified settings to show", severity="warning", timeout=2)
            self._show_modified_only = False
            return
        self.build_tree()
        self._update_status("Ready")
        if self._show_modified_only:
            self.notify(f"Showing {len(self._modified_paths)} modified settings", timeout=2)
        else:
            self.notify("Showing all settings", timeout=1)

    def action_undo_changes(self) -> None:
        trace.info("action_undo_changes called", tags=["config", "action"])
        if not self._modified_paths:
            self.notify("No changes to undo", timeout=2)
            return
        try:
            self.load_config()
            self._modified_paths.clear()
            self._invalid_paths.clear()
            self._validation_errors.clear()
            self.modified = False
            self._show_modified_only = False
            trace.info("Configuration reloaded from file", tags=["config", "mutation"])
            self.build_tree()
            self._update_status("Changes undone - reloaded from file")
            self.notify("Changes undone - file reloaded", timeout=2)
        except Exception as e:
            trace.error("Failed to reload config file for undo", tags=["config", "error"], exception=e)
            self.notify(f"Failed to reload config: {_escape_markup(str(e))}", severity="error")
