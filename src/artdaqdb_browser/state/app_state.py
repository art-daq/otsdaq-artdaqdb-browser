"""
File: app_state.py
Purpose: Application state manager.
Category: Utility
Author: ArtdaqDB Browser Team
Depends: None
Exports: NavigationState, FilterState, ViewState, AppState
Complexity: High | Lines: 206
"""

from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING
from ..trace import trace

if TYPE_CHECKING:
    from ..data.analyzers import BaseAnalyzer


@dataclass
class NavigationState:
    current_screen: str = "home"
    history: List[str] = field(default_factory=list)
    current_configuration: Optional[str] = None
    current_collection: Optional[str] = None
    current_version: Optional[str] = None
    current_document_id: Optional[str] = None

    def push_screen(self, screen_name: str) -> None:
        if self.current_screen:
            self.history.append(self.current_screen)
        self.current_screen = screen_name

    def pop_screen(self) -> Optional[str]:
        if self.history:
            self.current_screen = self.history.pop()
            return self.current_screen
        return None

    def clear_history(self) -> None:
        self.history.clear()
        self.current_screen = "home"


@dataclass
class FilterState:
    active_filter: str = ""
    filter_enabled: bool = False

    def set_filter(self, filter_text: str) -> None:
        self.active_filter = filter_text
        self.filter_enabled = bool(filter_text.strip())

    def clear_filter(self) -> None:
        self.active_filter = ""
        self.filter_enabled = False


@dataclass
class ViewState:
    show_dates: bool = False
    show_deleted: bool = True
    dark_mode: bool = True


class AppState:

    def __init__(self):
        self.navigation = NavigationState()
        self.filter = FilterState()
        self.view = ViewState()
        self.data_source: Optional[str] = None
        self.backend_type: Optional[str] = None
        self.cache_enabled: bool = True
        from ..data.analyzers import DEFAULT_ANALYZER

        self._analyzer: "BaseAnalyzer" = DEFAULT_ANALYZER

    @property
    def analyzer(self) -> "BaseAnalyzer":
        return self._analyzer

    def get_analyzer(self) -> "BaseAnalyzer":
        return self._analyzer

    def set_analyzer(self, analyzer: "BaseAnalyzer") -> None:
        from ..data.analyzers import BaseAnalyzer

        if not isinstance(analyzer, BaseAnalyzer):
            raise TypeError(f"Expected BaseAnalyzer, got {type(analyzer)}")
        previous_name = self._analyzer.name if self._analyzer else "none"
        self._analyzer = analyzer
        trace.debug(
            "Analyzer changed for data filtering",
            tags=["state", "diff"],
            previous_analyzer=previous_name,
            new_analyzer=analyzer.name,
        )

    def clear_analyzer(self) -> None:
        from ..data.analyzers import DEFAULT_ANALYZER

        previous_name = self._analyzer.name if self._analyzer else "none"
        self._analyzer = DEFAULT_ANALYZER
        trace.debug(
            "Analyzer reset to default (no filtering)",
            tags=["state", "diff"],
            previous_analyzer=previous_name,
            new_analyzer=DEFAULT_ANALYZER.name,
        )

    def reset(self) -> None:
        trace.info("Resetting application state to defaults", tags=["state", "lifecycle"])
        self.navigation = NavigationState()
        self.filter = FilterState()
        self.view = ViewState()
        self.clear_analyzer()

    def navigate_to_configuration(self, config_name: str) -> None:
        previous = self.navigation.current_configuration
        self.navigation.current_configuration = config_name
        self.navigation.current_collection = None
        self.navigation.current_version = None
        self.navigation.current_document_id = None
        trace.info(
            "Navigating to configuration",
            tags=["state", "navigation", "diff"],
            config_from=previous,
            config_to=config_name,
        )

    def navigate_to_collection(self, collection_name: str, from_config: bool = False) -> None:
        previous = self.navigation.current_collection
        self.navigation.current_collection = collection_name
        if not from_config:
            self.navigation.current_configuration = None
        self.navigation.current_version = None
        self.navigation.current_document_id = None
        trace.info(
            "Navigating to collection",
            tags=["state", "navigation", "diff"],
            collection_from=previous,
            collection_to=collection_name,
            context="configuration" if from_config else "standalone",
        )

    def navigate_to_version(self, version: str) -> None:
        previous = self.navigation.current_version
        self.navigation.current_version = version
        self.navigation.current_document_id = None
        trace.info(
            "Navigating to document version",
            tags=["state", "navigation", "diff"],
            version_from=previous,
            version_to=version,
            collection=self.navigation.current_collection,
        )

    def navigate_to_document(self, document_id: str) -> None:
        previous = self.navigation.current_document_id
        self.navigation.current_document_id = document_id
        trace.info(
            "Navigating to document by ID",
            tags=["state", "navigation", "diff"],
            document_from=previous,
            document_to=document_id,
        )

    def get_breadcrumb(self) -> str:
        parts = ["Home"]
        if self.navigation.current_configuration:
            parts.append(f"Config: {self.navigation.current_configuration}")
        if self.navigation.current_collection:
            parts.append(f"Collection: {self.navigation.current_collection}")
        if self.navigation.current_version:
            parts.append(f"v{self.navigation.current_version}")
        if self.navigation.current_document_id:
            parts.append(f"Doc: {self.navigation.current_document_id[:8]}...")
        return " > ".join(parts)
