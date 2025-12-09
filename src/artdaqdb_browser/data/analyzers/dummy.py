"""
File: dummy.py
Purpose: Dummy analyzer for testing the progress widget.
Category: Analyzer
Author: ArtdaqDB Browser Team
Depends: None
Exports: DummyAnalyzer
Complexity: Low | Lines: 180
"""

import random
import time
import threading
from typing import List, Optional, Any
from ...models import DocumentSummary, VersionSummary, ConfigurationInfo, CollectionInfo
from ...utils import ThrottledCallback
from ...trace import trace
from .base import BaseAnalyzer, AnalysisResult, ProgressCallback, DEFAULT_THROTTLE_INTERVAL


class DummyAnalyzer(BaseAnalyzer):
    DURATION_SECONDS = 30

    def __init__(self) -> None:
        self._analysis: Optional[AnalysisResult] = None
        self._cancelled = False

    @property
    def name(self) -> str:
        return "Dummy Test Analyzer"

    @property
    def description(self) -> str:
        return "Test analyzer that simulates a 2-minute database scan"

    def cancel(self) -> None:
        trace.debug("TPW-203: Cancellation requested", tags=["app"])
        self._cancelled = True

    def analyze(
        self,
        backend: Any = None,
        progress_callback: Optional[ProgressCallback] = None,
        throttle_interval: float = DEFAULT_THROTTLE_INTERVAL,
    ) -> AnalysisResult:
        trace.debug(
            "TPW-201: Entry",
            tags=["app"],
            thread_name=threading.current_thread().name,
            has_callback=progress_callback is not None,
            throttle_interval=throttle_interval,
        )
        self._cancelled = False
        result = AnalysisResult()
        total_queries = random.randint(100, 1000)
        time_per_query = self.DURATION_SECONDS / total_queries
        trace.debug(
            "TPW-201: Analysis parameters",
            tags=["app"],
            total_queries=total_queries,
            duration_seconds=self.DURATION_SECONDS,
            time_per_query_ms=time_per_query * 1000,
        )
        throttled_callback = ThrottledCallback(
            progress_callback, min_interval=throttle_interval, always_call_first=True
        )
        trace.info("TPW-201: Starting query loop", tags=["app", "lifecycle"])
        for i in range(total_queries):
            if self._cancelled:
                trace.debug("TPW-201: Cancelled at iteration", tags=["app"], iteration=i)
                break
            throttled_callback(i, total_queries)
            if i % 50 == 0:
                trace.debug(
                    "TPW-202: Loop progress",
                    tags=["app", "progress"],
                    iteration=i,
                    total=total_queries,
                    percent=round(i / total_queries * 100, 1),
                )
            time.sleep(time_per_query)
        if not self._cancelled and progress_callback:
            trace.debug("TPW-201: Flushing final progress", tags=["app", "progress"])
            throttled_callback.flush(total_queries, total_queries)
        trace.debug("TPW-201: Analysis complete", tags=["app", "lifecycle"], cancelled=self._cancelled)
        self._analysis = result
        return result

    def get_analysis(self) -> Optional[AnalysisResult]:
        return self._analysis

    def filter_configurations(self, configurations: List[ConfigurationInfo]) -> List[ConfigurationInfo]:
        return configurations

    def filter_collections(self, collections: List[CollectionInfo]) -> List[CollectionInfo]:
        return collections

    def filter_documents_by_config(
        self, documents: List[DocumentSummary], config_name: Optional[str] = None
    ) -> List[DocumentSummary]:
        return documents

    def filter_versions(
        self, versions: List[VersionSummary], collection_name: Optional[str] = None, config_name: Optional[str] = None
    ) -> List[VersionSummary]:
        return versions

    def get_status_suffix(self) -> str:
        return " [TEST MODE]"
