"""
File: schema.py
Purpose: Pydantic models for configuration validation.
Category: Utility
Author: ArtdaqDB Browser Team
Depends: pydantic
Exports: AppSettings, FilesystemConfig, UserPassAuthConfig, X509AuthConfig, MongoDBAuthConfig, ...
Complexity: High | Lines: 347
"""

import os
import re
from pathlib import Path
from typing import Optional, List
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator


class AppSettings(BaseModel):
    name: str = "OTS ArtdaqDB Browser"
    debug: bool = False


class FilesystemConfig(BaseModel):
    uri: str = "filesystemdb://${HOME}/artdaqdb/sampledata/teststand_db"

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, v: str) -> str:
        if not v.startswith("filesystemdb://"):
            raise ValueError("URI must start with 'filesystemdb://'")
        return v

    def get_path(self) -> Path:
        path_str = self.uri.replace("filesystemdb://", "")
        path_str = os.path.expandvars(path_str)
        return Path(path_str).expanduser()


class UserPassAuthConfig(BaseModel):
    user: str = ""
    password: str = ""
    auth_source: str = "admin"
    auth_mechanism: str = Field(default="DEFAULT", pattern="^(DEFAULT|SCRAM-SHA-1|SCRAM-SHA-256)$")


class X509AuthConfig(BaseModel):
    cert_dir: str = "~/.mongodb"
    ca_cert: str = "ca.pem"
    client_cert: str = "client.pem"
    auth_mechanism: str = Field(default="MONGODB-X509", pattern="^MONGODB-X509$")
    auth_source: str = Field(default="$external", pattern="^\\$external$")
    allow_invalid_certificates: bool = False
    allow_invalid_hostnames: bool = False

    @field_validator("ca_cert", "client_cert")
    @classmethod
    def validate_cert_filename(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Certificate filename cannot be empty")
        if "/" in v or "\\" in v:
            raise ValueError("Certificate should be a filename, not a path. Use cert_dir for the directory.")
        return v

    def get_cert_dir_path(self) -> Path:
        return Path(self.cert_dir).expanduser()

    def get_ca_cert_path(self) -> Path:
        return self.get_cert_dir_path() / self.ca_cert

    def get_client_cert_path(self) -> Path:
        return self.get_cert_dir_path() / self.client_cert


class MongoDBAuthConfig(BaseModel):
    type: str = Field(default="none", pattern="^(userpass|x509|none)$")
    userpass: UserPassAuthConfig = Field(default_factory=UserPassAuthConfig)
    x509: X509AuthConfig = Field(default_factory=X509AuthConfig)

    @property
    def is_enabled(self) -> bool:
        return self.type != "none"

    def get_cert_dir_path(self) -> Path:
        return self.x509.get_cert_dir_path()

    def get_ca_cert_path(self) -> Path:
        return self.x509.get_ca_cert_path()

    def get_client_cert_path(self) -> Path:
        return self.x509.get_client_cert_path()


class MongoDBConfig(BaseModel):
    uri: str = "mongodb://localhost:27017/teststand_db"
    connect_timeout_ms: int = Field(default=20000, ge=1000, le=120000)
    server_selection_timeout_ms: int = Field(default=30000, ge=1000, le=120000)
    socket_timeout_ms: int = Field(default=30000, ge=0, le=300000)
    direct_connection: bool = False
    auth: MongoDBAuthConfig = Field(default_factory=MongoDBAuthConfig)

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, v: str) -> str:
        if not v.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError("URI must start with 'mongodb://' or 'mongodb+srv://'")
        return v

    @property
    def requires_tls(self) -> bool:
        return self.uri.startswith("mongodb+srv://") or self.auth.type == "x509"

    @property
    def database(self) -> str:
        return self.get_database()

    def get_database(self) -> str:
        parsed = urlparse(self.uri)
        db = parsed.path.lstrip("/").split("?")[0]
        return db or "admin"


class DataSourceConfig(BaseModel):
    type: str = Field(default="filesystem", pattern="^(filesystem|mongodb)$")
    filesystem: FilesystemConfig = Field(default_factory=FilesystemConfig)
    mongodb: MongoDBConfig = Field(default_factory=MongoDBConfig)


class CacheConfig(BaseModel):
    enabled: bool = True
    directory: str = "~/.ots-browser/cache"
    ttl: int = Field(default=600, ge=0)
    max_entries: int = Field(default=10000, ge=0)
    max_size_mb: int = Field(default=100, ge=0)
    auto_purge: bool = True

    def get_directory_path(self) -> Path:
        return Path(self.directory).expanduser()


class UIConfig(BaseModel):
    theme: str = Field(
        default="tokyo-night",
        pattern="^(textual-dark|textual-light|textual-ansi|catppuccin-mocha|catppuccin-latte|dracula|flexoki|gruvbox|monokai|nord|solarized-light|tokyo-night)$",
        description="Color theme for the application. Available themes: Dark themes (tokyo-night, catppuccin-mocha, textual-dark, textual-ansi, dracula, flexoki, gruvbox, monokai, nord), Light themes (catppuccin-latte, textual-light, solarized-light)",
    )
    show_deleted: bool = False
    mouse_support: bool = True
    show_key_hints: bool = True
    datetime_format: str = "%Y-%m-%d %H:%M:%S"
    date_format: str = "%Y-%m-%d"
    timezone: Optional[str] = "America/Chicago"
    max_list_items: int = Field(default=1000, ge=100, le=100000)
    max_text_length: int = Field(default=500, ge=0)


class TableColumnsConfig(BaseModel):
    configuration_name: int = Field(default=40, ge=10, le=100)
    collection_name: int = Field(default=35, ge=10, le=100)
    version: int = Field(default=10, ge=5, le=20)
    document_id: int = Field(default=26, ge=20, le=50)
    timestamp: int = Field(default=20, ge=15, le=40)
    status: int = Field(default=12, ge=8, le=30)


class TablesConfig(BaseModel):
    zebra_stripes: bool = False
    default_sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
    columns: TableColumnsConfig = Field(default_factory=TableColumnsConfig)


class LoggingConfig(BaseModel):
    trace_enabled: bool = True
    trace_file: str = "./trace.log"
    level: str = Field(default="info", pattern="^(debug|info|warning|error)$")
    max_trace_size_mb: int = Field(default=10, ge=0)
    trace_backup_count: int = Field(default=3, ge=0, le=10)


class BackupConfig(BaseModel):
    output_directory: str = "."
    filename_pattern: str = "{database}-{timestamp}.tgz"
    timestamp_format: str = "%Y%m%d_%H%M%S"
    exclude_collections: List[str] = Field(default_factory=list)
    compress: bool = True
    compression_level: int = Field(default=6, ge=1, le=9)


class RestoreConfig(BaseModel):
    require_confirmation: bool = True
    exclude_collections: List[str] = Field(default_factory=list)
    drop_existing: bool = False


class DBUtilitiesConfig(BaseModel):
    default_database: str = "teststand_db"
    extended_stats: bool = False
    auto_refresh_interval: int = Field(default=0, ge=0)


class DocumentsConfig(BaseModel):
    config_name_pattern: str = "^[A-Za-z0-9_]+_v[0-9]+$"
    config_name_required: str = "_v"
    soft_delete: bool = True
    confirm_hard_delete: bool = True

    @field_validator("config_name_pattern")
    @classmethod
    def validate_regex(cls, v: str) -> str:
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
        return v


class SearchConfig(BaseModel):
    fuzzy_match: bool = True
    min_search_chars: int = Field(default=1, ge=1, le=10)
    debounce_ms: int = Field(default=100, ge=0, le=1000)
    case_insensitive: bool = True


class ToolsConfig(BaseModel):
    mongo_shell: Optional[str] = "mongosh"
    mongodump: str = "mongodump"
    mongorestore: str = "mongorestore"


class DBDoctorExcludeConfig(BaseModel):
    configurations: List[str] = Field(
        default_factory=lambda: ["notprovided"],
        description="Configuration names to exclude from duplicate collection analysis",
    )
    collections: List[str] = Field(
        default_factory=lambda: ["run_configurations"],
        description="Collection names to exclude from duplicate version analysis",
    )


class DBDoctorConfig(BaseModel):
    exclude: DBDoctorExcludeConfig = Field(default_factory=DBDoctorExcludeConfig)


class AppConfig(BaseModel):
    model_config = {"extra": "ignore"}
    app: AppSettings = Field(default_factory=AppSettings)
    data_source: DataSourceConfig = Field(default_factory=DataSourceConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    tables: TablesConfig = Field(default_factory=TablesConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    backup: BackupConfig = Field(default_factory=BackupConfig)
    restore: RestoreConfig = Field(default_factory=RestoreConfig)
    db_utilities: DBUtilitiesConfig = Field(default_factory=DBUtilitiesConfig)
    documents: DocumentsConfig = Field(default_factory=DocumentsConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    dbdoctor: DBDoctorConfig = Field(default_factory=DBDoctorConfig)

    @property
    def mongodb_auth(self) -> MongoDBAuthConfig:
        return self.data_source.mongodb.auth
