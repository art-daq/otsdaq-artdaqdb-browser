"""
File: __init__.py
Purpose: TUI screens for OTS browser.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: None
Exports: None
Complexity: Low | Lines: 89
"""

from .base import (
    BaseScreen,
    DataTableScreen,
    FilterableTableScreen,
    LoadableDataMixin,
    StateBasedDataMixin,
    NAVIGATION_BINDINGS,
    BACK_BINDINGS,
    SCROLL_BINDINGS,
    FOCUS_BINDINGS,
)
from .home import HomeScreen
from .help_screen import HelpScreen
from .db_browser import (
    DatabaseBrowserScreen,
    ConfigurationListScreen,
    CollectionTableScreen,
    CollectionBrowserScreen,
    VersionListScreen,
    AssignConfigurationModal,
)
from .db_utils import (
    DatabaseUtilitiesScreen,
    ServerStatsScreen,
    DatabaseStatsScreen,
    CacheViewerScreen,
    RecreateIndexesScreen,
    BackupScreen,
    RestoreScreen,
    DirectoryBrowserModal,
)
from .viewers import TraceViewerScreen, DocumentViewScreen, ConfigEditorScreen
from .db_doctor import (
    DatabaseDoctorScreen,
    RepairCollectionListScreen,
    RepairConfigurationListScreen,
    JSONDiffMergeScreen,
)

__all__ = [
    "BaseScreen",
    "DataTableScreen",
    "FilterableTableScreen",
    "LoadableDataMixin",
    "StateBasedDataMixin",
    "NAVIGATION_BINDINGS",
    "BACK_BINDINGS",
    "SCROLL_BINDINGS",
    "FOCUS_BINDINGS",
    "HomeScreen",
    "HelpScreen",
    "DatabaseBrowserScreen",
    "ConfigurationListScreen",
    "CollectionTableScreen",
    "CollectionBrowserScreen",
    "VersionListScreen",
    "AssignConfigurationModal",
    "TraceViewerScreen",
    "DocumentViewScreen",
    "ConfigEditorScreen",
    "DatabaseUtilitiesScreen",
    "ServerStatsScreen",
    "DatabaseStatsScreen",
    "CacheViewerScreen",
    "RecreateIndexesScreen",
    "BackupScreen",
    "RestoreScreen",
    "DirectoryBrowserModal",
    "DatabaseDoctorScreen",
    "RepairCollectionListScreen",
    "RepairConfigurationListScreen",
    "JSONDiffMergeScreen",
]
