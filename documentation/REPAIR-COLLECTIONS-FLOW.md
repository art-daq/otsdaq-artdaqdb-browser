# Repair Collections Flow: Duplicate Versions

## Overview

The **Repair Collections** flow identifies and repairs collections that contain duplicate version numbers. In a healthy database, each version number within a collection should correspond to exactly one document. When multiple documents share the same version number, this flow helps identify and remove the duplicates.

## Problem Definition

A **duplicate version** occurs when:
- Two or more documents in the same collection have identical `version` values
- This typically happens due to import errors, migration issues, or manual document creation

### Example

```
Collection: GatewaySupervisorTable
├── doc_abc123 (version: "5", created: 2024-01-01)  ← Original (oldest)
├── doc_def456 (version: "5", created: 2024-01-15)  ← Duplicate
└── doc_ghi789 (version: "5", created: 2024-01-20)  ← Duplicate
```

## Resolution Strategy

The repair flow uses an **"oldest wins"** strategy:
- For each set of duplicate versions, the **oldest document** (by `created` timestamp) is kept
- All newer duplicates are marked for deletion (moved to "trash")
- Users can review and confirm deletions before they are executed
- Deletions are **hard deletes** (documents are permanently removed from the database)

## Screen Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Database Doctor Menu                             │
│                    "Repair Collection (Duplicate Versions)"              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     RepairCollectionListScreen                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Collection Name          │ Dup Versions │ Total Docs           │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │ GatewaySupervisorTable   │     3        │     8                │   │
│  │ ARTDAQServicesTable      │     2        │     5                │   │
│  │ TrackSeedFilterTable     │     1        │     2                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  [/] Filter  [j/k] Navigate  [Enter] Select  [Ctrl+T] Global Trash      │
└─────────────────────────────────────────────────────────────────────────┘
           │                                              │
           │ [Enter] Select collection                    │ [Ctrl+T]
           ▼                                              ▼
┌────────────────────────────────┐    ┌────────────────────────────────────┐
│  DiffableVersionListScreen     │    │      GlobalTrashListScreen          │
│  (Single Collection View)      │    │      (All Collections View)         │
│                                │    │                                      │
│  Shows all duplicate versions  │    │  Shows ALL trash documents across   │
│  for the selected collection   │    │  all collections with duplicates    │
│                                │    │                                      │
│  [Ctrl+T] Toggle Trash Mode    │    │  [d] Delete single document         │
│  [d] Delete document           │    │  [Ctrl+D] Delete ALL trash          │
│  [w] Diff with next            │    │  [v] View document                  │
│  [Ctrl+D] Delete all trash     │    │                                      │
└────────────────────────────────┘    └────────────────────────────────────┘
```

## Screens Reference

### 1. RepairCollectionListScreen

**Purpose**: Lists all collections that have duplicate version numbers.

**Entry Point**: Database Doctor Menu → "Repair Collection (Duplicate Versions)"

**Analysis Process**:
1. On mount, the screen runs `DuplicateVersionAnalyzer.analyze()`
2. The analyzer scans all collections and groups documents by version
3. Collections with any version having more than one document are flagged

**Table Columns**:
| Column | Description |
|--------|-------------|
| Collection Name | Name of the collection with duplicates |
| Dup Versions | Number of version numbers that have duplicates |
| Total Docs | Total number of duplicate documents (sum across all versions) |

**Sorting**: Collections are sorted by "Dup Versions" count (most duplicates first)

**Key Bindings**:
| Key | Action | Description |
|-----|--------|-------------|
| `j/k` or `↑/↓` | Navigate | Move cursor up/down in the table |
| `/` | Search | Activate fuzzy filter input |
| `Enter` or `l/→` | Select | Open the selected collection in DiffableVersionListScreen |
| `Ctrl+T` | Global Trash | Open GlobalTrashListScreen showing all trash documents |
| `Escape` or `h/←` | Back | Return to Database Doctor menu |

**Filtering**: Type in the filter input to fuzzy-match collection names

---

### 2. DiffableVersionListScreen

**Purpose**: Shows all versions in a single collection, with special handling for duplicates.

**Entry Point**: RepairCollectionListScreen → Select a collection

**Display Modes**:

1. **Duplicate Mode** (default):
   - Shows all documents that are part of duplicate version sets
   - All duplicates are visible, including the keeper (oldest)
   - Status bar shows: `[REPAIR MODE: Duplicate Versions]`

2. **Trash Mode** (toggle with `Ctrl+T`):
   - Shows only documents that should be deleted
   - The keeper (oldest document for each version) is hidden
   - Status bar shows: `[TRASH MODE]`

**Table Columns**:
| Column | Description |
|--------|-------------|
| Version | Version number (duplicates will show the same number) |
| Created | Document creation timestamp |
| Status | Active or Deleted status |
| Document ID | 24-character hex identifier |

**Key Bindings**:
| Key | Action | Description |
|-----|--------|-------------|
| `j/k` or `↑/↓` | Navigate | Move cursor up/down |
| `/` | Search | Activate fuzzy filter |
| `Ctrl+T` | Toggle Trash | Switch between Duplicate and Trash modes |
| `d` | Delete | Delete the selected document (with confirmation) |
| `Ctrl+D` | Delete All | Delete ALL trash documents (with confirmation) |
| `w` | Diff | Show JSON diff between selected and next document |
| `v` | View | Open document in full viewer |
| `Enter` | Select | Open document in full viewer |
| `Escape` | Back | Return to RepairCollectionListScreen |

**Trash Mode Filtering Logic**:
```
For each version with duplicates:
    1. Sort documents by 'created' timestamp (ascending)
    2. Mark the OLDEST document as "keeper"
    3. All other documents become "trash"
```

---

### 3. GlobalTrashListScreen

**Purpose**: Shows a flat list of ALL trash documents across ALL collections with duplicate versions.

**Entry Point**: RepairCollectionListScreen → Press `Ctrl+T`

**Use Case**: When you want to review and delete all duplicate documents at once, regardless of which collection they belong to.

**Table Columns**:
| Column | Description |
|--------|-------------|
| Collection | Collection name |
| Version | Version number |
| Created | Document creation timestamp |
| Document ID | 24-character hex identifier |

**Key Bindings**:
| Key | Action | Description |
|-----|--------|-------------|
| `j/k` or `↑/↓` | Navigate | Move cursor up/down |
| `/` | Search | Filter by collection or version |
| `d` | Delete | Delete selected document (with confirmation) |
| `Ctrl+D` | Delete All | Delete ALL visible trash documents (with confirmation) |
| `v` | View | Open document in full viewer |
| `Ctrl+T` or `Escape` | Back | Return to RepairCollectionListScreen |

**Filtering**: Fuzzy-match on both collection name and version number

---

## Deletion Process

### Single Document Deletion

1. Press `d` on a document
2. Confirmation modal appears showing:
   - Collection name
   - Version number
   - Document ID (truncated)
3. Press `Enter` or `Y` to confirm, `Escape` or `N` to cancel
4. On confirmation: Document is **hard deleted** from database
5. Display refreshes automatically

### Bulk Deletion (Delete All Trash)

1. Press `Ctrl+D` (works in Trash Mode or GlobalTrashListScreen)
2. Confirmation modal appears showing:
   - Number of documents to delete
   - Number of collections affected
3. Press `Enter` or `Y` to confirm
4. Documents are deleted using MongoDB's `bulk_write` API for efficient batch processing
5. Success/failure count is displayed
6. Cache is cleared after successful bulk delete

**Performance Note**: Bulk deletions use MongoDB's `bulk_write` operation which:
- Pre-fetches all documents in a single batch query using `$in` operator
- Groups operations by collection and executes them in parallel
- Handles partial failures gracefully, reporting individual errors

---

## Analyzer Details

### DuplicateVersionAnalyzer

**Location**: `src/artdaqdb_browser/data/analyzers.py`

**Analysis Output**:
```python
@dataclass
class DuplicateVersionAnalysisResult:
    collections_with_duplicate_versions: Dict[str, List[str]]
    # Maps: collection_name -> [list of version numbers with duplicates]

    duplicate_version_details: Dict[str, Dict[str, List[str]]]
    # Maps: collection_name -> {version -> [list of document IDs]}
```

**Filter Methods**:
- `filter_versions(versions, collection_name)`: Returns only versions that are duplicates

### TrashDuplicateVersionAnalyzer

**Purpose**: Wraps `DuplicateVersionAnalyzer` to filter out keepers

**Keeper Selection Logic**:
```python
def _compute_keepers(versions, collection_name):
    for each version with duplicates:
        find document with OLDEST 'created' timestamp
        mark as keeper
    return set of keeper document IDs
```

### GlobalTrashDuplicateVersionAnalyzer

**Purpose**: Computes all trash documents across all collections

**Output**:
```python
@dataclass
class GlobalTrashItem:
    id: str           # Document ID
    collection: str   # Collection name
    version: str      # Version number
    created: str      # Creation timestamp
```

---

## Bookkeeping Events

When a document is deleted, it is **hard deleted** (permanently removed from the database). No bookkeeping event is recorded because the document no longer exists.

If you need to track deletions, consider using soft delete (`bookkeeping.isdeleted = true`) instead, which would record:
```json
{
  "event": "markDeleted",
  "timestamp": "2025-01-15T14:30:00.000-0600",
  "value": {
    "reason": "Duplicate version cleanup"
  }
}
```

---

## Example Workflow

### Scenario: Clean up duplicate versions in GatewaySupervisorTable

1. **Enter Repair Mode**
   - Open Database Doctor menu
   - Select "Repair Collection (Duplicate Versions)"

2. **Review Broken Collections**
   - See list of collections with duplicates
   - GatewaySupervisorTable shows: 3 dup versions, 8 total docs

3. **Select Collection**
   - Press `Enter` on GatewaySupervisorTable
   - Opens DiffableVersionListScreen

4. **Review Duplicates**
   - See all documents that are duplicates
   - Version "5" appears 3 times
   - Version "12" appears 2 times
   - Version "18" appears 3 times

5. **Switch to Trash Mode**
   - Press `Ctrl+T`
   - Now only showing documents to delete (6 documents)
   - The 3 keeper documents (oldest for each version) are hidden

6. **Review and Delete**
   - Option A: Delete one at a time with `d`
   - Option B: Delete all with `Ctrl+D`

7. **Confirm Deletion**
   - Modal shows count of documents to delete
   - Press `Enter` to confirm
   - Documents are permanently deleted

8. **Return to List**
   - Press `Escape` to return
   - Collection may no longer appear if all duplicates were fixed

---

## Status Bar Indicators

| Indicator | Meaning |
|-----------|---------|
| `[REPAIR MODE]` | Viewing collections with issues |
| `[REPAIR MODE: Duplicate Versions]` | Viewing duplicate versions in a collection |
| `[TRASH MODE]` | Viewing only documents to delete |
| `[GLOBAL TRASH MODE]` | Viewing all trash across all collections |

---

## Error Handling

- **Analysis Errors**: Displayed in status bar and notification
- **Delete Failures**: Count shown in notification (e.g., "Deleted 5, failed 1")
- **Empty Results**: "No collections with duplicate versions found!" notification
