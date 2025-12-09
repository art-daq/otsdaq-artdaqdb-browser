"""
File: defaults.py
Purpose: Default configuration values.
Category: Utility
Author: ArtdaqDB Browser Team
Depends: None
Exports: DEFAULT_CONFIG, CONFIG_TEMPLATE
Complexity: Medium | Lines: 225
"""

from .schema import AppConfig

DEFAULT_CONFIG = AppConfig()
CONFIG_TEMPLATE = """# OTS ArtdaqDB Browser - Configuration File

app:
  name: "OTS ArtdaqDB Browser"
  debug: false

data_source:
  type: "filesystem"

  filesystem:
    uri: "filesystemdb://${HOME}/artdaqdb/sampledata/teststand_db"

  mongodb:
    uri: "mongodb://localhost:27017/teststand_db"
    connect_timeout_ms: 20000
    server_selection_timeout_ms: 30000
    socket_timeout_ms: 30000
    direct_connection: false

    auth:
      type: "none"

      userpass:
        user: ""
        password: ""
        auth_source: "admin"
        auth_mechanism: "DEFAULT"

      x509:
        cert_dir: "~/.mongodb"
        ca_cert: "ca.pem"
        client_cert: "client.pem"
        allow_invalid_certificates: false
        allow_invalid_hostnames: false

cache:
  enabled: true
  directory: "~/.ots-browser/cache"
  ttl: 600
  max_entries: 10000
  max_size_mb: 100
  auto_purge: true

ui:
  theme: "tokyo-night"
  show_deleted: false
  mouse_support: true
  show_key_hints: true
  datetime_format: "%Y-%m-%d %H:%M:%S"
  date_format: "%Y-%m-%d"
  timezone: "America/Chicago"
  max_list_items: 1000
  max_text_length: 500

tables:
  zebra_stripes: false
  default_sort_order: "desc"
  columns:
    configuration_name: 40
    collection_name: 35
    version: 10
    document_id: 26
    timestamp: 20
    status: 12

logging:
  trace_enabled: true
  trace_file: "./trace.log"
  level: "info"
  max_trace_size_mb: 10
  trace_backup_count: 3

backup:
  output_directory: "."
  filename_pattern: "{database}-{timestamp}.tgz"
  timestamp_format: "%Y%m%d_%H%M%S"
  exclude_collections: []
  compress: true
  compression_level: 6

restore:
  require_confirmation: true
  exclude_collections: []
  drop_existing: false

db_utilities:
  default_database: "teststand_db"
  extended_stats: false
  auto_refresh_interval: 0

documents:
  config_name_pattern: "^[A-Za-z0-9_]+_v[0-9]+$"
  config_name_required: "_v"
  soft_delete: true
  confirm_hard_delete: true

search:
  fuzzy_match: true
  min_search_chars: 1
  debounce_ms: 100
  case_insensitive: true

tools:
  mongo_shell: "mongosh"
  mongodump: "mongodump"
  mongorestore: "mongorestore"
"""
