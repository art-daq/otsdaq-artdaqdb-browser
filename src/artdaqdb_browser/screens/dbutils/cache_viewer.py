"""
File: cache_viewer.py
Purpose: Cache viewer screen.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: CacheViewerScreen, format_size, format_timestamp
Complexity: Medium | Lines: 276
"""

from datetime import datetime
from typing import List, Dict, Any
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Static, DataTable
from textual.containers import Vertical
from ..base import DataTableScreen
from ...constants import WidgetID
from ...trace import trace


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_timestamp(ts: float) -> str:
    if ts is None:
        return "N/A"
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "Invalid"


class CacheViewerScreen(DataTableScreen):
    TABLE_ID = WidgetID.CACHE_TABLE
    FOCUSABLE_CONTROLS = [WidgetID.CACHE_TABLE]
    SECONDARY_ACTIONS = [
        ("c", "clear_cache", "Clear"),
        ("p", "purge_expired", "Purge"),
        ("Del", "delete_entry", "Delete"),
    ]
    BINDINGS = [
        *DataTableScreen.BINDINGS,
        Binding("c", "clear_cache", "Clear", show=False, priority=True),
        Binding("p", "purge_expired", "Purge", show=False, priority=True),
        Binding("delete", "delete_entry", "Delete", show=False, priority=True),
    ]

    def __init__(self):
        super().__init__()
        self.entries: List[Dict[str, Any]] = []

    def compose_content(self) -> ComposeResult:
        with Vertical(classes="screen-header"):
            yield Static("Cache Viewer", classes="screen-title")
        yield Static("", id=WidgetID.CACHE_SUMMARY, classes="cache-summary")
        yield DataTable(id=self.TABLE_ID)
        yield Static("", classes="status-bar", id=WidgetID.STATUS_BAR)

    def on_mount(self) -> None:
        trace.info("CacheViewerScreen mounted", tags=["screen", "lifecycle"])
        table = self.get_table()
        table.cursor_type = "row"
        table.zebra_stripes = self.app.config.tables.zebra_stripes
        table.add_column("Cache Key", key="key", width=45)
        table.add_column("Type", key="type", width=15)
        table.add_column("Size", key="size", width=10)
        table.add_column("Created", key="created", width=20)
        table.add_column("Status", key="status", width=12)
        self.load_entries()
        self.focus_first_control()

    def load_entries(self) -> None:
        trace.debug("Loading cache entries", tags=["screen", "cache", "query"])
        cache = self.app.cache
        if cache is None:
            self.entries = []
            summary = self.query_one(f"#{WidgetID.CACHE_SUMMARY}", Static)
            summary.update("Cache is disabled in configuration")
            self.update_table()
            self.update_status()
            return
        self.entries = cache.get_entries_info()
        stats = cache.get_stats()
        total_size = cache.get_total_size()
        summary = self.query_one(f"#{WidgetID.CACHE_SUMMARY}", Static)
        summary.update(
            f"Cache Directory: {stats.get('directory', 'N/A')} | Entries: {stats.get('size', 0)} | Total Size: {format_size(total_size)} | Hits: {stats.get('hits', 0)} | Misses: {stats.get('misses', 0)}"
        )
        self.update_table()
        self.update_status()

    def update_table(self) -> None:
        table = self.get_table()
        table.clear()
        sorted_entries = sorted(self.entries, key=lambda e: e.get("key", ""))
        for entry in sorted_entries:
            key = entry.get("key", "unknown")
            value_type = entry.get("type", "unknown")
            size = format_size(entry.get("size_bytes", 0))
            created = format_timestamp(entry.get("created_at"))
            if entry.get("is_expired"):
                status = "Expired"
            elif entry.get("type") == "error":
                status = "Corrupted"
            else:
                status = "Valid"
            table.add_row(key, value_type, size, created, status, key=entry.get("file_name", key))

    def update_status(self) -> None:
        status = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        total = len(self.entries)
        expired = sum((1 for e in self.entries if e.get("is_expired")))
        corrupted = sum((1 for e in self.entries if e.get("type") == "error"))
        parts = [f"{total} cache entries"]
        if expired > 0:
            parts.append(f"{expired} expired")
        if corrupted > 0:
            parts.append(f"{corrupted} corrupted")
        parts.append("r=Refresh | c=Clear | p=Purge | Del=Delete")
        status.update(" | ".join(parts))

    def refresh_data(self) -> None:
        trace.debug("Refreshing cache view", tags=["screen", "cache", "refresh"])
        self.load_entries()
        self.notify("Cache view refreshed", severity="information")

    def action_refresh_data(self) -> None:
        self.refresh_data()

    def action_clear_cache(self) -> None:
        if self.app.cache is None:
            self.notify("Cache is disabled", severity="warning")
            return
        trace.debug("Clearing all cache", tags=["screen", "cache", "mutation"])
        if self.app.cache.clear():
            trace.info(
                "Cache cleared - popping intermediate screens",
                tags=["screen", "cache", "navigation"],
                reason="Force data reload after cache clear",
            )
            self.notify("Cache cleared successfully", severity="information")
            while len(self.app.screen_stack) > 2:
                self.app.pop_screen()
            self.load_entries()
        else:
            self.notify("Failed to clear cache", severity="error")

    def action_purge_expired(self) -> None:
        if self.app.cache is None:
            self.notify("Cache is disabled", severity="warning")
            return
        trace.debug("Purging expired entries", tags=["screen", "cache"])
        expired_count = sum((1 for e in self.entries if e.get("is_expired")))
        if self.app.cache.purge():
            self.notify(f"Purged {expired_count} expired entries", severity="information")
            self.load_entries()
        else:
            self.notify("Failed to purge expired entries", severity="error")

    def action_delete_entry(self) -> None:
        if self.app.cache is None:
            self.notify("Cache is disabled", severity="warning")
            return
        table = self.get_table()
        if table.cursor_row is None:
            return
        sorted_entries = sorted(self.entries, key=lambda e: e.get("key", ""))
        if table.cursor_row >= len(sorted_entries):
            return
        entry = sorted_entries[table.cursor_row]
        key = entry.get("key", "")
        trace.debug("Deleting cache entry", tags=["screen", "cache"], key=key)
        if self.app.cache.delete(key):
            self.notify(f"Deleted: {key}", severity="information")
            self.load_entries()
        else:
            self.notify(f"Failed to delete: {key}", severity="error")

    def action_go_back(self) -> None:
        trace.info(
            "Returning from CacheViewerScreen",
            tags=["screen", "navigation"],
            from_screen="CacheViewerScreen",
            reason="User pressed back (escape/h/left)",
        )
        self.app.pop_screen()
