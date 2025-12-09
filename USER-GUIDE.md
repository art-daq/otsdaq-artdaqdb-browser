# OTS Configuration Browser User Guide

## Introduction

The OTS Configuration Browser is a terminal-based user interface (TUI) application for browsing and managing OTS (Online Tracking System) configuration data for the Mu2e experiment. The application provides a powerful, keyboard-driven interface for navigating, viewing, and managing versioned configuration documents stored in MongoDB or as JSON files.

### Key Concepts

Before using the application, it's important to understand the core concepts:

- **Document**: A JSON object containing configuration data with metadata, versioning information, and bookkeeping records
- **Collection**: A named grouping of related documents (e.g., `GatewaySupervisorTable`, `ARTDAQServicesTable`)
- **Configuration**: A named snapshot that references specific document versions across multiple collections (e.g., `MC2ShiftContext_v31`)
- **Version**: A numeric identifier for a specific revision of a document within a collection

### Data Sources

The application supports two backend types:
- **MongoDB**: Connect directly to a MongoDB database
- **Filesystem**: Browse JSON files stored in a directory structure

---

## Getting Started

### Launching the Application

```bash
# Using MongoDB backend
python -m artdaqdb_browser --mongodb mongodb://localhost:27017/teststand_db

# Using filesystem backend
python -m artdaqdb_browser --directory ./sampledata/teststand_db

# Using configuration file
python -m artdaqdb_browser
```

### First Steps

1. When the application starts, you'll see the **Home Screen** with a menu of navigation options
2. Use `j`/`k` or arrow keys to navigate the menu
3. Press `Enter` or `l` to select an option
4. Press `?` to view the help screen at any time
5. Press `q` to quit the application

---

## Navigation Fundamentals

### Vim-Style Navigation

The OTS Browser uses vim-style keyboard navigation throughout:

| Key | Action |
|-----|--------|
| `j` or `Down Arrow` | Move cursor down |
| `k` or `Up Arrow` | Move cursor up |
| `h` or `Left Arrow` | Go back to previous screen |
| `l` or `Right Arrow` | Select/Enter/Drill down |
| `Enter` | Select current item |
| `Escape` | Cancel/Go back |
| `g` | Go to first item |
| `G` | Go to last item |

### Common Actions

| Key | Action |
|-----|--------|
| `/` | Open search/filter input |
| `c` | Clear current filter |
| `Tab` | Switch between panes/controls |
| `?` | Show help screen |
| `q` | Quit application |

### Key Panel

At the top of each screen, you'll see a **Key Panel** showing available keyboard shortcuts for that specific screen. This panel updates based on context.

---

## Main Workflows

### Workflow 1: Configuration-First Navigation

This workflow starts from a configuration name and drills down to view specific documents.

```
Home Screen
    ↓ Select "Browse Configurations"
Configuration List
    ↓ Select a configuration
Collection Table
    ↓ Select a collection
Version List
    ↓ Select a version
Document View
```

**Steps:**
1. From Home, select **Browse Configurations**
2. Use `/` to filter configurations by name
3. Select a configuration to see all collections it references
4. Select a collection to see available versions
5. Select a version to view the full document

### Workflow 2: Collection-First Navigation

This workflow starts from a collection and explores its versions and configurations.

```
Home Screen
    ↓ Select "Browse Collections"
Collection Browser
    ↓ Select a collection
Version List
    ↓ Select a version
Document View
```

**Steps:**
1. From Home, select **Browse Collections**
2. Browse or filter the list of collections
3. Select a collection to see all its versions
4. Select a version to view the document and its configuration assignments

---

## Screen Reference

### Home Screen

The main entry point to the application, displaying a menu of primary functions.

**Menu Options:**
- **Browse Configurations** - View configurations and their document assignments
- **Browse Collections** - View collections and their versions
- **Database Utilities** - Access backup, restore, and statistics tools
- **Database Doctor** - Access repair and diagnostic tools
- **Settings** - Configure application settings
- **Help** - View keyboard shortcuts and help

**Summary Panel:**
The right side shows database summary information:
- Total configurations
- Total collections
- Total documents
- Data source type
- Cache status

**Key Bindings:**
| Key | Action |
|-----|--------|
| `j/k` | Navigate menu |
| `Enter/l` | Select option |
| `?` | Help screen |
| `q` | Quit |

---

### Configuration List Screen

Displays all available configurations with filtering capabilities.

**Table Columns:**
- **Configuration Name** - The unique identifier (e.g., `MC2ShiftContext_v31`)
- **Collections** - Number of collections referenced
- **Last Assigned** - Timestamp of most recent assignment

**Features:**
- Fuzzy search filtering with `/`
- Sorted by assignment date (newest first)

**Key Bindings:**
| Key | Action |
|-----|--------|
| `j/k` | Navigate list |
| `/` | Filter configurations |
| `c` | Clear filter |
| `Enter/l` | View selected configuration |
| `h` | Go back |

---

### Collection Table Screen

Shows all collections referenced by a selected configuration.

**Table Columns:**
- **Collection** - Collection name
- **Version** - Document version in this configuration
- **Created** - Document creation timestamp
- **Status** - Active or Deleted

**Features:**
- Toggle visibility of deleted documents
- Direct navigation to version list
- Soft-delete toggle with `d`

**Key Bindings:**
| Key | Action |
|-----|--------|
| `j/k` | Navigate table |
| `d` | Toggle delete status |
| `Enter/l` | View versions |
| `h` | Go back |

---

### Version List Screen

Displays all versions of documents within a collection.

**Table Columns:**
- **Ver** - Version number
- **Document ID** - MongoDB ObjectId
- **Created** - Creation timestamp
- **Configurations** - Number of configurations using this version

**Key Bindings:**
| Key | Action |
|-----|--------|
| `j/k` | Navigate versions |
| `Enter/l` | View document |
| `h` | Go back |

---

### Collection Browser Screen

Alternative entry point for exploring all collections in the database.

**Table Columns:**
- **Collection Name** - Name of the collection
- **Versions** - Total number of versions
- **Latest Ver** - Most recent version number
- **Last Update** - Most recent update timestamp

**Features:**
- Alphabetical sorting
- Version count overview

**Key Bindings:**
| Key | Action |
|-----|--------|
| `j/k` | Navigate collections |
| `/` | Filter collections |
| `c` | Clear filter |
| `Enter/l` | View collection versions |
| `h` | Go back |

---

### Document View Screen

Detailed view of a single document with all its metadata and content.

**Sections:**
1. **Header** - Document ID, collection, version
2. **Configurations** - List of configurations this document is assigned to
3. **Metadata** - Creation info, update history
4. **Content** - JSON data viewer with syntax highlighting

**Features:**
- Tab-based navigation between sections
- JSON syntax highlighting
- Copy document ID to clipboard
- Assign to configuration modal

**Key Bindings:**
| Key | Action |
|-----|--------|
| `Tab` | Switch between panes |
| `j/k` | Scroll content |
| `g/G` | Jump to top/bottom |
| `y` | Copy document ID |
| `a` | Assign to configuration |
| `Enter` | View selected configuration |
| `h` | Go back |

---

### Configuration Editor Screen

Edit application settings through a tree-based interface.

**Settings Categories:**
- **app** - Application name, debug mode
- **data_source** - Backend type, paths, MongoDB connection
- **mongodb_auth** - Authentication settings (userpass, x509)
- **cache** - Caching configuration
- **ui** - Theme, display options
- **tables** - Table display preferences
- **logging** - Trace logging settings
- **backup/restore** - Backup/restore defaults
- **search** - Search behavior settings
- **tools** - External tool paths

**Features:**
- Tree navigation for nested settings
- Radio buttons for discrete options
- Text input for string/numeric values
- Path validation for directories and executables
- Save/reset functionality

**Key Bindings:**
| Key | Action |
|-----|--------|
| `j/k` | Navigate tree |
| `Enter/l` | Edit selected field |
| `s` | Save configuration |
| `r` | Reset to defaults |
| `v` | Validate configuration |
| `Escape/h` | Go back |

---

### Database Utilities Menu

Access to database maintenance and administrative tools.

**Options:**
- **Server Statistics** - MongoDB server information
- **Database Statistics** - Collection and index statistics
- **Backup Database** - Create database backups
- **Restore Database** - Restore from backup
- **Recreate Indexes** - Rebuild database indexes
- **Cache Viewer** - View and manage application cache

---

### Server Statistics Screen

Display MongoDB server information and status.

**Information Displayed:**
- Server version
- Storage engine
- Uptime
- Connection statistics
- Memory usage
- Network statistics

**Key Bindings:**
| Key | Action |
|-----|--------|
| `j/k` | Scroll content |
| `g/G` | Jump to top/bottom |
| `r` | Refresh statistics |
| `a` | Toggle extended stats |
| `h` | Go back |

---

### Database Statistics Screen

Display detailed database and collection statistics.

**Information Displayed:**
- Database size
- Collection counts
- Index information
- Storage statistics
- Per-collection breakdown

**Key Bindings:**
| Key | Action |
|-----|--------|
| `j/k` | Scroll content |
| `r` | Refresh statistics |
| `h` | Go back |

---

### Backup Screen

Create backups of the MongoDB database.

**Fields:**
- **Database Selection** - Choose database to backup
- **Output Directory** - Backup destination (browse with directory picker)
- **Filename** - Generated filename with timestamp

**Features:**
- Directory browser modal for path selection
- Progress indicator during backup
- Compression options

**Key Bindings:**
| Key | Action |
|-----|--------|
| `Tab` | Navigate between fields |
| `Enter` | Execute backup / Browse directory |
| `h` | Go back |

---

### Restore Screen

Restore database from a backup archive.

**Fields:**
- **Source Path** - Path to backup archive (.tgz)
- **Target Database** - Database to restore to
- **Options** - Drop existing collections, confirmation

**Features:**
- Directory browser for backup selection
- Confirmation prompt before restore
- Progress indicator

**Key Bindings:**
| Key | Action |
|-----|--------|
| `Tab` | Navigate between fields |
| `Enter` | Execute restore / Browse |
| `h` | Go back |

---

### Cache Viewer Screen

View and manage the application's disk cache.

**Table Columns:**
- **Key** - Cache entry identifier
- **Size** - Entry size
- **Expires** - Expiration timestamp

**Features:**
- View cached entries
- Delete individual entries
- Purge entire cache
- Cache statistics summary

**Key Bindings:**
| Key | Action |
|-----|--------|
| `j/k` | Navigate entries |
| `r` | Refresh view |
| `c` | Clear selected entry |
| `p` | Purge all cache |
| `Delete` | Delete entry |
| `h` | Go back |

---

### Recreate Indexes Screen

Rebuild MongoDB indexes for all collections.

**Features:**
- List of collections with index status
- Rebuild individual or all indexes
- Progress tracking

**Key Bindings:**
| Key | Action |
|-----|--------|
| `j/k` | Navigate collections |
| `Enter` | Rebuild selected index |
| `a` | Rebuild all indexes |
| `h` | Go back |

---

### Database Doctor Menu

Access to diagnostic and repair tools.

**Options:**
- **Repair Collection** - Fix collections with duplicate versions
- **Repair Configuration** - Fix configurations with duplicate collections
- **JSON Diff/Merge** - Compare and merge JSON documents

---

### Repair Collection Screen

Find and resolve collections with duplicate document versions.

**Table Columns:**
- **Collection Name** - Name of the collection
- **Duplicate Versions** - Count of duplicate versions found
- **Total Versions** - Total version count

**Features:**
- Scan for duplicate versions
- View duplicate details
- Repair options (merge, delete)

**Key Bindings:**
| Key | Action |
|-----|--------|
| `j/k` | Navigate collections |
| `/` | Filter collections |
| `c` | Clear filter |
| `Enter/l` | View duplicates |
| `h` | Go back |

---

### Repair Configuration Screen

Find and resolve configurations with duplicate collection references.

**Table Columns:**
- **Configuration Name** - Name of the configuration
- **Duplicate Collections** - Count of duplicates
- **Total Collections** - Total collection count

**Features:**
- Scan for duplicate references
- View and resolve duplicates

**Key Bindings:**
| Key | Action |
|-----|--------|
| `j/k` | Navigate configurations |
| `/` | Filter |
| `c` | Clear filter |
| `Enter/l` | View duplicates |
| `h` | Go back |

---

### JSON Diff/Merge Screen

Compare and merge two JSON documents side by side.

**Features:**
- Side-by-side diff view
- Path-based navigation
- Merge operations (left-to-right, right-to-left)
- Save merged result

**Key Bindings:**
| Key | Action |
|-----|--------|
| `j/k` | Navigate differences |
| `Tab` | Switch panels |
| `c` | Copy selected value |
| `s` | Save result |
| `m` | Change mode |
| `h` | Go back |

---

### Trace Viewer Screen

View application trace logs for debugging.

**Features:**
- Table view with severity-colored entries
- Raw text view toggle
- Filtering by severity, source, tags
- Search within logs
- Auto-scroll to latest entries

**Filter Options:**
- **Time** - Filter by timestamp range
- **Severity** - Filter by log level (DEBUG, INFO, WARNING, ERROR)
- **Source** - Filter by source class
- **Tags** - Filter by log tags
- **Message** - Filter by message content

**Key Bindings:**
| Key | Action |
|-----|--------|
| `j/k` | Scroll/navigate |
| `g/G` | Jump to top/bottom |
| `/` | Search |
| `n/N` | Next/previous match |
| `f` | Toggle filters |
| `t` | Toggle table/raw view |
| `x` | Clear all filters |
| `a` | Toggle auto-scroll |
| `r` | Reload log |
| `c` | Clear log |
| `Escape` | Go back |

---

### Help Screen

Displays keyboard shortcuts and navigation help.

**Sections:**
- Navigation keys
- Screen-specific actions
- Global shortcuts
- Tips and tricks

**Key Bindings:**
| Key | Action |
|-----|--------|
| `j/k` | Scroll content |
| `Escape/h/q` | Close help |

---

## Modal Dialogs

### Assign Configuration Modal

Assign a document to a configuration.

**Interaction Modes:**
- **Command Mode** (default): Navigate with `j/k`, select with `Enter`
- **Insert Mode**: Press `i` to edit search field

**Features:**
- Fuzzy search for existing configurations
- Create new configuration names
- Pattern validation (`<SystemName>_v<number>`)

**Key Bindings:**
| Key | Action |
|-----|--------|
| `i` | Enter edit mode |
| `Escape` | Exit edit mode / Cancel |
| `j/k` | Navigate list (command mode) |
| `Enter` | Assign selected configuration |

---

### Directory Browser Modal

Browse and select directories for backup/restore operations.

**Features:**
- Tree-based directory navigation
- Directory contents summary
- Current selection display

**Key Bindings:**
| Key | Action |
|-----|--------|
| `j/k` | Navigate tree |
| `Enter` | Select directory |
| `Escape` | Cancel |

---

## Tips and Best Practices

### Efficient Navigation

1. **Use fuzzy search** - Type `/` and enter partial names to quickly filter large lists
2. **Learn vim keys** - `j/k/h/l` is faster than arrow keys once you're comfortable
3. **Use `g` and `G`** - Jump to the beginning or end of long lists instantly
4. **Tab between panes** - In multi-pane views, `Tab` cycles focus

### Performance

1. **Enable caching** - Caching significantly improves navigation speed
2. **Use the cache viewer** - Monitor cache status and clear when needed
3. **Prebuild cache** - Use `--build-cache` flag for large databases

### Data Safety

1. **Soft delete first** - Use `d` to soft-delete before permanent removal
2. **Backup regularly** - Use the backup utility before major changes
3. **Check duplicate repair** - Run Database Doctor periodically

### Troubleshooting

1. **View trace logs** - Access via Settings or `Ctrl+T`
2. **Clear cache** - If data appears stale, purge the cache
3. **Check connection** - Server Statistics shows MongoDB status

---

## Appendix: Document Schema

Documents follow the OTS schema structure:

```json
{
  "_id": "24-character-hex-string",
  "collection": "CollectionName",
  "version": "1",
  "configurations": [
    {"name": "ConfigName_v1", "assigned": "ISO8601 timestamp"}
  ],
  "bookkeeping": {
    "isdeleted": false,
    "isreadonly": false,
    "created": "ISO8601 timestamp",
    "updates": []
  },
  "document": {
    "data": {},
    "metadata": {},
    "search": []
  }
}
```

For complete schema documentation, refer to `DOCUMENT-SCHEMA.md`.
