"""
File: indexes.py
Purpose: MongoDB index management for OTS Browser.
Category: Data
Author: ArtdaqDB Browser Team
Depends: None
Exports: IndexSpec, get_recommended_indexes, get_index_keys_for_pymongo, recreate_indexes_on_collection, recreate_indexes_on_database, ...
Complexity: Medium | Lines: 349
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
        name="configurations_name_idx",
        keys=[("configurations.name", ASCENDING)],
        description="Index for configuration lookups (get_documents_by_configuration_summary)",
    ),
    IndexSpec(
        name="version_idx",
        keys=[("version", DESCENDING)],
        description="Index for version sorting (get_document_versions_summary)",
    ),
    IndexSpec(
        name="bookkeeping_created_idx",
        keys=[("bookkeeping.created", DESCENDING)],
        description="Index for finding latest documents by creation date",
    ),
    IndexSpec(
        name="config_version_compound_idx",
        keys=[("configurations.name", ASCENDING), ("version", DESCENDING)],
        description="Compound index for configuration + version queries",
    ),
    IndexSpec(
        name="config_summary_covering_idx",
        keys=[
            ("configurations.name", ASCENDING),
            ("collection", ASCENDING),
            ("version", DESCENDING),
            ("bookkeeping.created", DESCENDING),
        ],
        description="Covering index for get_documents_by_configuration_summary - avoids full document fetch",
    ),
    IndexSpec(
        name="config_assignment_covering_idx",
        keys=[
            ("configurations.name", ASCENDING),
            ("configurations.assigned", DESCENDING),
            ("collection", ASCENDING),
            ("version", DESCENDING),
        ],
        description="Covering index for configuration assignment queries with timestamps",
    ),
    IndexSpec(
        name="full_summary_covering_idx",
        keys=[
            ("configurations.name", ASCENDING),
            ("collection", ASCENDING),
            ("version", DESCENDING),
            ("bookkeeping.created", DESCENDING),
            ("bookkeeping.isdeleted", ASCENDING),
            ("bookkeeping.isreadonly", ASCENDING),
        ],
        description="Full covering index for document summaries including protection status",
    ),
    IndexSpec(
        name="collection_version_idx",
        keys=[("collection", ASCENDING), ("version", DESCENDING)],
        description="Index for duplicate version detection queries",
    ),
    IndexSpec(
        name="bookkeeping_status_idx",
        keys=[("bookkeeping.isdeleted", ASCENDING), ("bookkeeping.isreadonly", ASCENDING)],
        description="Index for filtering by document protection status",
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
    existing_indexes = set()
    try:
        for idx in collection.list_indexes():
            existing_indexes.add(idx["name"])
    except Exception as e:
        result["errors"].append(f"Failed to list indexes: {e}")
        return result
    for index_spec in indexes:
        try:
            if drop_existing and index_spec.name in existing_indexes:
                try:
                    collection.drop_index(index_spec.name)
                    result["dropped"].append(index_spec.name)
                    trace.debug(
                        f"Dropped existing index: {index_spec.name}",
                        tags=["database", "mutation"],
                        collection=collection.name,
                    )
                except Exception as e:
                    result["errors"].append(f"Failed to drop {index_spec.name}: {e}")
                    continue
            elif not drop_existing and index_spec.name in existing_indexes:
                result["skipped"].append(index_spec.name)
                continue
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
