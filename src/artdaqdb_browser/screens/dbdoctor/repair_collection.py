"""
File: repair_collection.py
Purpose: Repair Collection screen - lists collections with duplicate versions.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: BrokenCollectionInfo, RepairCollectionListScreen, DeleteGlobalTrashModal, DeleteSingleTrashModal, GlobalTrashListScreen
Complexity: High | Lines: 915
"""

from typing import List, Optional
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Static, Button, Label
from textual.containers import Vertical, Container
from textual.worker import Worker
from textual.screen import ModalScreen
from dataclasses import dataclass
from ..base import FilterableTableScreen
from ...widgets import FilterInput, fuzzy_match
from ...constants import WidgetID, TableColumns, ScreenName
from ...data.analyzers import DuplicateVersionAnalyzer, GlobalTrashDuplicateVersionAnalyzer, GlobalTrashItem
from ...trace import trace
from .json_diff_merge import DiffableVersionListScreen


@dataclass
class BrokenCollectionInfo:
    name: str
    duplicate_count: int
    total_versions: int


class RepairCollectionListScreen(FilterableTableScreen):
    TABLE_ID = WidgetID.REPAIR_TABLE
    FOCUSABLE_CONTROLS = [WidgetID.REPAIR_TABLE, WidgetID.FILTER_INPUT]
    SECONDARY_ACTIONS = [
        ("slash", "focus_filter", "Filter"),
        ("c", "clear_filter", "Clear"),
        ("ctrl+t", "toggle_global_trash", "TrashTgl"),
    ]
    BINDINGS = [Binding("ctrl+t", "toggle_global_trash", "TrashTgl", show=False, priority=True)]

    def __init__(self):
        super().__init__()
        self.analyzer = DuplicateVersionAnalyzer()
        self.all_items: List[BrokenCollectionInfo] = []
        self.filtered_items: List[BrokenCollectionInfo] = []
        self._loading = False

    def compose_content(self) -> ComposeResult:
        with Vertical(classes="screen-header"):
            yield Static("Repair Collection: Duplicate Versions", classes="screen-title")
        yield FilterInput(placeholder="Filter collections...", id=WidgetID.FILTER_INPUT)
        yield DataTable(id=self.TABLE_ID)
        yield Static("", classes="status-bar", id=WidgetID.STATUS_BAR)

    def on_mount(self) -> None:
        trace.info("RepairCollectionListScreen mounted", tags=["screen", "lifecycle"])
        self.setup_table(TableColumns.REPAIR_COLLECTION_LIST)
        self._start_analysis()
        self.focus_first_control()

    def on_screen_resume(self) -> None:
        if self.analyzer.get_analysis() is None:
            trace.info("Analyzer cache invalidated, re-running analysis", tags=["screen", "lifecycle", "refresh"])
            self._start_analysis()

    def _start_analysis(self) -> None:
        if self._loading:
            return
        self._loading = True
        self._update_status("Analyzing collections for duplicate versions...")
        self.all_items = []
        self.filtered_items = []
        table = self.get_table()
        table.clear()
        trace.info("Starting duplicate version analysis", tags=["screen", "collection", "lifecycle"])
        self.run_worker(self._analyze_collections(), name="analyze_collections", exclusive=True)

    async def _analyze_collections(self) -> List[BrokenCollectionInfo]:
        try:
            excluded_collections = self.app.config.dbdoctor.exclude.collections
            result = self.analyzer.analyze(self.app.backend, excluded_collections=excluded_collections)
            broken_collections = []
            for coll_name, dup_versions in result.collections_with_duplicate_versions.items():
                total_duplicates = sum(
                    (len(doc_ids) for doc_ids in result.duplicate_version_details.get(coll_name, {}).values())
                )
                broken_collections.append(
                    BrokenCollectionInfo(
                        name=coll_name, duplicate_count=len(dup_versions), total_versions=total_duplicates
                    )
                )
            trace.debug(
                "Analysis complete", tags=["screen", "collection", "lifecycle"], broken_count=len(broken_collections)
            )
            return broken_collections
        except Exception as e:
            trace.error("Collection analysis failed", tags=["database", "error"], exception=e)
            raise

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name != "analyze_collections":
            return
        self._loading = False
        if event.state.name == "SUCCESS":
            self.all_items = event.worker.result or []
            self.apply_filters()
            if not self.all_items:
                self._update_status("No collections with duplicate versions found!")
                self.notify("All collections have unique versions", severity="information")
        elif event.state.name == "ERROR":
            error_msg = str(event.worker.error) if event.worker.error else "Unknown error"
            self._update_status(f"Error: {error_msg}")
            self.notify(f"Analysis failed: {error_msg}", severity="error")

    def get_filtered_items(self) -> List[BrokenCollectionInfo]:
        if not self.filter_text:
            return self.all_items
        return [c for c in self.all_items if fuzzy_match(self.filter_text, c.name.lower())]

    def apply_filters(self) -> None:
        self.filtered_items = self.get_filtered_items()
        self.update_table()
        self.update_status()

    def update_table(self) -> None:
        table = self.get_table()
        table.clear()
        sorted_items = sorted(self.filtered_items, key=lambda x: x.duplicate_count, reverse=True)
        for item in sorted_items:
            table.add_row(item.name, str(item.duplicate_count), str(item.total_versions), key=item.name)

    def update_status(self) -> None:
        total = len(self.all_items)
        visible = len(self.filtered_items)
        parts = [f"{visible}/{total} collections with issues"]
        if self.filter_text:
            parts.append(f"filter: '{self.filter_text}'")
        parts.append("[REPAIR MODE]")
        self._update_status(" | ".join(parts))

    def _update_status(self, status: str) -> None:
        status_widget = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        status_widget.update(status)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if not event.row_key:
            return
        collection_name = str(event.row_key.value)
        self._navigate_to_collection(collection_name)

    def _navigate_to_collection(self, collection_name: str) -> None:
        trace.info(
            "Navigating to DiffableVersionListScreen",
            tags=["screen", "navigation"],
            from_screen="RepairCollectionListScreen",
            to_screen="DiffableVersionListScreen",
            reason="User selected collection with duplicate versions",
            collection_name=collection_name,
        )
        self.app.state.set_analyzer(self.analyzer)
        self.app.state.navigate_to_collection(collection_name)
        self.app.push_screen(DiffableVersionListScreen())

    def action_go_forward(self) -> None:
        table = self.get_table()
        if table.cursor_row is not None and self.filtered_items:
            if table.cursor_row < len(self.filtered_items):
                sorted_items = sorted(self.filtered_items, key=lambda x: x.duplicate_count, reverse=True)
                collection_name = sorted_items[table.cursor_row].name
                self._navigate_to_collection(collection_name)

    def action_toggle_global_trash(self) -> None:
        if not self.all_items:
            self.notify("No collections with duplicates to show trash for", severity="warning")
            return
        trace.info(
            "Navigating to GlobalTrashListScreen",
            tags=["screen", "navigation"],
            from_screen="RepairCollectionListScreen",
            to_screen="GlobalTrashListScreen",
            reason="User pressed Ctrl+T for global trash view",
            collection_count=len(self.all_items),
        )
        global_analyzer = GlobalTrashDuplicateVersionAnalyzer(self.analyzer)
        self.app.push_screen(GlobalTrashListScreen(global_analyzer))

    def action_refresh_data(self) -> None:
        trace.info("Refreshing with cache invalidation", tags=["screen", "refresh", "cache"])
        if hasattr(self.app, "backend") and hasattr(self.app.backend, "cache"):
            cache = self.app.backend.cache
            cache.delete("collections_list")
            cache.delete("collections_list_optimized")
            cache.delete("collection_info")
            cache.delete("collection_info_optimized")
            cache.delete("all_documents")
            for item in self.all_items:
                cache.delete(f"collection_docs:{item.name}")
                cache.delete(f"versions:{item.name}")
                cache.delete(f"versions_summary:{item.name}")
            trace.debug(
                "Cache invalidated for collections", tags=["cache", "mutation"], collection_count=len(self.all_items)
            )
        self.analyzer = DuplicateVersionAnalyzer()
        self._start_analysis()
        self.notify("Refreshing (cache invalidated)...")


class DeleteGlobalTrashModal(ModalScreen[bool]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("enter", "confirm", "Confirm", priority=True),
        Binding("y", "confirm", "Yes", show=False),
        Binding("n", "cancel", "No", show=False),
    ]

    def __init__(self, document_count: int, collection_count: int):
        super().__init__()
        self.document_count = document_count
        self.collection_count = collection_count

    def compose(self):
        with Container(id="delete-confirm-dialog"):
            yield Label("Delete All Global Trash", classes="modal-title")
            yield Label(
                f"Are you sure you want to delete ALL {self.document_count} trash documents across {self.collection_count} collections?\n\nThis action cannot be undone!",
                classes="modal-message",
            )
            yield Label("Press [Y/Enter] to confirm, [N/Esc] to cancel", classes="modal-hint")
            with Container(classes="modal-buttons"):
                yield Button("Delete All", variant="error", id="btn-delete")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-delete":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class DeleteSingleTrashModal(ModalScreen[bool]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("enter", "confirm", "Confirm", priority=True),
        Binding("y", "confirm", "Yes", show=False),
        Binding("n", "cancel", "No", show=False),
    ]

    def __init__(self, doc_id: str, collection: str, version: str):
        super().__init__()
        self.doc_id = doc_id
        self.collection = collection
        self.version = version

    def compose(self):
        with Container(id="delete-confirm-dialog"):
            yield Label("Delete Trash Document", classes="modal-title")
            yield Label(
                f"Delete this document?\n\nCollection: {self.collection}\nVersion: {self.version}\nID: {self.doc_id[:16]}...",
                classes="modal-message",
            )
            yield Label("Press [Y/Enter] to confirm, [N/Esc] to cancel", classes="modal-hint")
            with Container(classes="modal-buttons"):
                yield Button("Delete", variant="error", id="btn-delete")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-delete":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class GlobalTrashListScreen(FilterableTableScreen):
    TABLE_ID = WidgetID.REPAIR_TABLE
    FOCUSABLE_CONTROLS = [WidgetID.REPAIR_TABLE, WidgetID.FILTER_INPUT]
    SECONDARY_ACTIONS = [
        ("slash", "focus_filter", "Filter"),
        ("c", "clear_filter", "Clear"),
        ("v", "view_document", "View"),
        ("d", "delete_selected", "Del"),
        ("ctrl+d", "delete_all_trash", "DelAll"),
        ("ctrl+t", "go_back", "Back"),
    ]
    BINDINGS = [
        Binding("enter", "view_document", "View", show=False),
        Binding("v", "view_document", "View", show=False, priority=True),
        Binding("d", "delete_selected", "Del", show=False, priority=True),
        Binding("ctrl+d", "delete_all_trash", "DelAll", show=False, priority=True),
        Binding("ctrl+t", "go_back", "Back", show=False, priority=True),
    ]

    def __init__(self, global_analyzer: GlobalTrashDuplicateVersionAnalyzer):
        super().__init__()
        self.global_analyzer = global_analyzer
        self.all_items: List[GlobalTrashItem] = []
        self.filtered_items: List[GlobalTrashItem] = []
        self._loading = False

    def compose_content(self) -> ComposeResult:
        with Vertical(classes="screen-header"):
            yield Static("Global Trash: Documents to Delete", classes="screen-title")
        yield FilterInput(placeholder="Filter by collection or version...", id=WidgetID.FILTER_INPUT)
        yield DataTable(id=self.TABLE_ID)
        yield Static("", classes="status-bar", id=WidgetID.STATUS_BAR)

    def on_mount(self) -> None:
        trace.info("GlobalTrashListScreen mounted", tags=["screen", "lifecycle"])
        table = self.get_table()
        table.cursor_type = "row"
        columns_config = self.app.config.tables.columns
        table.add_column("Collection", width=columns_config.collection_name)
        table.add_column("Version", width=columns_config.version)
        table.add_column("Created", width=columns_config.timestamp)
        table.add_column("Document ID", width=columns_config.document_id)
        self._start_computation()
        self.focus_first_control()

    def _start_computation(self) -> None:
        if self._loading:
            return
        self._loading = True
        self._update_status("Computing global trash list...")
        trace.info("Starting global trash computation", tags=["screen", "global-trash", "lifecycle"])
        self.run_worker(self._compute_trash(), name="compute_global_trash", exclusive=True)

    async def _compute_trash(self) -> List[GlobalTrashItem]:
        try:
            return self.global_analyzer.compute_global_trash(self.app.backend)
        except Exception as e:
            trace.error("Global trash computation failed", tags=["database", "error"], exception=e)
            raise

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name != "compute_global_trash":
            return
        self._loading = False
        if event.state.name == "SUCCESS":
            self.all_items = event.worker.result or []
            self.apply_filters()
            if not self.all_items:
                self._update_status("No trash documents found!")
                self.notify("No documents to delete", severity="information")
        elif event.state.name == "ERROR":
            error_msg = str(event.worker.error) if event.worker.error else "Unknown error"
            self._update_status(f"Error: {error_msg}")
            self.notify(f"Computation failed: {error_msg}", severity="error")

    def get_filtered_items(self) -> List[GlobalTrashItem]:
        if not self.filter_text:
            return self.all_items
        filter_lower = self.filter_text.lower()
        return [
            item
            for item in self.all_items
            if fuzzy_match(filter_lower, item.collection.lower()) or fuzzy_match(filter_lower, item.version.lower())
        ]

    def apply_filters(self) -> None:
        self.filtered_items = self.get_filtered_items()
        self.update_table()
        self.update_status()

    def update_table(self) -> None:
        table = self.get_table()
        table.clear()
        for item in self.filtered_items:
            created_display = item.created[:19] if item.created else "N/A"
            table.add_row(item.collection, item.version, created_display, item.id, key=item.id)

    def update_status(self) -> None:
        total = len(self.all_items)
        visible = len(self.filtered_items)
        collections = set((item.collection for item in self.filtered_items))
        parts = [f"{visible}/{total} trash documents", f"{len(collections)} collections"]
        if self.filter_text:
            parts.append(f"filter: '{self.filter_text}'")
        parts.append("[GLOBAL TRASH MODE]")
        self._update_status(" | ".join(parts))

    def _update_status(self, status: str) -> None:
        status_widget = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        status_widget.update(status)

    def action_view_document(self) -> None:
        table = self.get_table()
        if table.cursor_row is None or not self.filtered_items:
            self.notify("No document selected", severity="warning")
            return
        if table.cursor_row >= len(self.filtered_items):
            self.notify("No document selected", severity="warning")
            return
        item = self.filtered_items[table.cursor_row]
        trace.info(
            "Navigating to DocumentViewScreen",
            tags=["screen", "navigation"],
            from_screen="GlobalTrashListScreen",
            to_screen="DOCUMENT_VIEW",
            reason="User pressed view (v) on trash document",
            document_id=item.id,
            collection=item.collection,
            version=item.version,
        )
        self.app.state.navigate_to_document(item.id)
        self.app.push_screen(ScreenName.DOCUMENT_VIEW)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_view_document()

    def action_go_forward(self) -> None:
        self.action_view_document()

    def _perform_single_hard_delete(self, item) -> None:
        if item.is_readonly_or_deleted():
            trace.warn(
                "Cannot delete protected document",
                tags=["repair", "validation", "global-trash"],
                document_id=item.id,
                is_readonly=item.is_readonly,
                is_deleted=item.is_deleted,
            )
            status = "readonly" if item.is_readonly else "already deleted"
            self.notify(f"Cannot delete {status} document: {item.collection}", severity="error")
            return
        try:
            success = self.app.backend.delete_document(item.id, soft_delete=False)
            if success:
                trace.info("Trash document deleted", tags=["document", "mutation", "global-trash"], document_id=item.id)
                self.notify(f"Deleted {item.collection} v{item.version}")
                self.all_items = [i for i in self.all_items if i.id != item.id]
                self.apply_filters()
            else:
                trace.error(
                    "Failed to delete trash document",
                    tags=["document", "mutation", "global-trash", "error"],
                    document_id=item.id,
                )
                self.notify("Delete failed", severity="error")
        except Exception as e:
            trace.error("Error deleting trash document", tags=["database", "error"], exception=e, document_id=item.id)
            self.notify(f"Error: {e}", severity="error")

    def action_delete_selected(self) -> None:
        table = self.get_table()
        if table.cursor_row is None or not self.filtered_items:
            self.notify("No document selected", severity="warning")
            return
        if table.cursor_row >= len(self.filtered_items):
            self.notify("No document selected", severity="warning")
            return
        item = self.filtered_items[table.cursor_row]
        trace.info(
            "Delete single trash requested",
            tags=["document", "mutation", "global-trash"],
            document_id=item.id,
            collection=item.collection,
            version=item.version,
        )
        confirm_required = self.app.config.documents.confirm_hard_delete
        if not confirm_required:
            trace.debug(
                "Skipping delete confirmation (confirm_hard_delete=False)",
                tags=["document", "mutation", "global-trash"],
                document_id=item.id,
            )
            self._perform_single_hard_delete(item)
            return
        modal = DeleteSingleTrashModal(item.id, item.collection, item.version)
        trace.info(
            "Opening DeleteSingleTrashModal",
            tags=["screen", "navigation"],
            from_screen="GlobalTrashListScreen",
            to_screen="DeleteSingleTrashModal",
            reason="User pressed delete on single trash document",
            document_id=item.id,
        )

        def handle_result(confirmed: bool) -> None:
            if not confirmed:
                self.notify("Delete cancelled")
                return
            self._perform_single_hard_delete(item)

        self.app.push_screen(modal, handle_result)

    def _perform_bulk_hard_delete(self, items_to_delete) -> None:
        document_count = len(items_to_delete)
        trace.info(
            "Deleting all global trash using batch API",
            tags=["document", "mutation", "global-trash", "bulk"],
            document_count=document_count,
        )
        if hasattr(self.app.backend, "batch_delete_documents"):
            doc_ids = [item.id for item in items_to_delete]
            result = self.app.backend.batch_delete_documents(doc_ids, soft_delete=False, skip_protected=True)
            deleted_ids = set(doc_ids) - set(result.failed_ids) - set(result.skipped_ids)
            self.all_items = [i for i in self.all_items if i.id not in deleted_ids]
            trace.info(
                "Global trash bulk delete completed",
                tags=["document", "mutation", "global-trash", "bulk"],
                result=str(result),
            )
            if result.all_succeeded and result.skipped_count == 0:
                self.notify(f"Deleted {result.success_count} documents", severity="information")
            elif result.skipped_count > 0:
                self.notify(
                    f"Deleted {result.success_count}, skipped {result.skipped_count} protected", severity="warning"
                )
            else:
                self.notify(f"Deleted {result.success_count}, failed {result.failed_count}", severity="warning")
            if result.success_count > 0:
                self._invalidate_analyzer()
        else:
            deleted_count = 0
            failed_count = 0
            skipped_count = 0
            for item in items_to_delete:
                if item.is_readonly_or_deleted():
                    skipped_count += 1
                    continue
                try:
                    success = self.app.backend.delete_document(item.id, soft_delete=False)
                    if success:
                        deleted_count += 1
                        self.all_items = [i for i in self.all_items if i.id != item.id]
                    else:
                        failed_count += 1
                except Exception:
                    failed_count += 1
            if failed_count == 0 and skipped_count == 0:
                self.notify(f"Deleted {deleted_count} documents", severity="information")
            elif skipped_count > 0:
                self.notify(f"Deleted {deleted_count}, skipped {skipped_count} protected", severity="warning")
            else:
                self.notify(f"Deleted {deleted_count}, failed {failed_count}", severity="warning")
            if deleted_count > 0:
                self._invalidate_analyzer()
        self.apply_filters()

    def action_delete_all_trash(self) -> None:
        if not self.filtered_items:
            self.notify("No trash documents to delete", severity="warning")
            return
        collections = set((item.collection for item in self.filtered_items))
        document_count = len(self.filtered_items)
        items_to_delete = list(self.filtered_items)
        trace.info(
            "Delete all global trash requested",
            tags=["document", "mutation", "global-trash", "bulk"],
            document_count=document_count,
            collection_count=len(collections),
        )
        confirm_required = self.app.config.documents.confirm_hard_delete
        if not confirm_required:
            trace.debug(
                "Skipping bulk delete confirmation (confirm_hard_delete=False)",
                tags=["document", "mutation", "global-trash", "bulk"],
                document_count=document_count,
            )
            self._perform_bulk_hard_delete(items_to_delete)
            return
        modal = DeleteGlobalTrashModal(document_count, len(collections))
        trace.info(
            "Opening DeleteGlobalTrashModal",
            tags=["screen", "navigation"],
            from_screen="GlobalTrashListScreen",
            to_screen="DeleteGlobalTrashModal",
            reason="User requested delete all global trash",
            document_count=document_count,
            collection_count=len(collections),
        )

        def handle_result(confirmed: bool) -> None:
            if not confirmed:
                trace.debug("Delete all cancelled", tags=["document", "mutation", "global-trash", "bulk"])
                self.notify("Delete all cancelled")
                return
            self._perform_bulk_hard_delete(items_to_delete)

        self.app.push_screen(modal, handle_result)

    def _invalidate_analyzer(self) -> None:
        if hasattr(self.global_analyzer, "invalidate"):
            self.global_analyzer.invalidate()
            trace.debug(
                "Global trash analyzer cache invalidated after deletion",
                tags=["analyzer", "cache", "invalidate", "global-trash"],
            )

    def action_refresh_data(self) -> None:
        trace.info(
            "Refreshing global trash with cache invalidation", tags=["screen", "refresh", "cache", "global-trash"]
        )
        if hasattr(self.app, "backend") and hasattr(self.app.backend, "cache"):
            cache = self.app.backend.cache
            cache.delete("collections_list")
            cache.delete("collections_list_optimized")
            cache.delete("collection_info")
            cache.delete("collection_info_optimized")
            cache.delete("all_documents")
            collections = set((item.collection for item in self.all_items))
            for coll_name in collections:
                cache.delete(f"collection_docs:{coll_name}")
                cache.delete(f"versions:{coll_name}")
                cache.delete(f"versions_summary:{coll_name}")
            trace.debug(
                "Cache invalidated for global trash collections",
                tags=["cache", "mutation"],
                collection_count=len(collections),
            )
        self._invalidate_analyzer()
        self._start_computation()
        self.notify("Refreshing (cache invalidated)...")
