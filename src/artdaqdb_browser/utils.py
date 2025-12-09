"""
File: utils.py
Purpose: Utility functions for OTS Browser.
Category: Utility
Author: ArtdaqDB Browser Team
Depends: None
Exports: ThrottledCallback, format_datetime, truncate_text, get_max_list_items
Complexity: Medium | Lines: 310
"""

import time
from datetime import datetime
from typing import Callable, Optional
from zoneinfo import ZoneInfo
from .trace import trace

_datetime_config_cache = None
_ui_config_cache = None


class ThrottledCallback:

    def __init__(
        self, callback: Optional[Callable[..., None]], min_interval: float = 3.0, always_call_first: bool = True
    ):
        self._callback = callback
        self._min_interval = min_interval
        self._always_call_first = always_call_first
        self._last_call_time: Optional[float] = None
        self._call_count = 0
        self._actual_call_count = 0

    def __call__(self, *args, **kwargs) -> bool:
        if self._callback is None:
            return False
        self._call_count += 1
        current_time = time.time()
        if self._last_call_time is None:
            if self._always_call_first:
                self._last_call_time = current_time
                self._actual_call_count += 1
                trace.trace(
                    "Throttled callback first call",
                    tags=["util", "callback"],
                    call_count=self._call_count,
                    actual_count=self._actual_call_count,
                )
                self._callback(*args, **kwargs)
                return True
            else:
                self._last_call_time = current_time
                return False
        elapsed = current_time - self._last_call_time
        if elapsed >= self._min_interval:
            self._last_call_time = current_time
            self._actual_call_count += 1
            trace.trace(
                "Throttled callback interval passed",
                tags=["util", "callback"],
                call_count=self._call_count,
                actual_count=self._actual_call_count,
                elapsed_secs=round(elapsed, 2),
            )
            self._callback(*args, **kwargs)
            return True
        if self._call_count % 100 == 0:
            trace.trace(
                "Throttled callback suppressed",
                tags=["util", "callback"],
                call_count=self._call_count,
                actual_count=self._actual_call_count,
                remaining_secs=round(self._min_interval - elapsed, 2),
            )
        return False

    def flush(self, *args, **kwargs) -> None:
        if self._callback is None:
            return
        trace.trace(
            "Throttled callback flushed",
            tags=["util", "callback"],
            call_count=self._call_count,
            actual_count=self._actual_call_count + 1,
        )
        self._last_call_time = time.time()
        self._actual_call_count += 1
        self._callback(*args, **kwargs)

    def reset(self) -> None:
        self._last_call_time = None
        self._call_count = 0
        self._actual_call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def actual_call_count(self) -> int:
        return self._actual_call_count

    @property
    def throttle_ratio(self) -> float:
        if self._call_count == 0:
            return 0.0
        return self._actual_call_count / self._call_count


def _get_datetime_config():
    global _datetime_config_cache
    if _datetime_config_cache is None:
        try:
            from .config import ConfigLoader

            loader = ConfigLoader()
            (config, _) = loader.load()
            _datetime_config_cache = {
                "datetime_format": config.ui.datetime_format,
                "date_format": config.ui.date_format,
                "timezone": config.ui.timezone,
            }
        except Exception:
            _datetime_config_cache = {
                "datetime_format": "%Y-%m-%d %H:%M:%S",
                "date_format": "%Y-%m-%d",
                "timezone": None,
            }
    return _datetime_config_cache


def format_datetime(iso_string: Optional[str], include_time: bool = True) -> str:
    if not iso_string:
        return "N/A"
    config = _get_datetime_config()
    try:
        if "T" in iso_string:
            dt_str = iso_string[:26] if len(iso_string) > 26 else iso_string
            if "." in dt_str:
                dt = datetime.fromisoformat(dt_str)
            else:
                dt = datetime.fromisoformat(dt_str[:19])
        else:
            dt = datetime.fromisoformat(iso_string[:10])
        if config["timezone"]:
            try:
                tz = ZoneInfo(config["timezone"])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo("UTC"))
                dt = dt.astimezone(tz)
            except Exception:
                pass
        if include_time:
            return dt.strftime(config["datetime_format"])
        else:
            return dt.strftime(config["date_format"])
    except Exception:
        if include_time:
            return iso_string[:19] if len(iso_string) >= 19 else iso_string
        else:
            return iso_string[:10] if len(iso_string) >= 10 else iso_string


def _get_ui_config():
    global _ui_config_cache
    if _ui_config_cache is None:
        try:
            from .config import ConfigLoader

            loader = ConfigLoader()
            (config, _) = loader.load()
            _ui_config_cache = {
                "max_list_items": config.ui.max_list_items,
                "max_text_length": config.ui.max_text_length,
            }
        except Exception:
            _ui_config_cache = {"max_list_items": 1000, "max_text_length": 500}
    return _ui_config_cache


def truncate_text(text: str, max_length: Optional[int] = None, suffix: str = "...") -> str:
    if not text:
        return text
    if max_length is None:
        config = _get_ui_config()
        max_length = config["max_text_length"]
    if max_length == 0:
        return text
    if len(text) <= max_length:
        return text
    cut_length = max_length - len(suffix)
    if cut_length <= 0:
        return suffix[:max_length]
    return text[:cut_length] + suffix


def get_max_list_items() -> int:
    config = _get_ui_config()
    return config["max_list_items"]


from .widgets.filter_input import fuzzy_match

__all__ = ["format_datetime", "fuzzy_match", "ThrottledCallback", "truncate_text", "get_max_list_items"]
