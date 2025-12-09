"""
File: trace.py
Purpose: Trace logging API for v3 format.
Category: Utility
Author: ArtdaqDB Browser Team
Depends: None
Exports: Tracer, SpanContext, clear_trace_log, init_trace_log, is_trace_enabled, ...
Complexity: High | Lines: 865
"""

from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar
import functools
import json
import logging
import sys
import traceback
import uuid

F = TypeVar("F", bound=Callable[..., Any])
_current_trace_id: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
_current_span_id: ContextVar[Optional[str]] = ContextVar("span_id", default=None)
_trace_enabled: bool = True
_trace_file_path: Path = Path("trace.log")
_max_trace_size_mb: int = 10
_trace_backup_count: int = 3
_min_log_level: int = 10
_logger: Optional[logging.Logger] = None
_initialized: bool = False
DELIMITER = " │ "
CONT_BRANCH = "  ├─ "
CONT_FINAL = "  └─ "
CONT_NESTED = "  │    "
LEVELS = {"TRACE": 0, "DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40, "CRIT": 50}
LEVEL_MAP = {"debug": LEVELS["DEBUG"], "info": LEVELS["INFO"], "warning": LEVELS["WARN"], "error": LEVELS["ERROR"]}


def _load_trace_config() -> None:
    global _trace_enabled, _trace_file_path, _max_trace_size_mb, _trace_backup_count, _min_log_level
    try:
        from .config import ConfigLoader

        loader = ConfigLoader()
        (config, _) = loader.load()
        _trace_enabled = config.logging.trace_enabled
        _trace_file_path = Path(config.logging.trace_file)
        _max_trace_size_mb = config.logging.max_trace_size_mb
        _trace_backup_count = config.logging.trace_backup_count
        if config.app.debug:
            _min_log_level = LEVELS["DEBUG"]
        else:
            _min_log_level = LEVEL_MAP.get(config.logging.level.lower(), LEVELS["DEBUG"])
    except Exception:
        _trace_enabled = True
        _trace_file_path = Path("trace.log")
        _max_trace_size_mb = 10
        _trace_backup_count = 3
        _min_log_level = LEVELS["DEBUG"]


def _setup_logger() -> logging.Logger:
    global _logger, _initialized
    if _logger is not None:
        return _logger
    if not _initialized:
        _load_trace_config()
        _initialized = True
    _logger = logging.getLogger("artdaqdb_browser.trace")
    _logger.setLevel(logging.DEBUG)
    _logger.handlers.clear()
    max_bytes = _max_trace_size_mb * 1024 * 1024
    handler = RotatingFileHandler(
        _trace_file_path, maxBytes=max_bytes, backupCount=_trace_backup_count, encoding="utf-8"
    )
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    _logger.addHandler(handler)
    return _logger


def _get_timestamp() -> str:
    now = datetime.now()
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}"


def _get_source(depth: int = 2) -> tuple:
    try:
        frame = sys._getframe(depth)
        filename = frame.f_code.co_filename.split("/")[-1]
        return (filename, frame.f_lineno, frame.f_code.co_name)
    except (ValueError, AttributeError):
        return ("unknown", 0, "unknown")


class Tracer:

    def __init__(
        self,
        module: str = "",
        default_tags: Optional[list] = None,
        output: Optional[Callable[[str], None]] = None,
        min_level: int = 0,
    ):
        self.module = module
        self.default_tags = default_tags or []
        self.output = output if output is not None else self._default_output
        self.min_level = min_level

    def __call__(self, source: str, action: str, value_source: str = "unknown", **values: Any) -> None:
        action_lower = action.lower()
        value_source_lower = value_source.lower()
        if "error" in action_lower or value_source_lower == "error":
            severity = "ERROR"
            tags = ["error", value_source_lower] if value_source_lower != "error" else ["error"]
        elif "warning" in action_lower or "warn" in action_lower:
            severity = "WARN"
            tags = [value_source_lower]
        else:
            severity = "TRACE"
            tags = [value_source_lower] if value_source_lower != "unknown" else []
        data = dict(values)
        data["value_source"] = value_source
        self._log_internal(severity, action, tags, source, data)

    def _default_output(self, line: str) -> None:
        global _initialized
        if not _initialized:
            _load_trace_config()
            _initialized = True
        if not _trace_enabled:
            return
        logger = _setup_logger()
        logger.debug(line)

    def _format_entry(self, severity: str, message: str, tags: list, data: dict, source) -> str:
        ts = _get_timestamp()
        sev = severity.ljust(5)[:5]
        if isinstance(source, tuple):
            src = f"{source[0]}:{source[1]}:{source[2]}".ljust(25)
        else:
            src = str(source).ljust(25)
        if isinstance(tags, str):
            tags = [tags] if tags else []
        all_tags = list(self.default_tags) + list(tags)
        tags_str = f"[{','.join(all_tags)}]".ljust(20) if all_tags else "[-]".ljust(20)
        trace_data = dict(data)
        if trace_id := _current_trace_id.get():
            trace_data["trace_id"] = trace_id
        if span_id := _current_span_id.get():
            trace_data["span_id"] = span_id
        parts = [ts, sev, src, tags_str, message]
        if trace_data:
            parts.append(json.dumps(trace_data, separators=(",", ":")))
        return DELIMITER.join(parts)

    def _log_internal(
        self, severity: str, message: str, tags: list, source: str, data: dict, exception: Optional[Exception] = None
    ) -> None:
        level = LEVELS.get(severity, 20)
        effective_min_level = _min_log_level if self.min_level == 0 else self.min_level
        if level < effective_min_level:
            return
        line = self._format_entry(severity, message, tags, data, source)
        self.output(line)
        if exception:
            self.output(f"{CONT_BRANCH}exception: {type(exception).__name__}")
            self.output(f"{CONT_BRANCH}message: {str(exception)}")
            self.output(f"{CONT_FINAL}stack:")
            for frame in traceback.format_tb(exception.__traceback__):
                for frame_line in frame.strip().split("\n"):
                    self.output(f"{CONT_NESTED}{frame_line}")

    def log(
        self,
        severity: str,
        message: str,
        tags: Optional[list] = None,
        exception: Optional[Exception] = None,
        **data: Any,
    ) -> None:
        level = LEVELS.get(severity, 20)
        effective_min_level = _min_log_level if self.min_level == 0 else self.min_level
        if level < effective_min_level:
            return
        tags = tags or []
        source = _get_source(depth=3)
        if exception and "error" not in tags:
            tags = tags + ["error"]
            data["error"] = type(exception).__name__
            data["message"] = str(exception)
        line = self._format_entry(severity, message, tags, data, source)
        self.output(line)
        if exception:
            self.output(f"{CONT_BRANCH}exception: {type(exception).__name__}")
            self.output(f"{CONT_BRANCH}message: {str(exception)}")
            self.output(f"{CONT_FINAL}stack:")
            for frame in traceback.format_tb(exception.__traceback__):
                for frame_line in frame.strip().split("\n"):
                    self.output(f"{CONT_NESTED}{frame_line}")

    def trace(self, message: str, tags: Optional[list] = None, **data: Any) -> None:
        self.log("TRACE", message, tags, **data)

    def debug(self, message: str, tags: Optional[list] = None, **data: Any) -> None:
        self.log("DEBUG", message, tags, **data)

    def info(self, message: str, tags: Optional[list] = None, **data: Any) -> None:
        self.log("INFO", message, tags, **data)

    def warn(self, message: str, tags: Optional[list] = None, **data: Any) -> None:
        self.log("WARN", message, tags, **data)

    def error(
        self, message: str, tags: Optional[list] = None, exception: Optional[Exception] = None, **data: Any
    ) -> None:
        self.log("ERROR", message, tags, exception=exception, **data)

    def crit(
        self, message: str, tags: Optional[list] = None, exception: Optional[Exception] = None, **data: Any
    ) -> None:
        self.log("CRIT", message, tags, exception=exception, **data)

    def span(self, operation: str, tags: Optional[list] = None) -> "SpanContext":
        return SpanContext(self, operation, tags or [])

    def traced(self, tags: Optional[list] = None) -> Callable:

        def decorator(func: Callable) -> Callable:

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                func_tags = (tags or []) + ["span"]
                with self.span(func.__name__, func_tags):
                    return func(*args, **kwargs)

            return wrapper

        return decorator


@dataclass
class SpanContext:
    tracer: Tracer
    operation: str
    tags: list
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_span_id: Optional[str] = None
    start_time: Optional[datetime] = None
    _token: Any = None

    def __enter__(self) -> "SpanContext":
        self.parent_span_id = _current_span_id.get()
        self._token = _current_span_id.set(self.span_id)
        if not _current_trace_id.get():
            _current_trace_id.set(uuid.uuid4().hex)
        self.start_time = datetime.now()
        self.tracer.debug(
            f"-> {self.operation}", tags=self.tags + ["span"], span_id=self.span_id, parent_span_id=self.parent_span_id
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        duration_ms = (datetime.now() - self.start_time).total_seconds() * 1000
        if exc_type:
            self.tracer.error(
                f"x {self.operation}",
                tags=self.tags + ["span", "error"],
                exception=exc_val,
                duration_ms=round(duration_ms, 2),
            )
        else:
            self.tracer.debug(
                f"<- {self.operation}", tags=self.tags + ["span"], duration_ms=round(duration_ms, 2), status="ok"
            )
        _current_span_id.reset(self._token)

    def trace(self, message: str, **data: Any) -> None:
        self.tracer.trace(message, self.tags, **data)

    def debug(self, message: str, **data: Any) -> None:
        self.tracer.debug(message, self.tags, **data)

    def info(self, message: str, **data: Any) -> None:
        self.tracer.info(message, self.tags, **data)

    def warn(self, message: str, **data: Any) -> None:
        self.tracer.warn(message, self.tags, **data)

    def error(self, message: str, exception: Optional[Exception] = None, **data: Any) -> None:
        self.tracer.error(message, self.tags, exception=exception, **data)


trace = Tracer()


def clear_trace_log() -> None:
    global _initialized
    if not _initialized:
        _load_trace_config()
        _initialized = True
    if _trace_file_path.exists():
        _trace_file_path.unlink()


def init_trace_log() -> None:
    global _initialized
    _load_trace_config()
    _initialized = True
    if not _trace_enabled:
        return
    clear_trace_log()
    logger = _setup_logger()
    header = f"{'=' * 70}\nOTS Browser Trace Log (v3 Format)\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nConfig:  trace_enabled={_trace_enabled}, file={_trace_file_path}\n         max_size={_max_trace_size_mb}MB, backups={_trace_backup_count}\n{'=' * 70}\n\nFormat: TIMESTAMP {DELIMITER}SEVERITY{DELIMITER}SOURCE{DELIMITER}[tags]{DELIMITER}MESSAGE{DELIMITER}{{json}}\n\nSeverity Levels: TRACE < DEBUG < INFO < WARN < ERROR < CRIT\n\n{'=' * 70}\n"
    logger.debug(header)


def is_trace_enabled() -> bool:
    global _initialized
    if not _initialized:
        _load_trace_config()
        _initialized = True
    return _trace_enabled


def get_trace_file_path() -> Path:
    global _initialized
    if not _initialized:
        _load_trace_config()
        _initialized = True
    return _trace_file_path


def reload_trace_config() -> None:
    global _initialized, _logger
    _initialized = False
    if _logger:
        _logger.handlers.clear()
        _logger = None
    _load_trace_config()
    _initialized = True


def traced(source: str, action: Optional[str] = None) -> Callable[[F], F]:

    def decorator(func: F) -> F:

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            action_text = action or f"Executing {func.__name__}"
            parts = source.split(".")
            file_part = parts[0] + ".py" if parts else "unknown.py"
            func_part = parts[1] if len(parts) > 1 else func.__name__
            trace.debug(f"{action_text} - START", tags=["lifecycle"], source_hint=f"{file_part}:0:{func_part}")
            try:
                result = func(*args, **kwargs)
                trace.debug(f"{action_text} - SUCCESS", tags=["lifecycle"], source_hint=f"{file_part}:0:{func_part}")
                return result
            except Exception as e:
                trace.error(
                    f"{action_text} - FAILED",
                    tags=["lifecycle", "error"],
                    exception=e,
                    source_hint=f"{file_part}:0:{func_part}",
                )
                raise

        return wrapper

    return decorator


def trace_method(func: F) -> F:

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if args and hasattr(args[0], "__class__"):
            class_name = args[0].__class__.__name__
        else:
            class_name = "Unknown"
        trace.debug(f"Entering {func.__name__}", tags=["lifecycle"], class_name=class_name, method=func.__name__)
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            trace.error(
                f"Error in {func.__name__}",
                tags=["lifecycle", "error"],
                exception=e,
                class_name=class_name,
                method=func.__name__,
            )
            raise

    return wrapper


def trace_async_method(func: F) -> F:

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        if args and hasattr(args[0], "__class__"):
            class_name = args[0].__class__.__name__
        else:
            class_name = "Unknown"
        trace.debug(
            f"Entering {func.__name__} (async)",
            tags=["lifecycle", "async"],
            class_name=class_name,
            method=func.__name__,
        )
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            trace.error(
                f"Error in {func.__name__} (async)",
                tags=["lifecycle", "error", "async"],
                exception=e,
                class_name=class_name,
                method=func.__name__,
            )
            raise

    return wrapper


def trace_separator(label: str = "") -> None:
    global _initialized
    if not _initialized:
        _load_trace_config()
        _initialized = True
    if not _trace_enabled:
        return
    logger = _setup_logger()
    sep = "=" * 60
    if label:
        logger.debug(f"\n{sep}\n{_get_timestamp()} {label}\n{sep}\n")
    else:
        logger.debug(f"\n{sep}\n")


def trace_screen(screen_name: str, event: str) -> None:
    trace_separator(f"{screen_name.upper()} SCREEN - {event}")


def trace_error(source: str, error: Exception, action: str = "Error occurred") -> None:
    trace.error(f"{action}: {type(error).__name__}", tags=["error"], exception=error, source_module=source)


def trace_v2(source: str, action: str, value_source: str = "unknown", **values: Any) -> None:
    trace(source, action, value_source, **values)
