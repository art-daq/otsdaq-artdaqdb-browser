# OTS Configuration Browser - Quick Reference Card

## Global Navigation

| Key | Action |
|-----|--------|
| `j` / `Down` | Move down |
| `k` / `Up` | Move up |
| `h` / `Left` | Go back |
| `l` / `Right` | Select/Enter |
| `Enter` | Confirm selection |
| `Escape` | Cancel / Go back |
| `Tab` | Next pane/control |
| `q` | Quit application |
| `?` | Show help |

## Movement

| Key | Action |
|-----|--------|
| `g` | Go to first item |
| `G` | Go to last item |
| `Ctrl+d` | Page down |
| `Ctrl+u` | Page up |

## Search & Filter

| Key | Action |
|-----|--------|
| `/` | Open search/filter |
| `n` | Next search match |
| `N` | Previous match |
| `c` | Clear filter |

## List/Table Screens

| Key | Action |
|-----|--------|
| `j/k` | Navigate rows |
| `/` | Filter list |
| `c` | Clear filter |
| `Enter` | Select item |
| `h` | Go back |

## Document View

| Key | Action |
|-----|--------|
| `Tab` | Switch panes |
| `j/k` | Scroll content |
| `y` | Copy document ID |
| `a` | Assign config |
| `Enter` | View config |

## Collection Table

| Key | Action |
|-----|--------|
| `d` | Toggle delete |
| `Enter` | View versions |

## Configuration Editor

| Key | Action |
|-----|--------|
| `j/k` | Navigate tree |
| `Enter/l` | Edit field |
| `s` | Save config |
| `r` | Reset field |
| `v` | Validate |

## Trace Viewer

| Key | Action |
|-----|--------|
| `/` | Search |
| `f` | Toggle filters |
| `t` | Toggle view |
| `x` | Clear filters |
| `a` | Auto-scroll |
| `r` | Reload |
| `c` | Clear log |

## Database Utilities

| Key | Action |
|-----|--------|
| `r` | Refresh stats |
| `a` | Extended stats |
| `Tab` | Next field |

## Modal Dialogs

### Assign Configuration
| Key | Action |
|-----|--------|
| `i` | Edit mode |
| `Escape` | Exit edit/Close |
| `j/k` | Navigate list |
| `Enter` | Assign |

### Directory Browser
| Key | Action |
|-----|--------|
| `j/k` | Navigate |
| `Enter` | Select |
| `Escape` | Cancel |

---

## Screen Navigation Map

```
HOME
 ├── Browse Configurations ──→ Config List ──→ Collection Table ──→ Version List ──→ Document View
 │                                                                                         ↓
 ├── Browse Collections ───→ Collection Browser ──→ Version List ──→ Document View ←──────┘
 │
 ├── Database Utilities
 │    ├── Server Statistics
 │    ├── Database Statistics
 │    ├── Backup Database
 │    ├── Restore Database
 │    ├── Recreate Indexes
 │    └── Cache Viewer
 │
 ├── Database Doctor
 │    ├── Repair Collection
 │    ├── Repair Configuration
 │    └── JSON Diff/Merge
 │
 ├── Settings ──→ Configuration Editor
 │
 └── Help ──→ Help Screen
```

---

## Status Indicators

| Symbol | Meaning |
|--------|---------|
| Active | Document is active |
| Deleted | Document is soft-deleted |
| (filtered) | List has active filter |

## Color Coding

- **Green**: Success, active items
- **Yellow/Amber**: Warnings, pending
- **Red**: Errors, deleted items
- **Gray**: Disabled, unavailable

---

## Tips

1. Use `/` for fuzzy search in any list
2. `g` and `G` for quick top/bottom navigation
3. `Tab` cycles through panes in multi-pane screens
4. `y` in Document View copies ID to clipboard
5. `Escape` always goes back or cancels
