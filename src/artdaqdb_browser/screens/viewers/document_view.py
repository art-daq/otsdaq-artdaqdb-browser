"""
File: document_view.py
Purpose: Document view screen.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: DocumentViewScreen
Complexity: Medium | Lines: 429
"""

from textual.app import ComposeResult
from textual.widgets import Static, ListView, ListItem, Label
from textual.binding import Binding
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.events import MouseScrollDown, MouseScrollUp, Click
from ..base import BaseScreen, NAVIGATION_BINDINGS, FOCUS_BINDINGS
from ...widgets import JSONViewer
from ...utils import format_datetime
from ...constants import WidgetID, ScreenName, ErrorMessage
from ...trace import trace


class DocumentViewScreen(BaseScreen):
    FOCUSABLE_CONTROLS = [WidgetID.JSON_VIEWER, WidgetID.CONFIG_LIST]
    SECONDARY_ACTIONS = [("y", "copy_id", "Copy"), ("a", "assign_config", "Assign")]
    BINDINGS = [
        Binding("escape", "go_back", "Back", show=False),
        *NAVIGATION_BINDINGS,
        *FOCUS_BINDINGS,
        Binding("g", "goto_first", "First", show=False),
        Binding("G", "goto_last", "Last", show=False),
        Binding("enter", "view_configuration", "View Config", show=False, priority=True),
    ]

    def __init__(self):
        super().__init__()
        self.document = None
        self.selected_config_name = None
        self.selected_index = 0

    def compose_content(self) -> ComposeResult:
        with Vertical(classes="screen-header"):
            yield Static("", classes="screen-title", id=WidgetID.DOC_TITLE)
        with Horizontal(classes="main-content"):
            with Vertical(classes="left-pane"):
                yield JSONViewer(id=WidgetID.JSON_VIEWER)
            with Vertical(classes="right-pane"):
                yield Static("Assigned Configurations", classes="config-panel-header")
                with VerticalScroll(classes="config-list-container"):
                    yield ListView(id=WidgetID.CONFIG_LIST)
                with Vertical(classes="assignment-time-container"):
                    yield Static("Assignment Time:", classes="assignment-time-label")
                    yield Static("Select a configuration", classes="assignment-time-value", id=WidgetID.ASSIGNMENT_TIME)

    def on_mount(self) -> None:
        trace.info("DocumentViewScreen mounted", tags=["screen", "lifecycle"])
        self.load_document()
        self.focus_first_control()

    def on_screen_resume(self) -> None:
        self._apply_key_panel_visibility()
        self._update_footer()
        trace.debug("DocumentViewScreen resuming - reloading document", tags=["screen", "lifecycle", "refresh"])
        self.load_document()

    def refresh_data(self) -> None:
        self.load_document()

    def load_document(self) -> None:
        try:
            document_id = self.app.state.navigation.current_document_id
            collection_name = self.app.state.navigation.current_collection
            trace.debug(
                "Loading document from backend",
                tags=["screen", "query"],
                document_id=document_id,
                collection=collection_name,
            )
            if not document_id:
                self.notify(ErrorMessage.NO_DOCUMENT_SELECTED, severity="warning")
                return
            backend = self.app.backend
            self.document = backend.get_document_by_id_direct(document_id, collection_name)
            if not self.document:
                self.notify(ErrorMessage.DOCUMENT_NOT_FOUND, severity="error")
                return
            config_names = [c.name for c in self.document.configurations] if self.document.configurations else []
            trace.debug(
                "Document loaded successfully",
                tags=["screen", "query"],
                document_id=document_id,
                collection=self.document.collection,
                version=self.document.version,
                config_count=len(config_names),
            )
            self.query_one(f"#{WidgetID.DOC_TITLE}", Static).update(
                f"Document: {self.document.collection} v{self.document.version} | ID: {self.document.id[:16]}..."
            )
            json_viewer = self.query_one(f"#{WidgetID.JSON_VIEWER}", JSONViewer)
            json_viewer.set_data(self.document.model_dump(by_alias=True))
            config_list = self.query_one(f"#{WidgetID.CONFIG_LIST}", ListView)
            config_list.clear()
            if self.document.configurations:
                for i, config in enumerate(self.document.configurations):
                    config_list.append(ListItem(Label(config.name)))
                config_list.index = 0
                self.selected_index = 0
                self.selected_config_name = self.document.configurations[0].name
                trace.trace(
                    "Configuration list populated",
                    tags=["screen", "widget"],
                    config_count=len(self.document.configurations),
                    initial_selection=self.selected_config_name,
                )
                first_config = self.document.configurations[0]
                assignment_time = self.query_one(f"#{WidgetID.ASSIGNMENT_TIME}", Static)
                if hasattr(first_config, "assigned") and first_config.assigned:
                    assignment_time.update(format_datetime(first_config.assigned))
                else:
                    assignment_time.update("Not available")

                def mark_first_selected():
                    items = list(config_list.query(ListItem))
                    if items:
                        items[0].add_class("--selected")

                self.call_after_refresh(mark_first_selected)
            else:
                config_list.append(ListItem(Label("No configurations assigned", classes="config-list-empty")))
        except Exception as e:
            trace.error("Failed to load document", tags=["screen", "error"], exception=e)
            self.notify(ErrorMessage.LOADING_DOCUMENT.format(error=e), severity="error")

    def action_copy_id(self) -> None:
        if self.document:
            self.notify(f"Document ID: {self.document.id}", timeout=5)

    def action_assign_config(self) -> None:
        if not self.document:
            self.notify(ErrorMessage.NO_DOCUMENT_LOADED, severity="warning")
            return
        from ..dbbrowser.assign_config_modal import AssignConfigurationModal

        def handle_result(success: bool) -> None:
            if success:
                self.notify("Configuration assigned successfully!", severity="information")
                self.load_document()
            else:
                pass

        trace.info(
            "Opening AssignConfigurationModal",
            tags=["screen", "navigation"],
            from_screen="DocumentViewScreen",
            to_screen="AssignConfigurationModal",
            reason="User pressed assign config (a)",
            document_id=self.document.id,
            collection=self.document.collection,
            version=self.document.version,
        )
        self.app.push_screen(
            AssignConfigurationModal(
                document_id=self.document.id, collection=self.document.collection, version=self.document.version
            ),
            handle_result,
        )

    def action_go_back(self) -> None:
        trace.info(
            "Returning from DocumentViewScreen",
            tags=["screen", "navigation"],
            from_screen="DocumentViewScreen",
            reason="User pressed back (escape/h/left)",
        )
        self.app.pop_screen()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if not self.document or not self.document.configurations:
            return
        if event.item is not None:
            highlighted_index = event.list_view.index
            if highlighted_index is not None and highlighted_index < len(self.document.configurations):
                config_list = self.query_one(f"#{WidgetID.CONFIG_LIST}", ListView)
                items = list(config_list.query(ListItem))
                if self.selected_index < len(items):
                    items[self.selected_index].remove_class("--selected")
                if highlighted_index < len(items):
                    items[highlighted_index].add_class("--selected")
                old_index = self.selected_index
                self.selected_index = highlighted_index
                selected_config = self.document.configurations[highlighted_index]
                self.selected_config_name = selected_config.name
                assignment_time = self.query_one(f"#{WidgetID.ASSIGNMENT_TIME}", Static)
                if hasattr(selected_config, "assigned") and selected_config.assigned:
                    assignment_time.update(format_datetime(selected_config.assigned))
                else:
                    assignment_time.update("Not available")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.action_view_configuration()

    def action_view_configuration(self) -> None:
        if not self.document or not self.document.configurations:
            self.notify("No configurations available", severity="warning")
            return
        config_list = self.query_one(f"#{WidgetID.CONFIG_LIST}", ListView)
        current_index = config_list.index
        if current_index is None:
            self.notify("No configuration selected", severity="warning")
            return
        if current_index < 0 or current_index >= len(self.document.configurations):
            self.notify("Invalid selection", severity="warning")
            return
        config_name = self.document.configurations[current_index].name
        trace.info(
            "Navigating to CollectionTableScreen via configuration jump",
            tags=["screen", "navigation"],
            from_screen="DocumentViewScreen",
            to_screen="COLLECTION_TABLE",
            reason="User selected configuration to view",
            config_name=config_name,
        )
        self.app.state.navigate_to_configuration(config_name)
        self.app.pop_screen()
        self.app.push_screen(ScreenName.COLLECTION_TABLE)

    def action_cursor_down(self) -> None:
        config_list = self.query_one(f"#{WidgetID.CONFIG_LIST}", ListView)
        config_list.action_cursor_down()
        self._update_selection_from_index(config_list.index)

    def action_cursor_up(self) -> None:
        config_list = self.query_one(f"#{WidgetID.CONFIG_LIST}", ListView)
        config_list.action_cursor_up()
        self._update_selection_from_index(config_list.index)

    def _update_selection_from_index(self, index) -> None:
        if index is not None and self.document and self.document.configurations:
            if 0 <= index < len(self.document.configurations):
                selected_config = self.document.configurations[index]
                old_index = self.selected_index
                config_list = self.query_one(f"#{WidgetID.CONFIG_LIST}", ListView)
                items = list(config_list.query(ListItem))
                if old_index < len(items):
                    items[old_index].remove_class("--selected")
                if index < len(items):
                    items[index].add_class("--selected")
                self.selected_index = index
                self.selected_config_name = selected_config.name
                assignment_time = self.query_one(f"#{WidgetID.ASSIGNMENT_TIME}", Static)
                if hasattr(selected_config, "assigned") and selected_config.assigned:
                    assignment_time.update(format_datetime(selected_config.assigned))
                else:
                    assignment_time.update("Not available")

    def action_go_forward(self) -> None:
        self.action_view_configuration()

    def action_goto_first(self) -> None:
        if not self.document or not self.document.configurations:
            return
        config_list = self.query_one(f"#{WidgetID.CONFIG_LIST}", ListView)
        config_list.index = 0
        self._update_selection_from_index(0)

    def action_goto_last(self) -> None:
        if not self.document or not self.document.configurations:
            return
        config_list = self.query_one(f"#{WidgetID.CONFIG_LIST}", ListView)
        last_index = len(self.document.configurations) - 1
        config_list.index = last_index
        self._update_selection_from_index(last_index)

    def on_click(self, event: Click) -> None:
        try:
            config_list = self.query_one(f"#{WidgetID.CONFIG_LIST}", ListView)
            if config_list.region.contains(event.x, event.y):
                config_list.focus()
                items = list(config_list.query(ListItem))
                for i, item in enumerate(items):
                    if item.region.contains(event.x, event.y):
                        config_list.index = i
                        if self.document and self.document.configurations and (i < len(self.document.configurations)):
                            for j, other_item in enumerate(items):
                                if j == i:
                                    other_item.add_class("--selected")
                                else:
                                    other_item.remove_class("--selected")
                            self.selected_index = i
                            selected_config = self.document.configurations[i]
                            self.selected_config_name = selected_config.name
                            assignment_time = self.query_one(f"#{WidgetID.ASSIGNMENT_TIME}", Static)
                            if hasattr(selected_config, "assigned") and selected_config.assigned:
                                assignment_time.update(format_datetime(selected_config.assigned))
                            else:
                                assignment_time.update("Not available")
                        break
                return
        except Exception:
            pass
        try:
            json_viewer = self.query_one(f"#{WidgetID.JSON_VIEWER}", JSONViewer)
            if json_viewer.region.contains(event.x, event.y):
                json_viewer.focus()
                return
        except Exception:
            pass
        super().on_click(event)
