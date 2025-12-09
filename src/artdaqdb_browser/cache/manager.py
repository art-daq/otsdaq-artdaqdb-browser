"""
File: manager.py
Purpose: Cache manager for persistent disk-based caching using pickle files.
Category: Utility
Author: ArtdaqDB Browser Team
Depends: None
Exports: CacheManager
Complexity: High | Lines: 716
"""

import hashlib
import pickle
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..trace import trace


class CacheManager:
    DEFAULT_CACHE_DIR = Path.home() / ".ots-browser" / "cache"
    DEFAULT_TTL = 600
    DEFAULT_MAX_ENTRIES = 10000
    DEFAULT_MAX_SIZE_MB = 100
    DEFAULT_MEMORY_MAX_ENTRIES = 100
    PICKLE_PROTOCOL = 5

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        ttl: int = DEFAULT_TTL,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        max_size_mb: int = DEFAULT_MAX_SIZE_MB,
        memory_max_entries: int = DEFAULT_MEMORY_MAX_ENTRIES,
        auto_purge: bool = True,
    ):
        self.cache_dir = cache_dir or self.DEFAULT_CACHE_DIR
        self.ttl = ttl
        self.max_entries = max_entries
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.memory_max_entries = memory_max_entries
        self._memory_cache: OrderedDict[str, Any] = OrderedDict()
        self._memory_expires: Dict[str, Optional[float]] = {}
        self._stats = {"hits": 0, "misses": 0, "memory_hits": 0, "disk_hits": 0}
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        trace.debug(
            "Cache manager initialized",
            tags=["cache", "lifecycle"],
            cache_dir=str(self.cache_dir),
            ttl_seconds=self.ttl,
            max_entries=self.max_entries,
            max_size_mb=max_size_mb,
            memory_max_entries=memory_max_entries,
            auto_purge=auto_purge,
        )
        if auto_purge:
            self.purge()

    def _get_cache_path(self, key: str) -> Path:
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"

    def _is_expired(self, entry: Dict) -> bool:
        if "expires_at" not in entry:
            return False
        return time.time() > entry["expires_at"]

    def _is_file_expired(self, cache_path: Path) -> bool:
        try:
            if not cache_path.exists():
                return True
            file_mtime = cache_path.stat().st_mtime
            return time.time() > file_mtime + self.ttl
        except Exception:
            return True

    def _get_from_memory(self, key: str) -> tuple[bool, Optional[Any]]:
        if key not in self._memory_cache:
            return (False, None)
        expires_at = self._memory_expires.get(key)
        if expires_at is not None and time.time() > expires_at:
            del self._memory_cache[key]
            del self._memory_expires[key]
            return (False, None)
        self._memory_cache.move_to_end(key)
        return (True, self._memory_cache[key])

    def _set_in_memory(self, key: str, value: Any, expires_at: Optional[float]) -> None:
        if key in self._memory_cache:
            self._memory_cache.move_to_end(key)
        self._memory_cache[key] = value
        self._memory_expires[key] = expires_at
        while len(self._memory_cache) > self.memory_max_entries:
            oldest_key = next(iter(self._memory_cache))
            del self._memory_cache[oldest_key]
            self._memory_expires.pop(oldest_key, None)

    def _delete_from_memory(self, key: str) -> None:
        self._memory_cache.pop(key, None)
        self._memory_expires.pop(key, None)

    def get(self, key: str) -> Optional[Any]:
        (found, value) = self._get_from_memory(key)
        if found:
            self._stats["hits"] += 1
            self._stats["memory_hits"] += 1
            trace.trace("Cache hit (memory)", tags=["cache", "query", "memory"], key=key)
            return value
        try:
            cache_path = self._get_cache_path(key)
            if not cache_path.exists():
                self._stats["misses"] += 1
                return None
            if self._is_file_expired(cache_path):
                trace.trace("Cache entry expired (file mtime check)", tags=["cache", "expiration"], key=key)
                cache_path.unlink(missing_ok=True)
                self._stats["misses"] += 1
                return None
            with open(cache_path, "rb") as f:
                entry = pickle.load(f)
            if self._is_expired(entry):
                trace.trace("Cache entry expired (stored expires_at)", tags=["cache", "expiration"], key=key)
                cache_path.unlink(missing_ok=True)
                self._stats["misses"] += 1
                return None
            value = entry.get("value")
            expires_at = entry.get("expires_at")
            self._set_in_memory(key, value, expires_at)
            self._stats["hits"] += 1
            self._stats["disk_hits"] += 1
            trace.trace("Cache hit (disk, promoted to memory)", tags=["cache", "query", "disk"], key=key)
            return value
        except Exception as e:
            trace.warn("Cache read error", tags=["cache", "error"], key=key, error=str(e))
            self._stats["misses"] += 1
            return None

    def _enforce_limits(self) -> None:
        try:
            cache_files = list(self.cache_dir.glob("*.cache"))
            total_size = sum((f.stat().st_size for f in cache_files))
            entry_count = len(cache_files)
            if entry_count <= self.max_entries and total_size <= self.max_size_bytes:
                return
            cache_files.sort(key=lambda f: f.stat().st_mtime)
            evicted = 0
            for cache_file in cache_files:
                if entry_count <= self.max_entries and total_size <= self.max_size_bytes:
                    break
                try:
                    file_size = cache_file.stat().st_size
                    cache_file.unlink()
                    total_size -= file_size
                    entry_count -= 1
                    evicted += 1
                except Exception:
                    pass
            if evicted > 0:
                trace.debug(
                    "Cache entries evicted due to limits",
                    tags=["cache", "eviction"],
                    evicted_count=evicted,
                    remaining_entries=entry_count,
                    remaining_size_mb=total_size / (1024 * 1024),
                )
        except Exception as e:
            trace.warn("Cache limit enforcement error", tags=["cache", "error"], error=str(e))

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        try:
            expire_time = ttl if ttl is not None else self.ttl
            if expire_time < 0:
                trace.trace("Cache entry skipped (TTL < 0)", tags=["cache", "skip"], key=key, ttl_seconds=expire_time)
                return True
            expires_at = time.time() + expire_time if expire_time > 0 else None
            self._set_in_memory(key, value, expires_at)
            entry = {"key": key, "value": value, "created_at": time.time(), "expires_at": expires_at}
            cache_path = self._get_cache_path(key)
            with open(cache_path, "wb") as f:
                pickle.dump(entry, f, protocol=self.PICKLE_PROTOCOL)
            self._enforce_limits()
            trace.trace("Cache entry set (memory + disk)", tags=["cache", "mutation"], key=key, ttl_seconds=expire_time)
            return True
        except Exception as e:
            trace.warn("Cache write error", tags=["cache", "error"], key=key, error=str(e))
            return False

    def delete(self, key: str) -> bool:
        self._delete_from_memory(key)
        try:
            cache_path = self._get_cache_path(key)
            if cache_path.exists():
                cache_path.unlink()
                trace.debug("Cache entry deleted (memory + disk)", tags=["cache", "mutation"], key=key)
                return True
            return False
        except Exception as e:
            trace.warn("Cache delete error", tags=["cache", "error"], key=key, error=str(e))
            return False

    def clear(self) -> bool:
        memory_count = len(self._memory_cache)
        self._memory_cache.clear()
        self._memory_expires.clear()
        try:
            cache_files = list(self.cache_dir.glob("*.cache"))
            disk_count = len(cache_files)
            for cache_file in cache_files:
                cache_file.unlink()
            self._stats = {"hits": 0, "misses": 0, "memory_hits": 0, "disk_hits": 0}
            trace.info(
                "Cache cleared (memory + disk)",
                tags=["cache", "mutation"],
                memory_entries_removed=memory_count,
                disk_entries_removed=disk_count,
            )
            return True
        except Exception as e:
            trace.error("Failed to clear cache", tags=["cache", "error"], error=str(e))
            return False

    def purge(self) -> bool:
        try:
            purged_count = 0
            for cache_file in self.cache_dir.glob("*.cache"):
                should_delete = False
                try:
                    if self._is_file_expired(cache_file):
                        should_delete = True
                    else:
                        try:
                            with open(cache_file, "rb") as f:
                                entry = pickle.load(f)
                            if self._is_expired(entry):
                                should_delete = True
                        except Exception:
                            should_delete = True
                except Exception:
                    should_delete = True
                if should_delete:
                    try:
                        cache_file.unlink(missing_ok=True)
                        purged_count += 1
                    except Exception:
                        pass
            trace.info("Expired cache entries purged", tags=["cache", "mutation"], purged_count=purged_count)
            return True
        except Exception as e:
            trace.error("Failed to purge cache", tags=["cache", "error"], error=str(e))
            return False

    def get_stats(self) -> Dict[str, Any]:
        try:
            cache_files = list(self.cache_dir.glob("*.cache"))
            total_hits = self._stats.get("hits", 0)
            total_misses = self._stats.get("misses", 0)
            hit_rate = total_hits / (total_hits + total_misses) * 100 if total_hits + total_misses > 0 else 0
            stats = {
                "size": len(cache_files),
                "hits": total_hits,
                "misses": total_misses,
                "hit_rate": round(hit_rate, 1),
                "directory": str(self.cache_dir),
                "memory_size": len(self._memory_cache),
                "memory_max": self.memory_max_entries,
                "memory_hits": self._stats.get("memory_hits", 0),
                "disk_size": len(cache_files),
                "disk_hits": self._stats.get("disk_hits", 0),
            }
            trace.trace("Cache statistics retrieved", tags=["cache", "query"], **stats)
            return stats
        except Exception as e:
            trace.warn("Error getting cache statistics", tags=["cache", "error"], error=str(e))
            return {}

    def get_configurations(self) -> Optional[List[str]]:
        return self.get("configurations_list")

    def set_configurations(self, configurations: List[str]) -> bool:
        return self.set("configurations_list", configurations)

    def get_collections(self) -> Optional[List[str]]:
        return self.get("collections_list")

    def set_collections(self, collections: List[str]) -> bool:
        return self.set("collections_list", collections)

    def get_configuration_info(self) -> Optional[List[Dict]]:
        return self.get("configuration_info")

    def set_configuration_info(self, info: List[Dict]) -> bool:
        return self.set("configuration_info", info)

    def get_collection_info(self) -> Optional[List[Dict]]:
        return self.get("collection_info")

    def set_collection_info(self, info: List[Dict]) -> bool:
        return self.set("collection_info", info)

    def get_config_documents(self, config_name: str) -> Optional[List[Dict]]:
        return self.get(f"config_docs:{config_name}")

    def set_config_documents(self, config_name: str, documents: List[Dict]) -> bool:
        return self.set(f"config_docs:{config_name}", documents)

    def get_collection_documents(self, collection_name: str) -> Optional[List[Dict]]:
        return self.get(f"collection_docs:{collection_name}")

    def set_collection_documents(self, collection_name: str, documents: List[Dict]) -> bool:
        return self.set(f"collection_docs:{collection_name}", documents)

    def get_configuration_info_optimized(self) -> Optional[List[Dict]]:
        return self.get("configuration_info_optimized")

    def set_configuration_info_optimized(self, info: List[Dict]) -> bool:
        return self.set("configuration_info_optimized", info)

    def get_collection_info_optimized(self) -> Optional[List[Dict]]:
        return self.get("collection_info_optimized")

    def set_collection_info_optimized(self, info: List[Dict]) -> bool:
        return self.set("collection_info_optimized", info)

    def get_configurations_list_optimized(self) -> Optional[List[str]]:
        return self.get("configurations_list_optimized")

    def set_configurations_list_optimized(self, configs: List[str]) -> bool:
        return self.set("configurations_list_optimized", configs)

    def get_collections_list_optimized(self) -> Optional[List[str]]:
        return self.get("collections_list_optimized")

    def set_collections_list_optimized(self, collections: List[str]) -> bool:
        return self.set("collections_list_optimized", collections)

    def get_config_docs_summary(self, config_name: str) -> Optional[List[Dict]]:
        return self.get(f"config_docs_summary:{config_name}")

    def set_config_docs_summary(self, config_name: str, summaries: List[Dict]) -> bool:
        return self.set(f"config_docs_summary:{config_name}", summaries)

    def get_versions_summary(self, collection_name: str) -> Optional[List[Dict]]:
        return self.get(f"versions_summary:{collection_name}")

    def set_versions_summary(self, collection_name: str, summaries: List[Dict]) -> bool:
        return self.set(f"versions_summary:{collection_name}", summaries)

    def get_entries_info(self) -> List[Dict[str, Any]]:
        entries = []
        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    file_stat = cache_file.stat()
                    file_size = file_stat.st_size
                    file_mtime = file_stat.st_mtime
                    is_file_expired = self._is_file_expired(cache_file)
                    with open(cache_file, "rb") as f:
                        entry = pickle.load(f)
                    key = entry.get("key", "unknown")
                    value = entry.get("value")
                    created_at = entry.get("created_at")
                    expires_at = entry.get("expires_at")
                    if isinstance(value, list):
                        value_type = f"list[{len(value)}]"
                    elif isinstance(value, dict):
                        value_type = f"dict[{len(value)}]"
                    elif value is None:
                        value_type = "None"
                    else:
                        value_type = type(value).__name__
                    is_expired = is_file_expired or self._is_expired(entry)
                    entries.append(
                        {
                            "key": key,
                            "type": value_type,
                            "size_bytes": file_size,
                            "created_at": created_at,
                            "expires_at": expires_at,
                            "is_expired": is_expired,
                            "file_name": cache_file.name,
                            "file_mtime": file_mtime,
                        }
                    )
                except Exception:
                    try:
                        file_size = cache_file.stat().st_size if cache_file.exists() else 0
                    except Exception:
                        file_size = 0
                    entries.append(
                        {
                            "key": f"[corrupted: {cache_file.name}]",
                            "type": "error",
                            "size_bytes": file_size,
                            "created_at": None,
                            "expires_at": None,
                            "is_expired": True,
                            "file_name": cache_file.name,
                            "file_mtime": None,
                        }
                    )
        except Exception as e:
            trace.warn("Error getting cache entries info", tags=["cache", "error"], error=str(e))
        return entries

    def get_total_size(self) -> int:
        total = 0
        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                total += cache_file.stat().st_size
        except Exception:
            pass
        return total

    def close(self) -> None:
        pass
