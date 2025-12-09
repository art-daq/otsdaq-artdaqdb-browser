"""
File: repair_configuration.py
Purpose: Repair Configuration screen - lists configurations with duplicate c...
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: BrokenConfigurationInfo, RemoveConfigConfirmModal, RemoveAllTrashConfigModal, GlobalRemoveAllTrashConfigModal, DiffableCollectionTableScreen, ...
Complexity: High | Lines: 1448
"""

import asyncio
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass
from textual.app import ComposeResult
from textual.widgets import DataTable, Static, Button, Label
from textual.containers import Vertical, Container
from textual.binding import Binding
from textual.worker import Worker
from textual.screen import ModalScreen
from ..base import FilterableTableScreen
from ..dbbrowser.collection_table import CollectionTableScreen
from ...widgets import FilterInput, fuzzy_match
from ...constants import WidgetID, ScreenName, TableColumns
from ...data.analyzers import (
    AnalysisResult,
    DuplicateCollectionAnalyzer,
    TrashDuplicateCollectionAnalyzer,
    GlobalTrashDuplicateCollectionAnalyzer,
    GlobalTrashConfigItem,
)
from ...trace import trace


@dataclass
class BrokenConfigurationInfo:
    name: str
    duplicate_count: int
    total_collections: int


def get_current_timestamp() -> str:
    now = datetime.now().astimezone()
    return now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + now.strftime("%z")[:3] + ":" + now.strftime("%z")[3:]


class RemoveConfigConfirmModal(ModalScreen):
    BINDINGS = [Binding("escape", "cancel", "Cancel"), Binding("enter", "confirm", "Confirm", priority=True)]

    def __init__(self, doc_id: str, collection: str, version: str, config_name: str):
        super().__init__()
        self.doc_id = doc_id
        self.collection = collection
        self.version = version
        self.config_name = config_name

    def compose(self) -> ComposeResult:
        with Container(classes="modal-dialog"):
            yield Label("Remove Configuration Assignment", classes="modal-title")
            yield Label(
                f"Remove '{self.config_name}' from document?\n\nCollection: {self.collection}\nVersion: {self.version}\nDocument ID: {self.doc_id[:12]}...",
                classes="modal-message",
            )
            with Container(classes="modal-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Remove", variant="error", id="confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)


class RemoveAllTrashConfigModal(ModalScreen):
    BINDINGS = [Binding("escape", "cancel", "Cancel"), Binding("enter", "confirm", "Confirm", priority=True)]

    def __init__(self, count: int, config_name: str):
        super().__init__()
        self.count = count
        self.config_name = config_name

    def compose(self) -> ComposeResult:
        with Container(classes="modal-dialog"):
            yield Label("Remove All Configuration Assignments", classes="modal-title")
            yield Label(
                f"Remove '{self.config_name}' from {self.count} documents?\n\nThis will remove the configuration assignment from all\nduplicate collection documents (keeping oldest only).\n\nThis action cannot be undone.",
                classes="modal-message",
            )
            with Container(classes="modal-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button(f"Remove All ({self.count})", variant="error", id="confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)


class GlobalRemoveAllTrashConfigModal(ModalScreen):
    BINDINGS = [Binding("escape", "cancel", "Cancel"), Binding("enter", "confirm", "Confirm", priority=True)]

    def __init__(self, count: int, config_count: int):
        super().__init__()
        self.count = count
        self.config_count = config_count

    def compose(self) -> ComposeResult:
        with Container(classes="modal-dialog"):
            yield Label("Remove All Configuration Assignments", classes="modal-title")
            yield Label(
                f"Remove configuration assignments from {self.count} documents\nacross {self.config_count} configurations?\n\nThis will remove duplicate configuration assignments from all\ndocuments (keeping oldest document for each collection).\n\nThis action cannot be undone.",
                classes="modal-message",
            )
            with Container(classes="modal-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button(f"Remove All ({self.count})", variant="error", id="confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)


class DiffableCollectionTableScreen(CollectionTableScreen):
    SECONDARY_ACTIONS = [
        ("slash", "focus_filter", "Filter"),
        ("c", "clear_filter", "Clear"),
        ("d", "remove_config", "Remove"),
        ("ctrl+t", "toggle_trash_mode", "TrashTgl"),
        ("ctrl+d", "remove_all_trash", "All"),
        ("t", "toggle_deleted", "DelTgl"),
    ]
    BINDINGS = [
        Binding("enter", "select_row", "Select", show=False),
        Binding("d", "remove_config", "Remove", show=False, priority=True),
        Binding("ctrl+t", "toggle_trash_mode", "TrashTgl", show=False, priority=True),
        Binding("ctrl+d", "remove_all_trash", "All", show=False, priority=True),
        Binding("t", "toggle_deleted", "DelTgl", show=False, priority=True),
    ]

    def __init__(self):
        super().__init__()
        self._trash_mode = False
        self._trash_analyzer: Optional[TrashDuplicateCollectionAnalyzer] = None
        self._skip_next_resume_reload = False

    def load_data(self) -> None:
        if self._skip_next_resume_reload:
            trace.debug("Skipping load_data (in-place update active)", tags=["screen", "lifecycle", "debug"])
            return
        trace.debug("DiffableCollectionTableScreen.load_data proceeding", tags=["screen", "lifecycle", "debug"])
        super().load_data()

    def _clear_skip_flag(self) -> None:
        trace.debug("Clearing skip_next_resume_reload flag", tags=["screen", "lifecycle", "debug"])
        self._skip_next_resume_reload = False

    def _is_trash_mode(self) -> bool:
        return self._trash_mode and self._trash_analyzer is not None

    def _get_source_analyzer(self) -> Optional[DuplicateCollectionAnalyzer]:
        analyzer = self.app.state.get_analyzer()
        if isinstance(analyzer, TrashDuplicateCollectionAnalyzer):
            return analyzer.get_source_analyzer()
        elif isinstance(analyzer, DuplicateCollectionAnalyzer):
            return analyzer
        return None

    def action_toggle_trash_mode(self) -> None:
        source_analyzer = self._get_source_analyzer()
        if not source_analyzer:
            self.notify("No duplicate collection analysis available", severity="warning")
            return
        self._trash_mode = not self._trash_mode
        if self._trash_mode:
            self._trash_analyzer = TrashDuplicateCollectionAnalyzer(source_analyzer)
            self.app.state.set_analyzer(self._trash_analyzer)
            trace.info(
                "Switched to trash mode",
                tags=["repair", "trash"],
                config=self.app.state.navigation.current_configuration,
            )
        else:
            self._trash_analyzer = None
            self.app.state.set_analyzer(source_analyzer)
            trace.info(
                "Switched to duplicate mode",
                tags=["repair", "trash"],
                config=self.app.state.navigation.current_configuration,
            )
        self.load_data()

    def check_action(self, action: str, parameters: tuple) -> Optional[bool]:
        if action in ("remove_config", "remove_all_trash"):
            source_analyzer = self._get_source_analyzer()
            return source_analyzer is not None
        return super().check_action(action, parameters)

    def _perform_remove_config(self, doc, config_name: str) -> None:
        if doc.is_readonly_or_deleted():
            trace.warn(
                "Cannot modify protected document",
                tags=["repair", "validation"],
                document_id=doc.id,
                is_readonly=doc.is_readonly(),
                is_deleted=doc.is_deleted(),
            )
            status = "readonly" if doc.is_readonly() else "deleted"
            self.notify(f"Cannot modify {status} document: {doc.collection}", severity="error")
            return
        timestamp = get_current_timestamp()
        success = self.app.backend.remove_configuration_assignment(doc.id, config_name, timestamp)
        if success:
            trace.info(
                "Configuration assignment removed",
                tags=["repair", "mutation"],
                document_id=doc.id,
                config_name=config_name,
                collection=doc.collection,
            )
            self._skip_next_resume_reload = True
            trace.debug(
                "Set skip_next_resume_reload flag before in-place update",
                tags=["screen", "lifecycle", "debug"],
                documents_before=len(self.documents),
                filtered_before=len(self.filtered_items),
            )
            self.documents = [d for d in self.documents if d.id != doc.id]
            self.filtered_items = [d for d in self.filtered_items if d.id != doc.id]
            trace.debug(
                "Updated documents and filtered_items in-place",
                tags=["screen", "lifecycle", "debug"],
                documents_after=len(self.documents),
                filtered_after=len(self.filtered_items),
            )
            self.update_table()
            self.update_status()
            self._invalidate_analyzer()
            self.notify(f"Removed '{config_name}' from {doc.collection}")
            self.set_timer(0.5, self._clear_skip_flag)
        else:
            self.notify("Failed to remove configuration", severity="error")

    def action_remove_config(self) -> None:
        table = self.get_table()
        if table.cursor_row is None or not self.filtered_items:
            return
        if table.cursor_row >= len(self.filtered_items):
            return
        doc = self.filtered_items[table.cursor_row]
        config_name = self.app.state.navigation.current_configuration
        if not config_name:
            self.notify("No configuration selected", severity="warning")
            return
        confirm_required = self.app.config.documents.soft_delete
        if not confirm_required:
            trace.debug(
                "Skipping remove config confirmation (soft_delete=False)",
                tags=["repair", "mutation"],
                document_id=doc.id,
                config_name=config_name,
            )
            self._perform_remove_config(doc, config_name)
            return
        self.app.push_screen(
            RemoveConfigConfirmModal(doc.id, doc.collection, doc.version, config_name),
            lambda confirmed: self._on_remove_config_confirmed(confirmed, doc, config_name),
        )

    def _on_remove_config_confirmed(self, confirmed: bool, doc, config_name: str) -> None:
        if not confirmed:
            return
        self._perform_remove_config(doc, config_name)

    def _perform_bulk_remove_config(self, docs, config_name: str) -> None:
        timestamp = get_current_timestamp()
        success_count = 0
        trace.info(
            "Bulk remove config using batch API",
            tags=["repair", "mutation", "bulk"],
            config_name=config_name,
            document_count=len(docs),
        )
        if hasattr(self.app.backend, "batch_remove_configurations"):
            items = [(doc.id, config_name) for doc in docs]
            result = self.app.backend.batch_remove_configurations(items, timestamp, skip_protected=True)
            trace.info("Bulk config removal completed", tags=["repair", "mutation", "bulk"], result=str(result))
            success_count = result.success_count
            if result.all_succeeded and result.skipped_count == 0:
                self.notify(f"Removed '{config_name}' from {result.success_count} documents")
            elif result.skipped_count > 0:
                self.notify(
                    f"Removed from {result.success_count}, skipped {result.skipped_count} protected", severity="warning"
                )
            else:
                self.notify(f"Removed from {result.success_count}, failed {result.failed_count}", severity="warning")
        else:
            fail_count = 0
            skipped_count = 0
            for doc in docs:
                if doc.is_readonly_or_deleted():
                    skipped_count += 1
                    continue
                success = self.app.backend.remove_configuration_assignment(doc.id, config_name, timestamp)
                if success:
                    success_count += 1
                else:
                    fail_count += 1
            if success_count > 0 and hasattr(self.app.backend, "clear_cache"):
                self.app.backend.clear_cache()
            if fail_count == 0 and skipped_count == 0:
                self.notify(f"Removed '{config_name}' from {success_count} documents")
            elif skipped_count > 0:
                self.notify(f"Removed from {success_count}, skipped {skipped_count} protected", severity="warning")
            else:
                self.notify(f"Removed from {success_count}, failed {fail_count}", severity="warning")
        self._skip_next_resume_reload = True
        trace.debug(
            "Set skip_next_resume_reload flag before bulk in-place update", tags=["screen", "lifecycle", "debug"]
        )
        self.documents = []
        self.filtered_items = []
        self.update_table()
        self.update_status()
        if success_count > 0:
            self._invalidate_analyzer()
        self.set_timer(0.5, self._clear_skip_flag)

    def action_remove_all_trash(self) -> None:
        if not self._is_trash_mode():
            self.action_toggle_trash_mode()
            if not self._is_trash_mode():
                return
        config_name = self.app.state.navigation.current_configuration
        if not config_name:
            self.notify("No configuration selected", severity="warning")
            return
        trash_count = len(self.filtered_items)
        if trash_count == 0:
            self.notify("No documents to remove configuration from", severity="information")
            return
        docs_to_process = list(self.filtered_items)
        confirm_required = self.app.config.documents.soft_delete
        if not confirm_required:
            trace.debug(
                "Skipping bulk remove config confirmation (soft_delete=False)",
                tags=["repair", "mutation"],
                config_name=config_name,
                document_count=trash_count,
            )
            self._perform_bulk_remove_config(docs_to_process, config_name)
            return
        self.app.push_screen(
            RemoveAllTrashConfigModal(trash_count, config_name),
            lambda confirmed: self._on_remove_all_confirmed(confirmed, docs_to_process, config_name),
        )

    def _on_remove_all_confirmed(self, confirmed: bool, docs, config_name: str) -> None:
        if not confirmed:
            return
        self._perform_bulk_remove_config(docs, config_name)

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
        if self._is_trash_mode():
            parts.append("[TRASH MODE: Remove Config]")
        else:
            suffix = self.app.state.analyzer.get_status_suffix()
            if suffix:
                parts.append(suffix.strip())
        status.update(" | ".join(parts))

    def _invalidate_analyzer(self) -> None:
        from ...data.analyzers import DuplicateCollectionAnalyzer, TrashDuplicateCollectionAnalyzer

        analyzer = self.app.state.analyzer
        if analyzer is None:
            return
        if isinstance(analyzer, TrashDuplicateCollectionAnalyzer):
            source = analyzer.get_source_analyzer()
        elif isinstance(analyzer, DuplicateCollectionAnalyzer):
            source = analyzer
        else:
            return
        if hasattr(source, "invalidate"):
            source.invalidate()
            trace.debug(
                "Analyzer cache invalidated after config removal",
                tags=["analyzer", "cache", "invalidate"],
                config=self.app.state.navigation.current_configuration,
            )

    def action_refresh_data(self) -> None:
        config_name = self.app.state.navigation.current_configuration
        trace.info("Refreshing with cache invalidation", tags=["screen", "refresh", "cache"], config_name=config_name)
        if hasattr(self.app, "backend") and hasattr(self.app.backend, "cache"):
            cache = self.app.backend.cache
            cache.delete("configurations_list")
            cache.delete("configurations_list_optimized")
            cache.delete("configuration_info")
            cache.delete("configuration_info_optimized")
            if config_name:
                cache.delete(f"config_docs:{config_name}")
                cache.delete(f"config_docs_summary:{config_name}")
            trace.debug("Cache invalidated for configuration", tags=["cache", "mutation"], config_name=config_name)
        self._invalidate_analyzer()
        self.load_data()
        self.notify("Refreshing (cache invalidated)...")


class GlobalTrashConfigListScreen(FilterableTableScreen):
    TABLE_ID = WidgetID.GLOBAL_TRASH_TABLE
    FOCUSABLE_CONTROLS = [WidgetID.GLOBAL_TRASH_TABLE, WidgetID.FILTER_INPUT]
    SECONDARY_ACTIONS = [
        ("slash", "focus_filter", "Filter"),
        ("c", "clear_filter", "Clear"),
        ("d", "remove_config", "Remove"),
        ("ctrl+d", "remove_all_trash", "All"),
    ]
    BINDINGS = [
        Binding("escape", "go_back", "Back", priority=True),
        Binding("d", "remove_config", "Remove", show=False, priority=True),
        Binding("ctrl+d", "remove_all_trash", "All", show=False, priority=True),
    ]

    def __init__(self):
        super().__init__()
        self.trash_analyzer: Optional[GlobalTrashDuplicateCollectionAnalyzer] = None
        self.all_items: List[GlobalTrashConfigItem] = []
        self.filtered_items: List[GlobalTrashConfigItem] = []

    def compose_content(self) -> ComposeResult:
        with Vertical(classes="screen-header"):
            yield Static("Global Config Trash: Documents to Unassign", classes="screen-title")
        yield FilterInput(placeholder="Filter by config or collection...", id=WidgetID.FILTER_INPUT)
        yield DataTable(id=self.TABLE_ID)
        yield Static("", classes="status-bar", id=WidgetID.STATUS_BAR)

    def on_mount(self) -> None:
        trace.info("GlobalTrashConfigListScreen mounted", tags=["screen", "lifecycle"])
        table = self.get_table()
        table.add_columns("Configuration", "Collection", "Version", "Created")
        source_analyzer = self.app.state.get_analyzer()
        if isinstance(source_analyzer, DuplicateCollectionAnalyzer):
            self.trash_analyzer = GlobalTrashDuplicateCollectionAnalyzer(source_analyzer)
            all_trash = self.trash_analyzer.compute_global_trash(self.app.backend)
            excluded = set(self.app.config.dbdoctor.exclude.configurations)
            if excluded:
                original_count = len(all_trash)
                self.all_items = [item for item in all_trash if item.config_name not in excluded]
                excluded_count = original_count - len(self.all_items)
                if excluded_count > 0:
                    trace.debug(
                        "Excluded configurations from global trash view",
                        tags=["analyzer", "exclude"],
                        excluded_configs=list(excluded),
                        excluded_items=excluded_count,
                    )
            else:
                self.all_items = all_trash
            self.apply_filters()
        else:
            self._update_status("No duplicate collection analysis available")
        self.focus_first_control()

    def get_filtered_items(self) -> List[GlobalTrashConfigItem]:
        if not self.filter_text:
            return self.all_items
        filter_lower = self.filter_text.lower()
        return [
            item
            for item in self.all_items
            if fuzzy_match(filter_lower, item.config_name.lower()) or fuzzy_match(filter_lower, item.collection.lower())
        ]

    def apply_filters(self) -> None:
        self.filtered_items = self.get_filtered_items()
        self.update_table()
        self.update_status()

    def update_table(self) -> None:
        table = self.get_table()
        table.clear()
        for item in self.filtered_items:
            created_str = item.created[:19] if item.created else ""
            table.add_row(
                item.config_name, item.collection, item.version, created_str, key=f"{item.config_name}:{item.id}"
            )

    def update_status(self) -> None:
        total = len(self.all_items)
        visible = len(self.filtered_items)
        config_names = set((item.config_name for item in self.all_items))
        parts = [f"{visible}/{total} documents"]
        parts.append(f"{len(config_names)} configurations")
        if self.filter_text:
            parts.append(f"filter: '{self.filter_text}'")
        parts.append("[GLOBAL TRASH MODE]")
        self._update_status(" | ".join(parts))

    def _update_status(self, status: str) -> None:
        status_widget = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        status_widget.update(status)

    def action_go_back(self) -> None:
        trace.info(
            "Returning from GlobalTrashConfigListScreen",
            tags=["screen", "navigation"],
            from_screen="GlobalTrashConfigListScreen",
            reason="User pressed back",
        )
        self.app.pop_screen()

    def _perform_remove_config(self, item) -> None:
        if item.is_readonly_or_deleted():
            trace.warn(
                "Cannot modify protected document",
                tags=["repair", "validation", "global-trash"],
                document_id=item.id,
                is_readonly=item.is_readonly,
                is_deleted=item.is_deleted,
            )
            status = "readonly" if item.is_readonly else "deleted"
            self.notify(f"Cannot modify {status} document: {item.collection}", severity="error")
            return
        timestamp = get_current_timestamp()
        success = self.app.backend.remove_configuration_assignment(item.id, item.config_name, timestamp)
        if success:
            trace.info(
                "Configuration assignment removed",
                tags=["repair", "mutation"],
                document_id=item.id,
                config_name=item.config_name,
                collection=item.collection,
            )
            self.notify(f"Removed '{item.config_name}' from {item.collection}")
            self._invalidate_analyzer()
            self.all_items = [i for i in self.all_items if i.id != item.id or i.config_name != item.config_name]
            self.apply_filters()
        else:
            self.notify("Failed to remove configuration", severity="error")

    def action_remove_config(self) -> None:
        table = self.get_table()
        if table.cursor_row is None or not self.filtered_items:
            return
        if table.cursor_row >= len(self.filtered_items):
            return
        item = self.filtered_items[table.cursor_row]
        confirm_required = self.app.config.documents.soft_delete
        if not confirm_required:
            trace.debug(
                "Skipping remove config confirmation (soft_delete=False)",
                tags=["repair", "mutation"],
                document_id=item.id,
                config_name=item.config_name,
            )
            self._perform_remove_config(item)
            return
        self.app.push_screen(
            RemoveConfigConfirmModal(item.id, item.collection, item.version, item.config_name),
            lambda confirmed: self._on_remove_config_confirmed(confirmed, item),
        )

    def _on_remove_config_confirmed(self, confirmed: bool, item) -> None:
        if not confirmed:
            return
        self._perform_remove_config(item)

    def _perform_bulk_remove_config(self, items) -> None:
        timestamp = get_current_timestamp()
        trace.info(
            "Global trash bulk remove config using batch API",
            tags=["repair", "mutation", "bulk", "global-trash"],
            item_count=len(items),
        )
        if hasattr(self.app.backend, "batch_remove_configurations"):
            batch_items = [(item.id, item.config_name) for item in items]
            result = self.app.backend.batch_remove_configurations(batch_items, timestamp, skip_protected=True)
            trace.info(
                "Global trash bulk config removal completed",
                tags=["repair", "mutation", "bulk", "global-trash"],
                result=str(result),
            )
            if result.all_succeeded and result.skipped_count == 0:
                self.notify(f"Removed configuration from {result.success_count} documents")
            elif result.skipped_count > 0:
                self.notify(
                    f"Removed from {result.success_count}, skipped {result.skipped_count} protected", severity="warning"
                )
            else:
                self.notify(f"Removed from {result.success_count}, failed {result.failed_count}", severity="warning")
            if result.success_count > 0:
                self._invalidate_analyzer()
        else:
            success_count = 0
            fail_count = 0
            skipped_count = 0
            for item in items:
                if item.is_readonly_or_deleted():
                    skipped_count += 1
                    continue
                success = self.app.backend.remove_configuration_assignment(item.id, item.config_name, timestamp)
                if success:
                    success_count += 1
                else:
                    fail_count += 1
            if success_count > 0 and hasattr(self.app.backend, "clear_cache"):
                self.app.backend.clear_cache()
            if fail_count == 0 and skipped_count == 0:
                self.notify(f"Removed configuration from {success_count} documents")
            elif skipped_count > 0:
                self.notify(f"Removed from {success_count}, skipped {skipped_count} protected", severity="warning")
            else:
                self.notify(f"Removed from {success_count}, failed {fail_count}", severity="warning")
            if success_count > 0:
                self._invalidate_analyzer()
        self.all_items = []
        self.apply_filters()

    def action_remove_all_trash(self) -> None:
        if not self.all_items:
            self.notify("No documents to process", severity="information")
            return
        items_to_process = list(self.all_items)
        config_names = set((item.config_name for item in items_to_process))
        confirm_required = self.app.config.documents.soft_delete
        if not confirm_required:
            trace.debug(
                "Skipping bulk remove config confirmation (soft_delete=False)",
                tags=["repair", "mutation"],
                document_count=len(items_to_process),
            )
            self._perform_bulk_remove_config(items_to_process)
            return
        self.app.push_screen(
            GlobalRemoveAllTrashConfigModal(len(items_to_process), len(config_names)),
            lambda confirmed: self._on_remove_all_confirmed(confirmed, items_to_process),
        )

    def _on_remove_all_confirmed(self, confirmed: bool, items) -> None:
        if not confirmed:
            return
        self._perform_bulk_remove_config(items)

    def _invalidate_analyzer(self) -> None:
        if hasattr(self.trash_analyzer, "invalidate"):
            self.trash_analyzer.invalidate()
            trace.debug(
                "Global config trash analyzer cache invalidated after removal",
                tags=["analyzer", "cache", "invalidate", "global-trash"],
            )

    def action_refresh_data(self) -> None:
        trace.info(
            "Refreshing global config trash with cache invalidation",
            tags=["screen", "refresh", "cache", "global-trash"],
        )
        if hasattr(self.app, "backend") and hasattr(self.app.backend, "cache"):
            cache = self.app.backend.cache
            cache.delete("configurations_list")
            cache.delete("configurations_list_optimized")
            cache.delete("configuration_info")
            cache.delete("configuration_info_optimized")
            config_names = set((item.config_name for item in self.all_items))
            for config_name in config_names:
                cache.delete(f"config_docs:{config_name}")
                cache.delete(f"config_docs_summary:{config_name}")
            trace.debug(
                "Cache invalidated for global config trash", tags=["cache", "mutation"], config_count=len(config_names)
            )
        self._invalidate_analyzer()
        source_analyzer = self.app.state.get_analyzer()
        if isinstance(source_analyzer, DuplicateCollectionAnalyzer):
            self.trash_analyzer = GlobalTrashDuplicateCollectionAnalyzer(source_analyzer)
            self.all_items = self.trash_analyzer.compute_global_trash(self.app.backend)
            self.apply_filters()
        self.notify("Refreshing (cache invalidated)...")


class RepairConfigurationListScreen(FilterableTableScreen):
    TABLE_ID = WidgetID.REPAIR_TABLE
    FOCUSABLE_CONTROLS = [WidgetID.REPAIR_TABLE, WidgetID.FILTER_INPUT]
    SECONDARY_ACTIONS = [
        ("slash", "focus_filter", "Filter"),
        ("c", "clear_filter", "Clear"),
        ("ctrl+t", "toggle_global_trash", "TrashTgl"),
    ]
    BINDINGS = [
        Binding("escape", "cancel_or_back", "Back/Cancel", priority=True),
        Binding("ctrl+t", "toggle_global_trash", "TrashTgl", show=False, priority=True),
    ]

    def __init__(self):
        super().__init__()
        self.analyzer: Optional[DuplicateCollectionAnalyzer] = None
        self.all_items: List[BrokenConfigurationInfo] = []
        self.filtered_items: List[BrokenConfigurationInfo] = []
        self._loading = False
        self._current_worker: Optional[Worker] = None

    def compose_content(self) -> ComposeResult:
        with Vertical(classes="screen-header"):
            yield Static("Repair Configuration: Duplicate Collections", classes="screen-title")
        yield FilterInput(placeholder="Filter configurations...", id=WidgetID.FILTER_INPUT)
        yield DataTable(id=self.TABLE_ID)
        yield Static("", classes="status-bar", id=WidgetID.STATUS_BAR)

    def on_mount(self) -> None:
        trace.info("RepairConfigurationListScreen mounted", tags=["screen", "lifecycle"])
        self.setup_table(TableColumns.REPAIR_CONFIG_LIST)
        existing_analyzer = self.app.state.get_analyzer()
        if existing_analyzer and isinstance(existing_analyzer, DuplicateCollectionAnalyzer):
            self.analyzer = existing_analyzer
            self._load_from_existing_analyzer()
        else:
            self._start_analysis()
        self.focus_first_control()

    def on_screen_resume(self) -> None:
        if self.analyzer and self.analyzer.get_analysis() is None:
            trace.info("Analyzer cache invalidated, re-running analysis", tags=["screen", "lifecycle", "refresh"])
            self._start_analysis()

    def _load_from_existing_analyzer(self) -> None:
        trace.debug("Using pre-analyzed results", tags=["config"])
        result = self.analyzer.get_analysis() if self.analyzer else None
        if not result:
            self._start_analysis()
            return
        excluded = set(self.app.config.dbdoctor.exclude.configurations)
        broken_configs = []
        for config_name, dup_collections in result.configurations_with_duplicate_collections.items():
            if config_name in excluded:
                trace.debug("Excluding configuration from display", tags=["analyzer", "exclude"], config=config_name)
                continue
            total_duplicates = sum(
                (len(doc_ids) for doc_ids in result.duplicate_collection_details.get(config_name, {}).values())
            )
            broken_configs.append(
                BrokenConfigurationInfo(
                    name=config_name, duplicate_count=len(dup_collections), total_collections=total_duplicates
                )
            )
        self.all_items = broken_configs
        self.apply_filters()
        if not self.all_items:
            self._update_status("No configurations with duplicate collections found!")
            self.notify("All configurations have unique collections", severity="information")

    def _start_analysis(self) -> None:
        if self._loading:
            return
        self._loading = True
        self._update_status("Analyzing configurations... (Press ESC to cancel)")
        self.all_items = []
        self.filtered_items = []
        table = self.get_table()
        table.clear()
        if not self.analyzer:
            self.analyzer = DuplicateCollectionAnalyzer()
        trace.info("Starting duplicate collection analysis", tags=["config", "lifecycle"])
        self._current_worker = self.run_worker(
            self._analyze_configurations(), name="analyze_configurations", exclusive=True
        )

    def _run_analysis_sync(self) -> AnalysisResult:
        excluded_configurations = self.app.config.dbdoctor.exclude.configurations
        return self.analyzer.analyze(self.app.backend, excluded_configurations=excluded_configurations)

    async def _analyze_configurations(self) -> List[BrokenConfigurationInfo]:
        try:
            result = await asyncio.to_thread(self._run_analysis_sync)
            broken_configs = []
            for config_name, dup_collections in result.configurations_with_duplicate_collections.items():
                total_duplicates = sum(
                    (len(doc_ids) for doc_ids in result.duplicate_collection_details.get(config_name, {}).values())
                )
                broken_configs.append(
                    BrokenConfigurationInfo(
                        name=config_name, duplicate_count=len(dup_collections), total_collections=total_duplicates
                    )
                )
            trace.debug("Analysis complete", tags=["config", "lifecycle"], broken_count=len(broken_configs))
            return broken_configs
        except Exception as e:
            trace.error("Configuration analysis failed", tags=["database", "error"], exception=e)
            raise

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name != "analyze_configurations":
            return
        self._loading = False
        self._current_worker = None
        if event.state.name == "SUCCESS":
            self.all_items = event.worker.result or []
            self.apply_filters()
            if not self.all_items:
                self._update_status("No configurations with duplicate collections found!")
                self.notify("All configurations have unique collections", severity="information")
        elif event.state.name == "ERROR":
            error_msg = str(event.worker.error) if event.worker.error else "Unknown error"
            self._update_status(f"Error: {error_msg}")
            self.notify(f"Analysis failed: {error_msg}", severity="error")
        elif event.state.name == "CANCELLED":
            self._update_status("Analysis cancelled")

    def action_cancel_or_back(self) -> None:
        if self._loading and self._current_worker:
            self._current_worker.cancel()
            self._loading = False
            self.notify("Analysis cancelled", severity="warning")
            trace.info(
                "Returning from RepairConfigurationListScreen",
                tags=["screen", "navigation"],
                from_screen="RepairConfigurationListScreen",
                reason="User cancelled analysis and returned",
            )
            self.app.pop_screen()
        else:
            trace.info(
                "Returning from RepairConfigurationListScreen",
                tags=["screen", "navigation"],
                from_screen="RepairConfigurationListScreen",
                reason="User pressed back (escape/h/left)",
            )
            self.app.pop_screen()

    def get_filtered_items(self) -> List[BrokenConfigurationInfo]:
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
            table.add_row(item.name, str(item.duplicate_count), str(item.total_collections), key=item.name)

    def update_status(self) -> None:
        total = len(self.all_items)
        visible = len(self.filtered_items)
        parts = [f"{visible}/{total} configurations with issues"]
        if self.filter_text:
            parts.append(f"filter: '{self.filter_text}'")
        parts.append("[REPAIR MODE]")
        self._update_status(" | ".join(parts))

    def _update_status(self, status: str) -> None:
        status_widget = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        status_widget.update(status)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if self._loading:
            return
        if not event.row_key:
            return
        config_name = str(event.row_key.value)
        self._navigate_to_configuration(config_name)

    def _navigate_to_configuration(self, config_name: str) -> None:
        if self._loading:
            return
        trace.info(
            "Navigating to DiffableCollectionTableScreen",
            tags=["screen", "navigation"],
            from_screen="RepairConfigurationListScreen",
            to_screen="DiffableCollectionTableScreen",
            reason="User selected configuration with duplicate collections",
            config_name=config_name,
        )
        if self.analyzer:
            self.app.state.set_analyzer(self.analyzer)
        self.app.state.navigate_to_configuration(config_name)
        self.app.push_screen(DiffableCollectionTableScreen())

    def action_go_forward(self) -> None:
        if self._loading:
            return
        table = self.get_table()
        if table.cursor_row is not None and self.filtered_items:
            if table.cursor_row < len(self.filtered_items):
                sorted_items = sorted(self.filtered_items, key=lambda x: x.duplicate_count, reverse=True)
                config_name = sorted_items[table.cursor_row].name
                self._navigate_to_configuration(config_name)

    def action_go_back(self) -> None:
        self.action_cancel_or_back()

    def action_toggle_global_trash(self) -> None:
        if self._loading:
            return
        if not self.analyzer:
            self.notify("No analysis available yet", severity="warning")
            return
        trace.info(
            "Navigating to GlobalTrashConfigListScreen",
            tags=["screen", "navigation"],
            from_screen="RepairConfigurationListScreen",
            to_screen="GlobalTrashConfigListScreen",
            reason="User pressed Ctrl+T for global trash view",
        )
        self.app.state.set_analyzer(self.analyzer)
        self.app.push_screen(GlobalTrashConfigListScreen())

    def action_refresh_data(self) -> None:
        trace.info("Refreshing with cache invalidation", tags=["screen", "refresh", "cache"])
        if hasattr(self.app, "backend") and hasattr(self.app.backend, "cache"):
            cache = self.app.backend.cache
            cache.delete("configurations_list")
            cache.delete("configurations_list_optimized")
            cache.delete("configuration_info")
            cache.delete("configuration_info_optimized")
            for item in self.all_items:
                cache.delete(f"config_docs:{item.name}")
                cache.delete(f"config_docs_summary:{item.name}")
            trace.debug(
                "Cache invalidated for configurations", tags=["cache", "mutation"], config_count=len(self.all_items)
            )
        self.analyzer = DuplicateCollectionAnalyzer()
        self._start_analysis()
        self.notify("Refreshing (cache invalidated)...")
