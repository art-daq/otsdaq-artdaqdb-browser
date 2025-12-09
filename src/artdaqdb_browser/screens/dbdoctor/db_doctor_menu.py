"""
File: db_doctor_menu.py
Purpose: Database Doctor main menu screen.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: rich, textual
Exports: HNStory, BrokenConfigurationInfo, DatabaseDoctorScreen
Complexity: High | Lines: 1249
"""

import json
import random
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Tuple, Union
from rich.markup import escape as rich_escape
from textual.app import ComposeResult
from textual.widgets import Static, DataTable
from textual.binding import Binding
from textual.containers import Vertical, Horizontal, Container, VerticalScroll
from textual.worker import Worker
from ..base import DataTableScreen, NAVIGATION_BINDINGS, SCREEN_NAV_BINDINGS, ACTIONS_PRIMARY_BINDINGS, FOCUS_BINDINGS
from ..viewers import HNDetailScreen
from ...widgets import LoadingProgress
from ...constants import WidgetID, ScreenName
from ...trace import trace
from ...config import ConfigLoader, AppConfig, get_server_display_info
from ...data.analyzers import DuplicateCollectionAnalyzer, DummyAnalyzer


@dataclass
class HNStory:
    id: int
    title: str
    url: Optional[str] = None
    score: int = 0
    by: str = ""
    time: int = 0
    descendants: int = 0
    text: Optional[str] = None


def _get_config() -> AppConfig:
    loader = ConfigLoader()
    (config, warnings) = loader.load()
    for warning in warnings:
        trace.warn("Config warning", tags=["config"], warning=warning)
    return config


@dataclass
class BrokenConfigurationInfo:
    name: str
    duplicate_count: int
    total_collections: int


class DatabaseDoctorScreen(DataTableScreen):
    TABLE_ID = WidgetID.DOCTOR_MENU
    FOCUSABLE_CONTROLS = [WidgetID.DOCTOR_MENU]
    SECONDARY_ACTIONS = []
    BINDINGS = [
        *NAVIGATION_BINDINGS,
        Binding("h", "go_back", "Back", show=False),
        Binding("left", "go_back", "Back", show=False),
        Binding("l", "go_forward", "Forward", show=False),
        Binding("right", "go_forward", "Forward", show=False),
        Binding("escape", "cancel_or_back", "Back/Cancel", show=False, priority=True),
        *ACTIONS_PRIMARY_BINDINGS,
        *FOCUS_BINDINGS,
        Binding("n", "next_headline", "Next HN", show=False),
        Binding("p", "prev_headline", "Prev HN", show=False),
        Binding("d", "show_hn_detail", "HN Detail", show=False),
        Binding("s", "open_hn_story", "Open Story", show=False),
        Binding("c", "open_hn_comments", "Open Comments", show=False),
        Binding("ctrl+j", "scroll_down", "Scroll Down", show=False),
        Binding("ctrl+k", "scroll_up", "Scroll Up", show=False),
    ]
    MENU_ITEMS = [
        ("Repair Collection", "repair_collection", "Find collections with duplicate version numbers"),
        ("Repair Configuration", "repair_configuration", "Find configurations with duplicate collection references"),
        ("JSON Diff Tool", "json_diff", "Compare and merge two OTS documents side by side"),
        ("Test Progress Widget", "test_progress", "Test the progress bar with a 30-second simulated analysis"),
        ("Back to Home", "back", "Return to main menu"),
    ]

    def __init__(self):
        super().__init__()
        self._config: Optional[AppConfig] = None
        self._loading = False
        self._current_worker: Optional[Worker] = None
        self.analyzer: Optional[Union[DuplicateCollectionAnalyzer, DummyAnalyzer]] = None
        self._analysis_results: List[BrokenConfigurationInfo] = []
        self._loading_progress: Optional[LoadingProgress] = None
        self._current_analysis_type: Optional[str] = None
        self._hn_stories: List[HNStory] = []
        self._current_hn_index: int = 0
        self._fetching_hn: bool = False
        self._hn_rotation_timer = None

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            self._config = _get_config()
        return self._config

    def compose_content(self) -> ComposeResult:
        with Vertical(classes="screen-header"):
            yield Static("Database Doctor", classes="screen-title")
        with Container(classes="utilities-menu-container"):
            yield DataTable(id=self.TABLE_ID, show_header=False)
        with Container(classes="utilities-info-container"):
            yield Static("", id="menu_description", classes="menu-description")
            yield Static("", id="server_info", classes="server-info")
        yield LoadingProgress(id="loading_progress", classes="progress-only")
        hn_scroll = VerticalScroll(Static("Loading Hacker News...", id="hn_content"), id="hn_scroll")
        hn_scroll.can_focus = False
        yield hn_scroll

    def on_mount(self) -> None:
        trace.info("DatabaseDoctorScreen mounted", tags=["screen", "lifecycle"])
        self.app.state.clear_analyzer()
        self._loading_progress = self.query_one("#loading_progress", LoadingProgress)
        server_info = get_server_display_info(self.config)
        self.query_one("#server_info", Static).update(f"Server: {server_info}")
        trace.debug("Loaded configuration", tags=["screen", "dbdoctor", "query"], server_info=server_info)
        table = self.get_table()
        table.cursor_type = "row"
        table.zebra_stripes = self.app.config.tables.zebra_stripes
        table.add_column("Option", key="option", width=30)
        for name, key, desc in self.MENU_ITEMS:
            table.add_row(name, key=key)
        self.focus_first_control()
        self._update_description()
        self._fetch_hn_stories()

    def on_screen_resume(self) -> None:
        super().on_screen_resume()
        self.app.state.clear_analyzer()
        self._loading = False
        self.focus_first_control()

    def on_descendant_focus(self, event) -> None:
        widget_id = getattr(event.widget, "id", None)
        if widget_id in ("hn_scroll", "hn_content"):
            event.prevent_default()
            event.stop()
            self.get_table().focus()

    def _start_hn_rotation(self) -> None:
        self._stop_hn_rotation()
        self._hn_rotation_timer = self.set_interval(8.0, self._rotate_hn_story)

    def _stop_hn_rotation(self) -> None:
        if self._hn_rotation_timer is not None:
            self._hn_rotation_timer.stop()
            self._hn_rotation_timer = None

    def _rotate_hn_story(self) -> None:
        if self._hn_stories and self._loading:
            self._current_hn_index = (self._current_hn_index + 1) % len(self._hn_stories)
            self._show_headline_view()

    def on_click(self, event) -> None:
        target = event.widget
        while target is not None:
            if getattr(target, "id", None) in ("hn_scroll", "hn_content"):
                event.prevent_default()
                event.stop()
                self.get_table().focus()
                return
            target = getattr(target, "parent", None)

    def _get_output_widget(self) -> Optional[Static]:
        try:
            return self.query_one("#hn_content", Static)
        except Exception:
            return None

    def _get_scroll_container(self) -> Optional[VerticalScroll]:
        try:
            return self.query_one("#hn_scroll", VerticalScroll)
        except Exception:
            return None

    def _set_output_text(self, text: str, autoscroll: bool = True) -> None:
        widget = self._get_output_widget()
        if widget:
            widget.update(rich_escape(text))
            if autoscroll:
                scroll = self._get_scroll_container()
                if scroll:
                    self.call_after_refresh(lambda: scroll.scroll_end(animate=False))

    def action_scroll_down(self) -> None:
        scroll = self._get_scroll_container()
        if scroll:
            scroll.scroll_relative(y=1)

    def action_scroll_up(self) -> None:
        scroll = self._get_scroll_container()
        if scroll:
            scroll.scroll_relative(y=-1)

    def action_scroll_top(self) -> None:
        scroll = self._get_scroll_container()
        if scroll:
            scroll.scroll_home(animate=False)

    def action_scroll_bottom(self) -> None:
        scroll = self._get_scroll_container()
        if scroll:
            scroll.scroll_end(animate=False)

    def action_page_down(self) -> None:
        scroll = self._get_scroll_container()
        if scroll:
            scroll.scroll_page_down()

    def action_page_up(self) -> None:
        scroll = self._get_scroll_container()
        if scroll:
            scroll.scroll_page_up()

    def on_key(self, event) -> None:

        def update_after():
            self._update_description()

        self.call_after_refresh(update_after)

    def _update_description(self) -> None:
        if self._loading:
            return
        table = self.get_table()
        if table.cursor_row is not None and table.cursor_row < len(self.MENU_ITEMS):
            desc = self.MENU_ITEMS[table.cursor_row][2]
            self.query_one("#menu_description", Static).update(desc)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if self._loading:
            return
        if event.row_key:
            action_key = str(event.row_key.value)
            self._handle_menu_action(action_key)

    def _handle_menu_action(self, action_key: str) -> None:
        if self._loading:
            return
        action_map = {
            "repair_collection": (ScreenName.REPAIR_COLLECTION, "Repair Collection"),
            "json_diff": (ScreenName.JSON_DIFF_MERGE, "JSON Diff Tool"),
        }
        if action_key == "repair_configuration":
            self._start_configuration_analysis()
            return
        if action_key == "test_progress":
            self._start_test_progress()
            return
        if action_key == "back":
            trace.info(
                "Returning from DatabaseDoctorScreen",
                tags=["screen", "navigation"],
                from_screen="DatabaseDoctorScreen",
                reason="User selected 'Back to Home' from menu",
            )
            self.app.pop_screen()
            return
        if action_key in action_map:
            (target_screen, description) = action_map[action_key]
            trace.info(
                f"Navigating to {target_screen.value}",
                tags=["screen", "navigation"],
                from_screen="DatabaseDoctorScreen",
                to_screen=target_screen.value,
                reason=f"User selected '{description}' from menu",
            )
            self.app.push_screen(target_screen)

    def _start_configuration_analysis(self) -> None:
        if self._loading:
            return
        self._loading = True
        self._current_analysis_type = "repair_configuration"
        self.query_one("#menu_description", Static).update("Analyzing configurations... (Press ESC to cancel)")
        self._loading_progress = self.query_one("#loading_progress", LoadingProgress)
        self._loading_progress.start()
        self._start_hn_rotation()
        self.analyzer = DuplicateCollectionAnalyzer()
        trace.info("Starting duplicate collection analysis", tags=["config", "lifecycle"])
        self._current_worker = self.run_worker(
            self._run_analysis_sync, name="analyze_configurations", exclusive=True, thread=True
        )

    def _start_test_progress(self) -> None:
        trace.debug("TPW-001: Entry", tags=["screen", "dbdoctor"], loading_before=self._loading)
        if self._loading:
            trace.debug("TPW-001: Already loading, returning early", tags=["screen", "dbdoctor", "query"])
            return
        self._loading = True
        self._current_analysis_type = "test_progress"
        self.query_one("#menu_description", Static).update("Running 30-second test analysis... (Press ESC to cancel)")
        self._loading_progress = self.query_one("#loading_progress", LoadingProgress)
        trace.info(
            "TPW-001: About to call LoadingProgress.start()",
            tags=["screen", "dbdoctor", "query"],
            widget_found=self._loading_progress is not None,
        )
        self._loading_progress.start()
        self._start_hn_rotation()
        self.analyzer = DummyAnalyzer()
        trace.info(
            "TPW-001: Starting worker",
            tags=["screen", "dbdoctor", "lifecycle"],
            analyzer_type=type(self.analyzer).__name__,
        )
        self._current_worker = self.run_worker(
            self._run_test_analysis_sync, name="test_analysis", exclusive=True, thread=True
        )
        trace.info(
            "TPW-001: Worker started",
            tags=["screen", "dbdoctor", "lifecycle"],
            worker_name=self._current_worker.name if self._current_worker else None,
        )

    def _run_test_analysis_sync(self) -> None:
        import threading

        trace.debug(
            "TPW-002: Entry (in worker thread)",
            tags=["screen", "dbdoctor"],
            thread_name=threading.current_thread().name,
            analyzer_type=type(self.analyzer).__name__ if self.analyzer else None,
            callback_is_bound=callable(self._on_progress),
        )
        try:
            trace.debug("TPW-002: Calling analyzer.analyze()", tags=["screen", "dbdoctor"])
            self.analyzer.analyze(None, progress_callback=self._on_progress)
            trace.debug("TPW-002: Test analysis complete", tags=["screen", "dbdoctor", "lifecycle"])
        except Exception as e:
            trace.error("TPW-002: Test analysis failed", tags=["screen", "error"], exception=e)
            raise

    def _on_progress(self, current: int, total: int) -> None:
        import threading

        trace.debug(
            "TPW-003: Progress callback invoked",
            tags=["screen", "dbdoctor", "progress"],
            current=current,
            total=total,
            thread_name=threading.current_thread().name,
            has_loading_progress=hasattr(self, "_loading_progress") and self._loading_progress is not None,
        )
        if hasattr(self, "_loading_progress") and self._loading_progress:
            trace.debug(
                "TPW-003: Calling app.call_from_thread(set_progress)",
                tags=["screen", "dbdoctor", "progress"],
                current=current,
                total=total,
            )
            self.app.call_from_thread(self._loading_progress.set_progress, current, total)
        else:
            trace.warn("TPW-003: WARNING - no loading_progress widget reference!", tags=["screen", "dbdoctor", "query"])

    def _run_analysis_sync(self) -> List[BrokenConfigurationInfo]:
        try:
            result = self.analyzer.analyze(self.app.backend, progress_callback=self._on_progress)
            broken_configs = []
            for config_name, dup_collections in result.configurations_with_duplicate_collections.items():
                total_duplicates = sum(
                    (len(doc_ids) for doc_ids in result.duplicate_collection_details.get(config_name, {}).values())
                )
                broken_configs.append(
                    BrokenConfigurationInfo(
                        name=config_name, duplicate_count=len(dup_collections), total_collections=total_duplicates
                    )
                )
            trace.debug("Analysis complete", tags=["screen", "dbdoctor", "lifecycle"], broken_count=len(broken_configs))
            return broken_configs
        except Exception as e:
            trace.error("Duplicate collection analysis failed", tags=["database", "error"], exception=e)
            raise

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        trace.debug(
            "TPW-004: Worker state changed", tags=["state"], worker_name=event.worker.name, state=event.state.name
        )
        if event.worker.name not in ("analyze_configurations", "test_analysis"):
            trace.debug("TPW-004: Ignoring unrelated worker", tags=["state"], worker_name=event.worker.name)
            return
        if event.state.name not in ("SUCCESS", "ERROR", "CANCELLED"):
            trace.debug("TPW-004: Ignoring non-terminal state", tags=["state"], state=event.state.name)
            return
        trace.debug("TPW-004: Stopping loading progress", tags=["state", "query"])
        loading_progress = self.query_one("#loading_progress", LoadingProgress)
        loading_progress.stop()
        self._stop_hn_rotation()
        if event.state.name == "SUCCESS":
            self._loading = False
            if event.worker.name == "analyze_configurations":
                self._analysis_results = event.worker.result or []
                if self.analyzer:
                    self.app.state.set_analyzer(self.analyzer)
                trace.info(
                    "Navigating to RepairConfigurationListScreen",
                    tags=["screen", "navigation"],
                    from_screen="DatabaseDoctorScreen",
                    to_screen="REPAIR_CONFIGURATION",
                    reason="Configuration analysis completed",
                )
                self.app.push_screen(ScreenName.REPAIR_CONFIGURATION)
            elif event.worker.name == "test_analysis":
                self.notify("Test analysis completed successfully!", severity="information")
            self._update_description()
        elif event.state.name == "ERROR":
            self._loading = False
            error_msg = str(event.worker.error) if event.worker.error else "Unknown error"
            self.query_one("#menu_description", Static).update(f"Error: {error_msg}")
            self.notify(f"Analysis failed: {error_msg}", severity="error")
        elif event.state.name == "CANCELLED":
            self._loading = False
            self.query_one("#menu_description", Static).update("Analysis cancelled")
            self.notify("Analysis cancelled", severity="warning")
            self._update_description()
        self._current_worker = None
        self._current_analysis_type = None

    def action_cancel_or_back(self) -> None:
        if self._loading and self._current_worker:
            self._current_worker.cancel()
            if isinstance(self.analyzer, DummyAnalyzer):
                self.analyzer.cancel()
            self._loading = False
            loading_progress = self.query_one("#loading_progress", LoadingProgress)
            loading_progress.stop()
            self._stop_hn_rotation()
            self.notify("Analysis cancelled", severity="warning")
            self._update_description()
        else:
            trace.info(
                "Returning from DatabaseDoctorScreen",
                tags=["screen", "navigation"],
                from_screen="DatabaseDoctorScreen",
                reason="User pressed back (escape/h/left)",
            )
            self.app.pop_screen()

    def action_go_forward(self) -> None:
        if self._loading:
            return
        table = self.get_table()
        if table.cursor_row is not None and table.cursor_row < len(self.MENU_ITEMS):
            action_key = self.MENU_ITEMS[table.cursor_row][1]
            self._handle_menu_action(action_key)

    def action_go_back(self) -> None:
        if self._loading:
            return
        trace.info(
            "Returning from DatabaseDoctorScreen",
            tags=["screen", "navigation"],
            from_screen="DatabaseDoctorScreen",
            reason="User pressed back via action_go_back",
        )
        self.app.pop_screen()

    def action_next_headline(self) -> None:
        if self._hn_stories:
            self._current_hn_index = (self._current_hn_index + 1) % len(self._hn_stories)
            self._show_headline_view()

    def action_prev_headline(self) -> None:
        if self._hn_stories:
            self._current_hn_index = (self._current_hn_index - 1) % len(self._hn_stories)
            self._show_headline_view()

    def action_show_hn_detail(self) -> None:
        if self._hn_stories:
            story = self._hn_stories[self._current_hn_index]
            from ...widgets.loading_progress import HNStory as LPHNStory

            lp_story = LPHNStory(
                id=story.id,
                title=story.title,
                url=story.url,
                score=story.score,
                by=story.by,
                time=story.time,
                descendants=story.descendants,
                text=story.text,
            )
            lp_stories = [
                LPHNStory(
                    id=s.id,
                    title=s.title,
                    url=s.url,
                    score=s.score,
                    by=s.by,
                    time=s.time,
                    descendants=s.descendants,
                    text=s.text,
                )
                for s in self._hn_stories
            ]
            trace.info(
                "Navigating to HNDetailScreen",
                tags=["screen", "navigation"],
                from_screen="DatabaseDoctorScreen",
                to_screen="HNDetailScreen",
                reason="User pressed 'd' for HN story details",
                story_id=story.id,
            )
            self.app.push_screen(HNDetailScreen(lp_story, stories=lp_stories, index=self._current_hn_index))
        else:
            self.notify("HN feed not loaded yet", severity="warning", timeout=2)

    def action_open_hn_story(self) -> None:
        if self._hn_stories:
            self._show_full_story()
        else:
            self.notify("HN feed not loaded yet", severity="warning", timeout=2)

    def action_open_hn_comments(self) -> None:
        if self._hn_stories:
            self._fetch_and_show_comments()
        else:
            self.notify("HN feed not loaded yet", severity="warning", timeout=2)

    def _fetch_hn_stories(self) -> None:
        if self._fetching_hn:
            return
        self._fetching_hn = True

        def fetch_sync():
            try:
                with urllib.request.urlopen(
                    "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10
                ) as response:
                    all_story_ids = json.loads(response.read().decode())[:30]
                selected_ids = random.sample(all_story_ids, min(12, len(all_story_ids)))
                stories: List[HNStory] = []
                for story_id in selected_ids:
                    try:
                        with urllib.request.urlopen(
                            f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=5
                        ) as story_response:
                            data = json.loads(story_response.read().decode())
                            if data and "title" in data:
                                story = HNStory(
                                    id=data.get("id", 0),
                                    title=data.get("title", ""),
                                    url=data.get("url"),
                                    score=data.get("score", 0),
                                    by=data.get("by", ""),
                                    time=data.get("time", 0),
                                    descendants=data.get("descendants", 0),
                                    text=data.get("text"),
                                )
                                stories.append(story)
                    except Exception:
                        continue
                if stories:
                    random.shuffle(stories)
                return stories if stories else None
            except Exception:
                return None

        def on_fetch_complete(future):
            try:
                stories = future.result()
                if stories:
                    self._hn_stories = stories
                    self._current_hn_index = random.randint(0, len(stories) - 1)
                    try:
                        self.app.call_from_thread(self._show_headline_view)
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                self._fetching_hn = False

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(fetch_sync)
        future.add_done_callback(on_fetch_complete)
        executor.shutdown(wait=False)

    def _show_headline_view(self) -> None:
        if not self._hn_stories:
            self._set_output_text("No stories available.", autoscroll=False)
            return
        story = self._hn_stories[self._current_hn_index]
        lines = []
        lines.append("=" * 70)
        lines.append(f"  {story.title}")
        meta = f"  {story.score} pts · @{story.by} · {story.descendants} comments"
        lines.append(meta)
        if story.url:
            try:
                from urllib.parse import urlparse

                domain = urlparse(story.url).netloc
                if domain.startswith("www."):
                    domain = domain[4:]
                lines.append(f"  ({domain})")
            except Exception:
                pass
        lines.append("=" * 70)
        if story.text:
            text = self._clean_html(story.text)
            preview_lines = [p.strip() for p in text.split("\n") if p.strip()][:5]
            for line in preview_lines:
                wrapped = self._wrap_text(line, 66)
                for w in wrapped[:2]:
                    lines.append(f"  {w}")
            if len(preview_lines) > 5:
                lines.append("  ...")
        lines.append("-" * 70)
        lines.append(f"  [{self._current_hn_index + 1}/{len(self._hn_stories)}] n/p: nav · s: article · c: comments")
        self._set_output_text("\n".join(lines), autoscroll=False)

    def _update_hn_display(self) -> None:
        if not self._hn_stories:
            self._set_output_text("No stories available. Press 'n' to retry.", autoscroll=False)
            return
        story = self._hn_stories[self._current_hn_index]
        if story.url:
            self._set_output_text(f"Loading: {story.title}...", autoscroll=False)
            self._fetch_article_content(story)
        else:
            self._display_story_content(story, None)

    def _fetch_article_content(self, story: HNStory) -> None:

        def fetch_article():
            try:
                req = urllib.request.Request(
                    story.url, headers={"User-Agent": "Mozilla/5.0 (compatible; OTSBrowser/1.0)"}
                )
                with urllib.request.urlopen(req, timeout=15) as response:
                    html = response.read().decode("utf-8", errors="replace")
                    return self._extract_article_text(html)
            except Exception as e:
                return (None, f"Error fetching article: {e}")

        def on_article_fetched(future):
            try:
                content = future.result()
                self.app.call_from_thread(self._display_story_content, story, content)
            except Exception as e:
                self.app.call_from_thread(self._display_story_content, story, (None, f"Error: {e}"))

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(fetch_article)
        future.add_done_callback(on_article_fetched)
        executor.shutdown(wait=False)

    def _display_story_content(self, story: HNStory, content) -> None:
        lines = []
        lines.append("=" * 70)
        lines.append(f"  {story.title}")
        meta = f"  {story.score} pts · @{story.by} · {story.descendants} comments"
        lines.append(meta)
        lines.append("=" * 70)
        if content and isinstance(content, tuple):
            (page_title, article_text) = content
            if article_text and (not article_text.startswith("Error")):
                for line in article_text.split("\n"):
                    if line.strip():
                        lines.append(line)
            elif story.text:
                text = self._clean_html(story.text)
                for para in text.split("\n"):
                    if para.strip():
                        lines.append(f"  {para.strip()}")
            else:
                lines.append(f"  {(article_text if article_text else 'No content available')}")
        elif story.text:
            text = self._clean_html(story.text)
            for para in text.split("\n"):
                if para.strip():
                    lines.append(f"  {para.strip()}")
        else:
            lines.append("  [No article content - link only]")
        lines.append("-" * 70)
        lines.append(f"  [{self._current_hn_index + 1}/{len(self._hn_stories)}] n/p: nav · c: comments · d: details")
        self._set_output_text("\n".join(lines), autoscroll=False)

    def _extract_article_text(self, html: str) -> Tuple[str, str]:
        import re

        html = re.sub("<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub("<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub("<noscript[^>]*>.*?</noscript>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub("<nav[^>]*>.*?</nav>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub("<header[^>]*>.*?</header>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub("<footer[^>]*>.*?</footer>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub("<aside[^>]*>.*?</aside>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub("<!--.*?-->", "", html, flags=re.DOTALL)
        title_match = re.search("<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""
        title = re.sub("<[^>]+>", "", title)
        article_match = re.search("<article[^>]*>(.*?)</article>", html, re.IGNORECASE | re.DOTALL)
        if article_match:
            content = article_match.group(1)
        else:
            main_match = re.search("<main[^>]*>(.*?)</main>", html, re.IGNORECASE | re.DOTALL)
            if main_match:
                content = main_match.group(1)
            else:
                body_match = re.search("<body[^>]*>(.*?)</body>", html, re.IGNORECASE | re.DOTALL)
                content = body_match.group(1) if body_match else html
        content = re.sub("<h1[^>]*>(.*?)</h1>", "\\n## \\1 ##\\n", content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub("<h2[^>]*>(.*?)</h2>", "\\n### \\1 ###\\n", content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub("<h3[^>]*>(.*?)</h3>", "\\n#### \\1 ####\\n", content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub("<h[456][^>]*>(.*?)</h[456]>", "\\n**\\1**\\n", content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub("<p[^>]*>", "\n", content, flags=re.IGNORECASE)
        content = re.sub("</p>", "", content, flags=re.IGNORECASE)
        content = re.sub("<br\\s*/?>", "\n", content, flags=re.IGNORECASE)
        content = re.sub("<li[^>]*>", "\n  • ", content, flags=re.IGNORECASE)
        content = re.sub("<pre[^>]*>", "\n```\n", content, flags=re.IGNORECASE)
        content = re.sub("</pre>", "\n```\n", content, flags=re.IGNORECASE)
        content = re.sub("<code[^>]*>", "`", content, flags=re.IGNORECASE)
        content = re.sub("</code>", "`", content, flags=re.IGNORECASE)
        content = re.sub("<(strong|b)[^>]*>(.*?)</\\1>", "**\\2**", content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub("<(em|i)[^>]*>(.*?)</\\1>", "_\\2_", content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub("<[^>]+>", "", content)
        content = content.replace("&nbsp;", " ")
        content = content.replace("&amp;", "&")
        content = content.replace("&lt;", "<")
        content = content.replace("&gt;", ">")
        content = content.replace("&quot;", '"')
        content = content.replace("&#39;", "'")
        content = content.replace("&#x27;", "'")
        content = content.replace("&mdash;", "—")
        content = content.replace("&ndash;", "–")
        content = content.replace("&hellip;", "...")
        content = content.replace("&rsquo;", "'")
        content = content.replace("&lsquo;", "'")
        content = content.replace("&rdquo;", '"')
        content = content.replace("&ldquo;", '"')
        content = re.sub("\\n\\s*\\n\\s*\\n+", "\n", content)
        content = re.sub("[ \\t]+", " ", content)
        content = "\n".join((line.strip() for line in content.split("\n") if line.strip()))
        wrapped_lines = []
        for line in content.split("\n"):
            if len(line) > 68:
                wrapped = self._wrap_text(line, 68)
                wrapped_lines.extend(wrapped)
            else:
                wrapped_lines.append(line)
        return (title, "\n".join(wrapped_lines).strip())

    def _show_full_story(self) -> None:
        if not self._hn_stories:
            return
        story = self._hn_stories[self._current_hn_index]
        lines = []
        lines.append("=" * 70)
        lines.append(f"  {story.title}")
        lines.append("=" * 70)
        lines.append(f"  Author:    @{story.by}")
        lines.append(f"  Score:     {story.score} points")
        lines.append(f"  Comments:  {story.descendants}")
        if story.time:
            dt = datetime.fromtimestamp(story.time)
            lines.append(f"  Posted:    {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        if story.url:
            lines.append(f"  URL: {story.url}")
        lines.append(f"  HN: https://news.ycombinator.com/item?id={story.id}")
        if story.text:
            lines.append("-" * 70)
            text = self._clean_html(story.text)
            for para in text.split("\n"):
                if para.strip():
                    lines.append(f"  {para.strip()}")
        lines.append("-" * 70)
        lines.append(f"  [{self._current_hn_index + 1}/{len(self._hn_stories)}] n/p: nav · c: comments")
        self._set_output_text("\n".join(lines), autoscroll=False)

    def _fetch_and_show_comments(self) -> None:
        if not self._hn_stories:
            return
        story = self._hn_stories[self._current_hn_index]
        self._set_output_text(f"Loading comments for: {story.title}...", autoscroll=False)

        def fetch_comments():
            try:
                if not story.id:
                    return []
                with urllib.request.urlopen(
                    f"https://hacker-news.firebaseio.com/v0/item/{story.id}.json", timeout=10
                ) as response:
                    data = json.loads(response.read().decode())
                    kids = data.get("kids", [])[:20]
                comments = []
                self._fetch_comment_tree(kids, comments, depth=0)
                return comments
            except Exception:
                return []

        def on_comments_fetched(future):
            try:
                comments = future.result()
                self.app.call_from_thread(self._display_comments, story, comments)
            except Exception:
                pass

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(fetch_comments)
        future.add_done_callback(on_comments_fetched)
        executor.shutdown(wait=False)

    def _fetch_comment_tree(self, comment_ids: List[int], results: List[dict], depth: int, max_depth: int = 3) -> None:
        if depth > max_depth:
            return
        for comment_id in comment_ids[:10]:
            try:
                with urllib.request.urlopen(
                    f"https://hacker-news.firebaseio.com/v0/item/{comment_id}.json", timeout=5
                ) as response:
                    data = json.loads(response.read().decode())
                    if data and data.get("type") == "comment" and (not data.get("deleted")):
                        comment = {
                            "by": data.get("by", "[deleted]"),
                            "text": data.get("text", ""),
                            "time": data.get("time", 0),
                            "depth": depth,
                        }
                        results.append(comment)
                        if data.get("kids") and depth < max_depth:
                            self._fetch_comment_tree(data["kids"], results, depth + 1, max_depth)
            except Exception:
                continue

    def _display_comments(self, story: HNStory, comments: List[dict]) -> None:
        lines = []
        lines.append("=" * 70)
        lines.append(f"  Comments: {story.title}")
        lines.append(f"  {story.descendants} total · {len(comments)} loaded")
        lines.append("=" * 70)
        if not comments:
            lines.append("  No comments yet.")
        else:
            for comment in comments:
                indent = "  " * comment["depth"]
                lines.append(f"{indent}@{comment['by']}:")
                if comment["text"]:
                    text = self._clean_html(comment["text"])
                    for para in text.split("\n"):
                        if para.strip():
                            wrapped = self._wrap_text(para.strip(), 66 - len(indent))
                            for line in wrapped:
                                lines.append(f"{indent}  {line}")
        lines.append("-" * 70)
        lines.append(f"  [{self._current_hn_index + 1}/{len(self._hn_stories)}] n/p: nav · s: article")
        self._set_output_text("\n".join(lines), autoscroll=False)

    def _clean_html(self, text: str) -> str:
        import html
        import re

        text = text.replace("<p>", "\n")
        text = text.replace("</p>", "")
        text = text.replace("<br>", "\n")
        text = text.replace("<br/>", "\n")
        text = text.replace("<br />", "\n")
        text = text.replace("<pre><code>", "\n```\n")
        text = text.replace("</code></pre>", "\n```\n")
        text = text.replace("<code>", "`")
        text = text.replace("</code>", "`")
        text = text.replace("<i>", "_")
        text = text.replace("</i>", "_")
        text = text.replace("<em>", "_")
        text = text.replace("</em>", "_")
        text = text.replace("<b>", "**")
        text = text.replace("</b>", "**")
        text = text.replace("<strong>", "**")
        text = text.replace("</strong>", "**")

        def replace_anchor(match):
            url = html.unescape(match.group(1))
            link_text = match.group(2)
            if link_text == url or not link_text.strip():
                return url
            return f"{link_text} ({url})"

        text = re.sub('<a\\s+href="([^"]*)"[^>]*>([^<]*)</a>', replace_anchor, text)
        text = re.sub("<[^>]+>", "", text)
        text = html.unescape(text)
        return text

    def _wrap_text(self, text: str, width: int) -> List[str]:
        if len(text) <= width:
            return [text]
        lines = []
        while text:
            if len(text) <= width:
                lines.append(text)
                break
            split_pos = text.rfind(" ", 0, width)
            if split_pos == -1:
                split_pos = width
            lines.append(text[:split_pos])
            text = text[split_pos:].lstrip()
        return lines
