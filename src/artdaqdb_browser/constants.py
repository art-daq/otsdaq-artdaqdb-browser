"""
File: constants.py
Purpose: Centralized constants for OTS Browser application.
Category: Utility
Author: ArtdaqDB Browser Team
Depends: None
Exports: ScreenName, WidgetID, CacheKey, BookkeepingEvent, DocumentStatus, ...
Complexity: High | Lines: 564
"""

from enum import Enum, auto
from typing import List, Optional, Tuple


class ScreenName(str, Enum):
    HOME = "home"
    CONFIG_LIST = "config_list"
    COLLECTION_TABLE = "collection_table"
    VERSION_LIST = "version_list"
    DOCUMENT_VIEW = "document_view"
    COLLECTION_BROWSER = "collection_browser"
    HELP = "help"
    TRACE_VIEWER = "trace_viewer"
    DB_BROWSER = "db_browser"
    DB_UTILITIES = "db_utilities"
    SERVER_STATS = "server_stats"
    DATABASE_STATS = "database_stats"
    DB_BACKUP = "db_backup"
    DB_RESTORE = "db_restore"
    RECREATE_INDEXES = "recreate_indexes"
    CONFIG_EDITOR = "config_editor"
    DB_DOCTOR = "db_doctor"
    REPAIR_COLLECTION = "repair_collection"
    REPAIR_CONFIGURATION = "repair_configuration"
    CACHE_VIEWER = "cache_viewer"
    JSON_DIFF_MERGE = "json_diff_merge"


class WidgetID(str, Enum):
    MENU_TABLE = "menu_table"
    CONFIG_TABLE = "config_table"
    COLLECTION_TABLE = "collection_table"
    VERSION_TABLE = "version_table"
    FILTER_INPUT = "filter_input"
    FILTER_INPUT_FIELD = "filter_input_field"
    CONFIG_NAME_INPUT = "config_name_input"
    CONFIG_LIST = "config_list"
    JSON_VIEWER = "json_viewer"
    STATUS_BAR = "status_bar"
    DOC_TITLE = "doc_title"
    CONFIG_TITLE = "config_title"
    CONFIG_INFO = "config_info"
    COLLECTION_TITLE = "collection_title"
    COLLECTION_INFO = "collection_info"
    ASSIGNMENT_TIME = "assignment_time"
    MODE_INDICATOR = "mode_indicator"
    SUMMARY_COLLECTIONS = "summary_collections"
    SUMMARY_CONFIGS = "summary_configs"
    SUMMARY_DOCS = "summary_docs"
    SUMMARY_SOURCE = "summary_source"
    SUMMARY_CACHE = "summary_cache"
    BROWSER_MENU = "browser_menu"
    UTILITIES_MENU = "utilities_menu"
    STATS_CONTENT = "stats_content"
    DB_SELECT = "db_select"
    BACKUP_PATH = "backup_path"
    RESTORE_PATH = "restore_path"
    OUTPUT_LOG = "output_log"
    PROGRESS_BAR = "progress_bar"
    CONFIG_TREE = "config_tree"
    CONFIG_VALUE_INPUT = "config_value_input"
    CONFIG_PREVIEW = "config_preview"
    DOCTOR_MENU = "doctor_menu"
    REPAIR_TABLE = "repair_table"
    GLOBAL_TRASH_TABLE = "global_trash_table"
    CACHE_TABLE = "cache_table"
    CACHE_SUMMARY = "cache_summary"
    DIFF_TABLE = "diff-table"
    JSON_TREE = "json-tree"
    DIFF_STATUS_BAR = "diff-status-bar"
    MODE_SELECT = "mode-select"


class CacheKey(str, Enum):
    CONFIGURATIONS_LIST = "configurations_list"
    COLLECTIONS_LIST = "collections_list"
    CONFIGURATION_INFO = "configuration_info"
    COLLECTION_INFO = "collection_info"
    ALL_DOCUMENTS = "all_documents"

    @staticmethod
    def config_documents(config_name: str) -> str:
        return f"config_docs:{config_name}"

    @staticmethod
    def collection_documents(collection_name: str) -> str:
        return f"collection_docs:{collection_name}"

    @staticmethod
    def document_versions(collection_name: str) -> str:
        return f"doc_versions:{collection_name}"


class BookkeepingEvent(str, Enum):
    ADD_CONFIGURATION = "addConfiguration"
    ADD_ENTITY = "addEntity"
    SET_VERSION = "setVersion"
    SET_COLLECTION = "setCollection"
    MARK_DELETED = "markDeleted"


class DocumentStatus(str, Enum):
    ACTIVE = "Active"
    DELETED = "Deleted"


class KeyHint:
    NAVIGATE_JK = ("j/k", "Nav")
    NAVIGATE_ARROWS = ("↑/↓", "Nav")
    SEARCH = ("/", "Search")
    CLEAR = ("c", "Clear")
    BACK = ("h/←", "Back")
    FORWARD = ("l/→", "Forward")
    SELECT = ("Entr", "Select")
    VIEW = ("Entr", "View")
    QUIT = ("q", "Quit")
    TAB_SWITCH = ("Tab", "Switch")
    COPY_ID = ("y", "Copy")
    ASSIGN = ("a", "Assign")
    TOGGLE_DELETE = ("d", "Delete")
    VIEW_CONFIG = ("Entr", "View")


class KeyPanelCategory:
    NAVIGATION: List[Tuple[str, str]] = [("j/k", "Up/Down")]
    SCREEN_NAV: List[Tuple[str, str]] = [("h/←", "Back"), ("l/→", "Forward"), ("Esc", "Cancel")]
    ACTIONS_PRIMARY: List[Tuple[str, str]] = [("Entr", "Select"), ("r", "Refresh")]
    FOCUS: List[Tuple[str, str]] = [("Tab", "Focus")]
    APPLICATION: List[Tuple[str, str]] = [("?", "Help"), ("q", "Quit")]


def get_base_key_panel_bindings(
    include_navigation: bool = True,
    include_screen_nav: bool = True,
    include_actions_primary: bool = True,
    include_focus: bool = True,
    include_application: bool = True,
) -> List[Tuple[str, str]]:
    bindings: List[Tuple[str, str]] = []
    if include_navigation:
        bindings.extend(KeyPanelCategory.NAVIGATION)
    if include_screen_nav:
        bindings.extend(KeyPanelCategory.SCREEN_NAV)
    if include_focus:
        bindings.extend(KeyPanelCategory.FOCUS)
    if include_actions_primary:
        bindings.extend(KeyPanelCategory.ACTIONS_PRIMARY)
    if include_application:
        bindings.extend(KeyPanelCategory.APPLICATION)
    return bindings


STANDARD_KEY_PANEL_BINDINGS: List[Tuple[str, str]] = get_base_key_panel_bindings(include_application=False)


class KeyHints:
    FILTERABLE_TABLE: List[Tuple[str, str]] = [
        KeyHint.NAVIGATE_JK,
        KeyHint.NAVIGATE_ARROWS,
        KeyHint.BACK,
        KeyHint.FORWARD,
        KeyHint.SELECT,
    ]
    SIMPLE_TABLE: List[Tuple[str, str]] = [
        KeyHint.NAVIGATE_JK,
        KeyHint.NAVIGATE_ARROWS,
        KeyHint.BACK,
        KeyHint.FORWARD,
        KeyHint.VIEW,
    ]
    HOME_MENU: List[Tuple[str, str]] = [
        KeyHint.NAVIGATE_JK,
        KeyHint.NAVIGATE_ARROWS,
        KeyHint.FORWARD,
        KeyHint.SELECT,
        KeyHint.QUIT,
    ]
    DOCUMENT_VIEW: List[Tuple[str, str]] = [
        KeyHint.NAVIGATE_JK,
        KeyHint.NAVIGATE_ARROWS,
        KeyHint.TAB_SWITCH,
        KeyHint.COPY_ID,
        KeyHint.ASSIGN,
        KeyHint.BACK,
        KeyHint.FORWARD,
        KeyHint.VIEW_CONFIG,
    ]
    COLLECTION_TABLE: List[Tuple[str, str]] = [
        KeyHint.NAVIGATE_JK,
        KeyHint.NAVIGATE_ARROWS,
        KeyHint.TOGGLE_DELETE,
        KeyHint.BACK,
        KeyHint.FORWARD,
        KeyHint.SELECT,
    ]
    TRACE_VIEWER: List[Tuple[str, str]] = [
        ("j/k", "Scroll"),
        ("g/G", "Top/Bot"),
        ("/", "Search"),
        ("n/N", "Next/Prev"),
        ("r", "Refresh"),
        ("c", "Clear"),
        ("^T", "Back"),
    ]
    DB_UTILITIES: List[Tuple[str, str]] = [
        KeyHint.NAVIGATE_JK,
        KeyHint.NAVIGATE_ARROWS,
        KeyHint.FORWARD,
        KeyHint.SELECT,
        KeyHint.BACK,
    ]
    STATS_VIEWER: List[Tuple[str, str]] = [
        ("j/k", "Scroll"),
        ("g/G", "Top/Bot"),
        ("r", "Refresh"),
        ("a", "Extended"),
        KeyHint.BACK,
    ]
    BACKUP: List[Tuple[str, str]] = [
        ("j/k", "Nav"),
        ("g/G", "Top/Bot"),
        ("Tab", "Next"),
        ("e/l/→", "Backup"),
        KeyHint.BACK,
    ]
    RESTORE: List[Tuple[str, str]] = [
        ("j/k", "Nav"),
        ("g/G", "Top/Bot"),
        ("Tab", "Next"),
        ("b", "Browse"),
        ("s", "Select"),
        ("w", "Wipe"),
        ("e/l/→", "Restore"),
        KeyHint.BACK,
    ]
    CONFIG_EDITOR: List[Tuple[str, str]] = [
        KeyHint.NAVIGATE_JK,
        ("Entr", "Edit"),
        ("s", "Save"),
        ("r", "Reset"),
        ("v", "Validate"),
        KeyHint.BACK,
    ]
    DB_DOCTOR: List[Tuple[str, str]] = [
        KeyHint.NAVIGATE_JK,
        KeyHint.NAVIGATE_ARROWS,
        KeyHint.FORWARD,
        KeyHint.SELECT,
        KeyHint.BACK,
    ]
    REPAIR_TABLE: List[Tuple[str, str]] = [
        KeyHint.NAVIGATE_JK,
        KeyHint.NAVIGATE_ARROWS,
        KeyHint.BACK,
        KeyHint.FORWARD,
        KeyHint.SELECT,
    ]
    GLOBAL_TRASH_TABLE: List[Tuple[str, str]] = [KeyHint.NAVIGATE_JK, KeyHint.NAVIGATE_ARROWS, KeyHint.BACK]
    HN_DETAIL: List[Tuple[str, str]] = [
        ("j/k", "Scroll"),
        ("g/G", "Top/Bot"),
        ("n/p", "Next/Prev"),
        ("s", "Article"),
        ("c", "Comments"),
        ("i", "Info"),
        KeyHint.BACK,
    ]
    CACHE_VIEWER: List[Tuple[str, str]] = [
        KeyHint.NAVIGATE_JK,
        KeyHint.NAVIGATE_ARROWS,
        ("r", "Refresh"),
        ("c", "Clear"),
        ("p", "Purge"),
        ("Del", "Delete"),
        KeyHint.BACK,
    ]
    JSON_DIFF_MERGE: List[Tuple[str, str]] = [
        ("j/k", "Nav"),
        ("Tab", "Panel"),
        ("c", "Copy"),
        ("s", "Save"),
        ("m", "Mode"),
        ("h", "Back"),
    ]


class TableColumns:
    CONFIGURATION_LIST: List[Tuple[str, str, int]] = [
        ("Configuration Name", "name", 40),
        ("Collections", "collections", 12),
        ("Last Assigned", "assigned", 20),
    ]
    COLLECTION_BROWSER: List[Tuple[str, str, int]] = [
        ("Collection Name", "name", 35),
        ("Versions", "versions", 10),
        ("Latest Ver", "latest", 12),
        ("Last Update", "updated", 20),
    ]
    COLLECTION_TABLE: List[Tuple[str, str, int]] = [
        ("Collection", "collection", 35),
        ("Version", "version", 10),
        ("Created", "created", 20),
        ("Status", "status", 12),
    ]
    VERSION_LIST: List[Tuple[str, str, int]] = [
        ("Ver", "version", 6),
        ("Document ID", "id", 26),
        ("Created", "created", 20),
        ("Configurations", "configs", 15),
    ]
    REPAIR_COLLECTION_LIST: List[Tuple[str, str, int]] = [
        ("Collection Name", "name", 35),
        ("Duplicate Versions", "duplicates", 18),
        ("Total Versions", "total", 14),
    ]
    REPAIR_CONFIG_LIST: List[Tuple[str, str, int]] = [
        ("Configuration Name", "name", 40),
        ("Duplicate Collections", "duplicates", 20),
        ("Total Collections", "total", 18),
    ]
    DIFF_TABLE: List[Tuple[str, Optional[int]]] = [("", 2), ("Path", None), ("Left Value", None), ("Right Value", None)]


class ErrorMessage:
    LOADING_CONFIGURATIONS = "Error loading configurations: {error}"
    LOADING_COLLECTIONS = "Error loading collections: {error}"
    LOADING_VERSIONS = "Error loading versions: {error}"
    LOADING_DOCUMENT = "Error loading document: {error}"
    NO_CONFIGURATION_SELECTED = "No configuration selected"
    NO_COLLECTION_SELECTED = "No collection selected"
    NO_DOCUMENT_SELECTED = "No document selected"
    NO_DOCUMENT_LOADED = "No document loaded"
    DOCUMENT_NOT_FOUND = "Document not found"
    ASSIGN_CONFIG_FAILED = "Failed to assign configuration"
    ASSIGN_CONFIG_ERROR = "Error assigning configuration: {error}"
    EMPTY_CONFIG_NAME = "Configuration name cannot be empty"
    INVALID_CONFIG_PATTERN = "Configuration name should follow pattern: <SystemName>_v<number>"


class StatusMessage:
    ITEMS_FILTERED = "Showing {filtered} of {total} {item_type} (filtered: '{filter_text}')"
    ITEMS_TOTAL = "{total} {item_type}"
    VERSIONS_WITH_CURRENT = "{total} versions | Current: v{version}"
    VERSIONS_TOTAL = "{total} versions"
    COLLECTIONS_STATUS = "{total} collections | {deleted} deleted (hidden: {hidden})"
    CONFIGS_STATUS = "Showing {filtered} of {total} configs | Filter: '{filter_text}'"
    CONFIGS_TOTAL = "{total} configurations available"


CONFIG_NAME_PATTERN = "_v"
SYSTEM_DATABASES = frozenset({"admin", "config", "local"})


class TraceColumnWidth:
    TIME = 13
    SEV = 4
    SOURCE = 20

    @classmethod
    def get_table_columns(cls) -> list:
        return [("Time", cls.TIME), ("Sev", cls.SEV), ("Source", cls.SOURCE), ("Message", None)]
