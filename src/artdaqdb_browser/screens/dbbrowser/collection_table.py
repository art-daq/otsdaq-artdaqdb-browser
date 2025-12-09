"""
File: collection_table.py
Purpose: Collection table screen - shows collections in a configuration.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: CollectionTableScreen
Complexity: Medium | Lines: 232
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Static
from textual.containers import Vertical
from ..base import FilterableTableScreen, StateBasedDataMixin
from ...widgets import FilterInput, fuzzy_match
from ...utils import format_datetime
from ...constants import WidgetID, ScreenName, TableColumns, DocumentStatus, ErrorMessage
from ...trace import trace


class CollectionTableScreen(StateBasedDataMixin, FilterableTableScreen):
    TABLE_ID = WidgetID.COLLECTION_TABLE
    FOCUSABLE_CONTROLS = [WidgetID.COLLECTION_TABLE, WidgetID.FILTER_INPUT]
    STATE_ATTRIBUTE = "current_configuration"
    BACKEND_METHOD = "get_documents_by_configuration_summary"
    NO_SELECTION_MESSAGE = ErrorMessage.NO_CONFIGURATION_SELECTED
    LOAD_ERROR_MESSAGE = ErrorMessage.LOADING_COLLECTIONS
    TRACE_NAME = "collection_table"
    TITLE_WIDGET_ID = WidgetID.CONFIG_TITLE
    TITLE_PREFIX = "Configuration: "
    SECONDARY_ACTIONS = [
        ("slash", "focus_filter", "Filter"),
        ("c", "clear_filter", "Clear"),
        ("d", "toggle_deleted", "DelTgl"),
    ]
    BINDINGS = [*FilterableTableScreen.BINDINGS, Binding("d", "toggle_deleted", "DelTgl", show=False, priority=True)]

    def __init__(self):
        super().__init__()
        self.documents = []
        self.show_deleted = True

    def compose_content(self) -> ComposeResult:
        with Vertical(classes="screen-header"):
            yield Static("", classes="screen-title", id=WidgetID.CONFIG_TITLE)
        yield FilterInput(placeholder="Filter collections...", id=WidgetID.FILTER_INPUT)
        yield DataTable(id=self.TABLE_ID)
        yield Static("", classes="status-bar", id=WidgetID.STATUS_BAR)

    def on_mount(self) -> None:
        trace.info("CollectionTableScreen mounted", tags=["screen", "lifecycle"])
        self.show_deleted = self.app.config.ui.show_deleted
        self.setup_table(TableColumns.COLLECTION_TABLE)
        self.load_data()
        self.focus_first_control()

    def on_screen_resume(self) -> None:
        trace.debug("CollectionTableScreen resuming", tags=["screen", "lifecycle"])
        super().on_screen_resume()

    def get_visible_documents(self):
        docs = self.documents
        analyzer = self.app.state.analyzer
        config_name = self.app.state.navigation.current_configuration
        docs = analyzer.filter_documents_by_config(docs, config_name)
        if not self.show_deleted:
            docs = [d for d in docs if not d.is_deleted]
        if self.filter_text:
            docs = [d for d in docs if fuzzy_match(self.filter_text, d.collection.lower())]
        return docs

    def apply_filters(self) -> None:
        self.filtered_items = self.get_visible_documents()
        self.update_table()
        self.update_status()

    def update_table(self) -> None:
        table = self.get_table()
        table.clear()
        current_collection = self.app.state.navigation.current_collection
        current_version = self.app.state.navigation.current_version
        current_row_index = None
        for i, doc in enumerate(self.filtered_items):
            is_current = doc.collection == current_collection and doc.version == current_version
            collection_str = f"★ {doc.collection}" if is_current else doc.collection
            if is_current:
                current_row_index = i
            status = DocumentStatus.DELETED if doc.is_deleted else DocumentStatus.ACTIVE
            table.add_row(collection_str, doc.version, format_datetime(doc.created), status, key=doc.id)
        if current_row_index is not None:
            row_to_select = current_row_index

            def _move_cursor():
                table.move_cursor(row=row_to_select)

            self.call_after_refresh(_move_cursor)

    def update_status(self) -> None:
        status = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        total = len(self.documents)
        visible = len(self.filtered_items)
        deleted = sum((1 for doc in self.documents if doc.is_deleted))
        hidden = "on" if not self.show_deleted else "off"
        parts = [f"{visible}/{total} collections"]
        if self.filter_text:
            parts.append(f"filter: '{self.filter_text}'")
        parts.append(f"deleted: {deleted} (hide: {hidden})")
        suffix = self.app.state.analyzer.get_status_suffix()
        status.update(" | ".join(parts) + suffix)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key:
            doc_id = str(event.row_key.value)
            doc = next((d for d in self.filtered_items if d.id == doc_id), None)
            if doc:
                trace.info(
                    "Navigating to VersionListScreen",
                    tags=["screen", "navigation"],
                    from_screen="CollectionTableScreen",
                    to_screen="VERSION_LIST",
                    reason="User selected collection row",
                    collection=doc.collection,
                    version=doc.version,
                )
                self.app.state.navigate_to_collection(doc.collection, from_config=True)
                self.app.state.navigate_to_version(doc.version)
                self.app.push_screen(ScreenName.VERSION_LIST)

    def action_toggle_deleted(self) -> None:
        trace.debug("action_toggle_deleted called", tags=["screen", "action"], show_deleted_before=self.show_deleted)
        self.show_deleted = not self.show_deleted
        self.apply_filters()
        try:
            self.notify(f"Deleted documents: {('shown' if self.show_deleted else 'hidden')}")
        except Exception:
            pass

    def action_select_row(self) -> None:
        table = self.get_table()
        if table.cursor_row is not None and self.filtered_items:
            if table.cursor_row < len(self.filtered_items):
                doc = self.filtered_items[table.cursor_row]
                trace.info(
                    "Navigating to VersionListScreen",
                    tags=["screen", "navigation"],
                    from_screen="CollectionTableScreen",
                    to_screen="VERSION_LIST",
                    reason="User pressed enter/forward on collection",
                    collection=doc.collection,
                    version=doc.version,
                )
                self.app.state.navigate_to_collection(doc.collection, from_config=True)
                self.app.state.navigate_to_version(doc.version)
                self.app.push_screen(ScreenName.VERSION_LIST)

    def action_go_forward(self) -> None:
        self.action_select_row()
