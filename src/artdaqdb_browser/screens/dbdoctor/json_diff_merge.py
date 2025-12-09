"""
File: json_diff_merge.py
Purpose: JSON Diff/Merge screen for comparing and merging OTS documents.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: rich, textual
Exports: DiffType, ComparisonMode, BookkeepingMode, DiffEntry, CopyOperation, ...
Complexity: High | Lines: 2419
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, Union
import asyncio
import json
import re
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Static, Tree
from textual.widgets.tree import TreeNode
from textual.worker import Worker
from ..base import BaseScreen
from ...constants import WidgetID, ScreenName
from ...trace import trace

MISSING = object()
DEFAULT_LEFT_DOC = Path("sampledata/teststand_db/GatewaySupervisorTable/6920fd381a35f529610f6858.json")
DEFAULT_RIGHT_DOC = Path("sampledata/teststand_db/GatewaySupervisorTable/6925d88c362cbe590c0fbf19.json")


class DiffType(Enum):
    UNCHANGED = "unchanged"
    CHANGED = "changed"
    LEFT_ONLY = "left_only"
    RIGHT_ONLY = "right_only"


class ComparisonMode(Enum):
    ALL_DIFFERENCES = "all_diffs"
    LEFT_ONLY = "left_only"
    RIGHT_ONLY = "right_only"
    CHANGED_ONLY = "changed"
    SHOW_ALL = "show_all"


class BookkeepingMode(Enum):
    INCLUDE_ALL = "include_all"
    EXCLUDE_BOOKKEEPING = "exclude_bk"
    EXCLUDE_BK_AND_TS = "exclude_bk_ts"


@dataclass
class DiffEntry:
    path: str
    type: DiffType
    left: Optional[Any] = None
    right: Optional[Any] = None

    @property
    def left_indicator(self) -> Text:
        indicators = {
            DiffType.UNCHANGED: ("=", "dim"),
            DiffType.CHANGED: ("✎", "bold yellow"),
            DiffType.LEFT_ONLY: ("+", "bold green"),
            DiffType.RIGHT_ONLY: ("-", "dim red"),
        }
        (char, style) = indicators[self.type]
        return Text(char, style=style)

    @property
    def right_indicator(self) -> Text:
        indicators = {
            DiffType.UNCHANGED: ("=", "dim"),
            DiffType.CHANGED: ("✎", "bold yellow"),
            DiffType.LEFT_ONLY: ("-", "dim red"),
            DiffType.RIGHT_ONLY: ("+", "bold blue"),
        }
        (char, style) = indicators[self.type]
        return Text(char, style=style)

    @property
    def action_indicator(self) -> Text:
        indicators = {
            DiffType.CHANGED: ("●", "bold yellow"),
            DiffType.LEFT_ONLY: ("◀", "bold green"),
            DiffType.RIGHT_ONLY: ("▶", "bold blue"),
            DiffType.UNCHANGED: ("", ""),
        }
        (char, style) = indicators.get(self.type, ("", ""))
        return Text(char, style=style) if char else Text("")

    @property
    def can_copy_left(self) -> bool:
        return self.type in (DiffType.CHANGED, DiffType.RIGHT_ONLY)

    @property
    def can_copy_right(self) -> bool:
        return self.type in (DiffType.CHANGED, DiffType.LEFT_ONLY)

    @property
    def display_left(self) -> str:
        if self.type == DiffType.RIGHT_ONLY:
            return "-"
        return self._truncate(self.left)

    @property
    def display_right(self) -> str:
        if self.type == DiffType.LEFT_ONLY:
            return "-"
        return self._truncate(self.right)

    def _truncate(self, value: Any, max_len: int = 25) -> str:
        if value is None:
            return "null"
        if isinstance(value, str):
            s = value
        else:
            s = json.dumps(value, separators=(",", ":"))
        return s[:max_len] + "..." if len(s) > max_len else s


@dataclass
class CopyOperation:
    source: Literal["left", "right"]
    target: Literal["left", "right"]
    path: str
    value: Any
    timestamp: datetime = field(default_factory=datetime.now)

    def apply(self, left_doc: dict, right_doc: dict) -> None:
        target_doc = left_doc if self.target == "left" else right_doc
        self._set_nested(target_doc, self.path, self.value)

    def _set_nested(self, doc: dict, path: str, value: Any) -> None:
        parts = self._parse_path(path)
        current = doc
        for part in parts[:-1]:
            if isinstance(part, int):
                current = current[part]
            else:
                if part not in current:
                    current[part] = {}
                current = current[part]
        final = parts[-1]
        if isinstance(final, int):
            current[final] = value
        else:
            current[final] = value

    def _parse_path(self, path: str) -> List[Union[str, int]]:
        parts: List[Union[str, int]] = []
        for segment in re.split("\\.|\\[|\\]", path):
            if not segment:
                continue
            if segment.isdigit():
                parts.append(int(segment))
            else:
                parts.append(segment)
        return parts


def compute_diff(left: dict, right: dict, path: str = "", exclude_keys: Optional[Set[str]] = None) -> List[DiffEntry]:
    diffs: List[DiffEntry] = []
    exclude_keys = exclude_keys or set()
    all_keys = set(left.keys()) | set(right.keys())
    for key in sorted(all_keys):
        if not path and key in exclude_keys:
            continue
        current_path = f"{path}.{key}" if path else key
        left_val = left.get(key, MISSING)
        right_val = right.get(key, MISSING)
        if left_val is MISSING:
            diffs.append(DiffEntry(path=current_path, type=DiffType.RIGHT_ONLY, right=right_val))
        elif right_val is MISSING:
            diffs.append(DiffEntry(path=current_path, type=DiffType.LEFT_ONLY, left=left_val))
        elif isinstance(left_val, dict) and isinstance(right_val, dict):
            diffs.extend(compute_diff(left_val, right_val, current_path))
        elif isinstance(left_val, list) and isinstance(right_val, list):
            diffs.extend(compute_list_diff(left_val, right_val, current_path))
        elif left_val != right_val:
            diffs.append(DiffEntry(path=current_path, type=DiffType.CHANGED, left=left_val, right=right_val))
        else:
            diffs.append(DiffEntry(path=current_path, type=DiffType.UNCHANGED, left=left_val, right=right_val))
    return diffs


def compute_list_diff(left: list, right: list, path: str) -> List[DiffEntry]:
    diffs: List[DiffEntry] = []
    max_len = max(len(left), len(right))
    for i in range(max_len):
        current_path = f"{path}[{i}]"
        if i >= len(left):
            diffs.append(DiffEntry(path=current_path, type=DiffType.RIGHT_ONLY, right=right[i]))
        elif i >= len(right):
            diffs.append(DiffEntry(path=current_path, type=DiffType.LEFT_ONLY, left=left[i]))
        elif isinstance(left[i], dict) and isinstance(right[i], dict):
            diffs.extend(compute_diff(left[i], right[i], current_path))
        elif isinstance(left[i], list) and isinstance(right[i], list):
            diffs.extend(compute_list_diff(left[i], right[i], current_path))
        elif left[i] != right[i]:
            diffs.append(DiffEntry(path=current_path, type=DiffType.CHANGED, left=left[i], right=right[i]))
        else:
            diffs.append(DiffEntry(path=current_path, type=DiffType.UNCHANGED, left=left[i], right=right[i]))
    return diffs


def filter_diffs(diffs: List[DiffEntry], mode: ComparisonMode) -> List[DiffEntry]:
    if mode == ComparisonMode.SHOW_ALL:
        return diffs
    filters = {
        ComparisonMode.ALL_DIFFERENCES: lambda d: d.type != DiffType.UNCHANGED,
        ComparisonMode.LEFT_ONLY: lambda d: d.type == DiffType.LEFT_ONLY,
        ComparisonMode.RIGHT_ONLY: lambda d: d.type == DiffType.RIGHT_ONLY,
        ComparisonMode.CHANGED_ONLY: lambda d: d.type == DiffType.CHANGED,
    }
    return [d for d in diffs if filters[mode](d)]


class DiffTable(DataTable):
    TRUNCATE_INDICATOR = "…"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = False
        self.base_path: str = ""
        self.value_width: int = 40

    def setup_columns(self) -> None:
        try:
            total_width = self.app.size.width
            if not total_width or total_width < 80:
                total_width = 120
        except Exception:
            total_width = 120
        act_width = 1
        path_width = int(total_width * 0.27)
        remaining = total_width - act_width - path_width
        self.value_width = remaining // 2
        self.add_column("", width=act_width)
        self.add_column("Path", width=path_width)
        self.add_column("Left Value", width=self.value_width)
        self.add_column("Right Value", width=self.value_width)

    def _truncate_value(self, value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, str):
            s = value
        else:
            s = json.dumps(value, separators=(",", ":"))
        max_display = self.value_width - 2
        if max_display < 10:
            max_display = 10
        if len(s) > max_display:
            return s[:max_display] + self.TRUNCATE_INDICATOR
        return s

    def set_base_path(self, path: str) -> None:
        self.base_path = path

    def _relative_path(self, full_path: str) -> str:
        if not self.base_path:
            return full_path
        if full_path == self.base_path:
            return "."
        if full_path.startswith(self.base_path + "."):
            return full_path[len(self.base_path) + 1 :]
        if full_path.startswith(self.base_path + "["):
            return full_path[len(self.base_path) :]
        return full_path

    def add_diff(self, entry: DiffEntry) -> None:
        if entry.type == DiffType.RIGHT_ONLY:
            left_display = "-"
        else:
            left_display = self._truncate_value(entry.left)
        if entry.type == DiffType.LEFT_ONLY:
            right_display = "-"
        else:
            right_display = self._truncate_value(entry.right)
        self.add_row(
            entry.action_indicator, self._relative_path(entry.path), left_display, right_display, key=entry.path
        )

    def get_row_style(self, diff_type: DiffType) -> str:
        return {
            DiffType.CHANGED: "diff-changed",
            DiffType.LEFT_ONLY: "diff-left-only",
            DiffType.RIGHT_ONLY: "diff-right-only",
            DiffType.UNCHANGED: "diff-unchanged",
        }.get(diff_type, "")


class JSONTree(Tree):

    def __init__(self, label: str = "Document", **kwargs):
        super().__init__(label, **kwargs)
        self._diffs: List[DiffEntry] = []
        self._paths_with_descendant_diffs: Set[str] = set()
        self._visible_paths: Set[str] = set()
        self._node_count = 0
        self._comparison_mode = ComparisonMode.SHOW_ALL

    def load_document(self, doc: dict, diffs: List[DiffEntry], mode: ComparisonMode = ComparisonMode.SHOW_ALL) -> None:
        self.clear()
        self._node_count = 0
        self._diffs = diffs
        self._comparison_mode = mode
        filtered_diffs = filter_diffs(diffs, mode)
        self._visible_paths = self._compute_visible_paths(filtered_diffs, mode)
        self._paths_with_descendant_diffs = self._compute_ancestor_diff_paths(filtered_diffs)
        self._build_tree(self.root, doc, "", diffs, mode)
        self.root.expand()
        trace.debug(
            "Tree document loaded",
            tags=["tree", "lifecycle"],
            doc_keys=list(doc.keys()) if doc else [],
            diff_count=len(diffs),
            filtered_diff_count=len(filtered_diffs),
            node_count=self._node_count,
            root_children=len(self.root.children) if self.root else 0,
            paths_with_descendant_diffs=len(self._paths_with_descendant_diffs),
            visible_paths=len(self._visible_paths),
            mode=mode.value,
        )

    def _compute_visible_paths(self, filtered_diffs: List[DiffEntry], mode: ComparisonMode) -> Set[str]:
        if mode == ComparisonMode.SHOW_ALL:
            return set()
        visible: Set[str] = set()
        for diff in filtered_diffs:
            visible.add(diff.path)
            path = diff.path
            while True:
                last_dot = path.rfind(".")
                last_bracket = path.rfind("[")
                cut_pos = max(last_dot, last_bracket)
                if cut_pos <= 0:
                    break
                path = path[:cut_pos]
                visible.add(path)
        return visible

    def _compute_ancestor_diff_paths(self, diffs: List[DiffEntry]) -> Set[str]:
        ancestor_paths: Set[str] = set()
        for diff in diffs:
            if diff.type != DiffType.UNCHANGED:
                path = diff.path
                while True:
                    last_dot = path.rfind(".")
                    last_bracket = path.rfind("[")
                    cut_pos = max(last_dot, last_bracket)
                    if cut_pos <= 0:
                        break
                    path = path[:cut_pos]
                    ancestor_paths.add(path)
        return ancestor_paths

    def _build_tree(self, node: TreeNode, data: Any, path: str, diffs: List[DiffEntry], mode: ComparisonMode) -> None:
        show_all = mode == ComparisonMode.SHOW_ALL or not self._visible_paths
        if isinstance(data, dict):
            for key, value in data.items():
                child_path = f"{path}.{key}" if path else key
                if not show_all and child_path not in self._visible_paths:
                    continue
                diff = self._find_diff(child_path, diffs)
                has_descendant_diff = child_path in self._paths_with_descendant_diffs
                label = self._format_label(key, value, diff, has_descendant_diff)
                child = node.add(label, data={"path": child_path})
                self._node_count += 1
                if isinstance(value, (dict, list)):
                    self._build_tree(child, value, child_path, diffs, mode)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                child_path = f"{path}[{i}]"
                if not show_all and child_path not in self._visible_paths:
                    continue
                diff = self._find_diff(child_path, diffs)
                has_descendant_diff = child_path in self._paths_with_descendant_diffs
                label = self._format_label(f"[{i}]", item, diff, has_descendant_diff)
                child = node.add(label, data={"path": child_path})
                self._node_count += 1
                if isinstance(item, (dict, list)):
                    self._build_tree(child, item, child_path, diffs, mode)

    def _find_diff(self, path: str, diffs: List[DiffEntry]) -> Optional[DiffEntry]:
        for diff in diffs:
            if diff.path == path:
                return diff
        return None

    def _format_label(self, key: str, value: Any, diff: Optional[DiffEntry], has_descendant_diff: bool = False) -> Text:
        text = Text()
        is_container = isinstance(value, (dict, list))
        if diff and diff.type != DiffType.UNCHANGED:
            (marker_text, marker_style) = self._get_diff_marker(diff.type)
            text.append(marker_text, style=marker_style)
            text.append(" ")
        elif has_descendant_diff:
            text.append("●", style="bold yellow")
            text.append(" ")
        elif not is_container:
            text.append("▶ ", style="dim")
        if isinstance(value, dict):
            text.append(f"▶ {key}", style="bold")
            text.append(f" ({len(value)} keys)", style="dim")
        elif isinstance(value, list):
            text.append(f"▶ {key}", style="bold")
            text.append(f" ({len(value)} items)", style="dim")
        else:
            text.append(f"├─ {key}: ")
            text.append(self._truncate(value), style="dim")
        return text

    def _get_diff_marker(self, diff_type: DiffType) -> tuple:
        markers = {
            DiffType.CHANGED: ("●", "bold yellow"),
            DiffType.LEFT_ONLY: ("◀", "bold green"),
            DiffType.RIGHT_ONLY: ("▶", "bold blue"),
        }
        return markers.get(diff_type, ("", ""))

    def _truncate(self, value: Any, max_len: int = 30) -> str:
        if value is None:
            return "null"
        if isinstance(value, str):
            s = value
        else:
            s = json.dumps(value, separators=(",", ":"))
        return s[:max_len] + "..." if len(s) > max_len else s


class DocumentHeader(Static):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.left_doc: Optional[dict] = None
        self.right_doc: Optional[dict] = None

    def set_documents(self, left: Optional[dict], right: Optional[dict]) -> None:
        self.left_doc = left
        self.right_doc = right
        self._update_display()

    def _update_display(self) -> None:
        try:
            total_width = self.app.size.width - 20
            doc_width = total_width // 2
        except Exception:
            doc_width = 40
        left_info = self._format_doc(self.left_doc, doc_width)
        right_info = self._format_doc(self.right_doc, doc_width)
        self.update(f"Left: {left_info}  ⇄  Right: {right_info}")

    def _format_doc(self, doc: Optional[dict], max_width: int = 40) -> str:
        if not doc:
            return "[Not loaded]"
        collection = doc.get("collection", "Unknown")
        version = doc.get("version", "?")
        doc_id = doc.get("_id", "")[:12]
        full_text = f"{collection} v{version} ({doc_id}…)"
        if len(full_text) > max_width:
            suffix = f" v{version} ({doc_id}…)"
            available_for_collection = max_width - len(suffix) - 1
            if available_for_collection > 3:
                collection = collection[:available_for_collection] + "…"
            full_text = f"{collection} v{version} ({doc_id}…)"
        return full_text


class JSONDiffMergeScreen(BaseScreen):
    FOCUSABLE_CONTROLS = [WidgetID.JSON_TREE, WidgetID.DIFF_TABLE]
    SECONDARY_ACTIONS = [
        ("c", "copy_value", "Copy"),
        ("s", "save_changes", "Save"),
        ("m", "cycle_mode", "Mode"),
        ("b", "toggle_bookkeeping", "BkTgl"),
        ("w", "swap_documents", "Swap"),
        ("v", "view_left_document", "View"),
    ]
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False, priority=True),
        Binding("k", "cursor_up", "Up", show=False, priority=True),
        Binding("down", "cursor_down", "Down", show=False, priority=True),
        Binding("up", "cursor_up", "Up", show=False, priority=True),
        Binding("g", "first_item", "Top", show=False, priority=True),
        Binding("G", "last_item", "Bottom", show=False, priority=True),
        Binding("ctrl+d", "page_down", "Page Down", show=False, priority=True),
        Binding("ctrl+u", "page_up", "Page Up", show=False, priority=True),
        Binding("l", "tree_expand_or_enter", "Expand/Enter", show=False, priority=True),
        Binding("right", "tree_expand_or_enter", "Expand/Enter", show=False, priority=True),
        Binding("h", "tree_collapse_or_back", "Collapse/Back", show=False, priority=True),
        Binding("left", "tree_collapse_or_back", "Collapse/Back", show=False, priority=True),
        Binding("escape", "go_back", "Back", show=False, priority=True),
        Binding("tab", "switch_panel", "Switch Panel", show=False, priority=True),
        Binding("space", "toggle_expand", "Expand", show=False, priority=True),
        Binding("r", "refresh_data", "Refresh", show=False, priority=True),
        Binding("c", "copy_value", "Copy", show=False, priority=True),
        Binding("s", "save_changes", "Save", show=False, priority=True),
        Binding("m", "cycle_mode", "Mode", show=False, priority=True),
        Binding("b", "toggle_bookkeeping", "BK", show=False, priority=True),
        Binding("w", "swap_documents", "Swap", show=False, priority=True),
        Binding("v", "view_left_document", "View", show=False, priority=True),
    ]

    def __init__(self, left_doc: Optional[dict] = None, right_doc: Optional[dict] = None, **kwargs):
        super().__init__(**kwargs)
        self.left_doc = left_doc
        self.right_doc = right_doc
        self.left_modified = False
        self.right_modified = False
        self.comparison_mode = ComparisonMode.CHANGED_ONLY
        self.bookkeeping_mode = BookkeepingMode.EXCLUDE_BK_AND_TS
        self.all_diffs: List[DiffEntry] = []
        self.filtered_diffs: List[DiffEntry] = []
        self._loading = False
        self._active_panel = "tree"
        self.copy_operations: List[CopyOperation] = []
        self.selected_path: str = ""

    def compose_content(self) -> ComposeResult:
        yield Static("JSON Diff/Merge", classes="screen-title")
        with Horizontal(id="doc-header-row"):
            yield DocumentHeader(id="doc-header")
        with Vertical(id="main-panels"):
            yield JSONTree("Document", id=WidgetID.JSON_TREE)
            yield Static("", id=WidgetID.DIFF_STATUS_BAR)
            yield DiffTable(id=WidgetID.DIFF_TABLE)

    def on_mount(self) -> None:
        trace.info("JSONDiffMergeScreen mounted", tags=["screen", "lifecycle"])
        if not self.left_doc and (not self.right_doc):
            self._load_default_documents()
        try:
            diff_table = self.query_one(f"#{WidgetID.DIFF_TABLE}", DiffTable)
            diff_table.setup_columns()
        except Exception as e:
            trace.error("Failed to setup diff table columns", tags=["screen", "error"], exception=e)
        try:
            doc_header = self.query_one("#doc-header", DocumentHeader)
            doc_header.set_documents(self.left_doc, self.right_doc)
        except Exception as e:
            trace.error("Failed to setup document header", tags=["screen", "error"], exception=e)
        if self.left_doc and self.right_doc:
            self._start_comparison()
        else:
            self._update_status("No documents loaded. Use menu to select documents.")
        self.focus_first_control()

    def _load_default_documents(self) -> None:
        try:
            if DEFAULT_LEFT_DOC.exists():
                with open(DEFAULT_LEFT_DOC) as f:
                    self.left_doc = json.load(f)
                trace.debug("Loaded default left document", tags=["diff-merge", "load"], path=str(DEFAULT_LEFT_DOC))
        except Exception as e:
            trace.error(
                "Failed to load default left document",
                tags=["filesystem", "error"],
                exception=e,
                path=str(DEFAULT_LEFT_DOC),
            )
        try:
            if DEFAULT_RIGHT_DOC.exists():
                with open(DEFAULT_RIGHT_DOC) as f:
                    self.right_doc = json.load(f)
                trace.debug("Loaded default right document", tags=["diff-merge", "load"], path=str(DEFAULT_RIGHT_DOC))
        except Exception as e:
            trace.error(
                "Failed to load default right document",
                tags=["filesystem", "error"],
                exception=e,
                path=str(DEFAULT_RIGHT_DOC),
            )

    def _start_comparison(self) -> None:
        if self._loading:
            return
        self._loading = True
        trace.debug(
            "Starting diff computation",
            tags=["diff-merge", "comparison"],
            left_id=self.left_doc.get("_id") if self.left_doc else None,
            right_id=self.right_doc.get("_id") if self.right_doc else None,
            bookkeeping_mode=self.bookkeeping_mode.value,
        )
        self.run_worker(self._compute_diff_async(), name="compute_diff", exclusive=True)

    async def _compute_diff_async(self) -> List[DiffEntry]:
        return await asyncio.to_thread(self._compute_diff_sync)

    def _compute_diff_sync(self) -> List[DiffEntry]:
        if not self.left_doc or not self.right_doc:
            return []
        exclude_keys: Set[str] = set()
        if self.bookkeeping_mode in (BookkeepingMode.EXCLUDE_BOOKKEEPING, BookkeepingMode.EXCLUDE_BK_AND_TS):
            exclude_keys.add("bookkeeping")
        diffs = compute_diff(self.left_doc, self.right_doc, exclude_keys=exclude_keys)
        if self.bookkeeping_mode == BookkeepingMode.EXCLUDE_BK_AND_TS:
            diffs = [d for d in diffs if not self._is_timestamp_path(d.path)]
        trace.info(
            "Diff computed",
            tags=["diff-merge", "comparison"],
            total=len(diffs),
            changed=len([d for d in diffs if d.type == DiffType.CHANGED]),
            left_only=len([d for d in diffs if d.type == DiffType.LEFT_ONLY]),
            right_only=len([d for d in diffs if d.type == DiffType.RIGHT_ONLY]),
            bookkeeping_mode=self.bookkeeping_mode.value,
        )
        return diffs

    def _is_timestamp_path(self, path: str) -> bool:
        timestamp_keys = (".assigned", ".created", ".CREATION_TIME", "assigned", "created", "CREATION_TIME")
        return path.endswith(timestamp_keys)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name != "compute_diff":
            return
        if event.state.name == "SUCCESS":
            self._loading = False
            self.all_diffs = event.worker.result or []
            self._update_display()
        elif event.state.name == "ERROR":
            self._loading = False
            trace.error("Diff computation failed", tags=["screen", "error"], exception=event.worker.error)
            self.notify(f"Error computing diff: {event.worker.error}", severity="error")

    def _update_display(self, rebuild_tree: bool = True) -> None:
        mode_filtered = filter_diffs(self.all_diffs, self.comparison_mode)
        if self.selected_path:
            self.filtered_diffs = [d for d in mode_filtered if d.path.startswith(self.selected_path)]
        else:
            self.filtered_diffs = mode_filtered
        try:
            diff_table = self.query_one(f"#{WidgetID.DIFF_TABLE}", DiffTable)
            diff_table.clear()
            diff_table.set_base_path(self.selected_path)
            for diff in self.filtered_diffs:
                diff_table.add_diff(diff)
        except Exception as e:
            trace.error("Failed to update diff table", tags=["screen", "error"], exception=e)
        if rebuild_tree:
            try:
                json_tree = self.query_one(f"#{WidgetID.JSON_TREE}", JSONTree)
                if self.left_doc:
                    json_tree.load_document(self.left_doc, self.all_diffs, self.comparison_mode)
            except Exception as e:
                trace.error("Failed to update JSON tree", tags=["screen", "error"], exception=e)
        self._update_status_counts()

    def _update_status_counts(self) -> None:
        total = len([d for d in self.all_diffs if d.type != DiffType.UNCHANGED])
        left_only = len([d for d in self.all_diffs if d.type == DiffType.LEFT_ONLY])
        right_only = len([d for d in self.all_diffs if d.type == DiffType.RIGHT_ONLY])
        changed = len([d for d in self.all_diffs if d.type == DiffType.CHANGED])
        bk_labels = {
            BookkeepingMode.INCLUDE_ALL: "BK:All",
            BookkeepingMode.EXCLUDE_BOOKKEEPING: "BK:Off",
            BookkeepingMode.EXCLUDE_BK_AND_TS: "BK+TS:Off",
        }
        bk_status = bk_labels[self.bookkeeping_mode]
        mode_labels = {
            ComparisonMode.ALL_DIFFERENCES: "All",
            ComparisonMode.LEFT_ONLY: "Left",
            ComparisonMode.RIGHT_ONLY: "Right",
            ComparisonMode.CHANGED_ONLY: "Changed",
            ComparisonMode.SHOW_ALL: "Show All",
        }
        mode_status = mode_labels[self.comparison_mode]
        status = f"{bk_status} │ Mode: {mode_status} │ Diffs: {total} │ Left: {left_only} │ Right: {right_only} │ Changed: {changed}"
        if self.left_modified or self.right_modified:
            status += " │ [MODIFIED]"
        self._update_status(status)

    def _update_status(self, text: str) -> None:
        try:
            status_bar = self.query_one(f"#{WidgetID.DIFF_STATUS_BAR}", Static)
            status_bar.update(text)
        except Exception:
            pass

    def action_cursor_down(self) -> None:
        if self._active_panel == "diff":
            try:
                diff_table = self.query_one(f"#{WidgetID.DIFF_TABLE}", DiffTable)
                diff_table.action_cursor_down()
            except Exception:
                pass
        else:
            try:
                json_tree = self.query_one(f"#{WidgetID.JSON_TREE}", JSONTree)
                before_node = json_tree.cursor_node
                before_label = str(before_node.label)[:30] if before_node else "None"
                json_tree.action_cursor_down()
                after_node = json_tree.cursor_node
                after_label = str(after_node.label)[:30] if after_node else "None"
                trace.debug(
                    "Tree cursor down",
                    tags=["tree", "navigation"],
                    panel=self._active_panel,
                    before=before_label,
                    after=after_label,
                    moved=before_label != after_label,
                )
            except Exception as e:
                trace.debug("Tree cursor down failed", tags=["tree", "navigation", "error"], error=str(e))

    def action_cursor_up(self) -> None:
        if self._active_panel == "diff":
            try:
                diff_table = self.query_one(f"#{WidgetID.DIFF_TABLE}", DiffTable)
                diff_table.action_cursor_up()
            except Exception:
                pass
        else:
            try:
                json_tree = self.query_one(f"#{WidgetID.JSON_TREE}", JSONTree)
                before_node = json_tree.cursor_node
                before_label = str(before_node.label)[:30] if before_node else "None"
                json_tree.action_cursor_up()
                after_node = json_tree.cursor_node
                after_label = str(after_node.label)[:30] if after_node else "None"
                trace.debug(
                    "Tree cursor up",
                    tags=["tree", "navigation"],
                    panel=self._active_panel,
                    before=before_label,
                    after=after_label,
                    moved=before_label != after_label,
                )
            except Exception as e:
                trace.debug("Tree cursor up failed", tags=["tree", "navigation", "error"], error=str(e))

    def action_first_item(self) -> None:
        if self._active_panel == "diff":
            try:
                diff_table = self.query_one(f"#{WidgetID.DIFF_TABLE}", DiffTable)
                diff_table.action_scroll_top()
            except Exception:
                pass

    def action_last_item(self) -> None:
        if self._active_panel == "diff":
            try:
                diff_table = self.query_one(f"#{WidgetID.DIFF_TABLE}", DiffTable)
                diff_table.action_scroll_bottom()
            except Exception:
                pass

    def action_page_down(self) -> None:
        if self._active_panel == "diff":
            try:
                diff_table = self.query_one(f"#{WidgetID.DIFF_TABLE}", DiffTable)
                diff_table.action_page_down()
            except Exception:
                pass

    def action_page_up(self) -> None:
        if self._active_panel == "diff":
            try:
                diff_table = self.query_one(f"#{WidgetID.DIFF_TABLE}", DiffTable)
                diff_table.action_page_up()
            except Exception:
                pass

    def action_go_back(self) -> None:
        if self.left_modified or self.right_modified:
            self.notify("Unsaved changes will be lost", severity="warning")
        trace.info(
            "Returning from JSONDiffMergeScreen",
            tags=["screen", "navigation"],
            from_screen="JSONDiffMergeScreen",
            reason="User pressed back (escape/h/left)",
        )
        self.app.pop_screen()

    def action_switch_panel(self) -> None:
        old_panel = self._active_panel
        try:
            diff_table = self.query_one(f"#{WidgetID.DIFF_TABLE}", DiffTable)
            json_tree = self.query_one(f"#{WidgetID.JSON_TREE}", JSONTree)
            if self._active_panel == "diff":
                json_tree.focus()
                self._active_panel = "tree"
            else:
                diff_table.focus()
                self._active_panel = "diff"
            trace.debug(
                "Panel switched",
                tags=["tree", "navigation", "focus"],
                from_panel=old_panel,
                to_panel=self._active_panel,
            )
        except Exception as e:
            trace.error("Failed to switch panel", tags=["screen", "error"], exception=e)

    def action_toggle_expand(self) -> None:
        if self._active_panel == "tree":
            try:
                json_tree = self.query_one(f"#{WidgetID.JSON_TREE}", JSONTree)
                node = json_tree.cursor_node
                if node:
                    was_expanded = node.is_expanded
                    has_children = bool(node.children)
                    node_label = str(node.label)[:30]
                    node.toggle()
                    trace.debug(
                        "Tree toggle expand",
                        tags=["tree", "expand"],
                        node=node_label,
                        was_expanded=was_expanded,
                        now_expanded=node.is_expanded,
                        has_children=has_children,
                        child_count=len(node.children) if node.children else 0,
                    )
                else:
                    trace.debug("Tree toggle expand - no cursor node", tags=["tree", "expand", "warning"])
            except Exception as e:
                trace.debug("Tree toggle expand failed", tags=["tree", "expand", "error"], error=str(e))

    def action_tree_expand_or_enter(self) -> None:
        trace.debug("Tree expand/enter requested", tags=["tree", "navigation"], panel=self._active_panel)
        if self._active_panel == "tree":
            try:
                json_tree = self.query_one(f"#{WidgetID.JSON_TREE}", JSONTree)
                node = json_tree.cursor_node
                if node:
                    node_label = str(node.label)[:30]
                    is_expanded = node.is_expanded
                    has_children = bool(node.children)
                    child_count = len(node.children) if node.children else 0
                    trace.debug(
                        "Tree expand/enter - node state",
                        tags=["tree", "navigation"],
                        node=node_label,
                        is_expanded=is_expanded,
                        has_children=has_children,
                        child_count=child_count,
                    )
                    if not is_expanded and has_children:
                        node.expand()
                        trace.debug(
                            "Tree expand/enter - expanded node",
                            tags=["tree", "expand"],
                            node=node_label,
                            action="expand",
                        )
                    elif is_expanded and has_children:
                        first_child = node.children[0]
                        child_label = str(first_child.label)[:30]
                        trace.debug(
                            "Tree expand/enter - entering first child",
                            tags=["tree", "navigation"],
                            from_node=node_label,
                            to_child=child_label,
                            action="enter_child",
                        )
                        json_tree.select_node(first_child)
                        after_node = json_tree.cursor_node
                        after_label = str(after_node.label)[:30] if after_node else "None"
                        trace.debug(
                            "Tree expand/enter - after select_node",
                            tags=["tree", "navigation"],
                            expected=child_label,
                            actual=after_label,
                            success=after_label == child_label,
                        )
                    else:
                        trace.debug(
                            "Tree expand/enter - no action (leaf or no children)",
                            tags=["tree", "navigation"],
                            node=node_label,
                            reason="leaf_node" if not has_children else "unknown",
                        )
                else:
                    trace.debug("Tree expand/enter - no cursor node", tags=["tree", "navigation", "warning"])
            except Exception as e:
                trace.debug(
                    "Tree expand/enter failed",
                    tags=["tree", "navigation", "error"],
                    error=str(e),
                    error_type=type(e).__name__,
                )

    def action_tree_collapse_or_back(self) -> None:
        trace.debug("Tree collapse/back requested", tags=["tree", "navigation"], panel=self._active_panel)
        if self._active_panel == "tree":
            try:
                json_tree = self.query_one(f"#{WidgetID.JSON_TREE}", JSONTree)
                node = json_tree.cursor_node
                if node:
                    node_label = str(node.label)[:30]
                    is_expanded = node.is_expanded
                    has_children = bool(node.children)
                    has_parent = node.parent is not None
                    is_root_child = node.parent == json_tree.root if node.parent else False
                    trace.debug(
                        "Tree collapse/back - node state",
                        tags=["tree", "navigation"],
                        node=node_label,
                        is_expanded=is_expanded,
                        has_children=has_children,
                        has_parent=has_parent,
                        is_root_child=is_root_child,
                    )
                    if is_expanded and has_children:
                        node.collapse()
                        trace.debug(
                            "Tree collapse/back - collapsed node",
                            tags=["tree", "expand"],
                            node=node_label,
                            action="collapse",
                        )
                    elif has_parent and (not is_root_child):
                        parent_label = str(node.parent.label)[:30]
                        trace.debug(
                            "Tree collapse/back - going to parent",
                            tags=["tree", "navigation"],
                            from_node=node_label,
                            to_parent=parent_label,
                            action="go_to_parent",
                        )
                        json_tree.select_node(node.parent)
                        after_node = json_tree.cursor_node
                        after_label = str(after_node.label)[:30] if after_node else "None"
                        trace.debug(
                            "Tree collapse/back - after select_node",
                            tags=["tree", "navigation"],
                            expected=parent_label,
                            actual=after_label,
                            success=after_label == parent_label,
                        )
                    else:
                        trace.debug(
                            "Tree collapse/back - exiting screen",
                            tags=["tree", "navigation"],
                            node=node_label,
                            reason="at_root_level",
                            action="go_back",
                        )
                        self.action_go_back()
                else:
                    trace.debug(
                        "Tree collapse/back - no cursor node, going back", tags=["tree", "navigation", "warning"]
                    )
                    self.action_go_back()
            except Exception as e:
                trace.debug(
                    "Tree collapse/back failed",
                    tags=["tree", "navigation", "error"],
                    error=str(e),
                    error_type=type(e).__name__,
                )
        else:
            trace.debug(
                "Tree collapse/back - not in tree panel, going back",
                tags=["tree", "navigation"],
                panel=self._active_panel,
                action="go_back",
            )
            self.action_go_back()

    def action_copy_value(self) -> None:
        if self._active_panel != "diff":
            self.notify("Select a diff entry in the table to copy", severity="warning")
            return
        try:
            diff_table = self.query_one(f"#{WidgetID.DIFF_TABLE}", DiffTable)
            if diff_table.cursor_row is not None and diff_table.cursor_row < len(self.filtered_diffs):
                diff = self.filtered_diffs[diff_table.cursor_row]
                self._perform_copy(diff)
        except Exception as e:
            trace.error("Copy value operation failed", tags=["screen", "error"], exception=e)
            self.notify(f"Copy failed: {e}", severity="error")

    def _perform_copy(self, diff: DiffEntry) -> None:
        if diff.type == DiffType.UNCHANGED:
            self.notify("No difference to copy", severity="information")
            return
        if diff.type == DiffType.LEFT_ONLY:
            if self.right_doc is not None:
                op = CopyOperation(source="left", target="right", path=diff.path, value=diff.left)
                op.apply(self.left_doc or {}, self.right_doc)
                self.copy_operations.append(op)
                self.right_modified = True
                trace.debug("Copy operation", tags=["diff-merge", "copy"], path=diff.path, direction="left_to_right")
                self.notify(f"Copied to right: {diff.path}")
        elif diff.type == DiffType.RIGHT_ONLY:
            if self.left_doc is not None:
                op = CopyOperation(source="right", target="left", path=diff.path, value=diff.right)
                op.apply(self.left_doc, self.right_doc or {})
                self.copy_operations.append(op)
                self.left_modified = True
                trace.debug("Copy operation", tags=["diff-merge", "copy"], path=diff.path, direction="right_to_left")
                self.notify(f"Copied to left: {diff.path}")
        elif diff.type == DiffType.CHANGED:
            if self.right_doc is not None:
                op = CopyOperation(source="left", target="right", path=diff.path, value=diff.left)
                op.apply(self.left_doc or {}, self.right_doc)
                self.copy_operations.append(op)
                self.right_modified = True
                trace.debug("Copy operation", tags=["diff-merge", "copy"], path=diff.path, direction="left_to_right")
                self.notify(f"Copied left value to right: {diff.path}")
        self._start_comparison()

    def action_cycle_mode(self) -> None:
        modes = list(ComparisonMode)
        current_idx = modes.index(self.comparison_mode)
        next_idx = (current_idx + 1) % len(modes)
        self.comparison_mode = modes[next_idx]
        trace.debug("Mode changed", tags=["diff-merge", "ui"], mode=self.comparison_mode.value)
        self._update_display()
        self.notify(f"Mode: {self.comparison_mode.name.replace('_', ' ').title()}")

    def action_toggle_bookkeeping(self) -> None:
        modes = list(BookkeepingMode)
        current_idx = modes.index(self.bookkeeping_mode)
        next_idx = (current_idx + 1) % len(modes)
        self.bookkeeping_mode = modes[next_idx]
        trace.debug("Bookkeeping mode changed", tags=["diff-merge", "ui"], bookkeeping_mode=self.bookkeeping_mode.value)
        self._start_comparison()
        mode_labels = {
            BookkeepingMode.INCLUDE_ALL: "All fields included",
            BookkeepingMode.EXCLUDE_BOOKKEEPING: "Bookkeeping excluded",
            BookkeepingMode.EXCLUDE_BK_AND_TS: "Bookkeeping & timestamps excluded",
        }
        self.notify(mode_labels[self.bookkeeping_mode])

    def action_swap_documents(self) -> None:
        (self.left_doc, self.right_doc) = (self.right_doc, self.left_doc)
        (self.left_modified, self.right_modified) = (self.right_modified, self.left_modified)
        try:
            doc_header = self.query_one("#doc-header", DocumentHeader)
            doc_header.set_documents(self.left_doc, self.right_doc)
        except Exception:
            pass
        trace.debug("Documents swapped", tags=["diff-merge", "ui"])
        self._start_comparison()
        self.notify("Documents swapped")

    def action_refresh_data(self) -> None:
        left_id = self.left_doc.get("_id") if self.left_doc else None
        right_id = self.right_doc.get("_id") if self.right_doc else None
        trace.info(
            "Refreshing with cache invalidation",
            tags=["diff-merge", "refresh", "cache"],
            left_id=left_id,
            right_id=right_id,
        )
        if hasattr(self.app, "backend") and hasattr(self.app.backend, "cache"):
            cache = self.app.backend.cache
            if left_id:
                cache.delete(f"doc:{left_id}")
                trace.debug("Cache invalidated for left document", tags=["cache", "mutation"], document_id=left_id)
            if right_id:
                cache.delete(f"doc:{right_id}")
                trace.debug("Cache invalidated for right document", tags=["cache", "mutation"], document_id=right_id)
        if hasattr(self.app, "backend"):
            if left_id:
                try:
                    left_doc = self.app.backend.get_document_by_id(left_id)
                    if left_doc:
                        self.left_doc = left_doc.model_dump(by_alias=True)
                        trace.debug("Left document reloaded", tags=["diff-merge", "refresh"], document_id=left_id)
                except Exception as e:
                    trace.error(
                        "Failed to reload left document",
                        tags=["diff-merge", "refresh", "error"],
                        exception=e,
                        document_id=left_id,
                    )
            if right_id:
                try:
                    right_doc = self.app.backend.get_document_by_id(right_id)
                    if right_doc:
                        self.right_doc = right_doc.model_dump(by_alias=True)
                        trace.debug("Right document reloaded", tags=["diff-merge", "refresh"], document_id=right_id)
                except Exception as e:
                    trace.error(
                        "Failed to reload right document",
                        tags=["diff-merge", "refresh", "error"],
                        exception=e,
                        document_id=right_id,
                    )
        try:
            doc_header = self.query_one("#doc-header", DocumentHeader)
            doc_header.set_documents(self.left_doc, self.right_doc)
        except Exception:
            pass
        self._start_comparison()
        self.notify("Refreshing (cache invalidated)...")

    def action_view_left_document(self) -> None:
        if not self.left_doc:
            self.notify("No left document loaded", severity="warning")
            return
        document_id = self.left_doc.get("_id")
        if not document_id:
            self.notify("Left document has no ID", severity="warning")
            return
        trace.info(
            "Navigating to DocumentViewScreen",
            tags=["screen", "navigation"],
            from_screen="JSONDiffMergeScreen",
            to_screen="DOCUMENT_VIEW",
            reason="User pressed view (v) on left document",
            document_id=document_id,
        )
        self.app.state.navigate_to_document(document_id)
        self.app.push_screen(ScreenName.DOCUMENT_VIEW)

    def action_save_changes(self) -> None:
        if not self.left_modified and (not self.right_modified):
            self.notify("No changes to save", severity="information")
            return
        trace.info(
            "Save requested",
            tags=["diff-merge", "save"],
            left_modified=self.left_modified,
            right_modified=self.right_modified,
            operation_count=len(self.copy_operations),
        )
        self.notify("Save functionality not yet implemented", severity="warning")

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        node_label = str(event.node.label)[:30] if event.node else "None"
        node_data = event.node.data
        old_path = self.selected_path
        if node_data and "path" in node_data:
            self.selected_path = node_data["path"]
        else:
            self.selected_path = ""
        trace.debug(
            "Tree node highlighted",
            tags=["tree", "event"],
            node=node_label,
            old_path=old_path[:30] if old_path else "root",
            new_path=self.selected_path[:30] if self.selected_path else "root",
            has_data=bool(node_data),
        )
        self._update_display(rebuild_tree=False)


from ..dbbrowser.version_list import VersionListScreen
from textual.binding import Binding as TextualBinding
from textual.screen import ModalScreen
from textual.widgets import Button, Label
from textual.containers import Container


class DeleteConfirmModal(ModalScreen[bool]):
    BINDINGS = [
        TextualBinding("escape", "cancel", "Cancel", priority=True),
        TextualBinding("enter", "confirm", "Confirm", priority=True),
        TextualBinding("y", "confirm", "Yes", show=False),
        TextualBinding("n", "cancel", "No", show=False),
    ]

    def __init__(self, document_id: str, collection: str, version: str):
        super().__init__()
        self.document_id = document_id
        self.collection = collection
        self.version = version

    def compose(self):
        with Container(id="delete-confirm-dialog"):
            yield Label("Delete Document", classes="modal-title")
            yield Label(
                f"Are you sure you want to delete this document?\n\nCollection: {self.collection}\nVersion: {self.version}\nID: {self.document_id[:16]}...",
                classes="modal-message",
            )
            yield Label("Press [Y/Enter] to confirm, [N/Esc] to cancel", classes="modal-hint")
            with Container(classes="modal-buttons"):
                yield Button("Delete", variant="error", id="btn-delete")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-delete":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class DeleteAllTrashModal(ModalScreen[bool]):
    BINDINGS = [
        TextualBinding("escape", "cancel", "Cancel", priority=True),
        TextualBinding("enter", "confirm", "Confirm", priority=True),
        TextualBinding("y", "confirm", "Yes", show=False),
        TextualBinding("n", "cancel", "No", show=False),
    ]

    def __init__(self, collection: str, document_count: int, document_ids: list):
        super().__init__()
        self.collection = collection
        self.document_count = document_count
        self.document_ids = document_ids

    def compose(self):
        with Container(id="delete-confirm-dialog"):
            yield Label("Delete All Trash Documents", classes="modal-title")
            yield Label(
                f"Are you sure you want to delete ALL {self.document_count} trash documents?\n\nCollection: {self.collection}\n\nThis action cannot be undone!",
                classes="modal-message",
            )
            yield Label("Press [Y/Enter] to confirm, [N/Esc] to cancel", classes="modal-hint")
            with Container(classes="modal-buttons"):
                yield Button("Delete All", variant="error", id="btn-delete")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-delete":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class DiffableVersionListScreen(VersionListScreen):
    _skip_resume_reload: bool = False
    SECONDARY_ACTIONS = [
        ("slash", "focus_filter", "Filter"),
        ("c", "clear_filter", "Clear"),
        ("w", "diff_with_next", "Diff"),
        ("d", "delete_document", "Del"),
        ("ctrl+t", "toggle_trash_mode", "TrashTgl"),
        ("ctrl+d", "delete_all_trash", "DelAll"),
    ]
    BINDINGS = [
        Binding("w", "diff_with_next", "Diff", show=False, priority=True),
        Binding("d", "delete_document", "Del", show=False, priority=True),
        Binding("ctrl+t", "toggle_trash_mode", "TrashTgl", show=False, priority=True),
        Binding("ctrl+d", "delete_all_trash", "DelAll", show=False, priority=True),
    ]

    def _is_trash_mode(self) -> bool:
        from ...data.analyzers import TrashDuplicateVersionAnalyzer

        return isinstance(self.app.state.analyzer, TrashDuplicateVersionAnalyzer)

    def check_action(self, action: str, parameters: tuple) -> Optional[bool]:
        if action == "delete_all_trash":
            return self._is_trash_mode()
        return True

    def on_screen_resume(self) -> None:
        if self._skip_resume_reload:
            trace.debug(
                "Skipping resume reload after deletion",
                tags=["screen", "lifecycle", "refresh"],
                collection=self._collection_name,
            )
            self._apply_key_panel_visibility()
            self._update_footer()
            return
        super().on_screen_resume()

    def action_diff_with_next(self) -> None:
        table = self.get_table()
        if table.cursor_row is None or not self.filtered_items:
            self.notify("No document selected", severity="warning")
            return
        cursor_row = table.cursor_row
        if cursor_row >= len(self.filtered_items):
            self.notify("No document selected", severity="warning")
            return
        if cursor_row + 1 >= len(self.filtered_items):
            self.notify("No document below to compare with", severity="warning")
            return
        left_doc_id = self.filtered_items[cursor_row].id
        right_doc_id = self.filtered_items[cursor_row + 1].id
        trace.debug(
            "Opening diff for adjacent documents",
            tags=["screen", "version", "diff"],
            left_id=left_doc_id,
            right_id=right_doc_id,
        )
        try:
            left_doc = self.app.backend.get_document_by_id(left_doc_id)
            right_doc = self.app.backend.get_document_by_id(right_doc_id)
            if not left_doc or not right_doc:
                self.notify("Failed to load documents for comparison", severity="error")
                return
            left_dict = left_doc.model_dump(by_alias=True)
            right_dict = right_doc.model_dump(by_alias=True)
            trace.info(
                "Navigating to JSONDiffMergeScreen",
                tags=["screen", "navigation"],
                from_screen="DiffableVersionListScreen",
                to_screen="JSONDiffMergeScreen",
                reason="User pressed diff (w) on adjacent versions",
                left_id=left_doc_id,
                right_id=right_doc_id,
            )
            diff_screen = JSONDiffMergeScreen(left_doc=left_dict, right_doc=right_dict)
            self.app.push_screen(diff_screen)
        except Exception as e:
            trace.error("Failed to load documents for diff comparison", tags=["database", "error"], exception=e)
            self.notify(f"Error loading documents: {e}", severity="error")

    def _perform_hard_delete(self, document_id: str, collection: str, version: int) -> None:
        trace.info(
            "Deleting document",
            tags=["document", "mutation"],
            document_id=document_id,
            collection=collection,
            version=version,
        )
        try:
            success = self.app.backend.delete_document(document_id, soft_delete=False)
            if success:
                trace.info(
                    "Document deleted successfully",
                    tags=["document", "mutation"],
                    document_id=document_id,
                    collection=collection,
                    version=version,
                )
                self.notify(f"Document v{version} deleted", severity="information")
                self._skip_resume_reload = True
                self.documents = [d for d in self.documents if d.id != document_id]
                self.filtered_items = [d for d in self.filtered_items if d.id != document_id]
                self.update_table()
                self.update_status()
                self._invalidate_analyzer()
            else:
                trace.error(
                    "Document deletion failed",
                    tags=["document", "mutation", "error"],
                    document_id=document_id,
                    collection=collection,
                    version=version,
                )
                self.notify("Failed to delete document", severity="error")
        except Exception as e:
            trace.error("Error deleting document", tags=["database", "error"], exception=e, document_id=document_id)
            self.notify(f"Error deleting document: {e}", severity="error")

    def action_delete_document(self) -> None:
        table = self.get_table()
        if table.cursor_row is None or not self.filtered_items:
            self.notify("No document selected", severity="warning")
            return
        cursor_row = table.cursor_row
        if cursor_row >= len(self.filtered_items):
            self.notify("No document selected", severity="warning")
            return
        doc_summary = self.filtered_items[cursor_row]
        document_id = doc_summary.id
        version = doc_summary.version
        collection = self._collection_name or "Unknown"
        is_trash = self._is_trash_mode()
        trace.info(
            "Delete document requested",
            tags=["document", "mutation", "trash"] if is_trash else ["document", "mutation"],
            document_id=document_id,
            collection=collection,
            version=version,
            trash_mode=is_trash,
        )
        confirm_required = self.app.config.documents.confirm_hard_delete
        if not confirm_required:
            trace.debug(
                "Skipping delete confirmation (confirm_hard_delete=False)",
                tags=["document", "mutation"],
                document_id=document_id,
            )
            self._perform_hard_delete(document_id, collection, version)
            return
        modal = DeleteConfirmModal(document_id, collection, version)
        trace.info(
            "Opening DeleteConfirmModal",
            tags=["screen", "navigation"],
            from_screen="DiffableVersionListScreen",
            to_screen="DeleteConfirmModal",
            reason="User pressed delete (d) on document",
            document_id=document_id,
            trash_mode=is_trash,
        )

        def handle_delete_result(confirmed: bool) -> None:
            if not confirmed:
                trace.debug("Delete cancelled by user", tags=["document", "mutation"], document_id=document_id)
                self.notify("Delete cancelled")
                return
            self._perform_hard_delete(document_id, collection, version)

        self.app.push_screen(modal, handle_delete_result)

    def action_toggle_trash_mode(self) -> None:
        from ...data.analyzers import DuplicateVersionAnalyzer, TrashDuplicateVersionAnalyzer

        current_analyzer = self.app.state.analyzer
        if isinstance(current_analyzer, TrashDuplicateVersionAnalyzer):
            source = current_analyzer.get_source_analyzer()
            self.app.state.set_analyzer(source)
            trace.info(
                "Switched to Duplicate Versions mode", tags=["analyzer", "mode"], collection=self._collection_name
            )
            self.notify("Switched to Duplicate Versions mode")
        elif isinstance(current_analyzer, DuplicateVersionAnalyzer):
            trash_analyzer = TrashDuplicateVersionAnalyzer(current_analyzer)
            self.app.state.set_analyzer(trash_analyzer)
            trace.info("Switched to Trash Versions mode", tags=["analyzer", "mode"], collection=self._collection_name)
            self.notify("Switched to Trash Versions mode (showing only docs to delete)")
        else:
            self.notify("Trash mode only available in Repair Mode", severity="warning")
            return
        self.apply_filters()
        self.refresh_bindings()

    def _perform_bulk_hard_delete(self, document_ids: List[str], collection: str) -> None:
        document_count = len(document_ids)
        trace.info(
            "Deleting all trash documents",
            tags=["document", "mutation", "bulk"],
            collection=collection,
            document_count=document_count,
        )
        deleted_count = 0
        failed_count = 0
        for doc_id in document_ids:
            try:
                success = self.app.backend.delete_document(doc_id, soft_delete=False)
                if success:
                    deleted_count += 1
                    trace.debug("Trash document deleted", tags=["document", "mutation", "bulk"], document_id=doc_id)
                else:
                    failed_count += 1
                    trace.error(
                        "Failed to delete trash document",
                        tags=["document", "mutation", "bulk", "error"],
                        document_id=doc_id,
                    )
            except Exception as e:
                failed_count += 1
                trace.error(
                    "Error deleting trash document", tags=["database", "error"], exception=e, document_id=doc_id
                )
        trace.info(
            "Bulk delete completed",
            tags=["document", "mutation", "bulk"],
            collection=collection,
            deleted_count=deleted_count,
            failed_count=failed_count,
            total_count=document_count,
        )
        if failed_count == 0:
            self.notify(f"Deleted {deleted_count} documents", severity="information")
        else:
            self.notify(f"Deleted {deleted_count}, failed {failed_count}", severity="warning")
        self._skip_resume_reload = True
        deleted_set = set(document_ids)
        self.documents = [d for d in self.documents if d.id not in deleted_set]
        self.filtered_items = [d for d in self.filtered_items if d.id not in deleted_set]
        self.update_table()
        self.update_status()
        if deleted_count > 0:
            self._invalidate_analyzer()

    def action_delete_all_trash(self) -> None:
        if not self._is_trash_mode():
            self.notify("Delete All only available in Trash mode (Ctrl+T)", severity="warning")
            return
        if not self.filtered_items:
            self.notify("No trash documents to delete", severity="warning")
            return
        collection = self._collection_name or "Unknown"
        document_ids = [item.id for item in self.filtered_items]
        document_count = len(document_ids)
        trace.info(
            "Delete all trash requested",
            tags=["document", "mutation", "bulk"],
            collection=collection,
            document_count=document_count,
        )
        confirm_required = self.app.config.documents.confirm_hard_delete
        if not confirm_required:
            trace.debug(
                "Skipping bulk delete confirmation (confirm_hard_delete=False)",
                tags=["document", "mutation", "bulk"],
                collection=collection,
                document_count=document_count,
            )
            self._perform_bulk_hard_delete(document_ids, collection)
            return
        modal = DeleteAllTrashModal(collection, document_count, document_ids)
        trace.info(
            "Opening DeleteAllTrashModal",
            tags=["screen", "navigation"],
            from_screen="DiffableVersionListScreen",
            to_screen="DeleteAllTrashModal",
            reason="User requested delete all trash documents",
            collection=collection,
            document_count=document_count,
        )

        def handle_delete_all_result(confirmed: bool) -> None:
            if not confirmed:
                trace.debug(
                    "Delete all cancelled by user", tags=["document", "mutation", "bulk"], collection=collection
                )
                self.notify("Delete all cancelled")
                return
            self._perform_bulk_hard_delete(document_ids, collection)

        self.app.push_screen(modal, handle_delete_all_result)

    def _invalidate_analyzer(self) -> None:
        from ...data.analyzers import DuplicateVersionAnalyzer, TrashDuplicateVersionAnalyzer

        analyzer = self.app.state.analyzer
        if analyzer is None:
            return
        if isinstance(analyzer, TrashDuplicateVersionAnalyzer):
            source = analyzer.get_source_analyzer()
        elif isinstance(analyzer, DuplicateVersionAnalyzer):
            source = analyzer
        else:
            return
        if hasattr(source, "invalidate"):
            source.invalidate()
            trace.debug(
                "Analyzer cache invalidated after deletion",
                tags=["analyzer", "cache", "invalidate"],
                collection=self._collection_name,
            )

    def action_refresh_data(self) -> None:
        trace.info(
            "Refreshing DiffableVersionListScreen with cache invalidation",
            tags=["screen", "refresh", "cache"],
            collection=self._collection_name,
        )
        if hasattr(self.app, "backend") and hasattr(self.app.backend, "cache"):
            cache = self.app.backend.cache
            collection = self._collection_name
            if collection:
                cache.delete(f"collection_docs:{collection}")
                cache.delete(f"versions:{collection}")
                cache.delete(f"versions_summary:{collection}")
            cache.delete("collections_list")
            cache.delete("collections_list_optimized")
            cache.delete("all_documents")
            trace.debug("Cache invalidated for collection", tags=["cache", "mutation"], collection=collection)
        self._invalidate_analyzer()
        self._start_lazy_load()
        self.notify("Refreshing (cache invalidated)...")
