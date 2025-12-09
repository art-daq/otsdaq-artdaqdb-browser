"""
File: hn_detail.py
Purpose: Hacker News story detail viewer screen.
Category: Screen
Author: ArtdaqDB Browser Team
Depends: textual
Exports: HNDetailScreen
Complexity: Medium | Lines: 514
"""

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, List
from textual.app import ComposeResult
from textual.widgets import Static, Footer, TextArea
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from ..base import BaseScreen, BACK_BINDINGS, SCROLL_BINDINGS, FOCUS_BINDINGS
from ...widgets import KeyPanel
from ...widgets.loading_progress import HNStory
from ...constants import KeyHints, WidgetID


class HNDetailScreen(BaseScreen):
    BINDINGS = [
        Binding("escape", "go_back", "Back", priority=True),
        *BACK_BINDINGS,
        Binding("s", "show_story", "Article"),
        Binding("c", "show_comments", "Comments"),
        Binding("i", "show_info", "Info"),
        Binding("n", "next_story", "Next", show=False),
        Binding("p", "prev_story", "Prev", show=False),
        *SCROLL_BINDINGS,
        *FOCUS_BINDINGS,
    ]

    def __init__(self, story: HNStory, stories: Optional[List[HNStory]] = None, index: int = 0):
        super().__init__()
        self.story = story
        self._stories = stories or [story]
        self._current_index = index
        self._showing_comments = False
        self._showing_article = False

    def compose(self) -> ComposeResult:
        yield KeyPanel(KeyHints.HN_DETAIL)
        with Horizontal(classes="screen-header"):
            yield Static("Hacker News Story", classes="screen-title")
        yield TextArea(id="hn_content", read_only=True)
        yield Static("", classes="status-bar", id=WidgetID.STATUS_BAR)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#hn_content", TextArea).focus()
        self.action_show_story()

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

    def _display_story(self) -> None:
        self._showing_comments = False
        text_area = self.query_one("#hn_content", TextArea)
        status_bar = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        lines = []
        lines.append("=" * 80)
        lines.append(f"  {self.story.title}")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"  Author:    @{self.story.by}")
        lines.append(f"  Score:     {self.story.score} points")
        lines.append(f"  Comments:  {self.story.descendants}")
        if self.story.time:
            dt = datetime.fromtimestamp(self.story.time)
            lines.append(f"  Posted:    {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        if self.story.url:
            lines.append("-" * 80)
            lines.append("  URL:")
            lines.append(f"  {self.story.url}")
            lines.append("")
        if self.story.text:
            lines.append("-" * 80)
            lines.append("  Content:")
            lines.append("")
            text = self._clean_html(self.story.text)
            for para in text.split("\n"):
                if para.strip():
                    lines.append(f"  {para.strip()}")
                else:
                    lines.append("")
            lines.append("")
        lines.append("-" * 80)
        lines.append("  Hacker News:")
        lines.append(f"  https://news.ycombinator.com/item?id={self.story.id}")
        lines.append("")
        lines.append("-" * 80)
        lines.append("  Press 's' to load article (reader mode)")
        lines.append("  Press 'c' to load comments")
        lines.append("  Press 'i' to show story info (current view)")
        lines.append("  Press 'n/p' for next/previous story")
        lines.append("  Press ESC or 'h' to go back")
        lines.append("")
        text_area.text = "\n".join(lines)
        nav_info = f"[{self._current_index + 1}/{len(self._stories)}]" if len(self._stories) > 1 else ""
        status_bar.update(
            f"{nav_info} Info | {self.story.score} pts | {self.story.descendants} comments | s=article c=comments i=info"
        )

    def action_go_back(self) -> None:
        from ...trace import trace

        trace.info(
            "Returning from HNDetailScreen",
            tags=["screen", "navigation"],
            from_screen="HNDetailScreen",
            reason="User pressed back (escape/h/left)",
        )
        self.app.pop_screen()

    def action_show_info(self) -> None:
        self._showing_article = False
        self._showing_comments = False
        self._display_story()
        text_area = self.query_one("#hn_content", TextArea)
        text_area.scroll_home(animate=False)

    def action_show_story(self) -> None:
        if not self.story.url:
            self._showing_article = False
            self._display_story()
            text_area = self.query_one("#hn_content", TextArea)
            text_area.scroll_home(animate=False)
            return
        self._showing_comments = False
        self._showing_article = True
        text_area = self.query_one("#hn_content", TextArea)
        status_bar = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        text_area.text = f"Loading article: {self.story.url}..."
        status_bar.update("Fetching article...")

        def fetch_article():
            try:
                req = urllib.request.Request(
                    self.story.url, headers={"User-Agent": "Mozilla/5.0 (compatible; OTSBrowser/1.0)"}
                )
                with urllib.request.urlopen(req, timeout=15) as response:
                    html = response.read().decode("utf-8", errors="replace")
                    return self._extract_article_text(html)
            except Exception as e:
                return f"Error fetching article: {e}"

        def on_article_fetched(future):
            try:
                content = future.result()
                self.app.call_from_thread(self._display_article, content)
            except Exception as e:
                self.app.call_from_thread(self._display_article, f"Error: {e}")

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(fetch_article)
        future.add_done_callback(on_article_fetched)
        executor.shutdown(wait=False)

    def action_show_comments(self) -> None:
        if self._showing_comments:
            return
        text_area = self.query_one("#hn_content", TextArea)
        status_bar = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        text_area.text = f"Loading comments for: {self.story.title}..."
        status_bar.update("Loading comments...")

        def fetch_comments():
            try:
                if not self.story.kids:
                    return []
                comments = []
                self._fetch_comment_tree(self.story.kids[:30], comments, depth=0)
                return comments
            except Exception:
                return []

        def on_comments_fetched(future):
            try:
                comments = future.result()
                self.app.call_from_thread(self._display_comments, comments)
            except Exception:
                pass

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(fetch_comments)
        future.add_done_callback(on_comments_fetched)
        executor.shutdown(wait=False)

    def _fetch_comment_tree(self, comment_ids: List[int], results: List[dict], depth: int, max_depth: int = 4) -> None:
        if depth > max_depth:
            return
        for comment_id in comment_ids[:15]:
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

    def _display_comments(self, comments: List[dict]) -> None:
        self._showing_comments = True
        text_area = self.query_one("#hn_content", TextArea)
        status_bar = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        lines = []
        lines.append("=" * 80)
        lines.append(f"  Comments: {self.story.title}")
        lines.append(f"  {self.story.descendants} total comments (showing {len(comments)} loaded)")
        lines.append("=" * 80)
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
                            wrapped = self._wrap_text(para.strip(), 75 - len(indent))
                            for line in wrapped:
                                lines.append(f"{indent}│  {line}")
                lines.append(f"{indent}└─")
                lines.append("")
        lines.append("-" * 80)
        lines.append("  Press 's' to show story, 'n/p' for next/prev story")
        lines.append("  Press ESC or 'h' to go back")
        lines.append("")
        text_area.text = "\n".join(lines)
        text_area.scroll_home(animate=False)
        nav_info = f"[{self._current_index + 1}/{len(self._stories)}]" if len(self._stories) > 1 else ""
        status_bar.update(f"{nav_info} Comments | {len(comments)} loaded | n/p=nav s=story c=comments")

    def _wrap_text(self, text: str, width: int) -> List[str]:
        if width <= 0:
            width = 40
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

    def action_scroll_down(self) -> None:
        text_area = self.query_one("#hn_content", TextArea)
        text_area.scroll_relative(y=1)

    def action_scroll_up(self) -> None:
        text_area = self.query_one("#hn_content", TextArea)
        text_area.scroll_relative(y=-1)

    def action_scroll_top(self) -> None:
        text_area = self.query_one("#hn_content", TextArea)
        text_area.scroll_home(animate=False)

    def action_scroll_bottom(self) -> None:
        text_area = self.query_one("#hn_content", TextArea)
        text_area.scroll_end(animate=False)

    def action_next_story(self) -> None:
        if len(self._stories) <= 1:
            return
        self._current_index = (self._current_index + 1) % len(self._stories)
        self.story = self._stories[self._current_index]
        self._showing_comments = False
        self.action_show_story()

    def action_prev_story(self) -> None:
        if len(self._stories) <= 1:
            return
        self._current_index = (self._current_index - 1) % len(self._stories)
        self.story = self._stories[self._current_index]
        self._showing_comments = False
        self.action_show_story()

    def _extract_article_text(self, html: str) -> str:
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
        content = re.sub("<h1[^>]*>(.*?)</h1>", "\\n\\n## \\1 ##\\n", content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub("<h2[^>]*>(.*?)</h2>", "\\n\\n### \\1 ###\\n", content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub("<h3[^>]*>(.*?)</h3>", "\\n\\n#### \\1 ####\\n", content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub("<h[456][^>]*>(.*?)</h[456]>", "\\n\\n**\\1**\\n", content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub("<p[^>]*>", "\n\n", content, flags=re.IGNORECASE)
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
        content = re.sub("\\n\\s*\\n\\s*\\n+", "\n\n", content)
        content = re.sub("[ \\t]+", " ", content)
        content = "\n".join((line.strip() for line in content.split("\n")))
        wrapped_lines = []
        for line in content.split("\n"):
            if len(line) > 78:
                wrapped = self._wrap_text(line, 78)
                wrapped_lines.extend(wrapped)
            else:
                wrapped_lines.append(line)
        return (title, "\n".join(wrapped_lines).strip())

    def _display_article(self, content) -> None:
        text_area = self.query_one("#hn_content", TextArea)
        status_bar = self.query_one(f"#{WidgetID.STATUS_BAR}", Static)
        lines = []
        lines.append("=" * 80)
        lines.append(f"  {self.story.title}")
        lines.append("=" * 80)
        lines.append("")
        if self.story.url:
            lines.append(f"  Source: {self.story.url}")
            lines.append("")
        lines.append("-" * 80)
        lines.append("")
        if isinstance(content, tuple):
            (page_title, article_text) = content
            if page_title and page_title != self.story.title:
                lines.append(f"  Page Title: {page_title}")
                lines.append("")
            lines.append(article_text)
        else:
            lines.append(content)
        lines.append("")
        lines.append("-" * 80)
        lines.append("  Press 'c' to load comments, 'n/p' for next/prev story")
        lines.append("  Press 'i' to show story info, ESC to go back")
        lines.append("")
        text_area.text = "\n".join(lines)
        text_area.scroll_home(animate=False)
        nav_info = f"[{self._current_index + 1}/{len(self._stories)}]" if len(self._stories) > 1 else ""
        status_bar.update(f"{nav_info} Article | {self.story.score} pts | n/p=nav s=article c=comments i=info")
