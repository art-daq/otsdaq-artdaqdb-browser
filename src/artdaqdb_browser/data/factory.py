"""
File: factory.py
Purpose: Factory for creating data backend instances.
Category: Data
Author: ArtdaqDB Browser Team
Depends: None
Exports: create_backend, create_backend_from_config
Complexity: Low | Lines: 85
"""

from typing import Optional
from ..config import ConfigLoader, AppConfig
from ..trace import trace
from .base import DataBackend
from .filesystem import FilesystemBackend


def create_backend(
    data_source: Optional[str] = None, backend_type: Optional[str] = None, config: Optional[AppConfig] = None
) -> DataBackend:
    if config is None:
        loader = ConfigLoader()
        (config, _) = loader.load()
    if backend_type is None:
        backend_type = config.data_source.type
    if data_source is None:
        if backend_type == "filesystem":
            data_source = config.data_source.filesystem.path
        elif backend_type == "mongodb":
            data_source = config.data_source.mongodb.uri
    trace.debug(
        "Creating data backend",
        tags=["database", "factory"],
        backend_type=backend_type,
        data_source=data_source[:50] if data_source else None,
    )
    if backend_type == "filesystem":
        return FilesystemBackend(data_source)
    elif backend_type == "mongodb":
        from .mongodb import MongoDBBackend

        return MongoDBBackend(config)
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")


def create_backend_from_config(config: Optional[AppConfig] = None) -> DataBackend:
    return create_backend(config=config)
