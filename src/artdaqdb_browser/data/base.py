"""
File: base.py
Purpose: Abstract base class for data backends.
Category: Data
Author: ArtdaqDB Browser Team
Depends: None
Exports: BatchOperationResult, DataBackend
Complexity: High | Lines: 734
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple
from ..models import (
    OTSDocument,
    ConfigurationInfo,
    CollectionInfo,
    ConfigurationAssignment,
    BookkeepingUpdate,
    DocumentSummary,
    VersionSummary,
)
from ..trace import trace


@dataclass
class BatchOperationResult:
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    failed_ids: List[str] = field(default_factory=list)
    skipped_ids: List[str] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)

    @property
    def total_processed(self) -> int:
        return self.success_count + self.failed_count

    @property
    def all_succeeded(self) -> bool:
        return self.failed_count == 0

    def __str__(self) -> str:
        parts = [f"{self.success_count} succeeded"]
        if self.failed_count:
            parts.append(f"{self.failed_count} failed")
        if self.skipped_count:
            parts.append(f"{self.skipped_count} skipped")
        return ", ".join(parts)


class DataBackend(ABC):

    def _apply_configuration_assignment(self, document: OTSDocument, config_name: str, timestamp: str) -> None:
        config_assignment = ConfigurationAssignment(name=config_name, assigned=timestamp)
        document.configurations.append(config_assignment)
        update_event = BookkeepingUpdate(
            event="addConfiguration", timestamp=timestamp, value={"name": config_name, "assigned": timestamp}
        )
        document.bookkeeping.updates.append(update_event)

    def _apply_configuration_removal(
        self, document: OTSDocument, config_name: str, timestamp: str
    ) -> Tuple[bool, Optional[str]]:
        original_assigned = None
        new_configurations = []
        for cfg in document.configurations:
            if cfg.name == config_name:
                original_assigned = cfg.assigned
            else:
                new_configurations.append(cfg)
        if original_assigned is None:
            return (False, None)
        document.configurations = new_configurations
        update_event = BookkeepingUpdate(
            event="removeConfiguration",
            timestamp=timestamp,
            value={"name": config_name, "assigned": original_assigned, "removed": timestamp},
        )
        document.bookkeeping.updates.append(update_event)
        trace.debug(
            "Bookkeeping entry created for removeConfiguration",
            tags=["bookkeeping", "mutation"],
            document_id=document.id,
            config_name=config_name,
            updates_count=len(document.bookkeeping.updates),
            event=update_event.event,
        )
        return (True, original_assigned)

    def _apply_soft_delete(self, document: OTSDocument) -> None:
        document.bookkeeping.isdeleted = True
        update_event = BookkeepingUpdate(
            event="markDeleted",
            timestamp=datetime.now().isoformat(),
            value={"name": "deleted", "assigned": datetime.now().isoformat()},
        )
        document.bookkeeping.updates.append(update_event)

    @abstractmethod
    def get_document_by_id(self, document_id: str) -> Optional[OTSDocument]:
        pass

    @abstractmethod
    def get_all_documents(self) -> List[OTSDocument]:
        pass

    @abstractmethod
    def get_documents_by_collection(self, collection_name: str) -> List[OTSDocument]:
        pass

    @abstractmethod
    def get_documents_by_configuration(self, config_name: str) -> List[OTSDocument]:
        pass

    @abstractmethod
    def get_document_versions(self, collection_name: str) -> List[OTSDocument]:
        pass

    @abstractmethod
    def list_configurations(self) -> List[str]:
        pass

    @abstractmethod
    def list_collections(self) -> List[str]:
        pass

    @abstractmethod
    def get_configuration_info(self) -> List[ConfigurationInfo]:
        pass

    @abstractmethod
    def get_collection_info(self) -> List[CollectionInfo]:
        pass

    @abstractmethod
    def update_document(self, document: OTSDocument) -> bool:
        pass

    @abstractmethod
    def delete_document(self, document_id: str, soft_delete: bool = True) -> bool:
        pass

    @abstractmethod
    def assign_configuration(self, document_id: str, config_name: str, timestamp: str) -> bool:
        pass

    @abstractmethod
    def remove_configuration_assignment(self, document_id: str, config_name: str, timestamp: str) -> bool:
        pass

    @abstractmethod
    def get_documents_by_configuration_summary(self, config_name: str) -> List[DocumentSummary]:
        pass

    @abstractmethod
    def get_documents_by_configurations_summary_batch(
        self, config_names: List[str]
    ) -> Dict[str, List[DocumentSummary]]:
        pass

    @abstractmethod
    def get_document_versions_summary(self, collection_name: str) -> List[VersionSummary]:
        pass

    @abstractmethod
    def get_document_versions_summary_batch(self, collection_names: List[str]) -> Dict[str, List[VersionSummary]]:
        pass

    @abstractmethod
    def list_configurations_optimized(self) -> List[str]:
        pass

    @abstractmethod
    def list_collections_optimized(self) -> List[str]:
        pass

    @abstractmethod
    def get_configuration_info_optimized(self) -> List[ConfigurationInfo]:
        pass

    @abstractmethod
    def get_collection_info_optimized(self) -> List[CollectionInfo]:
        pass

    @abstractmethod
    def get_document_by_id_direct(
        self, document_id: str, collection_name: Optional[str] = None
    ) -> Optional[OTSDocument]:
        pass

    def get_configurations_by_document(self, collection_name: str, version: str) -> List[str]:
        docs = self.get_documents_by_collection(collection_name)
        for doc in docs:
            if doc.version == version:
                return doc.get_configuration_names()
        return []

    def find_duplicate_versions(self) -> Dict[str, Dict[str, List[str]]]:
        from collections import defaultdict

        result: Dict[str, Dict[str, List[str]]] = {}
        collections = self.list_collections()
        for collection_name in collections:
            versions = self.get_document_versions_summary(collection_name)
            version_groups: Dict[str, List[str]] = defaultdict(list)
            for v in versions:
                version_groups[v.version].append(v.id)
            duplicates = {ver: ids for (ver, ids) in version_groups.items() if len(ids) > 1}
            if duplicates:
                result[collection_name] = duplicates
        return result

    def find_duplicate_collections_in_configs(
        self, progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Dict[str, List[str]]]:
        from collections import defaultdict

        result: Dict[str, Dict[str, List[str]]] = {}
        configs = self.list_configurations()
        total = len(configs)
        for i, config_name in enumerate(configs):
            if progress_callback:
                progress_callback(i, total)
            documents = self.get_documents_by_configuration_summary(config_name)
            collection_groups: Dict[str, List[str]] = defaultdict(list)
            for doc in documents:
                collection_groups[doc.collection].append(doc.id)
            duplicates = {coll: ids for (coll, ids) in collection_groups.items() if len(ids) > 1}
            if duplicates:
                result[config_name] = duplicates
        if progress_callback:
            progress_callback(total, total)
        return result

    def batch_delete_documents(
        self,
        document_ids: List[str],
        soft_delete: bool = True,
        skip_protected: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> BatchOperationResult:
        result = BatchOperationResult()
        total = len(document_ids)
        for i, doc_id in enumerate(document_ids):
            if progress_callback:
                progress_callback(i, total)
            try:
                if skip_protected:
                    doc = self.get_document_by_id(doc_id)
                    if doc and doc.is_readonly_or_deleted():
                        result.skipped_count += 1
                        result.skipped_ids.append(doc_id)
                        continue
                success = self.delete_document(doc_id, soft_delete)
                if success:
                    result.success_count += 1
                else:
                    result.failed_count += 1
                    result.failed_ids.append(doc_id)
                    result.errors[doc_id] = "Delete operation returned False"
            except Exception as e:
                result.failed_count += 1
                result.failed_ids.append(doc_id)
                result.errors[doc_id] = str(e)
        if progress_callback:
            progress_callback(total, total)
        return result

    def batch_remove_configurations(
        self,
        items: List[Tuple[str, str]],
        timestamp: str,
        skip_protected: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> BatchOperationResult:
        result = BatchOperationResult()
        total = len(items)
        for i, (doc_id, config_name) in enumerate(items):
            if progress_callback:
                progress_callback(i, total)
            try:
                if skip_protected:
                    doc = self.get_document_by_id(doc_id)
                    if doc and doc.is_readonly_or_deleted():
                        result.skipped_count += 1
                        result.skipped_ids.append(doc_id)
                        continue
                success = self.remove_configuration_assignment(doc_id, config_name, timestamp)
                if success:
                    result.success_count += 1
                else:
                    result.failed_count += 1
                    result.failed_ids.append(doc_id)
                    result.errors[doc_id] = f"Failed to remove config '{config_name}'"
            except Exception as e:
                result.failed_count += 1
                result.failed_ids.append(doc_id)
                result.errors[doc_id] = str(e)
        if progress_callback:
            progress_callback(total, total)
        return result

    def delete_document_with_info(
        self, document_id: str, collection_name: str, soft_delete: bool = True
    ) -> Tuple[bool, Optional[OTSDocument]]:
        doc = self.get_document_by_id_direct(document_id, collection_name)
        if doc is None:
            return (False, None)
        success = self.delete_document(document_id, soft_delete)
        return (success, doc)
