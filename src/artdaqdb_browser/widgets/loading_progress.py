"""
File: loading_progress.py
Purpose: Loading progress widget with clock and Hacker News feed.
Category: Widget
Author: ArtdaqDB Browser Team
Depends: textual
Exports: HNStory, LoadingProgress
Complexity: High | Lines: 809
"""

import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static, ProgressBar, TextArea
from textual.reactive import reactive
from textual.timer import Timer
from ..trace import trace


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
    kids: Optional[List[int]] = None


class LoadingProgress(Widget):
    DEFAULT_CSS = """
    LoadingProgress {
        height: 1fr;
        width: 100%;
        background: transparent;
    }

    LoadingProgress.progress-only {
        height: 1;
    }

    LoadingProgress .loading-container {
        height: 100%;
        width: 100%;
        background: transparent;
    }

    LoadingProgress .status-row {
        height: 1;
        width: 100%;
        background: transparent;
    }

    LoadingProgress .clock-display {
        width: 14;
        height: 1;
        color: $warning;
        text-style: bold;
        background: transparent;
    }

    LoadingProgress .progress-container {
        width: 1fr;
        height: 1;
        background: transparent;
    }

    LoadingProgress ProgressBar {
        width: 100%;
        height: 1;
        background: transparent;
        border: none;
    }

    LoadingProgress ProgressBar Bar {
        width: 100%;
        background: transparent;
        border: none;
    }

    LoadingProgress ProgressBar PercentageStatus {
        display: none;
    }
    """
    elapsed_seconds: reactive[int] = reactive(0)
    current_news_index: reactive[int] = reactive(0)
    is_running: reactive[bool] = reactive(False)
    progress_total: reactive[int] = reactive(0)
    progress_current: reactive[int] = reactive(0)

    def __init__(self, name: Optional[str] = None, id: Optional[str] = None, classes: Optional[str] = None) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._news_headlines: List[str] = [
            "Welcome to OTS Browser",
            "Analyzing database configurations...",
            "Finding duplicate collections...",
        ]
        self._hn_stories: List[HNStory] = []
        self._clock_timer: Optional[Timer] = None
        self._news_timer: Optional[Timer] = None
        self._start_time: Optional[datetime] = None
        self._fetching_news = False
        self._indeterminate = True

    def on_mount(self) -> None:
        self._update_idle_display()
        self._fetch_news()

    def compose(self) -> ComposeResult:
        with Vertical(classes="loading-container"):
            with Horizontal(classes="status-row"):
                yield Static("⏱ 00:00:00", id="lp_clock", classes="clock-display")
                with Horizontal(classes="progress-container"):
                    yield ProgressBar(id="lp_progress", show_eta=False, show_percentage=False)
            yield TextArea("", id="lp_news", read_only=True, show_line_numbers=False)

    def start(self, total: int = 0) -> None:
        trace.debug("TPW-101: Entry", tags=["widget", "loading"], total_param=total, is_running_before=self.is_running)
        if self.is_running:
            trace.debug("TPW-101: Already running, returning early", tags=["widget", "loading"])
            return
        self.is_running = True
        self._start_time = datetime.now()
        self.elapsed_seconds = 0
        self.current_news_index = 0
        self.progress_total = total
        self.progress_current = 0
        self._indeterminate = total <= 0
        trace.info(
            "TPW-101: State initialized",
            tags=["widget", "loading", "lifecycle"],
            is_running=self.is_running,
            indeterminate=self._indeterminate,
        )
        try:
            clock = self.query_one("#lp_clock", Static)
            clock.update("⏱ 00:00:00")
            clock.refresh()
        except Exception:
            pass
        self._clock_timer = self.app.set_interval(1.0, self._update_clock)
        self._news_timer = self.app.set_interval(9.0, self._rotate_news)
        try:
            progress = self.query_one("#lp_progress", ProgressBar)
            if self._indeterminate:
                progress.update(total=None)
            else:
                progress.update(total=self.progress_total, progress=0)
            progress.refresh()
        except Exception:
            pass
        self._update_news_display()
        self.refresh()

    def set_progress(self, current: int, total: Optional[int] = None) -> None:
        trace.debug(
            "TPW-102: Entry",
            tags=["widget", "loading"],
            current=current,
            total_param=total,
            is_running=self.is_running,
            progress_current_before=self.progress_current,
            progress_total_before=self.progress_total,
        )
        if not self.is_running:
            trace.debug("TPW-102: Not running, returning early", tags=["widget", "loading"])
            return
        self.progress_current = current
        if total is not None:
            self.progress_total = total
            self._indeterminate = total <= 0
        trace.debug(
            "TPW-102: State updated",
            tags=["widget", "loading", "mutation"],
            progress_current=self.progress_current,
            progress_total=self.progress_total,
            indeterminate=self._indeterminate,
        )
        try:
            progress = self.query_one("#lp_progress", ProgressBar)
            if self._indeterminate:
                progress.update(total=None)
                trace.debug("TPW-102: Updated ProgressBar (indeterminate)", tags=["widget", "loading", "mutation"])
            else:
                progress.update(total=self.progress_total, progress=current)
                trace.debug(
                    "TPW-102: Updated ProgressBar (determinate)",
                    tags=["widget", "loading", "mutation"],
                    bar_total=self.progress_total,
                    bar_progress=current,
                )
            progress.refresh()
            trace.debug("TPW-102: Called progress.refresh()", tags=["widget", "loading", "mutation"])
        except Exception as e:
            trace.error("TPW-102: ERROR updating ProgressBar", tags=["widget", "loading", "error"], error=str(e))

    def advance(self, amount: int = 1) -> None:
        if not self.is_running or self._indeterminate:
            return
        self.progress_current += amount
        try:
            progress = self.query_one("#lp_progress", ProgressBar)
            progress.update(progress=self.progress_current)
        except Exception:
            pass

    def stop(self) -> None:
        trace.debug("TPW-104: Entry", tags=["widget", "loading"], is_running_before=self.is_running)
        self.is_running = False
        if self._clock_timer:
            self._clock_timer.stop()
            self._clock_timer = None
        if self._news_timer:
            self._news_timer.stop()
            self._news_timer = None
        self._update_idle_display()

    def _update_idle_display(self) -> None:
        try:
            clock = self.query_one("#lp_clock", Static)
            clock.update("⏱ --:--:--")
            clock.refresh()
        except Exception:
            pass
        try:
            progress = self.query_one("#lp_progress", ProgressBar)
            progress.update(total=100, progress=0)
            progress.refresh()
        except Exception:
            pass
        try:
            news = self.query_one("#lp_news", TextArea)
            story = self.get_current_story()
            if story:
                lines = []
                lines.append(f"HN: {story.title}")
                meta_parts = []
                if story.score:
                    meta_parts.append(f"{story.score} pts")
                if story.by:
                    meta_parts.append(f"@{story.by}")
                if story.descendants:
                    meta_parts.append(f"{story.descendants} comments")
                if meta_parts:
                    lines.append(f"    {' · '.join(meta_parts)}")
                if story.url:
                    try:
                        from urllib.parse import urlparse

                        domain = urlparse(story.url).netloc
                        if domain.startswith("www."):
                            domain = domain[4:]
                        lines.append(f"    ({domain})")
                    except Exception:
                        pass
                if story.text:
                    lines.append("")
                    text = self._clean_html(story.text)
                    for para in text.split("\n")[:10]:
                        if para.strip():
                            lines.append(f"    {para.strip()}")
                lines.append("")
                lines.append(
                    f"  [{self.current_news_index + 1}/{len(self._hn_stories)}] n/p: next/prev · s: story · c: comments · d: details"
                )
                news.text = "\n".join(lines)
            elif self._news_headlines and len(self._news_headlines) > 3:
                headline = self._news_headlines[0]
                news.text = f"HN: {headline}"
            else:
                news.text = "Ready"
            news.refresh()
        except Exception:
            pass

    def _update_clock(self) -> None:
        if not self.is_running:
            return
        if self._start_time:
            elapsed = datetime.now() - self._start_time
            self.elapsed_seconds = int(elapsed.total_seconds())
            (hours, remainder) = divmod(self.elapsed_seconds, 3600)
            (minutes, seconds) = divmod(remainder, 60)
            time_str = f"⏱ {hours:02d}:{minutes:02d}:{seconds:02d}"
            try:
                clock = self.query_one("#lp_clock", Static)
                clock.update(time_str)
                clock.refresh()
            except Exception:
                pass

    def _rotate_news(self) -> None:
        if not self.is_running:
            return
        if self._news_headlines:
            self.current_news_index = (self.current_news_index + 1) % len(self._news_headlines)
            self._update_news_display()

    def _clean_html(self, text: str) -> str:
        text = text.replace("&#x27;", "'")
        text = text.replace("&quot;", '"')
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("<p>", "\n")
        text = text.replace("</p>", "")
        text = text.replace("<pre><code>", "\n```\n")
        text = text.replace("</code></pre>", "\n```\n")
        text = text.replace("<code>", "`")
        text = text.replace("</code>", "`")
        text = text.replace("<i>", "_")
        text = text.replace("</i>", "_")
        text = text.replace("<b>", "**")
        text = text.replace("</b>", "**")
        text = text.replace('<a href="', "[")
        text = text.replace('" rel="nofollow">', "](")
        text = text.replace("</a>", ")")
        return text

    def _update_news_display(self) -> None:
        try:
            news = self.query_one("#lp_news", TextArea)
            story = self.get_current_story()
            if story:
                lines = []
                lines.append(f"HN: {story.title}")
                meta_parts = []
                if story.score:
                    meta_parts.append(f"{story.score} pts")
                if story.by:
                    meta_parts.append(f"@{story.by}")
                if story.descendants:
                    meta_parts.append(f"{story.descendants} comments")
                if meta_parts:
                    lines.append("    " + " · ".join(meta_parts))
                if story.url:
                    try:
                        from urllib.parse import urlparse

                        domain = urlparse(story.url).netloc
                        if domain.startswith("www."):
                            domain = domain[4:]
                        lines.append(f"    ({domain})")
                    except Exception:
                        pass
                if story.text:
                    lines.append("")
                    lines.append("-" * 60)
                    text = self._clean_html(story.text)
                    for para in text.split("\n"):
                        if para.strip():
                            lines.append(f"    {para.strip()}")
                    lines.append("-" * 60)
                lines.append("")
                lines.append(
                    f"  [{self.current_news_index + 1}/{len(self._hn_stories)}] n/p: next/prev · s: story · c: comments · d: details"
                )
                news.text = "\n".join(lines)
            elif self._news_headlines:
                headline = self._news_headlines[self.current_news_index]
                news.text = f"HN: {headline}"
            else:
                news.text = "Loading news..."
            news.refresh()
        except Exception:
            pass

    def _fetch_news(self) -> None:
        if self._fetching_news:
            return
        self._fetching_news = True

        def fetch_sync():
            try:
                with urllib.request.urlopen(
                    "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10
                ) as response:
                    story_ids = json.loads(response.read().decode())[:15]
                stories: List[HNStory] = []
                for story_id in story_ids[:10]:
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
                                    kids=data.get("kids"),
                                )
                                stories.append(story)
                    except Exception:
                        continue
                return stories if stories else None
            except Exception:
                return None

        def on_fetch_complete(future):
            try:
                stories = future.result()
                if stories:
                    self._hn_stories = stories
                    self._news_headlines = [s.title for s in stories]
                    try:
                        self.app.call_from_thread(self._update_news_display)
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                self._fetching_news = False

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(fetch_sync)
        future.add_done_callback(on_fetch_complete)
        executor.shutdown(wait=False)

    def next_headline(self) -> None:
        if self._news_headlines:
            self.current_news_index = (self.current_news_index + 1) % len(self._news_headlines)
            self._update_news_display()

    def prev_headline(self) -> None:
        if self._news_headlines:
            self.current_news_index = (self.current_news_index - 1) % len(self._news_headlines)
            self._update_news_display()

    def get_current_story(self) -> Optional[HNStory]:
        if self._hn_stories and 0 <= self.current_news_index < len(self._hn_stories):
            return self._hn_stories[self.current_news_index]
        return None

    def has_hn_stories(self) -> bool:
        return len(self._hn_stories) > 0

    def get_all_stories(self) -> List[HNStory]:
        return self._hn_stories.copy()

    def get_current_index(self) -> int:
        return self.current_news_index

    def show_story(self) -> None:
        story = self.get_current_story()
        if not story:
            try:
                news = self.query_one("#lp_news", TextArea)
                news.text = "No story available. Press 'n' to cycle through headlines."
                news.refresh()
            except Exception:
                pass
            return
        try:
            news = self.query_one("#lp_news", TextArea)
        except Exception:
            return
        lines = []
        lines.append("=" * 70)
        lines.append(f"  {story.title}")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"  Author:    @{story.by}")
        lines.append(f"  Score:     {story.score} points")
        lines.append(f"  Comments:  {story.descendants}")
        if story.time:
            dt = datetime.fromtimestamp(story.time)
            lines.append(f"  Posted:    {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        if story.url:
            lines.append("-" * 70)
            lines.append(f"  URL: {story.url}")
            lines.append("")
        if story.text:
            lines.append("-" * 70)
            lines.append("  Content:")
            lines.append("")
            text = self._clean_html(story.text)
            for para in text.split("\n"):
                if para.strip():
                    lines.append(f"    {para.strip()}")
            lines.append("")
        lines.append("-" * 70)
        lines.append(f"  HN: https://news.ycombinator.com/item?id={story.id}")
        lines.append("")
        lines.append("-" * 70)
        lines.append("  Press 'c' to load comments, 'n/p' for next/prev story")
        lines.append("  Press 'd' for detail screen, ESC to go back")
        news.text = "\n".join(lines)
        news.scroll_home(animate=False)
        news.refresh()

    def show_comments(self) -> None:
        story = self.get_current_story()
        if not story:
            return
        try:
            news = self.query_one("#lp_news", TextArea)
            news.text = f"Loading comments for: {story.title}..."
            news.refresh()
        except Exception:
            pass

        def fetch_comments():
            try:
                if not story.kids:
                    return []
                comments = []
                self._fetch_comment_tree(story.kids[:20], comments, depth=0)
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
        try:
            news = self.query_one("#lp_news", TextArea)
            lines = []
            lines.append("=" * 70)
            lines.append(f"  Comments: {story.title}")
            lines.append(f"  {story.descendants} total comments")
            lines.append("=" * 70)
            lines.append("")
            if not comments:
                lines.append("  No comments yet.")
            else:
                for comment in comments:
                    indent = "    " * comment["depth"]
                    lines.append(f"{indent}┌─ @{comment['by']}")
                    if comment["text"]:
                        text = self._clean_html(comment["text"])
                        for para in text.split("\n"):
                            if para.strip():
                                wrapped = self._wrap_text(para.strip(), 65 - len(indent))
                                for line in wrapped:
                                    lines.append(f"{indent}│  {line}")
                    lines.append(f"{indent}└─")
                    lines.append("")
            lines.append("-" * 70)
            lines.append("  Press 's' to show story, 'n/p' for next/prev story")
            lines.append("  Press 'd' for detail screen")
            news.text = "\n".join(lines)
            news.scroll_home(animate=False)
            news.refresh()
        except Exception:
            pass

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
