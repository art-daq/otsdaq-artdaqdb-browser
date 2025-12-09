"""
File: __init__.py
Purpose: Configuration management for OTS Browser.
Category: Config
Author: ArtdaqDB Browser Team
Depends: None
Exports: None
Complexity: Low | Lines: 72
"""

from .schema import (
    AppConfig,
    AppSettings,
    DataSourceConfig,
    FilesystemConfig,
    MongoDBConfig,
    MongoDBAuthConfig,
    UserPassAuthConfig,
    X509AuthConfig,
    CacheConfig,
    UIConfig,
    TablesConfig,
    TableColumnsConfig,
    LoggingConfig,
    BackupConfig,
    RestoreConfig,
    DBUtilitiesConfig,
    DocumentsConfig,
    SearchConfig,
    ToolsConfig,
)
from .loader import ConfigLoader, ConfigError
from .defaults import DEFAULT_CONFIG, CONFIG_TEMPLATE
from .helpers import (
    parse_mongodb_uri,
    get_mongo_client_cmd,
    build_mongo_shell_cmd,
    build_mongodump_cmd,
    build_mongorestore_cmd,
    get_server_display_info,
)

__all__ = [
    "AppConfig",
    "AppSettings",
    "DataSourceConfig",
    "FilesystemConfig",
    "MongoDBConfig",
    "MongoDBAuthConfig",
    "UserPassAuthConfig",
    "X509AuthConfig",
    "CacheConfig",
    "UIConfig",
    "TablesConfig",
    "TableColumnsConfig",
    "LoggingConfig",
    "BackupConfig",
    "RestoreConfig",
    "DBUtilitiesConfig",
    "DocumentsConfig",
    "SearchConfig",
    "ToolsConfig",
    "ConfigLoader",
    "ConfigError",
    "DEFAULT_CONFIG",
    "CONFIG_TEMPLATE",
    "parse_mongodb_uri",
    "get_mongo_client_cmd",
    "build_mongo_shell_cmd",
    "build_mongodump_cmd",
    "build_mongorestore_cmd",
    "get_server_display_info",
]
