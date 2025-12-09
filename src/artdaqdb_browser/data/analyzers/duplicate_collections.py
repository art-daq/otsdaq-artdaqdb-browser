"""
File: duplicate_collections.py
Purpose: Analyzers for detecting and handling duplicate collection issues.
Category: Analyzer
Author: ArtdaqDB Browser Team
Depends: None
Exports: DuplicateCollectionAnalyzer, TrashDuplicateCollectionAnalyzer, GlobalTrashConfigItem, GlobalTrashDuplicateCollectionAnalyzer
Complexity: High | Lines: 587
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Any, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..base import DataBackend
from ...models import DocumentSummary, VersionSummary, ConfigurationInfo, CollectionInfo
from ...utils import ThrottledCallback
from ...trace import trace
from .base import BaseAnalyzer, AnalysisResult, ProgressCallback, DEFAULT_THROTTLE_INTERVAL


class DuplicateCollectionAnalyzer(BaseAnalyzer):

    def __init__(self) -> None:
        self._analysis: Optional[AnalysisResult] = None
        self._config_documents_cache: Dict[str, List[DocumentSummary]] = {}

    @property
    def name(self) -> str:
        return "Duplicate Collections"

    @property
    def description(self) -> str:
        return "Find configurations with duplicate collection references"

    def analyze(
        self,
        backend: Any,
        progress_callback: Optional[ProgressCallback] = None,
        throttle_interval: float = DEFAULT_THROTTLE_INTERVAL,
        excluded_configurations: Optional[List[str]] = None,
    ) -> AnalysisResult:
        result = AnalysisResult()
        excluded = set(excluded_configurations or [])
        throttled_callback = ThrottledCallback(
            progress_callback, min_interval=throttle_interval, always_call_first=True
        )
        duplicate_data = backend.find_duplicate_collections_in_configs(progress_callback=throttled_callback)
        if progress_callback and throttled_callback.call_count > 0:
            pass
        for config_name, collection_docs in duplicate_data.items():
            if config_name in excluded:
                trace.debug(
                    "Excluding configuration from duplicate collection analysis",
                    tags=["analyzer", "exclude"],
                    config=config_name,
                )
                continue
            result.configurations_with_duplicate_collections[config_name] = list(collection_docs.keys())
            result.duplicate_collection_details[config_name] = collection_docs
        config_names = list(result.configurations_with_duplicate_collections.keys())
        if config_names:
            batch_results = backend.get_documents_by_configurations_summary_batch(config_names)
            result.config_documents = batch_results
            self._config_documents_cache = batch_results.copy()
        trace.debug(
            "Document summaries cached for global trash computation (batch)",
            tags=["analyzer", "cache", "batch"],
            configs_cached=len(result.config_documents),
            excluded_count=len(excluded),
        )
        self._analysis = result
        return result

    def get_analysis(self) -> Optional[AnalysisResult]:
        return self._analysis

    def invalidate(self) -> None:
        trace.debug(
            "Invalidating DuplicateCollectionAnalyzer cache",
            tags=["analyzer", "cache", "invalidate"],
            had_analysis=self._analysis is not None,
            cached_configs=len(self._config_documents_cache),
        )
        self._analysis = None
        self._config_documents_cache = {}

    def get_broken_configurations(self) -> List[str]:
        if self._analysis:
            return list(self._analysis.configurations_with_duplicate_collections.keys())
        return []

    def get_duplicate_collections(self, config_name: str) -> List[str]:
        if self._analysis and config_name in self._analysis.configurations_with_duplicate_collections:
            return self._analysis.configurations_with_duplicate_collections[config_name]
        return []

    def get_documents_for_collection_in_config(self, config_name: str, collection_name: str) -> List[str]:
        if self._analysis and config_name in self._analysis.duplicate_collection_details:
            details = self._analysis.duplicate_collection_details[config_name]
            if collection_name in details:
                return details[collection_name]
        return []

    def filter_configurations(self, configurations: List[ConfigurationInfo]) -> List[ConfigurationInfo]:
        if not self._analysis:
            return []
        broken = set(self._analysis.configurations_with_duplicate_collections.keys())
        return [c for c in configurations if c.name in broken]

    def filter_collections(self, collections: List[CollectionInfo]) -> List[CollectionInfo]:
        return collections

    def filter_documents_by_config(
        self, documents: List[DocumentSummary], config_name: Optional[str] = None
    ) -> List[DocumentSummary]:
        if not self._analysis or not config_name:
            return []
        duplicate_collections = set(self.get_duplicate_collections(config_name))
        return [d for d in documents if d.collection in duplicate_collections]

    def filter_versions(
        self, versions: List[VersionSummary], collection_name: Optional[str] = None, config_name: Optional[str] = None
    ) -> List[VersionSummary]:
        if not self._analysis or not config_name or (not collection_name):
            return []
        doc_ids = set(self.get_documents_for_collection_in_config(config_name, collection_name))
        return [v for v in versions if v.id in doc_ids]

    def get_status_suffix(self) -> str:
        return " [REPAIR MODE: Duplicate Collections]"


class TrashDuplicateCollectionAnalyzer(BaseAnalyzer):

    def __init__(self, source_analyzer: DuplicateCollectionAnalyzer) -> None:
        self._source = source_analyzer
        self._keeper_ids: Dict[Tuple[str, str], Set[str]] = {}

    @property
    def name(self) -> str:
        return "Trash Collections"

    @property
    def description(self) -> str:
        return "Show only duplicate collection docs to have config removed (excludes oldest)"

    def _compute_keepers(self, documents: List[DocumentSummary], config_name: str, collection_name: str) -> Set[str]:
        cache_key = (config_name, collection_name)
        if cache_key in self._keeper_ids:
            return self._keeper_ids[cache_key]
        analysis = self._source.get_analysis()
        if not analysis or config_name not in analysis.duplicate_collection_details:
            self._keeper_ids[cache_key] = set()
            return self._keeper_ids[cache_key]
        duplicate_details = analysis.duplicate_collection_details[config_name]
        if collection_name not in duplicate_details:
            self._keeper_ids[cache_key] = set()
            return self._keeper_ids[cache_key]
        doc_ids = duplicate_details[collection_name]
        if len(doc_ids) <= 1:
            self._keeper_ids[cache_key] = set()
            return self._keeper_ids[cache_key]
        doc_map: Dict[str, DocumentSummary] = {d.id: d for d in documents}
        best_doc_id: Optional[str] = None
        best_created: Optional[str] = None
        for doc_id in doc_ids:
            if doc_id not in doc_map:
                continue
            created = doc_map[doc_id].created
            if created is None:
                continue
            if best_created is None or created < best_created:
                best_created = created
                best_doc_id = doc_id
        keepers: Set[str] = set()
        if best_doc_id:
            keepers.add(best_doc_id)
            trace.debug(
                "Keeper identified for duplicate collection",
                tags=["analyzer", "trash-config"],
                config=config_name,
                collection=collection_name,
                keeper_id=best_doc_id,
                keeper_created=best_created,
                total_duplicates=len(doc_ids),
            )
        self._keeper_ids[cache_key] = keepers
        return keepers

    def filter_configurations(self, configurations: List[ConfigurationInfo]) -> List[ConfigurationInfo]:
        return self._source.filter_configurations(configurations)

    def filter_collections(self, collections: List[CollectionInfo]) -> List[CollectionInfo]:
        return self._source.filter_collections(collections)

    def filter_documents_by_config(
        self, documents: List[DocumentSummary], config_name: Optional[str] = None
    ) -> List[DocumentSummary]:
        duplicates = self._source.filter_documents_by_config(documents, config_name)
        if not config_name or not duplicates:
            return duplicates
        by_collection: Dict[str, List[DocumentSummary]] = defaultdict(list)
        for doc in duplicates:
            by_collection[doc.collection].append(doc)
        trash: List[DocumentSummary] = []
        for collection_name, coll_docs in by_collection.items():
            keepers = self._compute_keepers(duplicates, config_name, collection_name)
            trash.extend([d for d in coll_docs if d.id not in keepers])
        trace.debug(
            "Trash filter applied for config",
            tags=["analyzer", "trash-config"],
            config=config_name,
            total_duplicates=len(duplicates),
            trash=len(trash),
        )
        return trash

    def filter_versions(
        self, versions: List[VersionSummary], collection_name: Optional[str] = None, config_name: Optional[str] = None
    ) -> List[VersionSummary]:
        return self._source.filter_versions(versions, collection_name, config_name)

    def get_status_suffix(self) -> str:
        return " [REPAIR MODE: Trash Collections]"

    def get_source_analyzer(self) -> DuplicateCollectionAnalyzer:
        return self._source

    def invalidate(self) -> None:
        trace.debug(
            "Invalidating TrashDuplicateCollectionAnalyzer cache",
            tags=["analyzer", "cache", "invalidate"],
            cached_keys=len(self._keeper_ids),
        )
        self._keeper_ids = {}
        self._source.invalidate()


@dataclass
class GlobalTrashConfigItem:
    id: str
    config_name: str
    collection: str
    version: str
    created: Optional[str] = None
    assigned: Optional[str] = None
    is_deleted: bool = False
    is_readonly: bool = False

    def is_readonly_or_deleted(self) -> bool:
        return self.is_readonly or self.is_deleted


class GlobalTrashDuplicateCollectionAnalyzer:

    def __init__(self, source_analyzer: DuplicateCollectionAnalyzer) -> None:
        self._source = source_analyzer
        self._trash_items: Optional[List[GlobalTrashConfigItem]] = None
        self._computed = False

    @property
    def name(self) -> str:
        return "Global Trash Collections"

    @property
    def description(self) -> str:
        return "All duplicate collection docs to have config removed across all configurations"

    def compute_global_trash(self, backend: Any) -> List[GlobalTrashConfigItem]:
        if self._computed and self._trash_items is not None:
            return self._trash_items
        analysis = self._source.get_analysis()
        if not analysis:
            self._trash_items = []
            self._computed = True
            return self._trash_items
        all_trash: List[GlobalTrashConfigItem] = []
        for config_name in analysis.configurations_with_duplicate_collections.keys():
            documents = analysis.config_documents.get(config_name)
            if not documents:
                documents = backend.get_documents_by_configuration_summary(config_name)
                trace.debug(
                    "Cache miss for configuration, fetched from backend",
                    tags=["analyzer", "global-trash-config", "cache-miss"],
                    config=config_name,
                )
            duplicate_details = analysis.duplicate_collection_details.get(config_name, {})
            doc_map: Dict[str, DocumentSummary] = {d.id: d for d in documents}
            for collection_name, doc_ids in duplicate_details.items():
                if len(doc_ids) <= 1:
                    continue
                best_doc_id: Optional[str] = None
                best_created: Optional[str] = None
                for doc_id in doc_ids:
                    if doc_id not in doc_map:
                        continue
                    created = doc_map[doc_id].created
                    if created is None:
                        continue
                    if best_created is None or created < best_created:
                        best_created = created
                        best_doc_id = doc_id
                for doc_id in doc_ids:
                    if doc_id == best_doc_id:
                        continue
                    doc_summary = doc_map.get(doc_id)
                    if doc_summary:
                        assigned = doc_summary.get_assigned_for_config(config_name)
                        all_trash.append(
                            GlobalTrashConfigItem(
                                id=doc_id,
                                config_name=config_name,
                                collection=collection_name,
                                version=doc_summary.version,
                                created=doc_summary.created,
                                assigned=assigned,
                                is_deleted=doc_summary.is_deleted,
                                is_readonly=doc_summary.is_readonly,
                            )
                        )
            trace.debug(
                "Computed trash for configuration",
                tags=["analyzer", "global-trash-config"],
                config=config_name,
                duplicate_collections=len(duplicate_details),
                trash_count=sum((1 for t in all_trash if t.config_name == config_name)),
            )
        all_trash.sort(key=lambda x: (x.config_name, x.collection))
        self._trash_items = all_trash
        self._computed = True
        trace.info(
            "Global config trash computation complete",
            tags=["analyzer", "global-trash-config"],
            total_configurations=len(analysis.configurations_with_duplicate_collections),
            total_trash=len(all_trash),
        )
        return all_trash

    def get_trash_items(self) -> List[GlobalTrashConfigItem]:
        return self._trash_items or []

    def get_source_analyzer(self) -> DuplicateCollectionAnalyzer:
        return self._source

    def invalidate(self) -> None:
        trace.debug(
            "Invalidating GlobalTrashDuplicateCollectionAnalyzer cache",
            tags=["analyzer", "cache", "invalidate"],
            had_trash_items=self._trash_items is not None,
            trash_count=len(self._trash_items) if self._trash_items else 0,
        )
        self._trash_items = None
        self._computed = False
        self._source.invalidate()

    def get_status_suffix(self) -> str:
        return " [REPAIR MODE: Global Config Trash]"
