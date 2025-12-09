"""
File: __init__.py
Purpose: Data analyzers for detecting and filtering database issues.
Category: Analyzer
Author: ArtdaqDB Browser Team
Depends: None
Exports: DEFAULT_ANALYZER
Complexity: Low | Lines: 55
"""

from .base import AnalysisResult, BaseAnalyzer, PassThroughAnalyzer, ProgressCallback, DEFAULT_THROTTLE_INTERVAL
from .duplicate_versions import (
    DuplicateVersionAnalyzer,
    TrashDuplicateVersionAnalyzer,
    GlobalTrashDuplicateVersionAnalyzer,
    GlobalTrashItem,
)
from .duplicate_collections import (
    DuplicateCollectionAnalyzer,
    TrashDuplicateCollectionAnalyzer,
    GlobalTrashDuplicateCollectionAnalyzer,
    GlobalTrashConfigItem,
)
from .dummy import DummyAnalyzer

DEFAULT_ANALYZER = PassThroughAnalyzer()
__all__ = [
    "AnalysisResult",
    "BaseAnalyzer",
    "PassThroughAnalyzer",
    "ProgressCallback",
    "DEFAULT_THROTTLE_INTERVAL",
    "DEFAULT_ANALYZER",
    "DuplicateVersionAnalyzer",
    "TrashDuplicateVersionAnalyzer",
    "GlobalTrashDuplicateVersionAnalyzer",
    "GlobalTrashItem",
    "DuplicateCollectionAnalyzer",
    "TrashDuplicateCollectionAnalyzer",
    "GlobalTrashDuplicateCollectionAnalyzer",
    "GlobalTrashConfigItem",
    "DummyAnalyzer",
]
