"""
File: filesystem.py
Purpose: Filesystem backend for reading JSON files.
Category: Data
Author: ArtdaqDB Browser Team
Depends: None
Exports: FilesystemBackend
Complexity: High | Lines: 680
"""

import json
from pathlib import Path
from typing import Callable, Dict, List, Optional
from ..models import OTSDocument, ConfigurationInfo, CollectionInfo, DocumentSummary, VersionSummary
from ..trace import trace
from .base import DataBackend
from .fs_index import FilesystemIndexManager, DocumentMetadata


class FilesystemBackend(DataBackend):

    def __init__(self, base_path: str, cache_dir: Optional[Path] = None):
        self.base_path = Path(base_path)
        if not self.base_path.exists():
            raise ValueError(f"Base path does not exist: {base_path}")
        if not self.base_path.is_dir():
            raise ValueError(f"Base path is not a directory: {base_path}")
        self._index_manager = FilesystemIndexManager(self.base_path, cache_dir)
        self._document_cache: Dict[str, OTSDocument] = {}
        self._document_cache_max_size = 100

    @property
    def _index(self):
        return self._index_manager.index

    def _load_full_document(self, file_path: str) -> Optional[OTSDocument]:
        path = Path(file_path)
        if not path.exists():
            return None
        try:
            with open(path, "r") as f:
                data = json.load(f)
            return OTSDocument(**data)
        except Exception as e:
            trace.warn(
                "Failed to load document from filesystem",
                tags=["filesystem", "error"],
                file_path=file_path,
                error=str(e),
            )
            return None

    def _get_cached_document(self, doc_id: str, file_path: str) -> Optional[OTSDocument]:
        if doc_id in self._document_cache:
            return self._document_cache[doc_id]
        doc = self._load_full_document(file_path)
        if doc:
            if len(self._document_cache) >= self._document_cache_max_size:
                oldest_key = next(iter(self._document_cache))
                del self._document_cache[oldest_key]
            self._document_cache[doc_id] = doc
        return doc

    def get_document_by_id(self, document_id: str) -> Optional[OTSDocument]:
        metadata = self._index.documents.get(document_id)
        if not metadata:
            return None
        return self._get_cached_document(document_id, metadata.file_path)

    def get_all_documents(self) -> List[OTSDocument]:
        trace.warn(
            "Loading all documents from filesystem (expensive operation)",
            tags=["filesystem", "query", "perf"],
            document_count=len(self._index.documents),
        )
        documents = []
        for metadata in self._index.documents.values():
            doc = self._load_full_document(metadata.file_path)
            if doc:
                documents.append(doc)
        trace.debug("All documents loaded from filesystem", tags=["filesystem", "query"], loaded_count=len(documents))
        return documents

    def get_documents_by_collection(self, collection_name: str) -> List[OTSDocument]:
        metadata_list = self._index.get_docs_by_collection(collection_name)
        documents = []
        for metadata in metadata_list:
            doc = self._get_cached_document(metadata.id, metadata.file_path)
            if doc:
                documents.append(doc)
        return documents

    def get_documents_by_configuration(self, config_name: str) -> List[OTSDocument]:
        metadata_list = self._index.get_docs_by_config(config_name)
        documents = []
        for metadata in metadata_list:
            doc = self._get_cached_document(metadata.id, metadata.file_path)
            if doc:
                documents.append(doc)
        return documents

    def get_document_versions(self, collection_name: str) -> List[OTSDocument]:
        docs = self.get_documents_by_collection(collection_name)
        return sorted(docs, key=lambda d: int(d.version) if d.version.isdigit() else 0)

    def list_configurations(self) -> List[str]:
        return self._index.get_configurations()

    def list_collections(self) -> List[str]:
        return self._index.get_collections()

    def get_configuration_info(self) -> List[ConfigurationInfo]:
        from collections import defaultdict

        config_data: Dict[str, Dict] = defaultdict(lambda: {"collections": set(), "last_assigned": ""})
        for metadata in self._index.documents.values():
            for config_name in metadata.config_names:
                config_data[config_name]["collections"].add(metadata.collection)
                if metadata.created:
                    current = config_data[config_name]["last_assigned"]
                    if not current or metadata.created > current:
                        config_data[config_name]["last_assigned"] = metadata.created
        result = [
            ConfigurationInfo(
                name=config_name,
                collection_count=len(data["collections"]),
                last_assigned=data["last_assigned"],
                collections=sorted(data["collections"]),
            )
            for (config_name, data) in config_data.items()
        ]
        result.sort(key=lambda c: c.last_assigned, reverse=True)
        return result

    def get_collection_info(self) -> List[CollectionInfo]:
        from collections import defaultdict

        collection_data: Dict[str, List[DocumentMetadata]] = defaultdict(list)
        for metadata in self._index.documents.values():
            collection_data[metadata.collection].append(metadata)
        result = []
        for collection_name, docs in collection_data.items():
            sorted_docs = sorted(docs, key=lambda d: int(d.version) if d.version.isdigit() else 0, reverse=True)
            latest = sorted_docs[0] if sorted_docs else None
            result.append(
                CollectionInfo(
                    name=collection_name,
                    version_count=len(docs),
                    latest_version=latest.version if latest else None,
                    last_updated=latest.created if latest else None,
                )
            )
        result.sort(key=lambda c: c.name)
        return result

    def update_document(self, document: OTSDocument) -> bool:
        trace.debug(
            "Updating document on filesystem",
            tags=["filesystem", "mutation"],
            document_id=document.id,
            collection=document.collection,
        )
        try:
            collection_dir = self.base_path / document.collection
            collection_dir.mkdir(exist_ok=True)
            file_path = collection_dir / f"{document.id}.json"
            with open(file_path, "w") as f:
                json.dump(document.model_dump(by_alias=True), f, indent=4)
            self._document_cache[document.id] = document
            self._index_manager.refresh_document(file_path)
            trace.info(
                "Document updated on filesystem",
                tags=["filesystem", "mutation"],
                document_id=document.id,
                file_path=str(file_path),
            )
            return True
        except Exception as e:
            trace.error(
                "Failed to update document on filesystem",
                tags=["filesystem", "mutation", "error"],
                exception=e,
                document_id=document.id,
            )
            return False

    def delete_document(self, document_id: str, soft_delete: bool = True) -> bool:
        trace.debug(
            "Delete document requested",
            tags=["filesystem", "mutation"],
            document_id=document_id,
            soft_delete=soft_delete,
        )
        try:
            metadata = self._index.documents.get(document_id)
            if not metadata:
                trace.warn(
                    "Delete failed: document not found in index",
                    tags=["filesystem", "mutation"],
                    document_id=document_id,
                )
                return False
            file_path = Path(metadata.file_path)
            if soft_delete:
                doc = self._get_cached_document(document_id, metadata.file_path)
                if not doc:
                    return False
                self._apply_soft_delete(doc)
                return self.update_document(doc)
            else:
                if file_path.exists():
                    file_path.unlink()
                    trace.info(
                        "Document permanently deleted from filesystem",
                        tags=["filesystem", "mutation"],
                        document_id=document_id,
                        file_path=str(file_path),
                    )
                self._document_cache.pop(document_id, None)
                self._index_manager.refresh_document(file_path)
                return True
        except Exception as e:
            trace.error(
                "Failed to delete document from filesystem",
                tags=["filesystem", "mutation", "error"],
                exception=e,
                document_id=document_id,
            )
            return False

    def assign_configuration(self, document_id: str, config_name: str, timestamp: str) -> bool:
        trace.debug(
            "Assigning configuration to document",
            tags=["filesystem", "mutation"],
            document_id=document_id,
            config_name=config_name,
        )
        try:
            metadata = self._index.documents.get(document_id)
            if not metadata:
                trace.warn(
                    "Configuration assignment failed: document not found",
                    tags=["filesystem", "mutation"],
                    document_id=document_id,
                    config_name=config_name,
                )
                return False
            doc = self._get_cached_document(document_id, metadata.file_path)
            if not doc:
                return False
            self._apply_configuration_assignment(doc, config_name, timestamp)
            success = self.update_document(doc)
            if success:
                trace.info(
                    "Configuration assigned to document successfully",
                    tags=["filesystem", "mutation"],
                    document_id=document_id,
                    config_name=config_name,
                )
            return success
        except Exception as e:
            trace.error(
                "Failed to assign configuration to document",
                tags=["filesystem", "mutation", "error"],
                exception=e,
                document_id=document_id,
                config_name=config_name,
            )
            return False

    def remove_configuration_assignment(self, document_id: str, config_name: str, timestamp: str) -> bool:
        trace.debug(
            "Removing configuration from document",
            tags=["filesystem", "mutation"],
            document_id=document_id,
            config_name=config_name,
        )
        try:
            metadata = self._index.documents.get(document_id)
            if not metadata:
                trace.warn(
                    "Configuration removal failed: document not found",
                    tags=["filesystem", "mutation"],
                    document_id=document_id,
                    config_name=config_name,
                )
                return False
            doc = self._get_cached_document(document_id, metadata.file_path)
            if not doc:
                return False
            (success_removal, original_assigned) = self._apply_configuration_removal(doc, config_name, timestamp)
            if not success_removal:
                trace.warn(
                    "Configuration removal failed: configuration not found in document",
                    tags=["filesystem", "mutation"],
                    document_id=document_id,
                    config_name=config_name,
                )
                return False
            success = self.update_document(doc)
            if success:
                trace.info(
                    "Configuration removed from document successfully",
                    tags=["filesystem", "mutation"],
                    document_id=document_id,
                    config_name=config_name,
                    original_assigned=original_assigned,
                )
            return success
        except Exception as e:
            trace.error(
                "Failed to remove configuration from document",
                tags=["filesystem", "mutation", "error"],
                exception=e,
                document_id=document_id,
                config_name=config_name,
            )
            return False

    def get_documents_by_configuration_summary(self, config_name: str) -> List[DocumentSummary]:
        from ..models import ConfigurationSummaryInfo

        metadata_list = self._index.get_docs_by_config(config_name)
        results = []
        for m in metadata_list:
            config_assignments = []
            for cfg in m.config_assignments:
                if cfg.name == config_name:
                    config_assignments.append(ConfigurationSummaryInfo(name=cfg.name, assigned=cfg.assigned))
            results.append(
                DocumentSummary(
                    id=m.id,
                    collection=m.collection,
                    version=m.version,
                    created=m.created,
                    is_deleted=m.is_deleted,
                    is_readonly=m.is_readonly,
                    config_assignments=config_assignments,
                )
            )
        return results

    def get_documents_by_configurations_summary_batch(
        self, config_names: List[str]
    ) -> Dict[str, List[DocumentSummary]]:
        from ..models import ConfigurationSummaryInfo

        if not config_names:
            return {}
        results: Dict[str, List[DocumentSummary]] = {}
        for config_name in config_names:
            metadata_list = self._index.get_docs_by_config(config_name)
            docs = []
            for m in metadata_list:
                config_assignments = []
                for cfg in m.config_assignments:
                    if cfg.name == config_name:
                        config_assignments.append(ConfigurationSummaryInfo(name=cfg.name, assigned=cfg.assigned))
                docs.append(
                    DocumentSummary(
                        id=m.id,
                        collection=m.collection,
                        version=m.version,
                        created=m.created,
                        is_deleted=m.is_deleted,
                        is_readonly=m.is_readonly,
                        config_assignments=config_assignments,
                    )
                )
            if docs:
                results[config_name] = docs
        trace.debug(
            "Batch document summaries retrieved from index",
            tags=["filesystem", "query", "batch"],
            config_count=len(config_names),
            configs_with_docs=len(results),
        )
        return results

    def get_document_versions_summary(self, collection_name: str) -> List[VersionSummary]:
        metadata_list = self._index.get_docs_by_collection(collection_name)
        results = [
            VersionSummary(
                id=m.id,
                version=m.version,
                created=m.created,
                config_count=len(m.config_names),
                is_deleted=m.is_deleted,
                is_readonly=m.is_readonly,
            )
            for m in metadata_list
        ]
        results.sort(key=lambda x: int(x.version) if x.version.isdigit() else 0, reverse=True)
        return results

    def get_document_versions_summary_batch(self, collection_names: List[str]) -> Dict[str, List[VersionSummary]]:
        if not collection_names:
            return {}
        results: Dict[str, List[VersionSummary]] = {}
        for collection_name in collection_names:
            metadata_list = self._index.get_docs_by_collection(collection_name)
            versions = [
                VersionSummary(
                    id=m.id,
                    version=m.version,
                    created=m.created,
                    config_count=len(m.config_names),
                    is_deleted=m.is_deleted,
                    is_readonly=m.is_readonly,
                )
                for m in metadata_list
            ]
            versions.sort(key=lambda x: int(x.version) if x.version.isdigit() else 0, reverse=True)
            if versions:
                results[collection_name] = versions
        trace.debug(
            "Batch version summaries retrieved from index",
            tags=["filesystem", "query", "batch"],
            collection_count=len(collection_names),
            collections_with_versions=len(results),
        )
        return results

    def list_configurations_optimized(self) -> List[str]:
        return self.list_configurations()

    def list_collections_optimized(self) -> List[str]:
        return self.list_collections()

    def get_configuration_info_optimized(self) -> List[ConfigurationInfo]:
        return self.get_configuration_info()

    def get_collection_info_optimized(self) -> List[CollectionInfo]:
        return self.get_collection_info()

    def get_document_by_id_direct(
        self, document_id: str, collection_name: Optional[str] = None
    ) -> Optional[OTSDocument]:
        metadata = self._index.documents.get(document_id)
        if metadata:
            return self._get_cached_document(document_id, metadata.file_path)
        if collection_name:
            file_path = self.base_path / collection_name / f"{document_id}.json"
            if file_path.exists():
                return self._load_full_document(str(file_path))
        return None

    def find_duplicate_versions(self) -> Dict[str, Dict[str, List[str]]]:
        return self._index.find_duplicate_versions()

    def find_duplicate_collections_in_configs(
        self, progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Dict[str, List[str]]]:
        return self._index.find_duplicate_collections_in_configs(progress_callback)

    def reload(self) -> None:
        trace.info("Reloading filesystem index", tags=["filesystem", "lifecycle"])
        self._document_cache.clear()
        self._index_manager.invalidate()

    def clear_document_cache(self) -> None:
        trace.debug(
            "Clearing filesystem document cache", tags=["filesystem", "cache"], cache_size=len(self._document_cache)
        )
        self._document_cache.clear()
