"""
File: version_list.py
Purpose: Version list screen with lazy loading.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: VersionListScreen
Complexity: High | Lines: 505
"""

from typing import List, Optional
from textual.app import ComposeResult
from textual.widgets import DataTable, Static
from textual.binding import Binding
from textual.containers import Vertical
from textual.worker import Worker
from ..base import FilterableTableScreen
from ...widgets import FilterInput, fuzzy_match
from ...models import VersionSummary
from ...utils import format_datetime
from ...constants import WidgetID, ScreenName, TableColumns, ErrorMessage
from ...trace import trace


class VersionListScreen(FilterableTableScreen):
    TABLE_ID = WidgetID.VERSION_TABLE
    FOCUSABLE_CONTROLS = [WidgetID.VERSION_TABLE, WidgetID.FILTER_INPUT]
    SECONDARY_ACTIONS = [
        ("slash", "focus_filter", "Filter"),
        ("c", "clear_filter", "Clear"),
        ("v", "view_document", "View"),
        ("w", "diff_with_next", "Diff"),
    ]
    BINDINGS = [
        *FilterableTableScreen.BINDINGS,
        Binding("enter", "view_document", "View", show=False),
        Binding("v", "view_document", "View", show=False, priority=True),
        Binding("w", "diff_with_next", "Diff", show=False, priority=True),
    ]

    def __init__(self):
        super().__init__()
        self.documents: List[VersionSummary] = []
        self.filter_text = ""
        self._loading = False
        self._collection_name: Optional[str] = None

    def compose_content(self) -> ComposeResult:
        with Vertical(classes="screen-header"):
            yield Static("", classes="screen-title", id=WidgetID.COLLECTION_TITLE)
        yield FilterInput(placeholder="Filter versions...", id=WidgetID.FILTER_INPUT)
        yield DataTable(id=self.TABLE_ID)
        yield Static("", classes="status-bar", id=WidgetID.STATUS_BAR)

    def on_mount(self) -> None:
        trace.info("VersionListScreen mounted", tags=["screen", "lifecycle"])
        self.setup_table(TableColumns.VERSION_LIST)
        self._collection_name = self.app.state.navigation.current_collection
        if self._collection_name:
            self._update_title(self._collection_name)
            self._start_lazy_load()
        else:
            self.notify(ErrorMessage.NO_COLLECTION_SELECTED, severity="warning")
            self._update_status("No collection selected")
        self.focus_first_control()

    def on_screen_resume(self) -> None:
        if hasattr(self, "_skip_resume_reload") and self._skip_resume_reload:
            trace.debug(
                "VersionListScreen skipping reload (flag set by subclass)",
                tags=["screen", "lifecycle", "refresh"],
                screen_id=id(self),
                screen_class=self.__class__.__name__,
            )
            self._skip_resume_reload = False
            return
        self._apply_key_panel_visibility()
        self._update_footer()
        trace.debug(
            "VersionListScreen resuming - reloading data",
            tags=["screen", "lifecycle", "refresh"],
            screen_id=id(self),
            screen_class=self.__class__.__name__,
        )
        new_collection = self.app.state.navigation.current_collection
        if new_collection != self._collection_name:
            self._collection_name = new_collection
            if self._collection_name:
                self._update_title(self._collection_name)
        if self._collection_name:
            self._start_lazy_load()

    def refresh_data(self) -> None:
        if self._collection_name:
            self._start_lazy_load()

    def _update_title(self, collection_name: str) -> None:
        title = self.query_one(f"#{WidgetID.COLLECTION_TITLE}", Static)
        title.update(f"Collection: {collection_name}")

    def _update_status(self, status: str) -> None:
        status_widget = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        status_widget.update(status)

    def _start_lazy_load(self) -> None:
        if self._loading:
            return
        self._loading = True
        self._update_status(f"Loading versions for '{self._collection_name}'...")
        self.documents = []
        self.filtered_items = []
        table = self.get_table()
        table.clear()
        trace.debug(
            "Starting lazy load of version summaries", tags=["screen", "query"], collection=self._collection_name
        )
        self.run_worker(self._fetch_versions(), name="fetch_versions", exclusive=True)

    async def _fetch_versions(self) -> List[VersionSummary]:
        if not self._collection_name:
            return []
        try:
            versions = self.app.backend.get_document_versions_summary(self._collection_name)
            trace.debug(
                "Version summaries fetched",
                tags=["screen", "query"],
                count=len(versions),
                collection=self._collection_name,
            )
            return versions
        except Exception as e:
            trace.error(
                "Failed to fetch version summaries",
                tags=["screen", "error"],
                exception=e,
                collection=self._collection_name,
            )
            raise

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name != "fetch_versions":
            return
        self._loading = False
        if event.state.name == "SUCCESS":
            self.documents = event.worker.result or []
            self.apply_filters()
            trace.debug(
                "Version list loaded successfully", tags=["screen", "query"], document_count=len(self.documents)
            )
        elif event.state.name == "ERROR":
            error_msg = str(event.worker.error) if event.worker.error else "Unknown error"
            self._update_status(f"Error: {error_msg}")
            self.notify(ErrorMessage.LOADING_VERSIONS.format(error=error_msg), severity="error")

    def get_sorted_documents(self, docs=None):
        if docs is None:
            docs = self.documents
        sort_order = self.app.config.tables.default_sort_order
        reverse = sort_order == "desc"
        return sorted(docs, key=lambda d: int(d.version) if d.version.isdigit() else 0, reverse=reverse)

    def get_filtered_documents(self):
        docs = self.documents
        analyzer = self.app.state.analyzer
        collection_name = self._collection_name
        config_name = self.app.state.navigation.current_configuration
        docs = analyzer.filter_versions(docs, collection_name, config_name)
        if self.filter_text:
            docs = [d for d in docs if fuzzy_match(self.filter_text, d.version)]
        return docs

    def apply_filters(self) -> None:
        self.filtered_items = self.get_sorted_documents(self.get_filtered_documents())
        self.update_table()
        self.update_status()

    def update_table(self) -> None:
        table = self.get_table()
        table.clear()
        current_version = self.app.state.navigation.current_version
        current_row_index = None
        for i, doc in enumerate(self.filtered_items):
            is_current = doc.version == current_version
            version_str = f"★ {doc.version}" if is_current else doc.version
            if is_current:
                current_row_index = i
            table.add_row(version_str, doc.id, format_datetime(doc.created), str(doc.config_count), key=doc.id)
        if current_row_index is not None:
            row_to_select = current_row_index

            def _move_cursor():
                table.move_cursor(row=row_to_select)

            self.call_after_refresh(_move_cursor)

    def update_status(self) -> None:
        total = len(self.documents)
        visible = len(self.filtered_items)
        current_version = self.app.state.navigation.current_version
        parts = [f"{visible}/{total} versions"]
        if self.filter_text:
            parts.append(f"filter: '{self.filter_text}'")
        if current_version:
            parts.append(f"current: v{current_version}")
        suffix = self.app.state.analyzer.get_status_suffix()
        self._update_status(" | ".join(parts) + suffix)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if not event.row_key:
            return
        document_id = str(event.row_key.value)
        trace.info(
            "Navigating to DocumentViewScreen",
            tags=["screen", "navigation"],
            from_screen="VersionListScreen",
            to_screen="DOCUMENT_VIEW",
            reason="User selected version row",
            document_id=document_id,
            collection=self._collection_name,
        )
        self.app.state.navigate_to_document(document_id)
        self.app.push_screen(ScreenName.DOCUMENT_VIEW)

    def action_view_document(self) -> None:
        trace.debug("action_view_document called", tags=["screen", "action"])
        table = self.get_table()
        if table.cursor_row is None or not self.filtered_items:
            try:
                self.notify("No document selected", severity="warning")
            except Exception:
                pass
            return
        if table.cursor_row >= len(self.filtered_items):
            try:
                self.notify("No document selected", severity="warning")
            except Exception:
                pass
            return
        document_id = self.filtered_items[table.cursor_row].id
        trace.info(
            "Navigating to DocumentViewScreen",
            tags=["screen", "navigation"],
            from_screen="VersionListScreen",
            to_screen="DOCUMENT_VIEW",
            reason="User pressed view (v/enter/forward)",
            document_id=document_id,
            collection=self._collection_name,
        )
        self.app.state.navigate_to_document(document_id)
        self.app.push_screen(ScreenName.DOCUMENT_VIEW)

    def action_go_forward(self) -> None:
        self.action_view_document()

    def action_refresh_data(self) -> None:
        trace.debug("Refresh action triggered for version list", tags=["screen", "event"])
        if self._collection_name:
            self._start_lazy_load()

    def action_diff_with_next(self) -> None:
        trace.debug("action_diff_with_next called", tags=["screen", "action"])
        table = self.get_table()
        if table.cursor_row is None or not self.filtered_items:
            self.notify("No document selected", severity="warning")
            return
        cursor_row = table.cursor_row
        if cursor_row >= len(self.filtered_items):
            self.notify("No document selected", severity="warning")
            return
        if cursor_row + 1 >= len(self.filtered_items):
            self.notify("No document below to compare with", severity="warning")
            return
        left_doc_id = self.filtered_items[cursor_row].id
        right_doc_id = self.filtered_items[cursor_row + 1].id
        trace.info(
            "Opening diff for adjacent document versions",
            tags=["screen", "event", "diff"],
            left_id=left_doc_id,
            right_id=right_doc_id,
            collection=self._collection_name,
        )
        try:
            trace.debug(
                "Loading left document for diff",
                tags=["screen", "diff", "query"],
                document_id=left_doc_id,
                collection=self._collection_name,
            )
            left_doc = self.app.backend.get_document_by_id_direct(left_doc_id, self._collection_name)
            trace.debug(
                "Loading right document for diff",
                tags=["screen", "diff", "query"],
                document_id=right_doc_id,
                collection=self._collection_name,
            )
            right_doc = self.app.backend.get_document_by_id_direct(right_doc_id, self._collection_name)
            if not left_doc:
                trace.error(
                    "Left document not found for diff",
                    tags=["screen", "diff", "error"],
                    document_id=left_doc_id,
                    collection=self._collection_name,
                )
                self.notify("Failed to load left document for comparison", severity="error")
                return
            if not right_doc:
                trace.error(
                    "Right document not found for diff",
                    tags=["screen", "diff", "error"],
                    document_id=right_doc_id,
                    collection=self._collection_name,
                )
                self.notify("Failed to load right document for comparison", severity="error")
                return
            trace.debug(
                "Documents loaded successfully, converting to dict",
                tags=["screen", "diff"],
                left_id=left_doc_id,
                right_id=right_doc_id,
            )
            left_dict = left_doc.model_dump(by_alias=True)
            right_dict = right_doc.model_dump(by_alias=True)
            trace.debug(
                "Documents converted to dict, creating diff screen",
                tags=["screen", "diff"],
                left_keys=len(left_dict),
                right_keys=len(right_dict),
            )
            from ..dbdoctor.json_diff_merge import JSONDiffMergeScreen

            trace.info(
                "Navigating to JSONDiffMergeScreen",
                tags=["screen", "navigation"],
                from_screen="VersionListScreen",
                to_screen="JSON_DIFF_MERGE",
                reason="User pressed diff (w) to compare adjacent versions",
                left_id=left_doc_id,
                right_id=right_doc_id,
            )
            diff_screen = JSONDiffMergeScreen(left_doc=left_dict, right_doc=right_dict)
            self.app.push_screen(diff_screen)
            trace.debug("Diff screen pushed successfully", tags=["screen", "diff", "navigation"])
        except Exception as e:
            trace.error(
                "Failed to load documents for diff comparison",
                tags=["screen", "error", "diff"],
                exception=e,
                left_id=left_doc_id,
                right_id=right_doc_id,
                collection=self._collection_name,
            )
            self.notify(f"Error loading documents: {e}", severity="error")
