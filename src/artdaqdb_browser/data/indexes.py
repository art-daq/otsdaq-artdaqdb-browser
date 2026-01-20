"""
File: indexes.py
Purpose: MongoDB index management for OTS Browser.
Category: Data
Author: ArtdaqDB Browser Team
Depends: None
Exports: IndexSpec, get_recommended_indexes, get_index_keys_for_pymongo, recreate_indexes_on_collection, recreate_indexes_on_database, ...
Complexity: Medium | Lines: 397
"""

from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from ..trace import trace


@dataclass
class IndexSpec:
    name: str
    keys: List[Tuple[str, int]]
    description: str


ASCENDING = 1
DESCENDING = -1
RECOMMENDED_INDEXES: List[IndexSpec] = [
    IndexSpec(
        name="idx_version_entities_name",
        keys=[("version", ASCENDING), ("entities.name", ASCENDING)],
        description="CRITICAL: Duplicate detection, findCompositionsContaining",
    ),
    IndexSpec(
        name="idx_configurations_name",
        keys=[("configurations.name", ASCENDING)],
        description="Configuration lookups (shared with GUI)",
    ),
    IndexSpec(
        name="idx_entities_name",
        keys=[("entities.name", ASCENDING)],
        description="Entity lookups (findVersions, findEntities)",
    ),
    IndexSpec(name="idx_version_asc", keys=[("version", ASCENDING)], description="Ascending version for API queries"),
    IndexSpec(
        name="idx_version_desc",
        keys=[("version", DESCENDING)],
        description="Descending version for GUI sorting (most recent first)",
    ),
    IndexSpec(
        name="idx_bookkeeping_created",
        keys=[("bookkeeping.created", DESCENDING)],
        description="Timestamp sorting for finding latest documents",
    ),
    IndexSpec(
        name="idx_bookkeeping_status",
        keys=[("bookkeeping.isdeleted", ASCENDING), ("bookkeeping.isreadonly", ASCENDING)],
        description="Document protection status filtering",
    ),
    IndexSpec(
        name="idx_config_version_compound",
        keys=[("configurations.name", ASCENDING), ("version", DESCENDING)],
        description="Configuration + version queries with descending sort",
    ),
    IndexSpec(
        name="idx_collection_version",
        keys=[("collection", ASCENDING), ("version", DESCENDING)],
        description="Duplicate version detection queries",
    ),
    IndexSpec(
        name="idx_config_summary_covering",
        keys=[
            ("configurations.name", ASCENDING),
            ("collection", ASCENDING),
            ("version", DESCENDING),
            ("bookkeeping.created", DESCENDING),
        ],
        description="Covering index for get_documents_by_configuration_summary",
    ),
    IndexSpec(
        name="idx_config_assignment_covering",
        keys=[
            ("configurations.name", ASCENDING),
            ("configurations.assigned", DESCENDING),
            ("collection", ASCENDING),
            ("version", DESCENDING),
        ],
        description="Covering index for configuration assignment queries",
    ),
    IndexSpec(
        name="idx_full_summary_covering",
        keys=[
            ("configurations.name", ASCENDING),
            ("collection", ASCENDING),
            ("version", DESCENDING),
            ("bookkeeping.created", DESCENDING),
            ("bookkeeping.isdeleted", ASCENDING),
            ("bookkeeping.isreadonly", ASCENDING),
        ],
        description="Full covering index for summaries with protection status",
    ),
]


def get_recommended_indexes() -> List[IndexSpec]:
    return RECOMMENDED_INDEXES.copy()


def get_index_keys_for_pymongo(index_spec: IndexSpec) -> List[Tuple[str, int]]:
    return index_spec.keys


def recreate_indexes_on_collection(
    collection, indexes: Optional[List[IndexSpec]] = None, drop_existing: bool = True
) -> Dict[str, Any]:
    if indexes is None:
        indexes = RECOMMENDED_INDEXES
    result = {"collection": collection.name, "created": [], "dropped": [], "skipped": [], "errors": []}
    if drop_existing:
        try:
            existing_indexes = list(collection.list_indexes())
            for idx in existing_indexes:
                idx_name = idx["name"]
                if idx_name == "_id_":
                    continue
                try:
                    collection.drop_index(idx_name)
                    result["dropped"].append(idx_name)
                    trace.debug(f"Dropped index: {idx_name}", tags=["database", "mutation"], collection=collection.name)
                except Exception as e:
                    result["errors"].append(f"Failed to drop {idx_name}: {e}")
                    trace.error(
                        f"Failed to drop index: {idx_name}",
                        tags=["database", "mutation", "error"],
                        exception=e,
                        collection=collection.name,
                    )
        except Exception as e:
            result["errors"].append(f"Failed to list indexes: {e}")
            trace.error(
                "Failed to list indexes for dropping",
                tags=["database", "error"],
                exception=e,
                collection=collection.name,
            )
            return result
    for index_spec in indexes:
        try:
            collection.create_index(index_spec.keys, name=index_spec.name, background=True)
            result["created"].append(index_spec.name)
            trace.debug(f"Created index: {index_spec.name}", tags=["database", "mutation"], collection=collection.name)
        except Exception as e:
            error_msg = f"Failed to create {index_spec.name}: {e}"
            result["errors"].append(error_msg)
            trace.error(
                f"Failed to create index: {index_spec.name}",
                tags=["database", "mutation", "error"],
                exception=e,
                collection=collection.name,
            )
    return result


def recreate_indexes_on_database(
    db, indexes: Optional[List[IndexSpec]] = None, drop_existing: bool = True, exclude_system: bool = True
) -> Dict[str, Any]:
    if indexes is None:
        indexes = RECOMMENDED_INDEXES
    result = {
        "database": db.name,
        "total_created": 0,
        "total_dropped": 0,
        "total_skipped": 0,
        "total_errors": 0,
        "collections": {},
    }
    try:
        collection_names = db.list_collection_names()
    except Exception as e:
        trace.error(
            "Failed to list collections for index recreation", tags=["database", "error"], exception=e, database=db.name
        )
        result["error"] = str(e)
        return result
    for collection_name in sorted(collection_names):
        if exclude_system and collection_name.startswith("system."):
            continue
        collection = db[collection_name]
        coll_result = recreate_indexes_on_collection(collection, indexes=indexes, drop_existing=drop_existing)
        result["collections"][collection_name] = coll_result
        result["total_created"] += len(coll_result["created"])
        result["total_dropped"] += len(coll_result["dropped"])
        result["total_skipped"] += len(coll_result["skipped"])
        result["total_errors"] += len(coll_result["errors"])
    trace.info(
        "Index recreation complete",
        tags=["database", "lifecycle"],
        database=db.name,
        created=result["total_created"],
        dropped=result["total_dropped"],
        errors=result["total_errors"],
    )
    return result


def format_index_report(result: Dict[str, Any], verbose: bool = True) -> str:
    lines = []
    lines.append("INDEX RECREATION REPORT")
    lines.append("=" * 100)
    lines.append("")
    lines.append(f"  Database:        {result.get('database', 'N/A')}")
    lines.append(f"  Indexes Created: {result.get('total_created', 0)}")
    lines.append(f"  Indexes Dropped: {result.get('total_dropped', 0)}")
    lines.append(f"  Indexes Skipped: {result.get('total_skipped', 0)}")
    lines.append(f"  Errors:          {result.get('total_errors', 0)}")
    lines.append("")
    if "error" in result:
        lines.append(f"ERROR: {result['error']}")
        lines.append("")
        return "\n".join(lines)
    if verbose and "collections" in result:
        lines.append("-" * 100)
        lines.append("COLLECTION DETAILS")
        lines.append("-" * 100)
        lines.append("")
        for coll_name, coll_result in result["collections"].items():
            created = coll_result.get("created", [])
            dropped = coll_result.get("dropped", [])
            skipped = coll_result.get("skipped", [])
            errors = coll_result.get("errors", [])
            lines.append(f"  {coll_name}:")
            if created:
                lines.append(f"    Created: {', '.join(created)}")
            if dropped:
                lines.append(f"    Dropped: {', '.join(dropped)}")
            if skipped:
                lines.append(f"    Skipped: {', '.join(skipped)}")
            if errors:
                for err in errors:
                    lines.append(f"    ERROR: {err}")
            if not (created or dropped or skipped or errors):
                lines.append("    (no changes)")
            lines.append("")
    lines.append("-" * 100)
    lines.append("RECOMMENDED INDEXES")
    lines.append("-" * 100)
    lines.append("")
    for idx in RECOMMENDED_INDEXES:
        keys_str = ", ".join((f"{k}:{d}" for (k, d) in idx.keys))
        lines.append(f"  {idx.name}")
        lines.append(f"    Keys: {keys_str}")
        lines.append(f"    Purpose: {idx.description}")
        lines.append("")
    return "\n".join(lines)
