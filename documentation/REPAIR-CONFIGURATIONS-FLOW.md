# Repair Configurations Flow: Duplicate Collections

## Overview

The **Repair Configurations** flow identifies and repairs configurations that reference the same collection multiple times. In a healthy database, each configuration should reference each collection at most once. When a configuration contains multiple documents from the same collection, this flow helps identify and remove the duplicate references.

## Problem Definition

A **duplicate collection** in a configuration occurs when:
- Two or more documents assigned to the same configuration belong to the same collection
- This typically happens when multiple versions of a collection document are accidentally assigned to the same configuration

### Example

```
Configuration: OnlineConfiguration_v15
├── doc_abc123 (collection: GatewaySupervisorTable, version: "5", created: 2024-01-01)  ← Original (oldest)
├── doc_def456 (collection: GatewaySupervisorTable, version: "7", created: 2024-01-15)  ← Duplicate assignment
└── doc_ghi789 (collection: ARTDAQServicesTable, version: "3", created: 2024-01-10)     ← OK (different collection)
```

In this example, `GatewaySupervisorTable` appears twice in the configuration - this is the issue to fix.

## Resolution Strategy

The repair flow uses an **"oldest wins"** strategy:
- For each collection that appears multiple times in a configuration, the **oldest document** (by `created` timestamp) keeps its configuration assignment
- All newer documents have their configuration assignment **removed** (not deleted)
- The documents themselves remain in the database; only the configuration reference is removed
- A `removeConfiguration` bookkeeping event is recorded for audit purposes

### Key Difference from Collection Repair

| Repair Collections | Repair Configurations |
|-------------------|----------------------|
| Fixes duplicate **version numbers** within a collection | Fixes duplicate **collection references** within a configuration |
| **Deletes** duplicate documents | **Removes configuration assignment** from duplicate documents |
| Documents are permanently removed | Documents remain, only the config reference is removed |

## Screen Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Database Doctor Menu                             │
│                "Repair Configuration (Duplicate Collections)"            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   RepairConfigurationListScreen                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Configuration Name       │ Dup Collections │ Total Docs         │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │ OnlineConfiguration_v15  │       3         │      8             │   │
│  │ TestConfig_v7            │       2         │      5             │   │
│  │ ProductionContext_v23    │       1         │      2             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  [/] Filter  [j/k] Navigate  [Enter] Select  [Ctrl+T] Global Trash      │
└─────────────────────────────────────────────────────────────────────────┘
           │                                              │
           │ [Enter] Select configuration                 │ [Ctrl+T]
           ▼                                              ▼
┌────────────────────────────────┐    ┌────────────────────────────────────┐
│ DiffableCollectionTableScreen  │    │    GlobalTrashConfigListScreen      │
│ (Single Configuration View)    │    │    (All Configurations View)        │
│                                │    │                                      │
│ Shows all duplicate collection │    │ Shows ALL documents needing config  │
│ docs for selected config       │    │ removal across all configurations   │
│                                │    │                                      │
│ [Ctrl+T] Toggle Trash Mode     │    │ [d] Remove config from document     │
│ [d] Remove config assignment   │    │ [Ctrl+D] Remove ALL configs         │
│ [Ctrl+D] Remove all trash      │    │                                      │
└────────────────────────────────┘    └────────────────────────────────────┘
```

## Screens Reference

### 1. RepairConfigurationListScreen

**Purpose**: Lists all configurations that have duplicate collection references.

**Entry Point**: Database Doctor Menu → "Repair Configuration (Duplicate Collections)"

**Analysis Process**:
1. On mount, the screen runs `DuplicateCollectionAnalyzer.analyze()`
2. The analyzer scans all configurations and groups documents by collection
3. Configurations with any collection appearing more than once are flagged

**Table Columns**:
| Column | Description |
|--------|-------------|
| Configuration Name | Name of the configuration with duplicates |
| Dup Collections | Number of collections that appear multiple times |
| Total Docs | Total number of duplicate documents (sum across all collections) |

**Sorting**: Configurations are sorted by "Dup Collections" count (most duplicates first)

**Key Bindings**:
| Key | Action | Description |
|-----|--------|-------------|
| `j/k` or `↑/↓` | Navigate | Move cursor up/down in the table |
| `/` | Search | Activate fuzzy filter input |
| `Enter` or `l/→` | Select | Open the selected config in DiffableCollectionTableScreen |
| `Ctrl+T` | Global Trash | Open GlobalTrashConfigListScreen |
| `Escape` or `h/←` | Back | Return to Database Doctor menu (cancels analysis if running) |

**Filtering**: Type in the filter input to fuzzy-match configuration names

**Analysis Cancellation**: If analysis is running, pressing `Escape` will cancel it and return to the previous screen.

---

### 2. DiffableCollectionTableScreen

**Purpose**: Shows all documents in a configuration, with special handling for duplicate collection references.

**Entry Point**: RepairConfigurationListScreen → Select a configuration

**Display Modes**:

1. **Duplicate Mode** (default):
   - Shows all documents that are part of duplicate collection sets
   - All duplicates are visible, including the keeper (oldest)
   - Status bar shows: `[REPAIR MODE: Duplicate Collections]`

2. **Trash Mode** (toggle with `Ctrl+T`):
   - Shows only documents that should have their config assignment removed
   - The keeper (oldest document for each collection) is hidden
   - Status bar shows: `[TRASH MODE: Remove Config]`

**Table Columns**:
| Column | Description |
|--------|-------------|
| Collection | Collection name (duplicates will show the same name) |
| Version | Version number of the document |
| Status | Active or Deleted status |
| Document ID | 24-character hex identifier |

**Key Bindings**:
| Key | Action | Description |
|-----|--------|-------------|
| `j/k` or `↑/↓` | Navigate | Move cursor up/down |
| `/` | Search | Activate fuzzy filter |
| `Ctrl+T` | Toggle Trash | Switch between Duplicate and Trash modes |
| `d` | Remove Config | Remove config assignment from selected document |
| `Ctrl+D` | Remove All | Remove config from ALL trash documents |
| `t` | Toggle Deleted | Show/hide soft-deleted documents |
| `Enter` | Select | Open document in full viewer |
| `Escape` | Back | Return to RepairConfigurationListScreen |

**Trash Mode Filtering Logic**:
```
For each collection that appears multiple times:
    1. Sort documents by 'created' timestamp (ascending)
    2. Mark the OLDEST document as "keeper" (keeps config assignment)
    3. All other documents become "trash" (will have config removed)
```

---

### 3. GlobalTrashConfigListScreen

**Purpose**: Shows a flat list of ALL documents across ALL configurations that need their configuration assignment removed.

**Entry Point**: RepairConfigurationListScreen → Press `Ctrl+T`

**Use Case**: When you want to review and clean up all duplicate configuration assignments at once, regardless of which configuration they belong to.

**Table Columns**:
| Column | Description |
|--------|-------------|
| Configuration | Configuration name |
| Collection | Collection name |
| Version | Version number |
| Created | Document creation timestamp |

**Key Bindings**:
| Key | Action | Description |
|-----|--------|-------------|
| `j/k` or `↑/↓` | Navigate | Move cursor up/down |
| `/` | Search | Filter by configuration or collection name |
| `d` | Remove Config | Remove config assignment from selected document |
| `Ctrl+D` | Remove All | Remove config from ALL visible trash documents |
| `Escape` | Back | Return to RepairConfigurationListScreen |

**Filtering**: Fuzzy-match on both configuration name and collection name

---

## Configuration Removal Process

### What Happens When You Remove a Configuration Assignment

Unlike the collection repair flow (which deletes documents), the configuration repair flow **removes the configuration reference** from documents:

1. The configuration entry is removed from the document's `configurations` array
2. A `removeConfiguration` event is added to `bookkeeping.updates`
3. The document is saved back to the database
4. The document remains in the database and can still be accessed

### Single Document Configuration Removal

1. Press `d` on a document
2. Confirmation modal appears showing:
   - Configuration name being removed
   - Collection name
   - Version number
   - Document ID (truncated)
3. Press `Enter` to confirm, `Escape` to cancel
4. On confirmation:
   - Configuration is removed from document
   - Bookkeeping event is recorded
   - Display refreshes automatically

### Bulk Configuration Removal (Remove All Trash)

1. Press `Ctrl+D` (works in Trash Mode or GlobalTrashConfigListScreen)
2. Confirmation modal appears showing:
   - Number of documents to process
   - Number of configurations affected (for global view)
3. Press `Enter` to confirm
4. Configuration assignments are removed using MongoDB's `bulk_write` API for efficient batch processing
5. Success/failure count is displayed

**Performance Note**: Bulk configuration removals use MongoDB's `bulk_write` operation which:
- Pre-fetches all documents in a single batch query using `$in` operator
- Groups operations by collection and executes them in parallel
- Handles partial failures gracefully, reporting individual errors
- Records proper `removeConfiguration` bookkeeping events for each document

---

## Bookkeeping Event

When a configuration assignment is removed, the following event is recorded in the document's `bookkeeping.updates` array:

```json
{
  "event": "removeConfiguration",
  "timestamp": "2025-06-16T14:40:01.962-0500",
  "value": {
    "name": "OnlineConfiguration_v15",
    "assigned": "2020-06-16T14:40:01.962-0500",
    "removed": "2025-06-16T14:40:01.962-0500"
  }
}
```

**Fields**:
| Field | Description |
|-------|-------------|
| `event` | Always `"removeConfiguration"` |
| `timestamp` | When the removal occurred |
| `value.name` | Name of the configuration that was removed |
| `value.assigned` | Original timestamp when config was assigned |
| `value.removed` | Timestamp when config was removed (same as event timestamp) |

---

## Analyzer Details

### DuplicateCollectionAnalyzer

**Location**: `src/artdaqdb_browser/data/analyzers.py`

**Analysis Output**:
```python
@dataclass
class DuplicateCollectionAnalysisResult:
    configurations_with_duplicate_collections: Dict[str, List[str]]
    # Maps: config_name -> [list of collection names with duplicates]

    duplicate_collection_details: Dict[str, Dict[str, List[str]]]
    # Maps: config_name -> {collection_name -> [list of document IDs]}
```

**Filter Methods**:
- `filter_documents_by_config(documents, config_name)`: Returns only documents from duplicate collections
- `filter_collections(collections)`: Returns only collections that are duplicates

### TrashDuplicateCollectionAnalyzer

**Purpose**: Wraps `DuplicateCollectionAnalyzer` to filter out keepers

**Keeper Selection Logic**:
```python
def _compute_keepers(documents, config_name, collection_name):
    for each collection with duplicates in config:
        find document with OLDEST 'created' timestamp
        mark as keeper (keeps config assignment)
    return set of keeper document IDs
```

### GlobalTrashDuplicateCollectionAnalyzer

**Purpose**: Computes all trash documents across all configurations

**Output**:
```python
@dataclass
class GlobalTrashConfigItem:
    id: str           # Document ID
    config_name: str  # Configuration name
    collection: str   # Collection name
    version: str      # Version number
    created: str      # Creation timestamp
    assigned: str     # Original config assignment timestamp
```

---

## Backend Method: remove_configuration_assignment

**Location**: `src/artdaqdb_browser/data/base.py` (abstract), implemented in `mongodb.py`, `filesystem.py`, `cached.py`

**Signature**:
```python
def remove_configuration_assignment(
    self,
    document_id: str,
    config_name: str,
    timestamp: str
) -> bool
```

**Process**:
1. Load the document by ID
2. Find the configuration in the `configurations` array
3. Remove the configuration entry
4. Create a `removeConfiguration` bookkeeping event with:
   - Original `assigned` timestamp
   - Current `removed` timestamp
5. Save the document back to storage
6. Return success/failure

---

## Example Workflow

### Scenario: Clean up duplicate collections in OnlineConfiguration_v15

1. **Enter Repair Mode**
   - Open Database Doctor menu
   - Select "Repair Configuration (Duplicate Collections)"

2. **Review Broken Configurations**
   - See list of configurations with duplicates
   - OnlineConfiguration_v15 shows: 3 dup collections, 8 total docs

3. **Select Configuration**
   - Press `Enter` on OnlineConfiguration_v15
   - Opens DiffableCollectionTableScreen

4. **Review Duplicates**
   - See all documents that are from duplicate collections
   - GatewaySupervisorTable appears 3 times (versions 5, 7, 9)
   - ARTDAQServicesTable appears 2 times (versions 12, 15)
   - TrackSeedFilterTable appears 3 times (versions 1, 2, 3)

5. **Switch to Trash Mode**
   - Press `Ctrl+T`
   - Now only showing documents to have config removed (5 documents)
   - The 3 keeper documents (oldest for each collection) are hidden

6. **Review and Remove**
   - Option A: Remove config one at a time with `d`
   - Option B: Remove all with `Ctrl+D`

7. **Confirm Removal**
   - Modal shows count of documents to process
   - Press `Enter` to confirm
   - Configuration assignments are removed
   - Documents remain in database with bookkeeping events

8. **Return to List**
   - Press `Escape` to return
   - Configuration may no longer appear if all duplicates were fixed

---

## Status Bar Indicators

| Indicator | Meaning |
|-----------|---------|
| `[REPAIR MODE]` | Viewing configurations with issues |
| `[REPAIR MODE: Duplicate Collections]` | Viewing duplicate collections in a config |
| `[TRASH MODE: Remove Config]` | Viewing only documents to have config removed |
| `[GLOBAL TRASH MODE]` | Viewing all trash across all configurations |

---

## Comparison: Before and After

### Before Configuration Removal

**Document: doc_def456**
```json
{
  "_id": "def456...",
  "collection": "GatewaySupervisorTable",
  "version": "7",
  "configurations": [
    {
      "name": "OnlineConfiguration_v15",
      "assigned": "2024-01-15T10:00:00.000-0600"
    }
  ],
  "bookkeeping": {
    "updates": []
  }
}
```

### After Configuration Removal

**Document: doc_def456**
```json
{
  "_id": "def456...",
  "collection": "GatewaySupervisorTable",
  "version": "7",
  "configurations": [],
  "bookkeeping": {
    "updates": [
      {
        "event": "removeConfiguration",
        "timestamp": "2025-06-16T14:40:01.962-0500",
        "value": {
          "name": "OnlineConfiguration_v15",
          "assigned": "2024-01-15T10:00:00.000-0600",
          "removed": "2025-06-16T14:40:01.962-0500"
        }
      }
    ]
  }
}
```

Note: The document still exists and can be assigned to other configurations or used for other purposes.

---

## Error Handling

- **Analysis Errors**: Displayed in status bar and notification; analysis can be cancelled with `Escape`
- **Removal Failures**: Count shown in notification (e.g., "Removed from 5, failed 1")
- **Empty Results**: "All configurations have unique collections" notification
- **Missing Document**: Warning logged if document not found during removal
- **Missing Configuration**: Warning logged if config not found in document

---

## Use Cases

### When to Use This Flow

1. **After Bulk Imports**: If documents were imported with incorrect configuration assignments
2. **After Manual Editing**: If users accidentally assigned multiple versions to the same config
3. **Database Migration**: When consolidating configurations from multiple sources
4. **Configuration Cleanup**: Regular maintenance to ensure configuration integrity

### When NOT to Use This Flow

1. **Intentional Duplicates**: Some workflows may legitimately need multiple versions of a collection in a config (rare, but consult your system administrator)
2. **If Unsure**: Always review the documents in trash mode before confirming removal
