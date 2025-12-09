"""
File: config_list.py
Purpose: Configuration list screen.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: ConfigurationListScreen
Complexity: Low | Lines: 123
"""

from textual.app import ComposeResult
from textual.widgets import DataTable, Static
from textual.containers import Vertical
from ..base import FilterableTableScreen, LoadableDataMixin
from ...widgets import FilterInput
from ...utils import format_datetime
from ...constants import WidgetID, ScreenName, TableColumns
from ...trace import trace


class ConfigurationListScreen(LoadableDataMixin, FilterableTableScreen):
    TABLE_ID = WidgetID.CONFIG_TABLE
    DATA_TYPE = "configurations"
    SECONDARY_ACTIONS = [("slash", "focus_filter", "Filter"), ("c", "clear_filter", "Clear")]

    def compose_content(self) -> ComposeResult:
        with Vertical(classes="screen-header"):
            yield Static("Configurations (Reverse Chronological)", classes="screen-title")
        yield FilterInput(placeholder="Filter configurations...", id=WidgetID.FILTER_INPUT)
        yield DataTable(id=self.TABLE_ID)
        yield Static("", classes="status-bar", id=WidgetID.STATUS_BAR)

    def on_mount(self) -> None:
        trace.info("ConfigurationListScreen mounted", tags=["screen", "lifecycle"])
        self.setup_table(TableColumns.CONFIGURATION_LIST)
        self.load_data()
        self.focus_first_control()

    def fetch_data(self):
        trace.debug("Fetching configuration list from backend", tags=["screen", "query"])
        return self.app.backend.get_configuration_info_optimized()

    def on_data_loaded(self) -> None:
        trace.debug("Configuration list loaded", tags=["screen", "query"], config_count=len(self.all_items))
        self.update_table()
        self.update_status()

    def on_data_error(self, error: Exception) -> None:
        trace.error("Failed to load configuration list", tags=["screen", "error"], exception=error)
        super().on_data_error(error)

    def update_table(self) -> None:
        table = self.get_table()
        table.clear()
        for config in self.filtered_items:
            table.add_row(
                config.name, str(config.collection_count), format_datetime(config.last_assigned), key=config.name
            )

    def update_status(self) -> None:
        self.update_status_with_filter("configurations")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.navigate_on_row_select(
            event,
            state_method="navigate_to_configuration",
            next_screen=ScreenName.COLLECTION_TABLE,
            trace_name="config_list",
        )

    def action_go_forward(self) -> None:
        table = self.get_table()
        if table.cursor_row is not None and self.filtered_items:
            if table.cursor_row < len(self.filtered_items):
                config_name = self.filtered_items[table.cursor_row].name
                trace.info(
                    "Navigating to CollectionTableScreen",
                    tags=["screen", "navigation"],
                    from_screen="ConfigurationListScreen",
                    to_screen="COLLECTION_TABLE",
                    reason="User pressed forward (l/right) on configuration",
                    config_name=config_name,
                )
                self.app.state.navigate_to_configuration(config_name)
                self.app.push_screen(ScreenName.COLLECTION_TABLE)
