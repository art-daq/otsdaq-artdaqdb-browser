"""
File: cached.py
Purpose: Cached backend wrapper for data access with caching layer.
Category: Data
Author: ArtdaqDB Browser Team
Depends: None
Exports: CachedBackend
Complexity: High | Lines: 662
"""

from typing import Callable, Dict, List, Optional, Tuple
from ..trace import trace
from .base import DataBackend, BatchOperationResult
from ..models import OTSDocument, ConfigurationInfo, CollectionInfo, DocumentSummary, VersionSummary
from ..cache import CacheManager


class CachedBackend(DataBackend):

    def __init__(self, backend: DataBackend, cache: CacheManager):
        self._backend = backend
        self._cache = cache
        trace.debug(
            "Cached backend wrapper initialized",
            tags=["cache", "lifecycle"],
            wrapped_backend=backend.__class__.__name__,
        )

    @property
    def cache(self) -> CacheManager:
        return self._cache

    def reload(self) -> None:
        trace.info("Reloading cached backend data", tags=["cache", "lifecycle"])
        if hasattr(self._backend, "reload"):
            self._backend.reload()
        self._cache.clear()

    def get_document_by_id(self, document_id: str) -> Optional[OTSDocument]:
        cache_key = f"doc:{document_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        doc = self._backend.get_document_by_id(document_id)
        if doc is not None:
            self._cache.set(cache_key, doc)
        return doc

    def get_all_documents(self) -> List[OTSDocument]:
        cache_key = "all_documents"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        docs = self._backend.get_all_documents()
        self._cache.set(cache_key, docs)
        return docs

    def get_documents_by_collection(self, collection_name: str) -> List[OTSDocument]:
        cache_key = f"collection_docs:{collection_name}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        docs = self._backend.get_documents_by_collection(collection_name)
        self._cache.set(cache_key, docs)
        return docs

    def get_documents_by_configuration(self, config_name: str) -> List[OTSDocument]:
        cache_key = f"config_docs:{config_name}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        docs = self._backend.get_documents_by_configuration(config_name)
        self._cache.set(cache_key, docs)
        return docs

    def get_document_versions(self, collection_name: str) -> List[OTSDocument]:
        cache_key = f"versions:{collection_name}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        docs = self._backend.get_document_versions(collection_name)
        self._cache.set(cache_key, docs)
        return docs

    def list_configurations(self) -> List[str]:
        cached = self._cache.get_configurations()
        if cached is not None:
            return cached
        configs = self._backend.list_configurations()
        self._cache.set_configurations(configs)
        return configs

    def list_collections(self) -> List[str]:
        cached = self._cache.get_collections()
        if cached is not None:
            return cached
        collections = self._backend.list_collections()
        self._cache.set_collections(collections)
        return collections

    def get_configuration_info(self) -> List[ConfigurationInfo]:
        cached = self._cache.get_configuration_info()
        if cached is not None:
            return [ConfigurationInfo(**c) if isinstance(c, dict) else c for c in cached]
        info = self._backend.get_configuration_info()
        self._cache.set_configuration_info([c.model_dump() for c in info])
        return info

    def get_collection_info(self) -> List[CollectionInfo]:
        cached = self._cache.get_collection_info()
        if cached is not None:
            return [CollectionInfo(**c) if isinstance(c, dict) else c for c in cached]
        info = self._backend.get_collection_info()
        self._cache.set_collection_info([c.model_dump() for c in info])
        return info

    def update_document(self, document: OTSDocument) -> bool:
        trace.debug(
            "Updating document - will invalidate cache",
            tags=["cache", "mutation", "update"],
            document_id=document.id,
            collection=document.collection,
        )
        result = self._backend.update_document(document)
        if result:
            has_configs = bool(document.configurations)
            config_names = None
            if document.configurations:
                config_names = [c.name for c in document.configurations]
            self._invalidate_document_cache(
                document.id, document.collection, has_configs, configuration_names=config_names
            )
            trace.info(
                "Document updated - cache invalidated",
                tags=["cache", "mutation", "update"],
                document_id=document.id,
                collection=document.collection,
                has_configurations=has_configs,
                configuration_names=config_names,
            )
        return result

    def delete_document(self, document_id: str, soft_delete: bool = True) -> bool:
        trace.debug(
            "Deleting document - will invalidate cache",
            tags=["cache", "mutation", "delete"],
            document_id=document_id,
            soft_delete=soft_delete,
        )
        doc = self._backend.get_document_by_id(document_id)
        result = self._backend.delete_document(document_id, soft_delete)
        if result and doc:
            has_configs = bool(doc.configurations)
            config_names = None
            if doc.configurations:
                config_names = [c.name for c in doc.configurations]
            self._invalidate_document_cache(document_id, doc.collection, has_configs, configuration_names=config_names)
            trace.info(
                "Document deleted - cache invalidated",
                tags=["cache", "mutation", "delete"],
                document_id=document_id,
                collection=doc.collection,
                soft_delete=soft_delete,
                has_configurations=has_configs,
                configuration_names=config_names,
            )
        return result

    def assign_configuration(self, document_id: str, config_name: str, timestamp: str) -> bool:
        trace.debug(
            "Assigning configuration - will invalidate cache",
            tags=["cache", "mutation", "assign_config"],
            document_id=document_id,
            config_name=config_name,
        )
        doc = self._backend.get_document_by_id(document_id)
        result = self._backend.assign_configuration(document_id, config_name, timestamp)
        if result and doc:
            self._invalidate_document_cache(document_id, doc.collection)
            config_keys = [
                f"config_docs:{config_name}",
                f"config_docs_summary:{config_name}",
                "configuration_info",
                "configuration_info_optimized",
                "configurations_list",
                "configurations_list_optimized",
            ]
            for key in config_keys:
                self._cache.delete(key)
            trace.info(
                "Configuration assigned - cache invalidated",
                tags=["cache", "mutation", "assign_config"],
                document_id=document_id,
                config_name=config_name,
                collection=doc.collection,
                invalidated_keys=config_keys,
            )
        return result

    def remove_configuration_assignment(self, document_id: str, config_name: str, timestamp: str) -> bool:
        trace.debug(
            "Removing configuration - will invalidate cache",
            tags=["cache", "mutation", "remove_config"],
            document_id=document_id,
            config_name=config_name,
        )
        doc = self._backend.get_document_by_id(document_id)
        result = self._backend.remove_configuration_assignment(document_id, config_name, timestamp)
        if result and doc:
            self._invalidate_document_cache(document_id, doc.collection)
            config_keys = [
                f"config_docs:{config_name}",
                f"config_docs_summary:{config_name}",
                "configuration_info",
                "configuration_info_optimized",
                "configurations_list",
                "configurations_list_optimized",
            ]
            for key in config_keys:
                self._cache.delete(key)
            trace.info(
                "Configuration removed - cache invalidated",
                tags=["cache", "mutation", "remove_config"],
                document_id=document_id,
                config_name=config_name,
                collection=doc.collection,
                invalidated_keys=config_keys,
            )
        return result

    def get_documents_by_configuration_summary(self, config_name: str) -> List[DocumentSummary]:
        cache_key = f"config_docs_summary:{config_name}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return [DocumentSummary(**d) if isinstance(d, dict) else d for d in cached]
        summaries = self._backend.get_documents_by_configuration_summary(config_name)
        self._cache.set(cache_key, [s.model_dump() for s in summaries])
        return summaries

    def get_documents_by_configurations_summary_batch(
        self, config_names: List[str]
    ) -> Dict[str, List[DocumentSummary]]:
        return self._backend.get_documents_by_configurations_summary_batch(config_names)

    def get_document_versions_summary(self, collection_name: str) -> List[VersionSummary]:
        cache_key = f"versions_summary:{collection_name}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return [VersionSummary(**d) if isinstance(d, dict) else d for d in cached]
        summaries = self._backend.get_document_versions_summary(collection_name)
        self._cache.set(cache_key, [s.model_dump() for s in summaries])
        return summaries

    def get_document_versions_summary_batch(self, collection_names: List[str]) -> Dict[str, List[VersionSummary]]:
        return self._backend.get_document_versions_summary_batch(collection_names)

    def list_configurations_optimized(self) -> List[str]:
        cache_key = "configurations_list_optimized"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        configs = self._backend.list_configurations_optimized()
        self._cache.set(cache_key, configs)
        return configs

    def list_collections_optimized(self) -> List[str]:
        cache_key = "collections_list_optimized"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        collections = self._backend.list_collections_optimized()
        self._cache.set(cache_key, collections)
        return collections

    def get_configuration_info_optimized(self) -> List[ConfigurationInfo]:
        cache_key = "configuration_info_optimized"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return [ConfigurationInfo(**c) if isinstance(c, dict) else c for c in cached]
        info = self._backend.get_configuration_info_optimized()
        self._cache.set(cache_key, [c.model_dump() for c in info])
        return info

    def get_collection_info_optimized(self) -> List[CollectionInfo]:
        cache_key = "collection_info_optimized"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return [CollectionInfo(**c) if isinstance(c, dict) else c for c in cached]
        info = self._backend.get_collection_info_optimized()
        self._cache.set(cache_key, [c.model_dump() for c in info])
        return info

    def get_document_by_id_direct(
        self, document_id: str, collection_name: Optional[str] = None
    ) -> Optional[OTSDocument]:
        cache_key = f"doc:{document_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        doc = self._backend.get_document_by_id_direct(document_id, collection_name)
        if doc is not None:
            self._cache.set(cache_key, doc)
        return doc

    def _invalidate_document_cache(
        self,
        document_id: str,
        collection_name: str,
        has_configurations: bool = True,
        configuration_names: Optional[List[str]] = None,
    ) -> None:
        invalidated_keys = [
            f"doc:{document_id}",
            f"collection_docs:{collection_name}",
            f"versions:{collection_name}",
            f"versions_summary:{collection_name}",
            "all_documents",
            "collection_info",
            "collections_list",
            "collection_info_optimized",
            "collections_list_optimized",
        ]
        if has_configurations:
            invalidated_keys.extend(
                [
                    "configuration_info",
                    "configurations_list",
                    "configuration_info_optimized",
                    "configurations_list_optimized",
                ]
            )
        if configuration_names:
            for config_name in configuration_names:
                invalidated_keys.append(f"config_docs:{config_name}")
                invalidated_keys.append(f"config_docs_summary:{config_name}")
        trace.debug(
            "Invalidating document-related cache entries",
            tags=["cache", "mutation", "invalidate"],
            document_id=document_id,
            collection=collection_name,
            has_configurations=has_configurations,
            keys_to_invalidate=invalidated_keys,
        )
        for key in invalidated_keys:
            self._cache.delete(key)
        trace.info(
            "Cache entries invalidated for document",
            tags=["cache", "mutation", "invalidate"],
            document_id=document_id,
            collection=collection_name,
            invalidated_count=len(invalidated_keys),
        )

    def find_duplicate_versions(self) -> Dict[str, Dict[str, List[str]]]:
        return self._backend.find_duplicate_versions()

    def find_duplicate_collections_in_configs(
        self, progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Dict[str, List[str]]]:
        return self._backend.find_duplicate_collections_in_configs(progress_callback)

    def clear_cache(self) -> None:
        trace.info("Clearing all cached data", tags=["cache", "mutation"])
        self._cache.clear()

    def get_cache_stats(self) -> dict:
        return self._cache.get_stats()

    def warm_cache(self) -> None:
        trace.info("Starting cache warming", tags=["cache", "warming"])
        try:
            self.list_collections_optimized()
            self.list_configurations_optimized()
            self.get_collection_info_optimized()
            self.get_configuration_info_optimized()
            trace.info("Cache warming complete", tags=["cache", "warming"], stats=self.get_cache_stats())
        except Exception as e:
            trace.warn("Cache warming failed (non-critical)", tags=["cache", "warming", "error"], error=str(e))

    def batch_delete_documents(
        self,
        document_ids: List[str],
        soft_delete: bool = True,
        skip_protected: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> BatchOperationResult:
        trace.info(
            "Batch delete operation - will clear cache after",
            tags=["cache", "mutation", "batch"],
            document_count=len(document_ids),
            soft_delete=soft_delete,
        )
        result = self._backend.batch_delete_documents(document_ids, soft_delete, skip_protected, progress_callback)
        if result.success_count > 0:
            self._cache.clear()
            trace.info(
                "Cache cleared after batch delete",
                tags=["cache", "mutation", "batch"],
                success_count=result.success_count,
                failed_count=result.failed_count,
                skipped_count=result.skipped_count,
            )
        return result

    def batch_remove_configurations(
        self,
        items: List[Tuple[str, str]],
        timestamp: str,
        skip_protected: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> BatchOperationResult:
        trace.info(
            "Batch remove config operation - will clear cache after",
            tags=["cache", "mutation", "batch"],
            item_count=len(items),
        )
        result = self._backend.batch_remove_configurations(items, timestamp, skip_protected, progress_callback)
        if result.success_count > 0:
            self._cache.clear()
            trace.info(
                "Cache cleared after batch remove config",
                tags=["cache", "mutation", "batch"],
                success_count=result.success_count,
                failed_count=result.failed_count,
                skipped_count=result.skipped_count,
            )
        return result

    def delete_document_with_info(
        self, document_id: str, collection_name: str, soft_delete: bool = True
    ) -> Tuple[bool, Optional[OTSDocument]]:
        cache_key = f"doc:{document_id}"
        doc = self._cache.get(cache_key)
        if doc is None:
            doc = self._backend.get_document_by_id_direct(document_id, collection_name)
        if doc is None:
            return (False, None)
        success = self._backend.delete_document(document_id, soft_delete)
        if success:
            has_configs = bool(doc.configurations)
            config_names = [c.name for c in doc.configurations] if doc.configurations else None
            self._invalidate_document_cache(document_id, doc.collection, has_configs, configuration_names=config_names)
            trace.info(
                "Document deleted with info - cache invalidated",
                tags=["cache", "mutation", "delete"],
                document_id=document_id,
                collection=doc.collection,
            )
        return (success, doc)
