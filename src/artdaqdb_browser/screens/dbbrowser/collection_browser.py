"""
File: collection_browser.py
Purpose: Collection browser screen - Workflow 2.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: CollectionBrowserScreen
Complexity: Low | Lines: 124
"""

from textual.app import ComposeResult
from textual.widgets import DataTable, Static
from textual.containers import Vertical
from ..base import FilterableTableScreen, LoadableDataMixin
from ...widgets import FilterInput
from ...utils import format_datetime
from ...constants import WidgetID, ScreenName, TableColumns
from ...trace import trace


class CollectionBrowserScreen(LoadableDataMixin, FilterableTableScreen):
    TABLE_ID = WidgetID.COLLECTION_TABLE
    DATA_TYPE = "collections"
    SECONDARY_ACTIONS = [("slash", "focus_filter", "Filter"), ("c", "clear_filter", "Clear")]

    def compose_content(self) -> ComposeResult:
        with Vertical(classes="screen-header"):
            yield Static("Collections", classes="screen-title")
        yield FilterInput(placeholder="Filter collections...", id=WidgetID.FILTER_INPUT)
        yield DataTable(id=self.TABLE_ID)
        yield Static("", classes="status-bar", id=WidgetID.STATUS_BAR)

    def on_mount(self) -> None:
        trace.info("CollectionBrowserScreen mounted", tags=["screen", "lifecycle"])
        self.setup_table(TableColumns.COLLECTION_BROWSER)
        self.load_data()
        self.focus_first_control()

    def fetch_data(self):
        trace.debug("Fetching collection list from backend", tags=["screen", "query"])
        return self.app.backend.get_collection_info_optimized()

    def on_data_loaded(self) -> None:
        trace.debug("Collection list loaded", tags=["screen", "query"], collection_count=len(self.all_items))
        self.update_table()
        self.update_status()

    def on_data_error(self, error: Exception) -> None:
        trace.error("Failed to load collection list", tags=["screen", "error"], exception=error)
        super().on_data_error(error)

    def update_table(self) -> None:
        table = self.get_table()
        table.clear()
        for coll in self.filtered_items:
            table.add_row(
                coll.name,
                str(coll.version_count),
                f"v{coll.latest_version}" if coll.latest_version else "N/A",
                format_datetime(coll.last_updated),
                key=coll.name,
            )

    def update_status(self) -> None:
        self.update_status_with_filter("collections")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.navigate_on_row_select(
            event,
            state_method="navigate_to_collection",
            next_screen=ScreenName.VERSION_LIST,
            trace_name="collection_browser",
            from_config=False,
        )

    def action_go_forward(self) -> None:
        table = self.get_table()
        if table.cursor_row is not None and self.filtered_items:
            if table.cursor_row < len(self.filtered_items):
                collection_name = self.filtered_items[table.cursor_row].name
                trace.info(
                    "Navigating to VersionListScreen",
                    tags=["screen", "navigation"],
                    from_screen="CollectionBrowserScreen",
                    to_screen="VERSION_LIST",
                    reason="User pressed forward (l/right) on collection",
                    collection_name=collection_name,
                )
                self.app.state.navigate_to_collection(collection_name, from_config=False)
                self.app.push_screen(ScreenName.VERSION_LIST)
