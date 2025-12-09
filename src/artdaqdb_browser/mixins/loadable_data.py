"""
File: loadable_data.py
Purpose: Loadable data mixin for screens with data loading patterns.
Category: Mixin
Author: ArtdaqDB Browser Team
Depends: None
Exports: LoadableDataMixin
Complexity: Low | Lines: 80
"""

from typing import Any


class LoadableDataMixin:
    DATA_TYPE: str = "data"

    def fetch_data(self) -> Any:
        raise NotImplementedError("Subclasses must implement fetch_data()")

    def on_data_loaded(self) -> None:
        pass

    def on_data_error(self, error: Exception) -> None:
        if hasattr(self, "notify"):
            self.notify(f"Error loading {self.DATA_TYPE}: {error}", severity="error")

    def load_data(self) -> None:
        try:
            data = self.fetch_data()
            if hasattr(self, "all_items"):
                self.all_items = data
            if hasattr(self, "filtered_items"):
                self.filtered_items = list(data) if data else []
            self.on_data_loaded()
        except Exception as e:
            self.on_data_error(e)
