"""
File: __init__.py
Purpose: Data access layer for OTS documents.
Category: Data
Author: ArtdaqDB Browser Team
Depends: None
Exports: None
Complexity: Low | Lines: 57
"""

from .base import DataBackend, BatchOperationResult
from .filesystem import FilesystemBackend
from .mongodb import MongoDBBackend
from .cached import CachedBackend
from .factory import create_backend, create_backend_from_config
from .analyzers import (
    AnalysisResult,
    BaseAnalyzer,
    PassThroughAnalyzer,
    ProgressCallback,
    DEFAULT_THROTTLE_INTERVAL,
    DEFAULT_ANALYZER,
    DuplicateVersionAnalyzer,
    TrashDuplicateVersionAnalyzer,
    GlobalTrashDuplicateVersionAnalyzer,
    GlobalTrashItem,
    DuplicateCollectionAnalyzer,
    TrashDuplicateCollectionAnalyzer,
    GlobalTrashDuplicateCollectionAnalyzer,
    GlobalTrashConfigItem,
    DummyAnalyzer,
)

__all__ = [
    "DataBackend",
    "BatchOperationResult",
    "FilesystemBackend",
    "MongoDBBackend",
    "CachedBackend",
    "create_backend",
    "create_backend_from_config",
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
