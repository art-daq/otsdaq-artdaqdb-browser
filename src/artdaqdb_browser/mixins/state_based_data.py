"""
File: state_based_data.py
Purpose: State-based data mixin for screens that load data based on navigati...
Category: Mixin
Author: ArtdaqDB Browser Team
Depends: textual
Exports: StateBasedDataMixin
Complexity: Low | Lines: 116
"""

from typing import Any, List, Optional
from textual.widgets import Static
from ..trace import trace


class StateBasedDataMixin:
    STATE_ATTRIBUTE: str = ""
    BACKEND_METHOD: str = ""
    NO_SELECTION_MESSAGE: str = ""
    LOAD_ERROR_MESSAGE: str = ""
    TRACE_NAME: str = ""
    TITLE_WIDGET_ID: str = ""
    TITLE_PREFIX: str = ""

    def get_state_value(self) -> Optional[str]:
        return getattr(self.app.state.navigation, self.STATE_ATTRIBUTE, None)

    def fetch_backend_data(self, state_value: str) -> List[Any]:
        method = getattr(self.app.backend, self.BACKEND_METHOD)
        return method(state_value)

    def update_title(self, state_value: str) -> None:
        if self.TITLE_WIDGET_ID:
            self.query_one(f"#{self.TITLE_WIDGET_ID}", Static).update(f"{self.TITLE_PREFIX}{state_value}")

    def load_data(self) -> None:
        try:
            state_value = self.get_state_value()
            trace.debug(
                f"Loading data for {self.STATE_ATTRIBUTE}",
                tags=["screen", "query"],
                **{self.STATE_ATTRIBUTE: state_value},
            )
            if not state_value:
                if hasattr(self, "notify"):
                    self.notify(self.NO_SELECTION_MESSAGE, severity="warning")
                return
            self.update_title(state_value)
            self.documents = self.fetch_backend_data(state_value)
            trace.debug(
                f"Data loaded successfully for {self.STATE_ATTRIBUTE}",
                tags=["screen", "query"],
                document_count=len(self.documents),
            )
            if hasattr(self, "apply_filters"):
                self.apply_filters()
        except Exception as e:
            trace.error(
                f"Failed to load data for {self.STATE_ATTRIBUTE}",
                tags=["screen", "error"],
                exception=e,
                trace_name=self.TRACE_NAME,
            )
            if hasattr(self, "notify"):
                error_msg = self.LOAD_ERROR_MESSAGE
                if "{error}" in error_msg:
                    error_msg = error_msg.format(error=str(e))
                self.notify(error_msg, severity="error")
