"""
File: output_window.py
Purpose: Output window mixin for scrollable text output.
Category: Mixin
Author: ArtdaqDB Browser Team
Depends: textual
Exports: OutputWindowMixin
Complexity: Low | Lines: 102
"""

from typing import Optional
from textual.widgets import TextArea
from ..constants import WidgetID


class OutputWindowMixin:
    OUTPUT_WIDGET_ID: str = WidgetID.OUTPUT_LOG

    def _get_output_widget(self) -> Optional[TextArea]:
        try:
            return self.query_one(f"#{self.OUTPUT_WIDGET_ID}", TextArea)
        except Exception:
            return None

    def _set_output_text(self, text: str, autoscroll: bool = True) -> None:
        widget = self._get_output_widget()
        if widget:
            widget.text = text
            if autoscroll:
                self.call_after_refresh(lambda: widget.scroll_end(animate=False))

    def _append_output_text(self, text: str, autoscroll: bool = True) -> None:
        widget = self._get_output_widget()
        if widget:
            widget.text = widget.text + text
            if autoscroll:
                self.call_after_refresh(lambda: widget.scroll_end(animate=False))

    def action_scroll_down(self) -> None:
        widget = self._get_output_widget()
        if widget:
            widget.scroll_relative(y=1)

    def action_scroll_up(self) -> None:
        widget = self._get_output_widget()
        if widget:
            widget.scroll_relative(y=-1)

    def action_scroll_top(self) -> None:
        widget = self._get_output_widget()
        if widget:
            widget.scroll_home(animate=False)

    def action_scroll_bottom(self) -> None:
        widget = self._get_output_widget()
        if widget:
            widget.scroll_end(animate=False)

    def action_page_down(self) -> None:
        widget = self._get_output_widget()
        if widget:
            widget.scroll_page_down()

    def action_page_up(self) -> None:
        widget = self._get_output_widget()
        if widget:
            widget.scroll_page_up()
