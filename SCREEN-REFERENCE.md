# OTS Configuration Browser - Screen Reference

This document provides detailed technical reference for each screen in the application, including widget layouts, data sources, and interaction patterns.

---

## Screen Architecture

All screens inherit from `BaseScreen` which provides:
- Common vim-style navigation bindings (`j/k/h/l`)
- Back navigation (`h`, `Left Arrow`, `Escape`)
- Focus management with `Tab` cycling
- Scroll bindings (`g/G` for top/bottom)

### Screen Classes

| Screen | File | Purpose |
|--------|------|---------|
| `HomeScreen` | `screens/home.py` | Main menu and dashboard |
| `ConfigListScreen` | `screens/config_list.py` | Configuration list with filtering |
| `CollectionTableScreen` | `screens/collection_table.py` | Collections in a configuration |
| `VersionListScreen` | `screens/version_list.py` | Document versions in a collection |
| `CollectionBrowserScreen` | `screens/collection_browser.py` | All collections overview |
| `DocumentViewScreen` | `screens/viewers/document_view.py` | Full document viewer |
| `ConfigEditorScreen` | `screens/viewers/config_editor.py` | Application settings editor |
| `TraceViewerScreen` | `screens/viewers/trace_viewer.py` | Trace log viewer |
| `HelpScreen` | `screens/help_screen.py` | Keyboard shortcuts help |

---

## Home Screen

**Class**: `HomeScreen`
**File**: `screens/home.py`

### Layout
```
┌─────────────────────────────────────────────────────────────────┐
│ [KeyPanel]                                                       │
├─────────────────────────────────────────────────────────────────┤
│ OTS Browser                                                      │
├─────────────────────────────┬───────────────────────────────────┤
│  Menu                       │  Database Summary                  │
│  ────────────────────────── │  ─────────────────────────────────│
│  > Browse Configurations    │  Configurations: 1,234             │
│    Browse Collections       │  Collections: 56                   │
│    Database Utilities       │  Documents: 12,345                 │
│    Database Doctor          │  Source: mongodb://...             │
│    Settings                 │  Cache: Enabled (45 MB)            │
│    Help                     │                                    │
│                             │                                    │
├─────────────────────────────┴───────────────────────────────────┤
│ Status: Ready                                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Navigation Actions
| Action | Target Screen |
|--------|---------------|
| Browse Configurations | `ConfigListScreen` |
| Browse Collections | `CollectionBrowserScreen` |
| Database Utilities | `DatabaseUtilitiesMenu` |
| Database Doctor | `DatabaseDoctorMenu` |
| Settings | `ConfigEditorScreen` |
| Help | `HelpScreen` |

### Key Bindings
- `j/k`, `Down/Up`: Navigate menu
- `Enter`, `l`, `Right`: Select option
- `?`: Open help screen
- `q`: Quit application

---

## Configuration List Screen

**Class**: `ConfigListScreen`
**File**: `screens/config_list.py`

### Layout
```
┌─────────────────────────────────────────────────────────────────┐
│ [KeyPanel]                                                       │
├─────────────────────────────────────────────────────────────────┤
│ Configurations                                                   │
├─────────────────────────────────────────────────────────────────┤
│ [Filter: _______________]                                        │
├─────────────────────────────────────────────────────────────────┤
│ Configuration Name          │ Collections │ Last Assigned        │
│ ─────────────────────────── │ ─────────── │ ──────────────────── │
│ MC2ShiftContext_v31         │ 45          │ 2025-01-15 14:30     │
│ ProductionConfig_v12        │ 38          │ 2025-01-14 09:15     │
│ TestStand_v8                │ 22          │ 2025-01-13 16:45     │
│ ...                         │ ...         │ ...                  │
├─────────────────────────────────────────────────────────────────┤
│ Showing 150 of 1234 configs (filtered: 'mc2')                    │
└─────────────────────────────────────────────────────────────────┘
```

### Data Source
- `backend.list_configurations()` - Returns all configuration names
- `backend.get_configuration_info(config_name)` - Returns collection count and assignment time

### Table Columns
| Column | Width | Data Field |
|--------|-------|------------|
| Configuration Name | 40 | `name` |
| Collections | 12 | `collections` count |
| Last Assigned | 20 | Latest `assigned` timestamp |

### Key Bindings
- `/`: Open filter input
- `c`: Clear filter
- `Enter`, `l`: Navigate to `CollectionTableScreen`
- `h`, `Escape`: Return to `HomeScreen`

---

## Collection Table Screen

**Class**: `CollectionTableScreen`
**File**: `screens/collection_table.py`

### Layout
```
┌─────────────────────────────────────────────────────────────────┐
│ [KeyPanel]                                                       │
├─────────────────────────────────────────────────────────────────┤
│ Configuration: MC2ShiftContext_v31                               │
│ Assigned: 2025-01-15T14:30:00                                    │
├─────────────────────────────────────────────────────────────────┤
│ Collection                  │ Version │ Created      │ Status    │
│ ─────────────────────────── │ ─────── │ ──────────── │ ───────── │
│ GatewaySupervisorTable      │ 5       │ 2025-01-10   │ Active    │
│ ARTDAQServicesTable         │ 12      │ 2025-01-08   │ Active    │
│ TrackSeedFilterTable        │ 3       │ 2024-12-20   │ Deleted   │
├─────────────────────────────────────────────────────────────────┤
│ 45 collections | 2 deleted (hidden: No)                          │
└─────────────────────────────────────────────────────────────────┘
```

### Data Source
- `backend.get_configuration_documents(config_name)` - Returns documents for configuration
- Document fields: `collection`, `version`, `bookkeeping.created`, `bookkeeping.isdeleted`

### Table Columns
| Column | Width | Data Field |
|--------|-------|------------|
| Collection | 35 | `collection` |
| Version | 10 | `version` |
| Created | 20 | `bookkeeping.created` |
| Status | 12 | `bookkeeping.isdeleted` ? "Deleted" : "Active" |

### Key Bindings
- `d`: Toggle soft-delete status
- `Enter`, `l`: Navigate to `VersionListScreen`
- `h`, `Escape`: Return to `ConfigListScreen`

---

## Version List Screen

**Class**: `VersionListScreen`
**File**: `screens/version_list.py`

### Layout
```
┌─────────────────────────────────────────────────────────────────┐
│ [KeyPanel]                                                       │
├─────────────────────────────────────────────────────────────────┤
│ Collection: GatewaySupervisorTable                               │
├─────────────────────────────────────────────────────────────────┤
│ Ver │ Document ID                 │ Created      │ Configs      │
│ ─── │ ─────────────────────────── │ ──────────── │ ──────────── │
│ 5   │ 507f1f77bcf86cd799439011    │ 2025-01-10   │ 3            │
│ 4   │ 507f1f77bcf86cd799439010    │ 2025-01-05   │ 2            │
│ 3   │ 507f1f77bcf86cd79943900f    │ 2024-12-28   │ 5            │
├─────────────────────────────────────────────────────────────────┤
│ 5 versions | Current: v5                                         │
└─────────────────────────────────────────────────────────────────┘
```

### Data Source
- `backend.get_collection_documents(collection_name)` - Returns all versions
- Grouped by version number, sorted descending

### Table Columns
| Column | Width | Data Field |
|--------|-------|------------|
| Ver | 6 | `version` |
| Document ID | 26 | `_id` |
| Created | 20 | `bookkeeping.created` |
| Configurations | 15 | `len(configurations)` |

### Key Bindings
- `Enter`, `l`: Navigate to `DocumentViewScreen`
- `h`, `Escape`: Return to previous screen

---

## Collection Browser Screen

**Class**: `CollectionBrowserScreen`
**File**: `screens/collection_browser.py`

### Layout
```
┌─────────────────────────────────────────────────────────────────┐
│ [KeyPanel]                                                       │
├─────────────────────────────────────────────────────────────────┤
│ Collections                                                      │
├─────────────────────────────────────────────────────────────────┤
│ [Filter: _______________]                                        │
├─────────────────────────────────────────────────────────────────┤
│ Collection Name             │ Versions │ Latest │ Last Update   │
│ ─────────────────────────── │ ──────── │ ────── │ ───────────── │
│ ARTDAQServicesTable         │ 12       │ v12    │ 2025-01-14    │
│ GatewaySupervisorTable      │ 5        │ v5     │ 2025-01-10    │
│ TrackSeedFilterTable        │ 3        │ v3     │ 2024-12-20    │
├─────────────────────────────────────────────────────────────────┤
│ 56 collections                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Data Source
- `backend.list_collections()` - Returns all collection names
- `backend.get_collection_info(collection)` - Returns version count and latest info

### Table Columns
| Column | Width | Data Field |
|--------|-------|------------|
| Collection Name | 35 | `name` |
| Versions | 10 | version count |
| Latest Ver | 12 | highest version |
| Last Update | 20 | latest `bookkeeping.created` |

### Key Bindings
- `/`: Filter collections
- `c`: Clear filter
- `Enter`, `l`: Navigate to `VersionListScreen`
- `h`, `Escape`: Return to `HomeScreen`

---

## Document View Screen

**Class**: `DocumentViewScreen`
**File**: `screens/viewers/document_view.py`

### Layout
```
┌─────────────────────────────────────────────────────────────────┐
│ [KeyPanel]                                                       │
├─────────────────────────────────────────────────────────────────┤
│ Document: 507f1f77bcf86cd799439011                               │
│ Collection: GatewaySupervisorTable | Version: 5                  │
├──────────────────────────────┬──────────────────────────────────┤
│  Configurations              │  Document Content                 │
│  ──────────────────────────  │  ────────────────────────────────│
│  > MC2ShiftContext_v31       │  {                                │
│    ProductionConfig_v12      │    "data": {                      │
│    TestStand_v8              │      "gateway_host": "mu2e-...",  │
│                              │      "port": 8080,                │
│                              │      "timeout_ms": 5000           │
│                              │    },                             │
│                              │    "metadata": {...}              │
│                              │  }                                │
├──────────────────────────────┴──────────────────────────────────┤
│ Created: 2025-01-10 | Configs: 3 | Status: Active                │
└─────────────────────────────────────────────────────────────────┘
```

### Data Source
- `backend.get_document(document_id)` - Returns full document
- Document contains all schema fields including `configurations`, `bookkeeping`, `document`

### Panes
1. **Header**: Document ID, collection, version
2. **Configuration List**: Assigned configurations with timestamps
3. **JSON Viewer**: Full document content with syntax highlighting
4. **Metadata Panel**: Creation info, update history

### Key Bindings
- `Tab`: Cycle between panes
- `j/k`: Scroll content
- `g/G`: Jump to top/bottom
- `y`: Copy document ID to clipboard
- `a`: Open assign configuration modal
- `Enter` (on config list): Navigate to that configuration's `CollectionTableScreen`
- `h`, `Escape`: Return to previous screen

---

## Configuration Editor Screen

**Class**: `ConfigEditorScreen`
**File**: `screens/viewers/config_editor.py`

### Layout
```
┌─────────────────────────────────────────────────────────────────┐
│ [KeyPanel]                                                       │
├─────────────────────────────────────────────────────────────────┤
│ Configuration Editor                                             │
├────────────────────────────┬────────────────────────────────────┤
│  Settings                  │  Path: data_source > type           │
│  ────────────────────────  │  ────────────────────────────────── │
│  ▼ app                     │  Backend type: 'filesystem' or      │
│    ├─ name: OTS Browser    │  'mongodb'                          │
│    └─ debug: false         │                                     │
│  ▼ data_source             │  ( ) Filesystem                     │
│    ├─ type: mongodb        │  (●) MongoDB                        │
│    ├─ ▶ filesystem         │                                     │
│    └─ ▶ mongodb            │  [Apply] [Reset Field]              │
│  ▶ mongodb_auth            │                                     │
│  ▶ cache                   │                                     │
│  ...                       │                                     │
├────────────────────────────┴────────────────────────────────────┤
│ Modified (unsaved) | File: ~/.config/ots-browser/config.yaml     │
├─────────────────────────────────────────────────────────────────┤
│ [Save] [Validate All] [Cancel]                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Configuration Sections
| Section | Contents |
|---------|----------|
| `app` | Application name, debug mode |
| `data_source` | Backend type, paths, MongoDB connection settings |
| `mongodb_auth` | Authentication (none, userpass, x509) |
| `cache` | Caching enabled, directory, TTL, size limits |
| `ui` | Theme, display options, mouse support |
| `tables` | Zebra stripes, sort order |
| `logging` | Trace enabled, file path, log level |
| `backup` | Output directory, compression settings |
| `restore` | Confirmation, drop existing options |
| `search` | Fuzzy match, case sensitivity |
| `tools` | External tool paths (mongodump, mongorestore) |

### Field Types
1. **Discrete fields**: Radio button selection (e.g., theme, auth type)
2. **Text fields**: Free-form input (e.g., paths, URIs)
3. **Path fields**: With validation and "Validate Path" button
4. **Read-only fields**: Complex nested objects

### Key Bindings
- `j/k`: Navigate tree
- `Enter`, `l`: Focus edit field
- `s`: Save configuration
- `r`: Reset field to default
- `v`: Validate all paths and settings
- `h`, `Escape`: Return (warns if unsaved)

---

## Database Utilities Menu

**Class**: `DatabaseUtilitiesMenu`
**File**: `screens/dbutils/db_utilities_menu.py`

### Menu Options
| Option | Screen | Purpose |
|--------|--------|---------|
| Server Statistics | `ServerStatsScreen` | MongoDB server info |
| Database Statistics | `DatabaseStatsScreen` | Collection/index stats |
| Backup Database | `BackupScreen` | Create backup |
| Restore Database | `RestoreScreen` | Restore from backup |
| Recreate Indexes | `RecreateIndexesScreen` | Rebuild indexes |
| Cache Viewer | `CacheViewerScreen` | View/manage cache |

---

## Server Statistics Screen

**Class**: `ServerStatsScreen`
**File**: `screens/dbutils/server_stats.py`

### Information Sections
- Server version and storage engine
- Uptime and connection counts
- Memory usage (resident, virtual, mapped)
- Network I/O statistics
- Operation counts (queries, inserts, updates, deletes)

### Key Bindings
- `j/k`: Scroll content
- `r`: Refresh statistics
- `a`: Toggle extended statistics view
- `h`, `Escape`: Return to menu

---

## Database Statistics Screen

**Class**: `DatabaseStatsScreen`
**File**: `screens/dbutils/database_stats.py`

### Information Sections
- Database size and storage size
- Collection count and index count
- Average object size
- Per-collection breakdown (document count, size, indexes)

### Key Bindings
- `j/k`: Scroll content
- `r`: Refresh statistics
- `h`, `Escape`: Return to menu

---

## Backup Screen

**Class**: `BackupScreen`
**File**: `screens/dbutils/backup_screen.py`

### Fields
| Field | Type | Description |
|-------|------|-------------|
| Database | Dropdown | Database to backup |
| Output Directory | Path + Browse | Destination folder |
| Filename | Auto-generated | Based on pattern and timestamp |
| Compress | Checkbox | Enable compression |

### Actions
- **Browse**: Opens `DirectoryBrowserModal`
- **Execute**: Runs `mongodump` with progress indicator

### Key Bindings
- `Tab`: Navigate fields
- `Enter`: Execute backup / Browse directory
- `h`, `Escape`: Return to menu

---

## Restore Screen

**Class**: `RestoreScreen`
**File**: `screens/dbutils/restore_screen.py`

### Fields
| Field | Type | Description |
|-------|------|-------------|
| Source Path | Path + Browse | Backup archive (.tgz) |
| Target Database | Dropdown | Database to restore to |
| Drop Existing | Checkbox | Drop collections before restore |

### Actions
- **Browse**: Opens `DirectoryBrowserModal`
- **Execute**: Runs `mongorestore` with confirmation

### Key Bindings
- `Tab`: Navigate fields
- `Enter`: Execute restore / Browse
- `h`, `Escape`: Return to menu

---

## Cache Viewer Screen

**Class**: `CacheViewerScreen`
**File**: `screens/dbutils/cache_viewer.py`

### Layout
```
┌─────────────────────────────────────────────────────────────────┐
│ Cache Statistics                                                 │
│ Total Entries: 156 | Size: 45.2 MB | Hit Rate: 87%              │
├─────────────────────────────────────────────────────────────────┤
│ Key                         │ Size    │ Expires                  │
│ ─────────────────────────── │ ─────── │ ──────────────────────── │
│ configurations_list         │ 12.5 KB │ 2025-01-16 14:30         │
│ config_docs:MC2ShiftCon...  │ 1.2 MB  │ 2025-01-16 14:30         │
│ collection_docs:Gateway...  │ 256 KB  │ 2025-01-16 14:30         │
├─────────────────────────────────────────────────────────────────┤
│ Ready                                                            │
└─────────────────────────────────────────────────────────────────┘
```

### Key Bindings
- `j/k`: Navigate entries
- `r`: Refresh cache view
- `c`: Clear selected entry
- `p`: Purge entire cache
- `Delete`: Delete selected entry
- `h`, `Escape`: Return to menu

---

## Database Doctor Menu

**Class**: `DatabaseDoctorMenu`
**File**: `screens/dbdoctor/db_doctor_menu.py`

### Menu Options
| Option | Screen | Purpose |
|--------|--------|---------|
| Repair Collection | `RepairCollectionScreen` | Fix duplicate versions |
| Repair Configuration | `RepairConfigurationScreen` | Fix duplicate references |
| JSON Diff/Merge | `JsonDiffMergeScreen` | Compare/merge documents |

---

## Repair Collection Screen

**Class**: `RepairCollectionScreen`
**File**: `screens/dbdoctor/repair_collection.py`

### Purpose
Identifies collections that have duplicate document versions (same version number assigned to multiple documents).

### Table Columns
| Column | Width | Data |
|--------|-------|------|
| Collection Name | 35 | Collection identifier |
| Duplicate Versions | 18 | Count of duplicated version numbers |
| Total Versions | 14 | Total version count |

### Key Bindings
- `j/k`: Navigate collections
- `/`: Filter by name
- `Enter`, `l`: View and repair duplicates
- `h`, `Escape`: Return to menu

---

## Repair Configuration Screen

**Class**: `RepairConfigurationScreen`
**File**: `screens/dbdoctor/repair_configuration.py`

### Purpose
Identifies configurations that reference the same collection multiple times.

### Table Columns
| Column | Width | Data |
|--------|-------|------|
| Configuration Name | 40 | Configuration identifier |
| Duplicate Collections | 20 | Count of duplicate references |
| Total Collections | 18 | Total collection count |

### Key Bindings
- `j/k`: Navigate configurations
- `/`: Filter by name
- `Enter`, `l`: View and repair duplicates
- `h`, `Escape`: Return to menu

---

## JSON Diff/Merge Screen

**Class**: `JsonDiffMergeScreen`
**File**: `screens/dbdoctor/json_diff_merge.py`

### Layout
```
┌─────────────────────────────────────────────────────────────────┐
│ JSON Diff/Merge                                                  │
├────────────────────────────┬────────────────────────────────────┤
│  Differences Table         │  JSON Tree View                     │
│  ────────────────────────  │  ──────────────────────────────────│
│  Act │ Path    │ Left│Right│  ▼ document                        │
│  ─── │ ─────── │ ────│─────│    ▼ data                          │
│  [<] │ .port   │ 8080│ 9090│      port: 9090                    │
│  [>] │ .host   │ a.co│ b.co│      host: "b.com"                 │
│  [=] │ .timeout│ 5000│ 5000│      timeout: 5000                 │
├────────────────────────────┴────────────────────────────────────┤
│ Mode: Compare | 3 differences                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Features
- Side-by-side comparison of two JSON documents
- Path-based diff highlighting
- Merge operations: copy left-to-right or right-to-left
- Save merged result

### Key Bindings
- `j/k`: Navigate differences
- `Tab`: Switch between panels
- `c`: Copy selected value to other side
- `s`: Save merged result
- `m`: Change mode (compare/merge)
- `h`, `Escape`: Return to menu

---

## Trace Viewer Screen

**Class**: `TraceViewerScreen`
**File**: `screens/viewers/trace_viewer.py`

### Layout
```
┌─────────────────────────────────────────────────────────────────┐
│ [KeyPanel]                                                       │
├─────────────────────────────────────────────────────────────────┤
│ Trace Log Viewer                                                 │
├─────────────────────────────────────────────────────────────────┤
│ [Time    ] [Sev] [Source              ] [Tags/Message         ] │
├─────────────────────────────────────────────────────────────────┤
│ 14:30:01.123│INF │HomeScreen.on_mount  │Screen mounted          │
│ 14:30:01.456│DBG │Backend.query        │Query executed          │
│ 14:30:02.789│WRN │Cache.get            │Cache miss              │
├─────────────────────────────────────────────────────────────────┤
│  Entry Details                                                   │
│  ─────────────────────────────────────────────────────────────── │
│  TIMESTAMP: 2025-01-15T14:30:01.123-0600                        │
│  SEVERITY:  INFO (20)                                            │
│  SOURCE:    HomeScreen.on_mount                                  │
│  MESSAGE:   Screen mounted                                       │
├─────────────────────────────────────────────────────────────────┤
│ Entry 1/150 | INF | HomeScreen.on_mount                          │
└─────────────────────────────────────────────────────────────────┘
```

### Filter Row Controls
| Control | Function |
|---------|----------|
| Time | Filter by timestamp range |
| Severity | Filter by log level (TRC, DBG, INF, WRN, ERR, CRT) |
| Source | Filter by source class |
| Tags | Filter by log tags |
| Message | Filter by message content |

### View Modes
1. **Table View**: Structured data table with columns
2. **Raw View**: Full text log output

### Key Bindings
- `/`: Open search input
- `n/N`: Next/previous search match
- `f`: Toggle filter row visibility
- `t`: Toggle table/raw view
- `x`: Clear all filters
- `a`: Toggle auto-scroll to latest
- `r`: Reload log file
- `c`: Clear log file
- `Tab`: Cycle focus (filters -> table -> detail)
- `j/k`: Navigate/scroll
- `g/G`: Jump to top/bottom
- `Escape`: Go back

---

## Help Screen

**Class**: `HelpScreen`
**File**: `screens/help_screen.py`

### Content Sections
1. **Navigation** - Basic vim-style navigation keys
2. **Actions** - Common actions and shortcuts
3. **Screen-Specific** - Context-sensitive help
4. **Tips** - Usage tips and best practices

### Key Bindings
- `j/k`: Scroll help content
- `Escape`, `h`, `q`: Close help screen

---

## Modal Screens

### AssignConfigurationModal

**File**: `screens/assign_config_modal.py`

#### Vim-Style Modes
- **Command Mode**: Navigate with `j/k`, select with `Enter`
- **Insert Mode**: Edit search field (press `i` to enter)

#### Data Flow
1. Loads existing configurations from backend
2. User filters or enters new configuration name
3. Validates pattern `<SystemName>_v<number>`
4. Calls `backend.assign_configuration(doc_id, config_name, timestamp)`

---

### DirectoryBrowserModal

**File**: `screens/dbutils/directory_browser.py`

#### Features
- Tree-based directory navigation
- Shows directory contents summary (folders, files, backups)
- Returns selected `Path` on confirm, `None` on cancel

---

## Navigation Constants

Defined in `constants.py`:

### ScreenName Enum
```python
HOME = "home"
CONFIG_LIST = "config_list"
COLLECTION_TABLE = "collection_table"
VERSION_LIST = "version_list"
DOCUMENT_VIEW = "document_view"
COLLECTION_BROWSER = "collection_browser"
HELP = "help"
TRACE_VIEWER = "trace_viewer"
DB_UTILITIES = "db_utilities"
SERVER_STATS = "server_stats"
DATABASE_STATS = "database_stats"
DB_BACKUP = "db_backup"
DB_RESTORE = "db_restore"
RECREATE_INDEXES = "recreate_indexes"
CONFIG_EDITOR = "config_editor"
DB_DOCTOR = "db_doctor"
REPAIR_COLLECTION = "repair_collection"
REPAIR_CONFIGURATION = "repair_configuration"
CACHE_VIEWER = "cache_viewer"
JSON_DIFF_MERGE = "json_diff_merge"
```

### Common Key Bindings (BaseScreen)
```python
BACK_BINDINGS = [
    Binding("h", "go_back", "Back", show=False),
    Binding("left", "go_back", "Back", show=False),
]

FOCUS_BINDINGS = [
    Binding("tab", "focus_next", "Next", show=False),
    Binding("shift+tab", "focus_previous", "Previous", show=False),
]

SCROLL_BINDINGS = [
    Binding("j", "scroll_down", "Down", show=False),
    Binding("k", "scroll_up", "Up", show=False),
    Binding("g", "scroll_top", "Top", show=False),
    Binding("G", "scroll_bottom", "Bottom", show=False),
]
```
