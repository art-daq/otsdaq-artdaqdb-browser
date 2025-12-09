"""
File: duplicate_versions.py
Purpose: Analyzers for detecting and handling duplicate version issues.
Category: Analyzer
Author: ArtdaqDB Browser Team
Depends: None
Exports: DuplicateVersionAnalyzer, TrashDuplicateVersionAnalyzer, GlobalTrashItem, GlobalTrashDuplicateVersionAnalyzer
Complexity: High | Lines: 513
"""

from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..base import DataBackend
from ...models import DocumentSummary, VersionSummary, ConfigurationInfo, CollectionInfo
from ...trace import trace
from .base import BaseAnalyzer, AnalysisResult


class DuplicateVersionAnalyzer(BaseAnalyzer):

    def __init__(self) -> None:
        self._analysis: Optional[AnalysisResult] = None
        self._all_versions_cache: Dict[str, List[VersionSummary]] = {}

    @property
    def name(self) -> str:
        return "Duplicate Versions"

    @property
    def description(self) -> str:
        return "Find collections with duplicate version numbers"

    def analyze(self, backend: Any, excluded_collections: Optional[List[str]] = None) -> AnalysisResult:
        result = AnalysisResult()
        excluded = set(excluded_collections or [])
        duplicate_data = backend.find_duplicate_versions()
        for collection_name, version_docs in duplicate_data.items():
            if collection_name in excluded:
                trace.debug(
                    "Excluding collection from duplicate version analysis",
                    tags=["analyzer", "exclude"],
                    collection=collection_name,
                )
                continue
            result.collections_with_duplicate_versions[collection_name] = list(version_docs.keys())
            result.duplicate_version_details[collection_name] = version_docs
        collection_names = list(result.collections_with_duplicate_versions.keys())
        if collection_names:
            batch_results = backend.get_document_versions_summary_batch(collection_names)
            result.collection_versions = batch_results
            self._all_versions_cache = batch_results.copy()
        trace.debug(
            "Version summaries cached for global trash computation (parallel batch)",
            tags=["analyzer", "cache", "batch"],
            collections_cached=len(result.collection_versions),
            excluded_count=len(excluded),
        )
        self._analysis = result
        return result

    def get_analysis(self) -> Optional[AnalysisResult]:
        return self._analysis

    def invalidate(self) -> None:
        trace.debug(
            "Invalidating DuplicateVersionAnalyzer cache",
            tags=["analyzer", "cache", "invalidate"],
            had_analysis=self._analysis is not None,
            cached_collections=len(self._all_versions_cache),
        )
        self._analysis = None
        self._all_versions_cache = {}

    def get_broken_collections(self) -> List[str]:
        if self._analysis:
            return list(self._analysis.collections_with_duplicate_versions.keys())
        return []

    def get_duplicate_versions(self, collection_name: str) -> List[str]:
        if self._analysis and collection_name in self._analysis.collections_with_duplicate_versions:
            return self._analysis.collections_with_duplicate_versions[collection_name]
        return []

    def filter_configurations(self, configurations: List[ConfigurationInfo]) -> List[ConfigurationInfo]:
        return configurations

    def filter_collections(self, collections: List[CollectionInfo]) -> List[CollectionInfo]:
        if not self._analysis:
            return []
        broken = set(self._analysis.collections_with_duplicate_versions.keys())
        return [c for c in collections if c.name in broken]

    def filter_documents_by_config(
        self, documents: List[DocumentSummary], config_name: Optional[str] = None
    ) -> List[DocumentSummary]:
        return documents

    def filter_versions(
        self, versions: List[VersionSummary], collection_name: Optional[str] = None, config_name: Optional[str] = None
    ) -> List[VersionSummary]:
        if not self._analysis or not collection_name:
            return []
        duplicate_versions = set(self.get_duplicate_versions(collection_name))
        return [v for v in versions if v.version in duplicate_versions]

    def get_status_suffix(self) -> str:
        return " [REPAIR MODE: Duplicate Versions]"


class TrashDuplicateVersionAnalyzer(BaseAnalyzer):

    def __init__(self, source_analyzer: DuplicateVersionAnalyzer) -> None:
        self._source = source_analyzer
        self._keeper_ids: Dict[str, Set[str]] = {}

    @property
    def name(self) -> str:
        return "Trash Versions"

    @property
    def description(self) -> str:
        return "Show only duplicate versions to be deleted (excludes oldest)"

    def _compute_keepers(self, versions: List[VersionSummary], collection_name: str) -> Set[str]:
        if collection_name in self._keeper_ids:
            return self._keeper_ids[collection_name]
        analysis = self._source.get_analysis()
        if not analysis or collection_name not in analysis.duplicate_version_details:
            self._keeper_ids[collection_name] = set()
            return self._keeper_ids[collection_name]
        duplicate_details = analysis.duplicate_version_details[collection_name]
        version_map: Dict[str, VersionSummary] = {v.id: v for v in versions}
        keepers: Set[str] = set()
        for version_num, doc_ids in duplicate_details.items():
            if len(doc_ids) <= 1:
                continue
            best_doc_id: Optional[str] = None
            best_created: Optional[str] = None
            for doc_id in doc_ids:
                if doc_id not in version_map:
                    continue
                created = version_map[doc_id].created
                if created is None:
                    continue
                if best_created is None or created < best_created:
                    best_created = created
                    best_doc_id = doc_id
            if best_doc_id:
                keepers.add(best_doc_id)
                trace.debug(
                    "Keeper identified for duplicate version",
                    tags=["analyzer", "trash"],
                    collection=collection_name,
                    version=version_num,
                    keeper_id=best_doc_id,
                    keeper_created=best_created,
                    total_duplicates=len(doc_ids),
                )
        self._keeper_ids[collection_name] = keepers
        return keepers

    def filter_configurations(self, configurations: List[ConfigurationInfo]) -> List[ConfigurationInfo]:
        return self._source.filter_configurations(configurations)

    def filter_collections(self, collections: List[CollectionInfo]) -> List[CollectionInfo]:
        return self._source.filter_collections(collections)

    def filter_documents_by_config(
        self, documents: List[DocumentSummary], config_name: Optional[str] = None
    ) -> List[DocumentSummary]:
        return self._source.filter_documents_by_config(documents, config_name)

    def filter_versions(
        self, versions: List[VersionSummary], collection_name: Optional[str] = None, config_name: Optional[str] = None
    ) -> List[VersionSummary]:
        duplicates = self._source.filter_versions(versions, collection_name, config_name)
        if not collection_name or not duplicates:
            return duplicates
        keepers = self._compute_keepers(versions, collection_name)
        trash = [v for v in duplicates if v.id not in keepers]
        trace.debug(
            "Trash filter applied",
            tags=["analyzer", "trash"],
            collection=collection_name,
            total_duplicates=len(duplicates),
            keepers=len(keepers),
            trash=len(trash),
        )
        return trash

    def get_status_suffix(self) -> str:
        return " [REPAIR MODE: Trash Versions]"

    def get_source_analyzer(self) -> DuplicateVersionAnalyzer:
        return self._source

    def invalidate(self) -> None:
        trace.debug(
            "Invalidating TrashDuplicateVersionAnalyzer cache",
            tags=["analyzer", "cache", "invalidate"],
            cached_collections=len(self._keeper_ids),
        )
        self._keeper_ids = {}
        self._source.invalidate()


@dataclass
class GlobalTrashItem:
    id: str
    collection: str
    version: str
    created: Optional[str] = None
    is_deleted: bool = False
    is_readonly: bool = False

    def is_readonly_or_deleted(self) -> bool:
        return self.is_readonly or self.is_deleted


class GlobalTrashDuplicateVersionAnalyzer:

    def __init__(self, source_analyzer: DuplicateVersionAnalyzer) -> None:
        self._source = source_analyzer
        self._trash_items: Optional[List[GlobalTrashItem]] = None
        self._computed = False

    @property
    def name(self) -> str:
        return "Global Trash Versions"

    @property
    def description(self) -> str:
        return "All duplicate versions to be deleted across all collections"

    def compute_global_trash(self, backend: Any) -> List[GlobalTrashItem]:
        if self._computed and self._trash_items is not None:
            return self._trash_items
        analysis = self._source.get_analysis()
        if not analysis:
            self._trash_items = []
            self._computed = True
            return self._trash_items
        all_trash: List[GlobalTrashItem] = []
        for collection_name in analysis.collections_with_duplicate_versions.keys():
            versions = analysis.collection_versions.get(collection_name)
            if not versions:
                versions = backend.get_document_versions_summary(collection_name)
                trace.debug(
                    "Cache miss for collection, fetched from backend",
                    tags=["analyzer", "global-trash", "cache-miss"],
                    collection=collection_name,
                )
            duplicate_details = analysis.duplicate_version_details.get(collection_name, {})
            version_map: Dict[str, VersionSummary] = {v.id: v for v in versions}
            for version_num, doc_ids in duplicate_details.items():
                if len(doc_ids) <= 1:
                    continue
                best_doc_id: Optional[str] = None
                best_created: Optional[str] = None
                for doc_id in doc_ids:
                    if doc_id not in version_map:
                        continue
                    created = version_map[doc_id].created
                    if created is None:
                        continue
                    if best_created is None or created < best_created:
                        best_created = created
                        best_doc_id = doc_id
                for doc_id in doc_ids:
                    if doc_id == best_doc_id:
                        continue
                    vs = version_map.get(doc_id)
                    if vs:
                        all_trash.append(
                            GlobalTrashItem(
                                id=doc_id,
                                collection=collection_name,
                                version=version_num,
                                created=vs.created,
                                is_deleted=vs.is_deleted,
                                is_readonly=vs.is_readonly,
                            )
                        )
            trace.debug(
                "Computed trash for collection",
                tags=["analyzer", "global-trash"],
                collection=collection_name,
                duplicate_versions=len(duplicate_details),
                trash_count=sum((1 for t in all_trash if t.collection == collection_name)),
            )
        all_trash.sort(key=lambda x: (x.collection, x.version))
        self._trash_items = all_trash
        self._computed = True
        trace.info(
            "Global trash computation complete",
            tags=["analyzer", "global-trash"],
            total_collections=len(analysis.collections_with_duplicate_versions),
            total_trash=len(all_trash),
        )
        return all_trash

    def get_trash_items(self) -> List[GlobalTrashItem]:
        return self._trash_items or []

    def get_source_analyzer(self) -> DuplicateVersionAnalyzer:
        return self._source

    def invalidate(self) -> None:
        trace.debug(
            "Invalidating GlobalTrashDuplicateVersionAnalyzer cache",
            tags=["analyzer", "cache", "invalidate"],
            had_trash_items=self._trash_items is not None,
            trash_count=len(self._trash_items) if self._trash_items else 0,
        )
        self._trash_items = None
        self._computed = False
        self._source.invalidate()

    def get_status_suffix(self) -> str:
        return " [REPAIR MODE: Global Trash]"
