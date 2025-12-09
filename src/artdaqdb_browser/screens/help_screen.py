"""
File: help_screen.py
Purpose: Help screen displaying README.md.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: HelpScreen
Complexity: Low | Lines: 154
"""

from pathlib import Path
from textual.app import ComposeResult
from textual.widgets import Static, Footer, MarkdownViewer
from textual.binding import Binding
from textual.containers import Vertical
from .base import BaseScreen, BACK_BINDINGS
from ..trace import trace


class HelpScreen(BaseScreen):
    FOCUSABLE_CONTROLS = ["help_viewer"]
    BINDINGS = [
        Binding("escape", "go_back", "Close"),
        Binding("q", "go_back", "Close"),
        *BACK_BINDINGS,
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
        Binding("down", "scroll_down", "Down", show=False),
        Binding("up", "scroll_up", "Up", show=False),
        Binding("g", "scroll_top", "Top", show=False),
        Binding("G", "scroll_bottom", "Bottom", show=False),
        Binding("pagedown", "page_down", "Page Down", show=False),
        Binding("pageup", "page_up", "Page Up", show=False),
        Binding("space", "page_down", "Page Down", show=False),
    ]

    def __init__(self):
        super().__init__()
        self._readme_content = ""
        self._load_readme()

    def _load_readme(self) -> None:
        possible_paths = [
            Path(__file__).parent.parent.parent.parent / "README.md",
            Path(__file__).parent.parent.parent.parent.parent / "README.md",
            Path.cwd() / "README.md",
        ]
        for readme_path in possible_paths:
            if readme_path.exists():
                try:
                    self._readme_content = readme_path.read_text()
                    return
                except Exception:
                    continue
        self._readme_content = """# OTS Configuration Browser - Help


- `â` / `â` or `j` / `k` - Move up/down in lists
- `Enter` - Select item / drill down
- `Esc` - Go back to previous screen
- `q` - Quit application

- `/` - Focus filter input
- `c` - Clear filter

- `d` - Toggle showing deleted items
- `Tab` / `Space` - Switch between panes

- `?` - Show this help
- `Ctrl+R` - Refresh current view


1. Home Screen â Select "Browse by Configuration"
2. Configuration List â Choose a configuration
3. Collection Table â View all collections
4. Version List â Select a version
5. Document View â View complete JSON

1. Home Screen â Select "Browse by Collection"
2. Collection Browser â Choose a collection
3. Version List â Browse all versions
4. Document View â View complete JSON

---
Press `Esc` or `q` to close this help screen.
"""

    def compose(self) -> ComposeResult:
        with Vertical(classes="help-header"):
            yield Static("Help - README.md", classes="help-title")
        yield MarkdownViewer(self._readme_content, id="help_viewer", show_table_of_contents=False)
        yield Static("Esc/q: close | j/k: scroll | g/G: top/bottom | PageUp/Down: page", classes="help-footer")
        yield Footer()

    def on_mount(self) -> None:
        trace.debug("HelpScreen mounted", tags=["screen", "lifecycle"])
        self.focus_first_control()

    def action_scroll_down(self) -> None:
        viewer = self.query_one("#help_viewer", MarkdownViewer)
        viewer.scroll_relative(y=3)

    def action_scroll_up(self) -> None:
        viewer = self.query_one("#help_viewer", MarkdownViewer)
        viewer.scroll_relative(y=-3)

    def action_scroll_top(self) -> None:
        viewer = self.query_one("#help_viewer", MarkdownViewer)
        viewer.scroll_home()

    def action_scroll_bottom(self) -> None:
        viewer = self.query_one("#help_viewer", MarkdownViewer)
        viewer.scroll_end()

    def action_page_down(self) -> None:
        viewer = self.query_one("#help_viewer", MarkdownViewer)
        viewer.scroll_page_down()

    def action_page_up(self) -> None:
        viewer = self.query_one("#help_viewer", MarkdownViewer)
        viewer.scroll_page_up()

    def action_go_back(self) -> None:
        trace.info(
            "Returning from HelpScreen",
            tags=["screen", "navigation"],
            from_screen="HelpScreen",
            reason="User closed help (escape/q/h/left)",
        )
        self.app.pop_screen()
