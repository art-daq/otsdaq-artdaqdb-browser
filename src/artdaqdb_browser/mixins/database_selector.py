"""
File: database_selector.py
Purpose: Database selector mixin for screens with database selection buttons.
Category: Mixin
Author: ArtdaqDB Browser Team
Depends: textual
Exports: DatabaseSelectorMixin
Complexity: Medium | Lines: 288
"""

import asyncio
from typing import List, Optional
from textual.widgets import Button, Static
from textual.containers import Horizontal
from ..constants import SYSTEM_DATABASES
from ..config import AppConfig, ConfigLoader, build_mongo_shell_cmd
from ..trace import trace


def _get_config() -> AppConfig:
    loader = ConfigLoader()
    (config, warnings) = loader.load()
    for warning in warnings:
        trace.warn("Configuration file warning", tags=["config"], warning=warning)
    return config


class DatabaseSelectorMixin:
    DB_BUTTONS_CONTAINER_ID: str = "db_buttons_container"
    FALLBACK_FOCUS_WIDGET_ID: str = ""
    available_databases: List[str]
    database: str
    _config: Optional[AppConfig]

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            self._config = _get_config()
        return self._config

    def _create_database_buttons(self) -> None:
        container = self.query_one(f"#{self.DB_BUTTONS_CONTAINER_ID}", Horizontal)
        container.remove_children()
        if not self.available_databases:
            container.mount(Static("No databases found", classes="db-no-databases"))
            return
        for db_name in self.available_databases:
            is_selected = db_name == self.database
            btn = Button(
                db_name, id=f"db_btn_{db_name}", classes="db-select-btn" + (" db-btn-selected" if is_selected else "")
            )
            container.mount(btn)

    def _update_button_selection(self) -> None:
        container = self.query_one(f"#{self.DB_BUTTONS_CONTAINER_ID}", Horizontal)
        for btn in container.query(Button):
            if not btn.id or not btn.id.startswith("db_btn_"):
                continue
            db_name = btn.id.replace("db_btn_", "")
            is_selected = db_name == self.database
            if is_selected:
                btn.add_class("db-btn-selected")
            else:
                btn.remove_class("db-btn-selected")

    async def _fetch_databases(self) -> List[str]:
        try:
            js_script = """
            (function() {
                var dbs = db.adminCommand({listDatabases: 1});
                if (dbs && dbs.databases) {
                    dbs.databases.forEach(function(d) {
                        print(d.name);
                    });
                }
            })();
            """
            cmd = build_mongo_shell_cmd(self.config, database="admin", quiet=True)
            cmd.extend(["--eval", js_script])
            trace.debug("Fetching database list from MongoDB server", tags=["database", "query"])
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            (stdout, stderr) = await process.communicate()
            if process.returncode != 0:
                trace.error(
                    "Failed to list databases from MongoDB",
                    tags=["database", "error"],
                    error=stderr.decode() if stderr else "Unknown error",
                )
                return []
            databases = []
            for line in stdout.decode().strip().split("\n"):
                db_name = line.strip()
                if db_name and db_name not in SYSTEM_DATABASES:
                    databases.append(db_name)
            trace.debug(
                "Database list retrieved", tags=["database", "query"], count=len(databases), databases=databases
            )
            return sorted(databases)
        except Exception as e:
            trace.error("Error fetching database list", tags=["database", "error"], exception=e)
            return []

    def get_db_button_focus_controls(self) -> List[str]:
        controls = []
        if self.available_databases:
            controls.append(f"db_btn_{self.available_databases[0]}")
        return controls

    def _focus_database_button(self, db_name: str) -> bool:
        btn_id = f"db_btn_{db_name}"
        try:
            btn = self.query_one(f"#{btn_id}", Button)
            btn.focus()
            return True
        except Exception:
            return False

    def focus_first_database_button(self) -> bool:
        if self.available_databases:
            return self._focus_database_button(self.available_databases[0])
        return False

    def focus_database_selector_control(self) -> bool:
        if self.focus_first_database_button():
            return True
        if self.FALLBACK_FOCUS_WIDGET_ID:
            try:
                widget = self.query_one(f"#{self.FALLBACK_FOCUS_WIDGET_ID}")
                widget.focus()
                return True
            except Exception:
                pass
        return False

    def handle_database_button_press(self, btn_id: str) -> Optional[str]:
        if not btn_id.startswith("db_btn_"):
            return None
        db_name = btn_id.replace("db_btn_", "")
        trace.debug("Database selected via button", tags=["widget", "event"], database=db_name)
        self.database = db_name
        self._update_button_selection()
        return db_name

    def select_default_database(self, default_db: str) -> None:
        if default_db in self.available_databases:
            self.database = default_db
        elif self.available_databases:
            self.database = self.available_databases[0]
        self._update_button_selection()
