"""
File: __init__.py
Purpose: Data models for OTS documents.
Category: Data
Author: ArtdaqDB Browser Team
Depends: None
Exports: None
Complexity: Low | Lines: 50
"""

from .document import (
    OTSDocument,
    DocumentData,
    ConfigurationAssignment,
    EntityAssignment,
    BookkeepingUpdate,
    Bookkeeping,
    Origin,
    Aliases,
    ConfigurationInfo,
    ConfigurationSummaryInfo,
    CollectionInfo,
    DocumentSummary,
    VersionSummary,
)
from .trace_entry import TraceEntry, TraceParser, DEFAULT_SEVERITIES, SEVERITY_SHORT_TO_FULL, parse_trace_log

TraceLogParser = TraceParser
__all__ = [
    "OTSDocument",
    "DocumentData",
    "ConfigurationAssignment",
    "EntityAssignment",
    "BookkeepingUpdate",
    "Bookkeeping",
    "Origin",
    "Aliases",
    "ConfigurationInfo",
    "ConfigurationSummaryInfo",
    "CollectionInfo",
    "DocumentSummary",
    "VersionSummary",
    "TraceEntry",
    "TraceParser",
    "TraceLogParser",
    "DEFAULT_SEVERITIES",
    "SEVERITY_SHORT_TO_FULL",
    "parse_trace_log",
]
