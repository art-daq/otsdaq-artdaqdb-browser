"""
File: assign_config_modal.py
Purpose: Assign Configuration modal dialog with vim-style navigation.
Category: Modal
Author: ArtdaqDB Browser Team
Depends: textual
Exports: AssignConfigurationModal
Complexity: Medium | Lines: 360
"""

from datetime import datetime, timezone
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static, Input, ListView, ListItem, Label
from textual.containers import Container, Vertical
from textual.binding import Binding
import re
from ...widgets import fuzzy_match
from ...constants import WidgetID, ErrorMessage, StatusMessage
from ...trace import trace


class AssignConfigurationModal(ModalScreen[bool]):
    BINDINGS = [
        Binding("escape", "handle_escape", "Cancel/Exit Edit", priority=True),
        Binding("enter", "submit", "Assign", priority=True),
        Binding("i", "enter_edit_mode", "Edit Mode", show=True),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(self, document_id: str, collection: str, version: str):
        super().__init__()
        self.document_id = document_id
        self.collection = collection
        self.version = version
        self.edit_mode = False
        self.all_configs = []
        self.filtered_configs = []

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Static("Assign Configuration", classes="screen-title")
            yield Static("-- COMMAND --", classes="mode-indicator", id=WidgetID.MODE_INDICATOR)
            yield Static(
                f"Document: {self.document_id[:16]}... | Collection: {self.collection} (v{self.version})",
                classes="info-line",
            )
            with Container(classes="input-container"):
                yield Input(
                    placeholder="Type to search (press 'i' to edit)...", id=WidgetID.CONFIG_NAME_INPUT, disabled=True
                )
            with Container(classes="list-container"):
                yield ListView(id=WidgetID.CONFIG_LIST)
            yield Static("⚠️  Pattern: <SystemName>_v<number>", classes="hint")
            yield Static("", classes="status-bar", id=WidgetID.STATUS_BAR)

    def on_mount(self) -> None:
        trace.info(
            "AssignConfigurationModal mounted",
            tags=["screen", "lifecycle"],
            document_id=self.document_id,
            collection=self.collection,
            version=self.version,
        )
        try:
            backend = self.app.backend
            config_names = backend.list_configurations_optimized()
            self.all_configs = sorted(config_names, reverse=True)
            self.filtered_configs = self.all_configs.copy()
            trace.debug(
                "Configurations loaded for assignment modal",
                tags=["screen", "query"],
                config_count=len(self.all_configs),
            )
        except Exception as e:
            trace.error("Failed to load configurations for assignment", tags=["screen", "error"], exception=e)
            self.notify(f"Warning: Could not load configurations: {e}", severity="warning")
            self.all_configs = []
            self.filtered_configs = []
        self.update_list()
        self.update_status()

        def set_command_mode():
            input_widget = self.query_one(f"#{WidgetID.CONFIG_NAME_INPUT}", Input)
            input_widget.disabled = True
            list_view = self.query_one(f"#{WidgetID.CONFIG_LIST}", ListView)
            list_view.focus()

        self.call_after_refresh(set_command_mode)

    def update_list(self) -> None:
        list_view = self.query_one(f"#{WidgetID.CONFIG_LIST}", ListView)
        list_view.clear()
        for config_name in self.filtered_configs:
            list_view.append(ListItem(Label(config_name)))
        if not self.filtered_configs:
            list_view.append(ListItem(Label("(No matches - type new config name)")))

    def update_status(self) -> None:
        status = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        total = len(self.all_configs)
        filtered = len(self.filtered_configs)
        input_widget = self.query_one(f"#{WidgetID.CONFIG_NAME_INPUT}", Input)
        filter_text = input_widget.value
        if filter_text:
            status.update(StatusMessage.CONFIGS_STATUS.format(filtered=filtered, total=total, filter_text=filter_text))
        else:
            status.update(StatusMessage.CONFIGS_TOTAL.format(total=total))

    def on_input_changed(self, event: Input.Changed) -> None:
        if not self.edit_mode:
            return
        filter_text = event.value.lower().strip()
        if not filter_text:
            self.filtered_configs = self.all_configs.copy()
        else:
            self.filtered_configs = [config for config in self.all_configs if fuzzy_match(filter_text, config.lower())]
        self.update_list()
        self.update_status()

    def on_key(self, event) -> None:
        if not self.edit_mode:
            if event.key in ("j", "k", "up", "down", "enter", "i", "escape"):
                event.stop()

    def action_enter_edit_mode(self) -> None:
        if self.edit_mode:
            return
        self.edit_mode = True
        mode_indicator = self.query_one(f"#{WidgetID.MODE_INDICATOR}", Static)
        mode_indicator.update("-- INSERT --")
        input_widget = self.query_one(f"#{WidgetID.CONFIG_NAME_INPUT}", Input)
        input_widget.disabled = False
        input_widget.focus()

    def action_exit_edit_mode(self) -> None:
        if not self.edit_mode:
            return
        self.edit_mode = False
        mode_indicator = self.query_one(f"#{WidgetID.MODE_INDICATOR}", Static)
        mode_indicator.update("-- COMMAND --")
        input_widget = self.query_one(f"#{WidgetID.CONFIG_NAME_INPUT}", Input)
        input_widget.disabled = True
        list_view = self.query_one(f"#{WidgetID.CONFIG_LIST}", ListView)
        list_view.focus()

    def action_handle_escape(self) -> None:
        if self.edit_mode:
            self.action_exit_edit_mode()
        else:
            trace.info(
                "Closing AssignConfigurationModal",
                tags=["screen", "navigation"],
                from_screen="AssignConfigurationModal",
                reason="User pressed escape to cancel",
            )
            self.dismiss(False)

    def action_cursor_down(self) -> None:
        if self.edit_mode:
            return
        list_view = self.query_one(f"#{WidgetID.CONFIG_LIST}", ListView)
        list_view.action_cursor_down()

    def action_cursor_up(self) -> None:
        if self.edit_mode:
            return
        list_view = self.query_one(f"#{WidgetID.CONFIG_LIST}", ListView)
        list_view.action_cursor_up()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item:
            try:
                label = event.item.query_one(Label)
                config_name = str(label.render())
                if config_name.startswith("("):
                    return
                input_widget = self.query_one(f"#{WidgetID.CONFIG_NAME_INPUT}", Input)
                input_widget.value = config_name
                self.action_submit()
            except Exception:
                pass

    def action_submit(self) -> None:
        input_widget = self.query_one(f"#{WidgetID.CONFIG_NAME_INPUT}", Input)
        config_name = input_widget.value.strip()
        if not config_name and (not self.edit_mode):
            list_view = self.query_one(f"#{WidgetID.CONFIG_LIST}", ListView)
            if list_view.highlighted_child:
                try:
                    label = list_view.highlighted_child.query_one(Label)
                    config_name = str(label.render())
                except Exception:
                    pass
        trace.debug(
            "Submitting configuration assignment",
            tags=["screen", "mutation"],
            config_name=config_name,
            document_id=self.document_id,
        )
        if not config_name or config_name.startswith("("):
            self.notify(ErrorMessage.EMPTY_CONFIG_NAME, severity="warning")
            return
        docs_config = self.app.config.documents
        config_name_required = docs_config.config_name_required
        config_name_pattern = docs_config.config_name_pattern
        if config_name_required and config_name_required not in config_name:
            self.notify(ErrorMessage.INVALID_CONFIG_PATTERN, severity="warning")
            return
        if config_name_pattern:
            try:
                if not re.match(config_name_pattern, config_name):
                    self.notify(ErrorMessage.INVALID_CONFIG_PATTERN, severity="warning")
                    return
            except re.error:
                pass
        try:
            backend = self.app.backend
            timestamp = datetime.now(timezone.utc).isoformat()
            success = backend.assign_configuration(self.document_id, config_name, timestamp)
            if success:
                trace.info(
                    "Configuration assigned successfully",
                    tags=["screen", "mutation"],
                    config_name=config_name,
                    document_id=self.document_id,
                )
                trace.debug(
                    "Backend cache invalidated by assign_configuration",
                    tags=["cache", "invalidate"],
                    document_id=self.document_id,
                    config_name=config_name,
                )
                trace.info(
                    "Closing AssignConfigurationModal",
                    tags=["screen", "navigation"],
                    from_screen="AssignConfigurationModal",
                    reason="Configuration assigned successfully",
                    config_name=config_name,
                )
                self.dismiss(True)
            else:
                trace.error(
                    "Configuration assignment failed", tags=["screen", "mutation", "error"], config_name=config_name
                )
                self.notify(ErrorMessage.ASSIGN_CONFIG_FAILED, severity="error")
        except Exception as e:
            trace.error(
                "Error assigning configuration",
                tags=["screen", "mutation", "error"],
                exception=e,
                config_name=config_name,
            )
            self.notify(ErrorMessage.ASSIGN_CONFIG_ERROR.format(error=e), severity="error")
