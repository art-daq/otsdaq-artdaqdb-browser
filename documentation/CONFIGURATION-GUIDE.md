# OTS ArtdaqDB Browser - Configuration Guide

This guide explains how to configure the OTS ArtdaqDB Browser application for your environment.

## Table of Contents

1. [Configuration File Locations](#configuration-file-locations)
2. [Quick Start](#quick-start)
3. [Configuration Sections](#configuration-sections)
   - [Application Settings](#application-settings)
   - [Data Source](#data-source)
   - [MongoDB Authentication](#mongodb-authentication)
   - [Cache](#cache)
   - [User Interface](#user-interface)
   - [Tables](#tables)
   - [Logging](#logging)
   - [Backup and Restore](#backup-and-restore)
   - [Document Settings](#document-settings)
   - [Search](#search)
   - [External Tools](#external-tools)
4. [Common Configurations](#common-configurations)
5. [Environment Variables](#environment-variables)
6. [Troubleshooting](#troubleshooting)

---

## Configuration File Locations

The application searches for configuration files in the following order:

1. **Explicit path** - Passed via `--config` command-line argument
2. **User config** - `~/.ots-browser/config.yaml`
3. **Project config** - `./appconfig.yml` (current working directory)
4. **Default config** - Built-in defaults

To create your own configuration:

```bash
# Create user config directory
mkdir -p ~/.ots-browser

# Copy the template
cp appconfig.yml ~/.ots-browser/config.yaml

# Edit to customize
nano ~/.ots-browser/config.yaml
```

---

## Quick Start

### Minimal Configuration for Local MongoDB

```yaml
data_source:
  type: "mongodb"
  mongodb:
    uri: "mongodb://localhost:27017/teststand_db"
    auth:
      type: "none"
```

### Minimal Configuration for Filesystem Backend

```yaml
data_source:
  type: "filesystem"
  filesystem:
    uri: "filesystemdb://${HOME}/data/teststand_db"
```

### Configuration for X.509 Authentication

```yaml
data_source:
  type: "mongodb"
  mongodb:
    uri: "mongodb://dbserver.example.com:27017/teststand_db"
    auth:
      type: "x509"
      x509:
        cert_dir: "~/.mongodb"
        ca_cert: "ca-bundle.pem"
        client_cert: "client-cert.pem"
```

---

## Configuration Sections

### Application Settings

```yaml
app:
  # Application name displayed in the header
  name: "OTS ArtdaqDB Browser"

  # Enable debug mode for verbose logging
  debug: false
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | "OTS ArtdaqDB Browser" | Application title shown in UI |
| `debug` | boolean | false | Enable verbose debug logging |

---

### Data Source

The data source section configures where document data is read from.

```yaml
data_source:
  # Backend type: "filesystem" or "mongodb"
  type: "mongodb"

  # Filesystem backend settings
  filesystem:
    uri: "filesystemdb://${HOME}/artdaqdb/sampledata/teststand_db"

  # MongoDB backend settings
  mongodb:
    uri: "mongodb://localhost:27017/teststand_db"
    connect_timeout_ms: 20000
    server_selection_timeout_ms: 30000
    socket_timeout_ms: 30000
    direct_connection: false
    auth:
      # See MongoDB Authentication section
```

#### Data Source Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | "filesystem" | Backend type: `filesystem` or `mongodb` |

#### Filesystem Backend

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `uri` | string | (required) | Path using `filesystemdb://` scheme |

The filesystem URI supports environment variable expansion:
- `${HOME}` - User's home directory
- `${USER}` - Current username
- `~` - Also expands to home directory

**Examples:**
```yaml
# Absolute path
uri: "filesystemdb:///data/teststand_db"

# Home directory
uri: "filesystemdb://~/databases/teststand_db"

# Environment variable
uri: "filesystemdb://${HOME}/artdaqdb/sampledata/teststand_db"
```

#### MongoDB Backend

| Field | Type | Default | Range | Description |
|-------|------|---------|-------|-------------|
| `uri` | string | (required) | - | MongoDB connection URI |
| `connect_timeout_ms` | int | 20000 | 1000-120000 | Connection timeout (ms) |
| `server_selection_timeout_ms` | int | 30000 | 1000-120000 | Server selection timeout (ms) |
| `socket_timeout_ms` | int | 30000 | 0-300000 | Socket timeout (ms, 0=no timeout) |
| `direct_connection` | boolean | false | - | Bypass replica set discovery |

**URI Format:**
```
mongodb://[username:password@]host[:port]/database[?options]
mongodb+srv://[username:password@]host/database[?options]
```

**Examples:**
```yaml
# Local MongoDB
uri: "mongodb://localhost:27017/teststand_db"

# Remote server with port
uri: "mongodb://dbserver.example.com:27018/production_db"

# MongoDB Atlas (SRV)
uri: "mongodb+srv://cluster.mongodb.net/mydb"

# With replica set
uri: "mongodb://primary.example.com:27017/mydb?replicaSet=rs0"
```

> **Note:** The `mongodb+srv://` scheme automatically requires TLS.

---

### MongoDB Authentication

Authentication is configured under `data_source.mongodb.auth`.

```yaml
data_source:
  mongodb:
    auth:
      # Auth type: "none", "userpass", or "x509"
      type: "none"

      # Username/password settings
      userpass:
        user: ""
        password: ""
        auth_source: "admin"
        auth_mechanism: "DEFAULT"

      # X.509 certificate settings
      x509:
        cert_dir: "~/.mongodb"
        ca_cert: "ca.pem"
        client_cert: "client.pem"
        allow_invalid_certificates: false
        allow_invalid_hostnames: false
```

#### Authentication Types

| Type | Description | TLS Required |
|------|-------------|--------------|
| `none` | No authentication | No (unless URI is `mongodb+srv://`) |
| `userpass` | Username/password (SCRAM) | Optional |
| `x509` | X.509 client certificate | **Yes** (automatic) |

#### Username/Password Authentication

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `user` | string | "" | MongoDB username |
| `password` | string | "" | MongoDB password |
| `auth_source` | string | "admin" | Database to authenticate against |
| `auth_mechanism` | string | "DEFAULT" | `DEFAULT`, `SCRAM-SHA-1`, or `SCRAM-SHA-256` |

**Example:**
```yaml
auth:
  type: "userpass"
  userpass:
    user: "app_user"
    password: "secret123"
    auth_source: "admin"
    auth_mechanism: "SCRAM-SHA-256"
```

#### X.509 Certificate Authentication

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cert_dir` | string | "~/.mongodb" | Directory containing certificates |
| `ca_cert` | string | "ca.pem" | CA certificate filename |
| `client_cert` | string | "client.pem" | Client certificate filename (with private key) |
| `allow_invalid_certificates` | boolean | false | Skip certificate validation (**INSECURE**) |
| `allow_invalid_hostnames` | boolean | false | Skip hostname validation (**INSECURE**) |

**Example:**
```yaml
auth:
  type: "x509"
  x509:
    cert_dir: "~/.mongodb"
    ca_cert: "mu2eots-mongodb-ca.pem"
    client_cert: "artdaq-rw-mu2eots.pem"
```

> **Certificate Requirements:**
> - The `client_cert` file must contain both the certificate and private key in PEM format
> - Certificate files should be filenames only, not paths (use `cert_dir` for the directory)

#### TLS/SSL Behavior

TLS is automatically enabled when:
1. Using `mongodb+srv://` URI scheme
2. Using X.509 authentication (`type: "x509"`)

For other cases with `userpass` or `none` auth, add `tls=true` to the URI:
```yaml
uri: "mongodb://server:27017/db?tls=true"
```

---

### Cache

```yaml
cache:
  # Enable disk-based caching
  enabled: true

  # Cache directory path
  directory: "~/.ots-browser/cache"

  # Cache time-to-live in seconds (0=no expiration)
  ttl: 600

  # Maximum number of cache entries
  max_entries: 10000

  # Maximum cache size in MB
  max_size_mb: 100

  # Auto-purge expired entries on startup
  auto_purge: true
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | true | Enable/disable caching |
| `directory` | string | "~/.ots-browser/cache" | Cache storage location |
| `ttl` | int | 600 | Time-to-live in seconds (0=never expire) |
| `max_entries` | int | 10000 | Maximum cached items (0=unlimited) |
| `max_size_mb` | int | 100 | Maximum cache size in MB (0=unlimited) |
| `auto_purge` | boolean | true | Purge expired entries on startup |

**Cache Management Commands:**
```bash
# Prebuild cache
python -m artdaqdb_browser --build-cache

# Clear cache
python -m artdaqdb_browser --purge-cache

# Force refresh
python -m artdaqdb_browser --refresh-cache
```

---

### User Interface

```yaml
ui:
  # Color theme
  theme: "catppuccin-mocha"

  # Show deleted documents by default
  show_deleted: false

  # Enable mouse support
  mouse_support: true

  # Show keyboard hints panel
  show_key_hints: true

  # DateTime display format
  datetime_format: "%Y-%m-%d %H:%M:%S"

  # Date-only display format
  date_format: "%Y-%m-%d"

  # Timezone for display (null=local)
  timezone: "America/Chicago"

  # Max items before pagination
  max_list_items: 1000

  # Truncate text after N characters (0=no truncation)
  max_text_length: 500
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `theme` | string | "catppuccin-mocha" | Color theme |
| `show_deleted` | boolean | false | Show soft-deleted documents |
| `mouse_support` | boolean | true | Enable mouse interactions |
| `show_key_hints` | boolean | true | Show keyboard shortcut panel |
| `datetime_format` | string | "%Y-%m-%d %H:%M:%S" | DateTime format (strftime) |
| `date_format` | string | "%Y-%m-%d" | Date-only format |
| `timezone` | string | "America/Chicago" | Display timezone (null=local) |
| `max_list_items` | int | 1000 | Items before pagination |
| `max_text_length` | int | 500 | Truncate text (0=disabled) |

**Available Themes:**
- `catppuccin-mocha` - Dark theme with warm colors (default)
- `catppuccin-latte` - Light theme with warm colors
- `dark` - Standard dark theme
- `light` - Standard light theme

**Timezone Examples:**
```yaml
timezone: "America/Chicago"      # Central Time
timezone: "America/New_York"     # Eastern Time
timezone: "America/Los_Angeles"  # Pacific Time
timezone: "UTC"                  # Coordinated Universal Time
timezone: null                   # Use system local timezone
```

---

### Tables

```yaml
tables:
  # Enable zebra striping
  zebra_stripes: false

  # Default sort order: asc or desc
  default_sort_order: "desc"

  # Column widths
  columns:
    configuration_name: 40
    collection_name: 35
    version: 10
    document_id: 26
    timestamp: 20
    status: 12
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `zebra_stripes` | boolean | false | Alternating row colors |
| `default_sort_order` | string | "desc" | `asc` or `desc` |
| `columns.*` | int | varies | Column width in characters |

---

### Logging

```yaml
logging:
  # Enable trace logging
  trace_enabled: true

  # Trace log file path
  trace_file: "./trace.log"

  # Log level: debug, info, warning, error
  level: "info"

  # Max trace log size in MB
  max_trace_size_mb: 10

  # Number of backup logs to keep
  trace_backup_count: 3
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `trace_enabled` | boolean | true | Enable trace logging |
| `trace_file` | string | "./trace.log" | Log file path |
| `level` | string | "info" | `debug`, `info`, `warning`, `error` |
| `max_trace_size_mb` | int | 10 | Max log size before rotation |
| `trace_backup_count` | int | 3 | Number of backup logs |

---

### Backup and Restore

```yaml
backup:
  # Default output directory
  output_directory: "."

  # Filename pattern
  filename_pattern: "{database}-{timestamp}.tgz"

  # Timestamp format for filenames
  timestamp_format: "%Y%m%d_%H%M%S"

  # Collections to exclude from backups
  exclude_collections: []

  # Enable compression
  compress: true

  # Compression level (1-9)
  compression_level: 6

restore:
  # Require confirmation before restore
  require_confirmation: true

  # Collections to exclude from restore
  exclude_collections: []

  # Drop existing collections before restore
  drop_existing: false
```

**Filename Pattern Placeholders:**
- `{database}` - Database name
- `{timestamp}` - Formatted timestamp

**Example Output:** `teststand_db-20241201_143052.tgz`

---

### Document Settings

```yaml
documents:
  # Config name validation pattern (regex)
  config_name_pattern: "^[A-Za-z0-9_]+_v[0-9]+$"

  # Required substring in config names
  config_name_required: "_v"

  # Use soft delete (mark as deleted)
  soft_delete: true

  # Confirm before permanent delete
  confirm_hard_delete: true
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `config_name_pattern` | string | `^[A-Za-z0-9_]+_v[0-9]+$` | Regex for config name validation |
| `config_name_required` | string | "_v" | Required substring in names |
| `soft_delete` | boolean | true | Mark as deleted vs. permanent |
| `confirm_hard_delete` | boolean | true | Require confirmation for permanent delete |

---

### Search

```yaml
search:
  # Enable fuzzy matching
  fuzzy_match: true

  # Min characters before search starts
  min_search_chars: 1

  # Search debounce delay (ms)
  debounce_ms: 100

  # Case-insensitive search
  case_insensitive: true
```

| Field | Type | Default | Range | Description |
|-------|------|---------|-------|-------------|
| `fuzzy_match` | boolean | true | - | Enable fuzzy matching |
| `min_search_chars` | int | 1 | 1-10 | Characters before search triggers |
| `debounce_ms` | int | 100 | 0-1000 | Debounce delay |
| `case_insensitive` | boolean | true | - | Ignore case in search |

---

### External Tools

```yaml
tools:
  # MongoDB shell command
  mongo_shell: "mongosh"

  # mongodump command path
  mongodump: "mongodump"

  # mongorestore command path
  mongorestore: "mongorestore"
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mongo_shell` | string | "mongosh" | MongoDB shell command (auto-detected if null) |
| `mongodump` | string | "mongodump" | mongodump command path |
| `mongorestore` | string | "mongorestore" | mongorestore command path |

---

## Common Configurations

### Development (Local MongoDB, No Auth)

```yaml
app:
  debug: true

data_source:
  type: "mongodb"
  mongodb:
    uri: "mongodb://localhost:27017/teststand_db"
    auth:
      type: "none"

cache:
  ttl: 60  # Short TTL for development

logging:
  level: "debug"
```

### Production (X.509 Auth, Fermilab)

```yaml
app:
  name: "OTS ArtdaqDB Browser"

data_source:
  type: "mongodb"
  mongodb:
    uri: "mongodb://mu2eots-db.fnal.gov:27017/teststand_db"
    connect_timeout_ms: 30000
    server_selection_timeout_ms: 60000
    auth:
      type: "x509"
      x509:
        cert_dir: "~/.mongodb"
        ca_cert: "mu2eots-mongodb-ca.pem"
        client_cert: "artdaq-rw-mu2eots.pem"

cache:
  ttl: 600
  max_size_mb: 200

ui:
  timezone: "America/Chicago"

logging:
  level: "info"
```

### Offline Testing (Filesystem Backend)

```yaml
data_source:
  type: "filesystem"
  filesystem:
    uri: "filesystemdb://${HOME}/artdaqdb/sampledata/teststand_db"

cache:
  enabled: false  # Disable caching for testing
```

---

## Environment Variables

The configuration supports environment variable expansion in paths:

| Variable | Description |
|----------|-------------|
| `${HOME}` | User's home directory |
| `${USER}` | Current username |
| `~` | Shorthand for home directory |

**Example:**
```yaml
filesystem:
  uri: "filesystemdb://${HOME}/databases/${USER}/teststand_db"
```

---

## Troubleshooting

### Configuration Not Loading

1. Check file path and permissions:
   ```bash
   ls -la ~/.ots-browser/config.yaml
   ```

2. Validate YAML syntax:
   ```bash
   python -c "import yaml; yaml.safe_load(open('config.yaml'))"
   ```

3. Use explicit config path:
   ```bash
   python -m artdaqdb_browser --config /path/to/config.yaml
   ```

### MongoDB Connection Issues

1. Test connectivity:
   ```bash
   mongosh "mongodb://localhost:27017/teststand_db"
   ```

2. Check authentication:
   ```bash
   # X.509
   mongosh "mongodb://localhost:27017/teststand_db" \
     --tls \
     --tlsCertificateKeyFile ~/.mongodb/client.pem \
     --tlsCAFile ~/.mongodb/ca.pem
   ```

3. Verify certificate files exist:
   ```bash
   ls -la ~/.mongodb/*.pem
   ```

### Cache Issues

Clear the cache if experiencing stale data:
```bash
rm -rf ~/.ots-browser/cache/*
# Or use built-in command
python -m artdaqdb_browser --purge-cache
```

### Logging for Debugging

Enable debug logging temporarily:
```yaml
app:
  debug: true

logging:
  level: "debug"
  trace_enabled: true
  trace_file: "./debug-trace.log"
```

---

## Configuration Schema Reference

For the complete Pydantic schema definitions, see:
- `src/artdaqdb_browser/config/schema.py`

For the default configuration template:
- `src/artdaqdb_browser/config/defaults.py`

---

*Last updated: December 2024*
