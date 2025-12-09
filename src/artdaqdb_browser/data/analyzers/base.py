"""
File: base.py
Purpose: Base analyzer classes and common types.
Category: Analyzer
Author: ArtdaqDB Browser Team
Depends: None
Exports: AnalysisResult, BaseAnalyzer, PassThroughAnalyzer, DEFAULT_THROTTLE_INTERVAL
Complexity: Medium | Lines: 151
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..base import DataBackend
from ...models import DocumentSummary, VersionSummary, ConfigurationInfo, CollectionInfo

ProgressCallback = Callable[[int, int], None]
DEFAULT_THROTTLE_INTERVAL = 3.0


@dataclass
class AnalysisResult:
    collections_with_duplicate_versions: Dict[str, List[str]] = field(default_factory=dict)
    configurations_with_duplicate_collections: Dict[str, List[str]] = field(default_factory=dict)
    duplicate_version_details: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)
    duplicate_collection_details: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)
    config_documents: Dict[str, List[DocumentSummary]] = field(default_factory=dict)
    collection_versions: Dict[str, List[VersionSummary]] = field(default_factory=dict)


class BaseAnalyzer(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def filter_configurations(self, configurations: List[ConfigurationInfo]) -> List[ConfigurationInfo]:
        pass

    @abstractmethod
    def filter_collections(self, collections: List[CollectionInfo]) -> List[CollectionInfo]:
        pass

    @abstractmethod
    def filter_documents_by_config(
        self, documents: List[DocumentSummary], config_name: Optional[str] = None
    ) -> List[DocumentSummary]:
        pass

    @abstractmethod
    def filter_versions(
        self, versions: List[VersionSummary], collection_name: Optional[str] = None, config_name: Optional[str] = None
    ) -> List[VersionSummary]:
        pass

    def get_status_suffix(self) -> str:
        return ""


class PassThroughAnalyzer(BaseAnalyzer):

    @property
    def name(self) -> str:
        return "Normal Browse"

    @property
    def description(self) -> str:
        return "Show all data without filtering"

    def filter_configurations(self, configurations: List[ConfigurationInfo]) -> List[ConfigurationInfo]:
        return configurations

    def filter_collections(self, collections: List[CollectionInfo]) -> List[CollectionInfo]:
        return collections

    def filter_documents_by_config(
        self, documents: List[DocumentSummary], config_name: Optional[str] = None
    ) -> List[DocumentSummary]:
        return documents

    def filter_versions(
        self, versions: List[VersionSummary], collection_name: Optional[str] = None, config_name: Optional[str] = None
    ) -> List[VersionSummary]:
        return versions
