# Keyboard Navigation

All screens inherit from `BaseScreen` which provides standardized keyboard navigation.

## KeyPanel Display

The KeyPanel (right sidebar) displays ONLY these key categories:

### Navigation
- `j`, `k`: Move up / down

### Screen Navigation
- `h`, `Left`: Back / previous screen
- `l`, `Right`: Forward / into selection
- `Escape`: Cancel current action / close modal

### Focus
- `Tab`: Cycle focus

### Actions Primary
- `Enter`: Confirm / select
- `r`: Refresh data

## FooterBar Display

The `FooterBar` widget displays secondary (context-specific) actions plus application keys.
It is **always visible** and **dynamically updates** based on the current screen's `SECONDARY_ACTIONS`.

### Application Keys (always shown)
- `?`: Open help screen
- `q`: Quit application

### Actions Secondary (screen-specific)
Common secondary actions (screens define which ones they use):
- `a`: Add / create new entry
- `e`: Edit selected entry
- `d`: Delete selected entry
- `x`: Execute command / run script
- `u`: Undo last action

### Search & Filter (FilterableTableScreen)
- `/`: Open search input
- `c`: Clear filter

## Implementation

### Screen Template Pattern

`BaseScreen.compose()` provides a standard template that automatically includes:
1. **KeyPanel** (right sidebar)
2. **Screen content** (from `compose_content()`)
3. **FooterBar** (bottom bar)

Subclasses override `compose_content()` instead of `compose()`:

```python
class MyScreen(BaseScreen):
    # Define secondary actions - bindings auto-generated, FooterBar auto-populated
    SECONDARY_ACTIONS = [
        ("a", "action_create", "Create"),
        ("d", "action_remove", "Remove"),
    ]

    def compose_content(self) -> ComposeResult:
        '''Add screen-specific widgets. KeyPanel and FooterBar are automatic.'''
        yield Static("My Screen Title", classes="screen-title")
        yield DataTable(id="my_table")

    def action_create(self) -> None:
        '''Handle 'a' key press.'''
        pass

    def action_remove(self) -> None:
        '''Handle 'd' key press.'''
        pass
```

### Adding Extra Key Bindings to KeyPanel

Override `get_extra_key_bindings()` to add screen-specific keys:

```python
class MyScreen(BaseScreen):
    def get_extra_key_bindings(self) -> List[Tuple[str, str]]:
        return [("/", "Search"), ("x", "Execute")]
```

Note: `FilterableTableScreen` already provides filter keys (`/`, `c`) automatically.

## Key Binding Rules

1. **KeyPanel** shows: Navigation, Screen Navigation, Focus, Actions Primary, Application
2. **FooterBar** shows: Only secondary actions from `SECONDARY_ACTIONS`
3. **FooterBar** is always visible (even when empty)
4. **Derived screens** define `SECONDARY_ACTIONS` - bindings are auto-generated
5. **Action names** must be ONE WORD (e.g., "Create", "Delete", "Execute")

## Hidden Keys (functional but not displayed)
- `g`, `G`: Jump to top / bottom
- `Page Up`, `Page Down`: Page navigation
- `Space`: Toggle selection
- `Shift+Tab`: Reverse focus cycle

## Confirmations (when prompted)
- `y`: Confirm action
- `n`, `Escape`: Cancel action
