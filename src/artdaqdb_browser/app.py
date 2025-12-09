"""
File: app.py
Purpose: Main application class for OTS Browser.
Category: Utility
Author: ArtdaqDB Browser Team
Depends: textual
Exports: OTSBrowserApp
Complexity: High | Lines: 508
"""

from pathlib import Path
from typing import Optional
from textual.app import App
from textual.binding import Binding
from .data import create_backend, DataBackend, CachedBackend
from .state import AppState
from .cache import CacheManager
from .config import ConfigLoader
from .constants import ScreenName
from .trace import init_trace_log, trace
from .screens import (
    HomeScreen,
    ConfigurationListScreen,
    CollectionTableScreen,
    VersionListScreen,
    DocumentViewScreen,
    CollectionBrowserScreen,
    HelpScreen,
    TraceViewerScreen,
    DatabaseBrowserScreen,
    DatabaseUtilitiesScreen,
    ServerStatsScreen,
    DatabaseStatsScreen,
    CacheViewerScreen,
    RecreateIndexesScreen,
    BackupScreen,
    RestoreScreen,
    ConfigEditorScreen,
    DatabaseDoctorScreen,
    RepairCollectionListScreen,
    RepairConfigurationListScreen,
    JSONDiffMergeScreen,
)


class OTSBrowserApp(App):
    TITLE = "OTS Configuration Browser"
    ENABLE_COMMAND_PALETTE = False
    key_panel_visible: bool = True
    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True, show=False),
        Binding("question_mark", "help", "Help", show=False),
        Binding("ctrl+r", "refresh", "Refresh", show=False),
        Binding("ctrl+k", "toggle_key_panel", "Toggle Keys", show=False),
        Binding("ctrl+shift+t", "toggle_trace_viewer", "Trace Log", show=False),
        Binding("ctrl+shift+x", "cycle_theme", "Cycle Theme", show=False),
    ]
    CSS_PATH = "styles/app.tcss"
    SCREENS = {
        ScreenName.HOME: HomeScreen,
        ScreenName.CONFIG_LIST: ConfigurationListScreen,
        ScreenName.COLLECTION_TABLE: CollectionTableScreen,
        ScreenName.VERSION_LIST: VersionListScreen,
        ScreenName.DOCUMENT_VIEW: DocumentViewScreen,
        ScreenName.COLLECTION_BROWSER: CollectionBrowserScreen,
        ScreenName.HELP: HelpScreen,
        ScreenName.TRACE_VIEWER: TraceViewerScreen,
        ScreenName.DB_BROWSER: DatabaseBrowserScreen,
        ScreenName.DB_UTILITIES: DatabaseUtilitiesScreen,
        ScreenName.SERVER_STATS: ServerStatsScreen,
        ScreenName.DATABASE_STATS: DatabaseStatsScreen,
        ScreenName.CACHE_VIEWER: CacheViewerScreen,
        ScreenName.RECREATE_INDEXES: RecreateIndexesScreen,
        ScreenName.DB_BACKUP: BackupScreen,
        ScreenName.DB_RESTORE: RestoreScreen,
        ScreenName.CONFIG_EDITOR: ConfigEditorScreen,
        ScreenName.DB_DOCTOR: DatabaseDoctorScreen,
        ScreenName.REPAIR_COLLECTION: RepairCollectionListScreen,
        ScreenName.REPAIR_CONFIGURATION: RepairConfigurationListScreen,
        ScreenName.JSON_DIFF_MERGE: JSONDiffMergeScreen,
    }

    def __init__(
        self,
        data_source: str,
        backend_type: Optional[str] = None,
        cache_enabled: bool = True,
        cache_dir: Optional[Path] = None,
    ):
        super().__init__()
        init_trace_log()
        trace.info(
            "OTS Browser application initializing",
            tags=["lifecycle"],
            data_source=data_source,
            backend_type=backend_type or "auto",
            cache_enabled=cache_enabled,
        )
        config_loader = ConfigLoader()
        (self.config, config_warnings) = config_loader.load()
        for warning in config_warnings:
            trace.warn("Configuration warning", tags=["config", "lifecycle"], message=warning)
        trace.info(
            "Configuration loaded",
            tags=["config", "lifecycle"],
            theme=self.config.ui.theme,
            config_file=str(config_loader.config_path) if config_loader.config_path else "defaults",
        )
        self.title = self.config.app.name
        self.data_source = data_source
        self.backend_type = backend_type
        self.cache_enabled = cache_enabled
        self.key_panel_visible = self.config.ui.show_key_hints
        trace.debug(
            "Creating data backend",
            tags=["database", "lifecycle"],
            data_source=data_source,
            backend_type=backend_type or "auto",
        )
        try:
            raw_backend: DataBackend = create_backend(data_source, backend_type)
            trace.info(
                "Data backend initialized successfully",
                tags=["database", "lifecycle"],
                backend_class=raw_backend.__class__.__name__,
            )
        except Exception as e:
            trace.error(
                "Failed to initialize data backend",
                tags=["database", "lifecycle", "error"],
                exception=e,
                data_source=data_source,
            )
            self.exit(message=f"Error initializing backend: {e}")
            raise
        cache_config = self.config.cache
        effective_cache_enabled = cache_enabled and cache_config.enabled
        effective_cache_dir = cache_dir or cache_config.get_directory_path()
        self.cache: Optional[CacheManager] = None
        if effective_cache_enabled:
            trace.debug(
                "Initializing cache manager",
                tags=["cache", "lifecycle"],
                cache_dir=str(effective_cache_dir),
                ttl=cache_config.ttl,
                max_entries=cache_config.max_entries,
                max_size_mb=cache_config.max_size_mb,
                auto_purge=cache_config.auto_purge,
            )
            try:
                self.cache = CacheManager(
                    cache_dir=effective_cache_dir,
                    ttl=cache_config.ttl,
                    max_entries=cache_config.max_entries,
                    max_size_mb=cache_config.max_size_mb,
                    auto_purge=cache_config.auto_purge,
                )
                self.backend: DataBackend = CachedBackend(raw_backend, self.cache)
                trace.info(
                    "Cache layer initialized and backend wrapped",
                    tags=["cache", "lifecycle"],
                    cache_dir=str(self.cache.cache_dir),
                )
            except Exception as e:
                trace.warn(
                    "Cache initialization failed, using raw backend",
                    tags=["cache", "lifecycle", "fallback"],
                    error=str(e),
                )
                self.backend = raw_backend
        else:
            trace.debug("Cache disabled by configuration", tags=["cache", "lifecycle"])
            self.backend = raw_backend
        self.state = AppState()
        self.state.data_source = data_source
        self.state.backend_type = backend_type
        self.state.cache_enabled = effective_cache_enabled and self.cache is not None
        trace.info(
            "Application initialization complete",
            tags=["lifecycle"],
            backend_type=self.backend.__class__.__name__,
            cache_enabled=self.state.cache_enabled,
        )

    def on_mount(self) -> None:
        theme_name = self.config.ui.theme
        if theme_name in self.available_themes:
            self.theme = theme_name
            trace.info("Theme applied from configuration", tags=["theme", "lifecycle"], theme=theme_name)
        else:
            trace.warn(
                "Configured theme not available, using default",
                tags=["theme", "lifecycle"],
                configured_theme=theme_name,
                available_themes=list(self.available_themes.keys()),
            )
        if isinstance(self.backend, CachedBackend):
            self.run_worker(self._warm_cache, exclusive=False)
        trace.info(
            "Navigating to HomeScreen",
            tags=["screen", "navigation"],
            from_screen="Application",
            to_screen="HOME",
            reason="Application startup - initial screen",
        )
        self.push_screen(ScreenName.HOME)

    async def _warm_cache(self) -> None:
        if isinstance(self.backend, CachedBackend):
            self.backend.warm_cache()

    def action_quit(self) -> None:
        trace.info("Application shutdown initiated", tags=["lifecycle"])
        if self.cache:
            trace.debug("Closing cache manager", tags=["cache", "lifecycle"])
            self.cache.close()
        trace.info("Application exiting", tags=["lifecycle"])
        self.exit()

    def action_help(self) -> None:
        trace.info(
            "Navigating to HelpScreen",
            tags=["screen", "navigation"],
            from_screen=self.screen.__class__.__name__,
            to_screen="HELP",
            reason="User pressed ? for help",
        )
        self.push_screen(ScreenName.HELP)

    def action_refresh(self) -> None:
        current_screen_name = self.screen.__class__.__name__
        trace.info("Manual refresh triggered (Ctrl+R)", tags=["event", "cache", "refresh"], screen=current_screen_name)
        if isinstance(self.backend, CachedBackend):
            trace.debug("Clearing all cache entries", tags=["cache", "mutation"])
            self.backend.clear_cache()
        current_screen = self.screen
        if hasattr(current_screen, "refresh_data") and callable(getattr(current_screen, "refresh_data")):
            trace.debug(
                "Calling refresh_data() on current screen",
                tags=["screen", "lifecycle", "refresh"],
                screen=current_screen_name,
            )
            current_screen.refresh_data()
        elif hasattr(current_screen, "load_data"):
            trace.debug(
                "Calling load_data on current screen (fallback)",
                tags=["screen", "lifecycle"],
                screen=current_screen_name,
            )
            current_screen.load_data()
        elif hasattr(current_screen, "load_document"):
            trace.debug(
                "Calling load_document on current screen (fallback)",
                tags=["screen", "lifecycle"],
                screen=current_screen_name,
            )
            current_screen.load_document()
        elif hasattr(current_screen, "update_stats"):
            trace.debug(
                "Calling update_stats on current screen (fallback)",
                tags=["screen", "lifecycle"],
                screen=current_screen_name,
            )
            current_screen.update_stats()
        self.notify("Data refreshed (cache cleared)", timeout=2)

    def action_cache_management(self) -> None:
        if not self.cache:
            trace.debug("Cache management requested but cache is disabled", tags=["cache", "event"])
            self.notify("Cache is disabled", severity="warning")
            return
        stats = self.cache.get_stats()
        hit_rate = 0
        total = stats.get("hits", 0) + stats.get("misses", 0)
        if total > 0:
            hit_rate = stats.get("hits", 0) / total * 100
        trace.debug(
            "Displaying cache statistics",
            tags=["cache", "event"],
            entries=stats.get("size", 0),
            hits=stats.get("hits", 0),
            misses=stats.get("misses", 0),
            hit_rate=round(hit_rate, 1),
        )
        cache_info = f"Cache Statistics:\n  Entries: {stats.get('size', 0)}\n  Hits: {stats.get('hits', 0)} | Misses: {stats.get('misses', 0)}\n  Hit Rate: {hit_rate:.1f}%\n  Directory: {stats.get('directory', 'N/A')}"
        self.notify(cache_info, timeout=5)

    def action_cache_clear(self) -> None:
        if isinstance(self.backend, CachedBackend):
            trace.info("Clearing all cache entries via backend", tags=["cache", "mutation"])
            self.backend.clear_cache()
            self.notify("Cache cleared", timeout=2)
        elif self.cache:
            trace.info("Clearing all cache entries via manager", tags=["cache", "mutation"])
            self.cache.clear()
            self.notify("Cache cleared", timeout=2)
        else:
            trace.debug("Cache clear requested but cache is disabled", tags=["cache", "event"])
            self.notify("Cache is disabled", severity="warning")

    def action_cache_purge(self) -> None:
        if self.cache:
            trace.info("Purging expired cache entries", tags=["cache", "mutation"])
            self.cache.purge()
            self.notify("Expired cache entries purged", timeout=2)
        else:
            trace.debug("Cache purge requested but cache is disabled", tags=["cache", "event"])
            self.notify("Cache is disabled", severity="warning")

    def action_toggle_key_panel(self) -> None:
        from .widgets import KeyPanel

        self.key_panel_visible = not self.key_panel_visible
        trace.debug("KeyPanel visibility toggled", tags=["widget", "event"], visible=self.key_panel_visible)
        try:
            key_panels = self.screen.query(KeyPanel)
            for panel in key_panels:
                if self.key_panel_visible:
                    panel.remove_class("hidden")
                else:
                    panel.add_class("hidden")
        except Exception:
            pass

    def apply_key_panel_visibility(self) -> None:
        from .widgets import KeyPanel

        try:
            key_panels = self.screen.query(KeyPanel)
            for panel in key_panels:
                if self.key_panel_visible:
                    panel.remove_class("hidden")
                else:
                    panel.add_class("hidden")
        except Exception:
            pass

    def action_toggle_trace_viewer(self) -> None:
        if isinstance(self.screen, TraceViewerScreen):
            trace.info(
                "Returning from TraceViewerScreen",
                tags=["screen", "navigation"],
                from_screen="TraceViewerScreen",
                reason="User toggled trace viewer closed (Ctrl+Shift+T)",
            )
            self.pop_screen()
        else:
            trace.info(
                "Navigating to TraceViewerScreen",
                tags=["screen", "navigation"],
                from_screen=self.screen.__class__.__name__,
                to_screen="TRACE_VIEWER",
                reason="User toggled trace viewer open (Ctrl+Shift+T)",
            )
            self.push_screen(ScreenName.TRACE_VIEWER)

    def action_cycle_theme(self) -> None:
        theme_names = sorted(self.available_themes.keys())
        try:
            current_idx = theme_names.index(self.theme)
        except ValueError:
            current_idx = -1
        next_idx = (current_idx + 1) % len(theme_names)
        next_theme = theme_names[next_idx]
        trace.info("Cycling theme", tags=["theme", "event"], from_theme=self.theme, to_theme=next_theme)
        self.theme = next_theme
        self.notify(f"Theme: {next_theme}", timeout=2)
