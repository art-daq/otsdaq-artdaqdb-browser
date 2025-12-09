"""
File: trace_entry.py
Purpose: Trace entry model and parser for v3 trace log format.
Category: Data
Author: ArtdaqDB Browser Team
Depends: None
Exports: TraceEntry, TraceParser, parse_trace_log, _TIME_WIDTH, _SOURCE_WIDTH, ...
Complexity: High | Lines: 621
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePath
from typing import Any, Dict, Iterator, List, Optional, Tuple

_TIME_WIDTH = 13
_SOURCE_WIDTH = 20
DEFAULT_SEVERITIES = {
    "TRACE": {"level": 0, "color": "muted", "short": "TRC"},
    "DEBUG": {"level": 10, "color": "primary", "short": "DBG"},
    "INFO": {"level": 20, "color": "success", "short": "INF"},
    "WARN": {"level": 30, "color": "warning", "short": "WRN"},
    "ERROR": {"level": 40, "color": "error", "short": "ERR"},
    "CRIT": {"level": 50, "color": "error", "short": "CRT"},
}
SEVERITY_SHORT_TO_FULL = {v["short"]: k for (k, v) in DEFAULT_SEVERITIES.items()}


@dataclass
class TraceEntry:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    line_number: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    severity: str = "INFO"
    tags: List[str] = field(default_factory=list)
    file: str = ""
    line: int = 0
    function: str = ""
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    continuations: Dict[str, Any] = field(default_factory=dict)
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    stack_trace: List[str] = field(default_factory=list)
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    DELIMITER: str = " │ "

    @property
    def source(self) -> str:
        parts = [self.file] if self.file else []
        if self.line:
            parts.append(str(self.line))
        if self.function:
            parts.append(self.function)
        return ":".join(parts) if parts else ""

    @property
    def source_class(self) -> str:
        if self.file:
            return PurePath(self.file).stem
        return ""

    @property
    def source_compact(self) -> str:
        if self.file and self.function:
            class_name = PurePath(self.file).stem
            full_source = f"{class_name}.{self.function}"
            return full_source[:_SOURCE_WIDTH]
        elif self.function:
            return self.function[:_SOURCE_WIDTH]
        elif self.file:
            return PurePath(self.file).stem[:_SOURCE_WIDTH]
        return ""

    @property
    def tags_str(self) -> str:
        if not self.tags:
            return "[-]"
        return f"[{','.join(self.tags)}]"

    @property
    def severity_display(self) -> str:
        return self.severity.ljust(5)[:5]

    @property
    def severity_short(self) -> str:
        return DEFAULT_SEVERITIES.get(self.severity, {}).get("short", self.severity[:3])

    @property
    def severity_color(self) -> str:
        return DEFAULT_SEVERITIES.get(self.severity, {}).get("color", "foreground")

    @property
    def severity_level(self) -> int:
        return DEFAULT_SEVERITIES.get(self.severity, {}).get("level", 20)

    @property
    def timestamp_str(self) -> str:
        return self.timestamp.strftime("%Y-%m-%dT%H:%M:%S.") + f"{self.timestamp.microsecond // 1000:03d}"

    @property
    def time_str(self) -> str:
        return self.timestamp.strftime("%H:%M:%S.") + f"{self.timestamp.microsecond // 1000:03d}"

    @property
    def has_error(self) -> bool:
        return self.exception_type is not None or "error" in self.tags

    @property
    def has_progress(self) -> bool:
        return "progress" in self.tags or ("current" in self.data and "total" in self.data)

    @property
    def has_diff(self) -> bool:
        return "diff" in self.tags or ("from" in self.data and "to" in self.data)

    @property
    def has_span(self) -> bool:
        return "span" in self.tags or self.span_id is not None

    def matches_severity(self, min_level: str) -> bool:
        min_numeric = DEFAULT_SEVERITIES.get(min_level, {}).get("level", 0)
        return self.severity_level >= min_numeric

    def matches_tags(self, required_tags: List[str]) -> bool:
        if not required_tags:
            return True
        return bool(set(self.tags) & set(required_tags))

    def matches_time_range(self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> bool:
        if start_time and self.timestamp < start_time:
            return False
        if end_time and self.timestamp > end_time:
            return False
        return True

    def to_line(self) -> str:
        parts = [
            self.timestamp_str,
            self.severity_display,
            self.source.ljust(25),
            self.tags_str.ljust(20),
            self.message,
        ]
        if self.data:
            parts.append(json.dumps(self.data, separators=(",", ":")))
        return self.DELIMITER.join(parts)

    def to_full_text(self) -> str:
        lines = [self.to_line()]
        cont_items = list(self.continuations.items())
        for i, (key, value) in enumerate(cont_items):
            prefix = "  └─ " if i == len(cont_items) - 1 else "  ├─ "
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}: {json.dumps(value)}")
            elif isinstance(value, list):
                lines.append(f"{prefix}{key}:")
                for item in value:
                    lines.append(f"  │    {item}")
            else:
                lines.append(f"{prefix}{key}: {value}")
        if self.exception_type:
            lines.append(f"  ├─ exception: {self.exception_type}")
            if self.exception_message:
                lines.append(f"  ├─ message: {self.exception_message}")
            if self.stack_trace:
                lines.append("  └─ stack:")
                for frame in self.stack_trace:
                    lines.append(f"  │    {frame}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "id": self.id,
            "line_number": self.line_number,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity,
            "tags": self.tags,
            "source": {"file": self.file, "line": self.line, "function": self.function},
            "message": self.message,
            "data": self.data,
        }
        if self.continuations:
            result["continuations"] = self.continuations
        if self.exception_type:
            result["error"] = {
                "type": self.exception_type,
                "message": self.exception_message,
                "stack": self.stack_trace,
            }
        if self.trace_id:
            result["trace"] = {
                "trace_id": self.trace_id,
                "span_id": self.span_id,
                "parent_span_id": self.parent_span_id,
            }
        return result

    def to_display_tuple(self) -> Tuple[str, str, str, str]:
        return (
            self.time_str[:_TIME_WIDTH],
            self.severity_short,
            self.source_compact.ljust(_SOURCE_WIDTH)[:_SOURCE_WIDTH],
            self.message,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraceEntry":
        source = data.get("source", {})
        error = data.get("error", {})
        trace = data.get("trace", {})
        return cls(
            id=data.get("id", ""),
            line_number=data.get("line_number", 0),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            severity=data.get("severity", "INFO"),
            tags=data.get("tags", []),
            file=source.get("file", ""),
            line=source.get("line", 0),
            function=source.get("function", ""),
            message=data.get("message", ""),
            data=data.get("data", {}),
            continuations=data.get("continuations", {}),
            exception_type=error.get("type") if error else None,
            exception_message=error.get("message") if error else None,
            stack_trace=error.get("stack", []) if error else [],
            trace_id=trace.get("trace_id") if trace else None,
            span_id=trace.get("span_id") if trace else None,
            parent_span_id=trace.get("parent_span_id") if trace else None,
        )


class TraceParser:
    DELIMITER = " │ "
    CONT_BRANCH = "  ├─ "
    CONT_FINAL = "  └─ "
    CONT_NESTED = "  │  "

    def __init__(self):
        self.entries: List[TraceEntry] = []
        self.tags: set = set()
        self.severities: set = set()

    def parse(self, log_content: str) -> List[TraceEntry]:
        self.entries = []
        self.tags = set()
        self.severities = set()
        lines = log_content.split("\n")
        return self._parse_lines(enumerate(lines, 1))

    def parse_file(self, filepath: Path) -> List[TraceEntry]:
        self.entries = []
        self.tags = set()
        self.severities = set()
        with open(filepath, "r", encoding="utf-8") as f:
            return self._parse_lines(enumerate(f, 1))

    def parse_stream(self, lines: Iterator[str]) -> Iterator[TraceEntry]:
        current_entry: Optional[TraceEntry] = None
        for line_num, line in enumerate(lines, 1):
            line = line.rstrip("\n\r")
            if not line:
                continue
            if line.startswith("  "):
                if current_entry:
                    self._parse_continuation(line, current_entry)
                continue
            entry = self._parse_primary(line, line_num)
            if entry:
                if current_entry:
                    yield current_entry
                current_entry = entry
        if current_entry:
            yield current_entry

    def _parse_lines(self, lines_iter) -> List[TraceEntry]:
        entries = []
        current_entry: Optional[TraceEntry] = None
        for line_num, line in lines_iter:
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            line = line.rstrip("\n\r")
            if not line:
                continue
            if line.startswith("="):
                continue
            if line.startswith("  "):
                if current_entry:
                    self._parse_continuation(line, current_entry)
                continue
            entry = self._parse_primary(line, line_num)
            if entry:
                if current_entry:
                    entries.append(current_entry)
                current_entry = entry
        if current_entry:
            entries.append(current_entry)
        self.entries = entries
        return entries

    def _parse_primary(self, line: str, line_num: int) -> Optional[TraceEntry]:
        parts = line.split(self.DELIMITER)
        if len(parts) < 5:
            return None
        ts_str = parts[0].strip()
        sev = parts[1].strip()
        src = parts[2].strip()
        tags_str = parts[3].strip()
        message = parts[4].strip()
        data_str = parts[5].strip() if len(parts) > 5 else None
        try:
            timestamp = datetime.fromisoformat(ts_str)
        except ValueError:
            try:
                from datetime import date

                time_parts = ts_str.split(".")
                hms = time_parts[0]
                ms = int(time_parts[1]) if len(time_parts) > 1 else 0
                (h, m, s) = map(int, hms.split(":"))
                timestamp = datetime.combine(
                    date.today(), datetime.min.time().replace(hour=h, minute=m, second=s, microsecond=ms * 1000)
                )
            except (ValueError, IndexError):
                timestamp = datetime.now()
        src_parts = src.split(":")
        file_name = src_parts[0] if src_parts else ""
        line_no = int(src_parts[1]) if len(src_parts) > 1 and src_parts[1].isdigit() else 0
        func = src_parts[2] if len(src_parts) > 2 else ""
        tags = []
        if tags_str.startswith("[") and tags_str.endswith("]"):
            inner = tags_str[1:-1]
            if inner and inner != "-":
                tags = [t.strip() for t in inner.split(",") if t.strip()]
                self.tags.update(tags)
        self.severities.add(sev)
        data = {}
        if data_str:
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                data = {"_raw": data_str}
        trace_id = data.pop("trace_id", None)
        span_id = data.pop("span_id", None)
        parent_span_id = data.pop("parent_span_id", None)
        return TraceEntry(
            line_number=line_num,
            timestamp=timestamp,
            severity=sev,
            file=file_name,
            line=line_no,
            function=func,
            tags=tags,
            message=message,
            data=data,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
        )

    def _parse_continuation(self, line: str, entry: TraceEntry) -> None:
        content = None
        if line.startswith(self.CONT_BRANCH):
            content = line[len(self.CONT_BRANCH) :]
        elif line.startswith(self.CONT_FINAL):
            content = line[len(self.CONT_FINAL) :]
        elif line.startswith(self.CONT_NESTED):
            nested = line[len(self.CONT_NESTED) :].strip()
            if entry.stack_trace is not None:
                entry.stack_trace.append(nested)
            return
        if not content:
            return
        if ": " in content:
            (key, value) = content.split(": ", 1)
            key = key.strip()
            value = value.strip()
            if key == "exception":
                entry.exception_type = value
            elif key == "message" and entry.exception_type:
                entry.exception_message = value
            elif key == "stack":
                entry.stack_trace = []
            else:
                try:
                    entry.continuations[key] = json.loads(value)
                except json.JSONDecodeError:
                    entry.continuations[key] = value
        else:
            entry.continuations[content.rstrip(":")] = []

    def get_unique_tags(self) -> List[str]:
        return sorted(self.tags)

    def get_unique_severities(self) -> List[str]:
        order = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "CRIT"]
        return [s for s in order if s in self.severities]


def parse_trace_log(log_content: str) -> Tuple[List[TraceEntry], List[str], List[str]]:
    parser = TraceParser()
    entries = parser.parse(log_content)
    return (entries, parser.get_unique_tags(), parser.get_unique_severities())
