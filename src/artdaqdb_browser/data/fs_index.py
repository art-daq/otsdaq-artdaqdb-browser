"""
File: fs_index.py
Purpose: Filesystem index for fast document lookups.
Category: Data
Author: ArtdaqDB Browser Team
Depends: None
Exports: LRUCache, ConfigAssignmentData, DocumentMetadata, FilesystemIndex, FilesystemIndexManager
Complexity: High | Lines: 835
"""

import gzip
import json
import pickle
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Set, Optional, Tuple
from collections import defaultdict, OrderedDict
from ..trace import trace


class LRUCache(OrderedDict):

    def __init__(self, max_size: int = 10000):
        super().__init__()
        self.max_size = max_size
        self._eviction_count = 0

    def __getitem__(self, key):
        self.move_to_end(key)
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        while len(self) > self.max_size:
            oldest = next(iter(self))
            del self[oldest]
            self._eviction_count += 1

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    @property
    def eviction_count(self) -> int:
        return self._eviction_count


@dataclass
class ConfigAssignmentData:
    name: str
    assigned: Optional[str] = None


@dataclass
class DocumentMetadata:
    id: str
    collection: str
    version: str
    config_names: List[str]
    config_assignments: List[ConfigAssignmentData] = field(default_factory=list)
    created: Optional[str] = None
    is_deleted: bool = False
    is_readonly: bool = False
    file_path: str = ""
    file_mtime: float = 0.0

    def get_assigned_for_config(self, config_name: str) -> Optional[str]:
        for cfg in self.config_assignments:
            if cfg.name == config_name:
                return cfg.assigned
        return None


@dataclass
class FilesystemIndex:
    documents: Dict[str, DocumentMetadata] = field(default_factory=dict)
    config_to_docs: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    collection_to_docs: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    collection_version_docs: Dict[str, Dict[str, List[str]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(list))
    )
    config_collection_docs: Dict[str, Dict[str, List[str]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(list))
    )
    base_path: str = ""
    build_time: float = 0.0
    document_count: int = 0

    def add_document(self, metadata: DocumentMetadata) -> None:
        doc_id = metadata.id
        self.documents[doc_id] = metadata
        self.collection_to_docs[metadata.collection].add(doc_id)
        for config_name in metadata.config_names:
            self.config_to_docs[config_name].add(doc_id)
        self.collection_version_docs[metadata.collection][metadata.version].append(doc_id)
        for config_name in metadata.config_names:
            self.config_collection_docs[config_name][metadata.collection].append(doc_id)
        self.document_count += 1

    def remove_document(self, doc_id: str) -> None:
        if doc_id not in self.documents:
            return
        metadata = self.documents[doc_id]
        self.collection_to_docs[metadata.collection].discard(doc_id)
        for config_name in metadata.config_names:
            self.config_to_docs[config_name].discard(doc_id)
        if metadata.collection in self.collection_version_docs:
            ver_docs = self.collection_version_docs[metadata.collection]
            if metadata.version in ver_docs:
                ver_docs[metadata.version] = [d for d in ver_docs[metadata.version] if d != doc_id]
        for config_name in metadata.config_names:
            if config_name in self.config_collection_docs:
                coll_docs = self.config_collection_docs[config_name]
                if metadata.collection in coll_docs:
                    coll_docs[metadata.collection] = [d for d in coll_docs[metadata.collection] if d != doc_id]
        del self.documents[doc_id]
        self.document_count -= 1

    def get_configurations(self) -> List[str]:
        return sorted(self.config_to_docs.keys())

    def get_collections(self) -> List[str]:
        return sorted(self.collection_to_docs.keys())

    def get_docs_by_config(self, config_name: str) -> List[DocumentMetadata]:
        doc_ids = self.config_to_docs.get(config_name, set())
        return [self.documents[d] for d in doc_ids if d in self.documents]

    def get_docs_by_collection(self, collection_name: str) -> List[DocumentMetadata]:
        doc_ids = self.collection_to_docs.get(collection_name, set())
        return [self.documents[d] for d in doc_ids if d in self.documents]

    def find_duplicate_versions(self) -> Dict[str, Dict[str, List[str]]]:
        result = {}
        for collection, version_docs in self.collection_version_docs.items():
            duplicates = {ver: list(ids) for (ver, ids) in version_docs.items() if len(ids) > 1}
            if duplicates:
                result[collection] = duplicates
        return result

    def find_duplicate_collections_in_configs(
        self, progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Dict[str, List[str]]]:
        result = {}
        configs = list(self.config_collection_docs.items())
        total = len(configs)
        for i, (config, coll_docs) in enumerate(configs):
            if progress_callback:
                progress_callback(i, total)
            duplicates = {coll: list(ids) for (coll, ids) in coll_docs.items() if len(ids) > 1}
            if duplicates:
                result[config] = duplicates
        if progress_callback:
            progress_callback(total, total)
        return result


class FilesystemIndexManager:
    CACHE_VERSION = 4
    DEFAULT_PARALLEL_WORKERS = 4
    DEFAULT_LRU_MAX_SIZE = 100000

    def __init__(
        self,
        base_path: Path,
        cache_dir: Optional[Path] = None,
        use_compression: bool = True,
        parallel_workers: int = DEFAULT_PARALLEL_WORKERS,
        lru_max_size: Optional[int] = None,
    ):
        self.base_path = Path(base_path)
        self.cache_dir = cache_dir or Path.home() / ".ots-browser" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.use_compression = use_compression
        self.parallel_workers = parallel_workers
        self.lru_max_size = lru_max_size
        self._index: Optional[FilesystemIndex] = None
        self._manifest: Dict[str, float] = {}
        self._dirty = False

    @property
    def index(self) -> FilesystemIndex:
        if self._index is None:
            self._load_or_build_index()
        return self._index

    def _get_cache_paths(self) -> Tuple[Path, Path]:
        path_hash = hashlib.md5(str(self.base_path).encode()).hexdigest()[:8]
        ext = ".pickle.gz" if self.use_compression else ".pickle"
        index_path = self.cache_dir / f"fs_index_{path_hash}{ext}"
        manifest_path = self.cache_dir / f"fs_manifest_{path_hash}.json"
        return (index_path, manifest_path)

    def _get_legacy_cache_path(self) -> Path:
        path_hash = hashlib.md5(str(self.base_path).encode()).hexdigest()[:8]
        return self.cache_dir / f"fs_index_{path_hash}.pickle"

    def _load_or_build_index(self) -> None:
        (index_path, manifest_path) = self._get_cache_paths()
        legacy_path = self._get_legacy_cache_path()
        cache_loaded = False
        for try_path in [index_path, legacy_path]:
            if try_path.exists() and manifest_path.exists():
                try:
                    is_compressed = try_path.suffix == ".gz"
                    if self._load_cached_index(try_path, manifest_path, is_compressed):
                        cache_loaded = True
                        trace.info(
                            "Loaded filesystem index from cache",
                            tags=["filesystem", "cache"],
                            document_count=self._index.document_count,
                            compressed=is_compressed,
                            cache_size_kb=try_path.stat().st_size // 1024,
                        )
                        if try_path == legacy_path and self.use_compression:
                            self._save_cached_index(index_path, manifest_path)
                            try_path.unlink()
                            trace.info("Migrated legacy cache to compressed format", tags=["filesystem", "cache"])
                        break
                except Exception as e:
                    trace.warn(
                        "Failed to load cached filesystem index",
                        tags=["filesystem", "cache", "error"],
                        error=str(e),
                        path=str(try_path),
                    )
        if cache_loaded:
            return
        self._build_index_parallel()
        try:
            self._save_cached_index(index_path, manifest_path)
        except Exception as e:
            trace.warn("Failed to save filesystem index to cache", tags=["filesystem", "cache", "error"], error=str(e))

    def _load_cached_index(self, index_path: Path, manifest_path: Path, compressed: bool = False) -> bool:
        with open(manifest_path, "r") as f:
            cache_data = json.load(f)
        cached_version = cache_data.get("version", 0)
        if cached_version < 3:
            trace.debug(
                "Cache version too old, rebuilding index",
                tags=["filesystem", "cache"],
                cached_version=cached_version,
                expected_version=self.CACHE_VERSION,
            )
            return False
        cached_manifest = cache_data.get("files", {})
        current_files = self._scan_file_mtimes()
        if not self._manifests_match(cached_manifest, current_files):
            trace.debug("Filesystem files changed, cache invalidated", tags=["filesystem", "cache"])
            return False
        if compressed:
            with gzip.open(index_path, "rb") as f:
                self._index = pickle.load(f)
        else:
            with open(index_path, "rb") as f:
                self._index = pickle.load(f)
        self._manifest = cached_manifest
        return True

    def _save_cached_index(self, index_path: Path, manifest_path: Path) -> None:
        manifest_data = {
            "version": self.CACHE_VERSION,
            "base_path": str(self.base_path),
            "files": self._manifest,
            "document_count": self._index.document_count,
            "compressed": self.use_compression,
        }
        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f)
        if self.use_compression:
            with gzip.open(index_path, "wb", compresslevel=6) as f:
                pickle.dump(self._index, f)
        else:
            with open(index_path, "wb") as f:
                pickle.dump(self._index, f)
        cache_size = index_path.stat().st_size
        trace.debug(
            "Filesystem index cached to disk",
            tags=["filesystem", "cache"],
            document_count=self._index.document_count,
            compressed=self.use_compression,
            cache_size_kb=cache_size // 1024,
        )
        self._dirty = False

    def _scan_file_mtimes(self) -> Dict[str, float]:
        files = {}
        for collection_dir in self.base_path.iterdir():
            if not collection_dir.is_dir():
                continue
            for json_file in collection_dir.glob("*.json"):
                rel_path = str(json_file.relative_to(self.base_path))
                files[rel_path] = json_file.stat().st_mtime
        return files

    def _manifests_match(self, cached: Dict[str, float], current: Dict[str, float]) -> bool:
        if set(cached.keys()) != set(current.keys()):
            return False
        for path, mtime in current.items():
            if cached.get(path) != mtime:
                return False
        return True

    def _build_index(self) -> None:
        import time

        start_time = time.time()
        trace.info(
            "Building filesystem index from scratch (sequential)",
            tags=["filesystem", "lifecycle"],
            base_path=str(self.base_path),
        )
        self._index = FilesystemIndex(base_path=str(self.base_path))
        self._manifest = {}
        for collection_dir in self.base_path.iterdir():
            if not collection_dir.is_dir():
                continue
            collection_name = collection_dir.name
            for json_file in collection_dir.glob("*.json"):
                try:
                    metadata = self._quick_parse_metadata(json_file, collection_name)
                    self._index.add_document(metadata)
                    rel_path = str(json_file.relative_to(self.base_path))
                    self._manifest[rel_path] = json_file.stat().st_mtime
                except Exception as e:
                    trace.warn(
                        "Error parsing document metadata for index",
                        tags=["filesystem", "error"],
                        file_path=str(json_file),
                        error=str(e),
                    )
                    continue
        self._index.build_time = time.time() - start_time
        trace.info(
            "Filesystem index built successfully",
            tags=["filesystem", "lifecycle"],
            document_count=self._index.document_count,
            build_time_ms=int(self._index.build_time * 1000),
        )

    def _build_index_parallel(self) -> None:
        import time

        start_time = time.time()
        trace.info(
            "Building filesystem index from scratch (parallel)",
            tags=["filesystem", "lifecycle"],
            base_path=str(self.base_path),
            workers=self.parallel_workers,
        )
        self._index = FilesystemIndex(base_path=str(self.base_path))
        self._manifest = {}
        files_to_process: List[Tuple[Path, str]] = []
        for collection_dir in self.base_path.iterdir():
            if not collection_dir.is_dir():
                continue
            collection_name = collection_dir.name
            for json_file in collection_dir.glob("*.json"):
                files_to_process.append((json_file, collection_name))
        if not files_to_process:
            self._index.build_time = time.time() - start_time
            return
        parsed_count = 0
        error_count = 0

        def parse_file(args: Tuple[Path, str]) -> Optional[Tuple[DocumentMetadata, str, float]]:
            (json_file, collection_name) = args
            try:
                metadata = self._quick_parse_metadata(json_file, collection_name)
                rel_path = str(json_file.relative_to(self.base_path))
                mtime = json_file.stat().st_mtime
                return (metadata, rel_path, mtime)
            except Exception as e:
                trace.warn(
                    "Error parsing document metadata for index",
                    tags=["filesystem", "error"],
                    file_path=str(json_file),
                    error=str(e),
                )
                return None

        with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
            futures = {executor.submit(parse_file, f): f for f in files_to_process}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    (metadata, rel_path, mtime) = result
                    self._index.add_document(metadata)
                    self._manifest[rel_path] = mtime
                    parsed_count += 1
                else:
                    error_count += 1
        self._index.build_time = time.time() - start_time
        trace.info(
            "Filesystem index built successfully (parallel)",
            tags=["filesystem", "lifecycle"],
            document_count=self._index.document_count,
            build_time_ms=int(self._index.build_time * 1000),
            workers=self.parallel_workers,
            errors=error_count,
        )

    def _quick_parse_metadata(self, file_path: Path, collection_name: str) -> DocumentMetadata:
        with open(file_path, "r") as f:
            data = json.load(f)
        doc_id = data.get("_id", file_path.stem)
        version = data.get("version", "0")
        config_names = []
        config_assignments = []
        for cfg in data.get("configurations", []):
            name = cfg.get("name")
            if name:
                config_names.append(name)
                config_assignments.append(ConfigAssignmentData(name=name, assigned=cfg.get("assigned")))
        bookkeeping = data.get("bookkeeping", {})
        created = bookkeeping.get("created")
        is_deleted = bookkeeping.get("isdeleted", False)
        is_readonly = bookkeeping.get("isreadonly", False)
        return DocumentMetadata(
            id=doc_id,
            collection=collection_name,
            version=version,
            config_names=config_names,
            config_assignments=config_assignments,
            created=created,
            is_deleted=is_deleted,
            is_readonly=is_readonly,
            file_path=str(file_path),
            file_mtime=file_path.stat().st_mtime,
        )

    def invalidate(self) -> None:
        self._index = None
        self._manifest = {}
        self._dirty = False
        (index_path, manifest_path) = self._get_cache_paths()
        legacy_path = self._get_legacy_cache_path()
        for path in [index_path, legacy_path]:
            if path.exists():
                path.unlink()
        if manifest_path.exists():
            manifest_path.unlink()
        trace.info("Filesystem index cache invalidated", tags=["filesystem", "cache"])

    def refresh_document(self, file_path: Path, auto_save: bool = True) -> None:
        if self._index is None:
            return
        try:
            collection_name = file_path.parent.name
            if file_path.exists():
                metadata = self._quick_parse_metadata(file_path, collection_name)
                self._index.remove_document(metadata.id)
                self._index.add_document(metadata)
                rel_path = str(file_path.relative_to(self.base_path))
                self._manifest[rel_path] = file_path.stat().st_mtime
                self._dirty = True
                trace.debug("Document refreshed in index", tags=["filesystem", "incremental"], doc_id=metadata.id)
            else:
                rel_path = str(file_path.relative_to(self.base_path))
                doc_id = file_path.stem
                self._index.remove_document(doc_id)
                self._manifest.pop(rel_path, None)
                self._dirty = True
                trace.debug("Document removed from index", tags=["filesystem", "incremental"], doc_id=doc_id)
            if auto_save and self._dirty:
                self.save()
        except Exception as e:
            trace.warn(
                "Error refreshing document in index",
                tags=["filesystem", "error"],
                file_path=str(file_path),
                error=str(e),
            )

    def refresh_documents(self, file_paths: List[Path], auto_save: bool = True) -> int:
        if self._index is None:
            return 0
        updated = 0
        for file_path in file_paths:
            try:
                self.refresh_document(file_path, auto_save=False)
                updated += 1
            except Exception:
                pass
        if auto_save and self._dirty:
            self.save()
        trace.info(
            "Batch document refresh complete",
            tags=["filesystem", "incremental"],
            requested=len(file_paths),
            updated=updated,
        )
        return updated

    def incremental_update(self) -> Tuple[int, int, int]:
        if self._index is None:
            self._load_or_build_index()
            return (self._index.document_count, 0, 0)
        current_files = self._scan_file_mtimes()
        cached_files = set(self._manifest.keys())
        current_file_set = set(current_files.keys())
        added = 0
        updated = 0
        removed = 0
        new_files = current_file_set - cached_files
        for rel_path in new_files:
            file_path = self.base_path / rel_path
            self.refresh_document(file_path, auto_save=False)
            added += 1
        for rel_path in cached_files & current_file_set:
            if current_files[rel_path] != self._manifest.get(rel_path):
                file_path = self.base_path / rel_path
                self.refresh_document(file_path, auto_save=False)
                updated += 1
        deleted_files = cached_files - current_file_set
        for rel_path in deleted_files:
            doc_id = Path(rel_path).stem
            self._index.remove_document(doc_id)
            self._manifest.pop(rel_path, None)
            removed += 1
            self._dirty = True
        if self._dirty:
            self.save()
        trace.info(
            "Incremental update complete",
            tags=["filesystem", "incremental"],
            added=added,
            updated=updated,
            removed=removed,
        )
        return (added, updated, removed)

    def save(self) -> None:
        if self._index is None:
            return
        try:
            (index_path, manifest_path) = self._get_cache_paths()
            self._save_cached_index(index_path, manifest_path)
        except Exception as e:
            trace.warn("Failed to save filesystem index", tags=["filesystem", "cache", "error"], error=str(e))

    def get_stats(self) -> Dict[str, any]:
        if self._index is None:
            return {"loaded": False}
        (index_path, _) = self._get_cache_paths()
        cache_size = index_path.stat().st_size if index_path.exists() else 0
        return {
            "loaded": True,
            "document_count": self._index.document_count,
            "configuration_count": len(self._index.config_to_docs),
            "collection_count": len(self._index.collection_to_docs),
            "build_time_ms": int(self._index.build_time * 1000),
            "cache_size_kb": cache_size // 1024,
            "compressed": self.use_compression,
            "dirty": self._dirty,
        }
