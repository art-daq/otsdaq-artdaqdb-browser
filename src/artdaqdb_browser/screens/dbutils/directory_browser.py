"""
File: directory_browser.py
Purpose: Directory browser modal screen.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: DirectoryBrowserModal
Complexity: Low | Lines: 135
"""

from pathlib import Path
from typing import Optional
from textual.app import ComposeResult
from textual.widgets import Static, Button, DirectoryTree
from textual.binding import Binding
from textual.containers import Vertical, Horizontal, Container
from textual.screen import ModalScreen
from ...trace import trace


class DirectoryBrowserModal(ModalScreen[Optional[Path]]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "select", "Select"),
        Binding("h", "cancel", "Back", show=False),
        Binding("left", "cancel", "Back", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
    ]

    def __init__(self, start_path: str = "/"):
        super().__init__()
        self.start_path = Path(start_path).expanduser()
        if not self.start_path.exists():
            self.start_path = Path.home()
        self.selected_path: Optional[Path] = None

    def compose(self) -> ComposeResult:
        with Container(id="dir_browser_dialog", classes="dir-browser-dialog"):
            yield Static("Select Backup Directory", classes="dir-browser-title")
            with Horizontal(classes="dir-browser-content"):
                yield DirectoryTree(str(self.start_path), id="dir_tree", classes="dir-tree")
                with Vertical(classes="dir-info-pane"):
                    yield Static("Selected:", classes="dir-info-label")
                    yield Static(str(self.start_path), id="selected_dir_display", classes="selected-dir")
                    yield Static("", id="dir_contents", classes="dir-contents")
            with Horizontal(classes="dir-browser-buttons"):
                yield Button("Select", id="select_btn", variant="primary")
                yield Button("Cancel", id="cancel_btn", variant="default")

    def on_mount(self) -> None:
        self.selected_path = self.start_path
        tree = self.query_one("#dir_tree", DirectoryTree)
        tree.focus()
        self._update_dir_info()

    def _update_dir_info(self) -> None:
        if self.selected_path:
            self.query_one("#selected_dir_display", Static).update(str(self.selected_path))
            try:
                contents = list(self.selected_path.iterdir())
                dirs = sum((1 for c in contents if c.is_dir()))
                files = sum((1 for c in contents if c.is_file()))
                tgz_files = sum((1 for c in contents if c.is_file() and c.name.endswith(".tgz")))
                info = f"{dirs} folders, {files} files"
                if tgz_files > 0:
                    info += f" ({tgz_files} backups)"
                self.query_one("#dir_contents", Static).update(info)
            except PermissionError:
                self.query_one("#dir_contents", Static).update("Permission denied")
            except Exception:
                self.query_one("#dir_contents", Static).update("")

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self.selected_path = event.path
        self._update_dir_info()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "select_btn":
            trace.info(
                "Closing DirectoryBrowserModal",
                tags=["screen", "navigation"],
                from_screen="DirectoryBrowserModal",
                reason="User clicked Select button",
                selected_path=str(self.selected_path),
            )
            self.dismiss(self.selected_path)
        elif event.button.id == "cancel_btn":
            trace.info(
                "Closing DirectoryBrowserModal",
                tags=["screen", "navigation"],
                from_screen="DirectoryBrowserModal",
                reason="User clicked Cancel button",
            )
            self.dismiss(None)

    def action_cancel(self) -> None:
        trace.info(
            "Closing DirectoryBrowserModal",
            tags=["screen", "navigation"],
            from_screen="DirectoryBrowserModal",
            reason="User pressed escape/cancel",
        )
        self.dismiss(None)

    def action_select(self) -> None:
        trace.info(
            "Closing DirectoryBrowserModal",
            tags=["screen", "navigation"],
            from_screen="DirectoryBrowserModal",
            reason="User pressed enter to select",
            selected_path=str(self.selected_path),
        )
        self.dismiss(self.selected_path)

    def action_cursor_down(self) -> None:
        tree = self.query_one("#dir_tree", DirectoryTree)
        tree.action_cursor_down()

    def action_cursor_up(self) -> None:
        tree = self.query_one("#dir_tree", DirectoryTree)
        tree.action_cursor_up()
