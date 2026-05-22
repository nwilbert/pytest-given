# Report Redesign — Design Spec

## Goal

Redesign the pytest-given HTML report to address three usability issues: visual polish, navigation, and information density. Align the design with [JGiven's HTML5 report](https://jgiven.org/jgiven-report/html5/) while keeping the report self-contained (single HTML file with all assets inlined).

## Approach

Pico CSS-inspired custom CSS (~8–10 KB). No framework dependency. Light theme. CSS custom properties for theming. Alpine.js stays for client-side interactivity.

## Design Tokens

```css
:root {
  /* Typography */
  --font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  --font-size-sm: 0.75rem;     /* 12px — meta, counts, badges */
  --font-size-base: 0.8125rem; /* 13px — step text, tree items */
  --font-size-md: 0.875rem;    /* 14px — scenario name */
  --font-size-lg: 1.25rem;     /* 20px — page title */

  /* Colors — light theme */
  --bg-page: #f8f9fa;
  --bg-card: #ffffff;
  --bg-sidebar: #ffffff;
  --border: #dee2e6;
  --text-primary: #212529;
  --text-secondary: #495057;
  --text-muted: #6c757d;

  /* Status */
  --color-passed: #28a745;
  --color-failed: #dc3545;
  --color-skipped: #ffc107;

  /* Accent (links, tag badges, active states) */
  --color-accent: #0d6efd;
  --color-accent-bg: #e7f1ff;

  /* Error block */
  --color-error-bg: #fff5f5;
  --color-error-border: #f5c6cb;

  /* Spacing scale */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 12px;
  --space-lg: 16px;
  --space-xl: 20px;

  /* Border radius */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-pill: 9999px;
}
```

Parameter highlight colors (adapted for light backgrounds — slightly deeper than current):

| Class | Color | Use |
|-------|-------|-----|
| `param-color-0` | `#d63384` (pink) | 1st parameter |
| `param-color-1` | `#198754` (green) | 2nd parameter |
| `param-color-2` | `#0d6efd` (blue) | 3rd parameter |
| `param-color-3` | `#ca8a04` (amber) | 4th parameter |
| `param-color-4` | `#7c3aed` (purple) | 5th parameter |
| `param-color-5` | `#e85d04` (orange) | 6th parameter |

## Layout

Two-column layout (same structure as current):

- **Sidebar** (260px, sticky, full height): project name, search, status filter, browse-by toggle, tree navigation.
- **Main content** (flex: 1, scrollable): context header, scenario cards.

Background: `--bg-page` for the page, `--bg-card` for cards, `--bg-sidebar` for sidebar. Separated by `--border` lines.

## Sidebar

Top to bottom:

1. **Project name** — bold, `--font-size-md`.
2. **Search input** — filters scenarios by name and tags. Light gray background (`--bg-page`), subtle border.
3. **Status filter pills** — three toggle-able pill badges:
   - Active: colored background matching status (green/red/yellow tints with dark text).
   - Inactive: dimmed, struck-through text, white background.
   - Clicking toggles the status filter. Filters apply to both the sidebar tree and the main content.
   - Each pill shows the count for that status.
4. **Status summary bar** — thin (3px) horizontal stacked bar showing pass/fail/skip proportions. Updates when status filters change (hides filtered-out segments).
5. **Browse-by toggle** — segmented button: "Tags" | "Modules". Active segment: `--color-accent` background, white text. Inactive: white background, muted text.
6. **Navigation tree** — collapsible groups:
   - Group header: ▸/▾ toggle, group name (tag or module), count badge (right-aligned, muted).
   - Children: scenario names as links. Each shows a status icon (✓/✗/○) to its left.
   - Click a scenario → scrolls to it in main content and expands it.
   - Tree respects all active filters (search + status + browse-by).

## Scenario Cards

### Collapsed state (default)

All scenarios render collapsed by default. A collapsed card shows:

- Left border: 3px solid, colored by status (passed=green, failed=red, skipped=yellow).
- ▸ toggle indicator.
- Scenario name (`--font-size-md`, weight 500).
- Tag badges: pill-shaped, `--color-accent-bg` background, `--color-accent` text. **Clickable** — clicking a tag badge filters the report to that tag (switches sidebar to Tags view, highlights the tag, shows only matching scenarios). Click again or clear search to remove filter.
- Status label: right-aligned, colored text with icon (✓ passed / ✗ failed / ○ skipped).

Click anywhere on the card header to expand.

### Expanded state

Adds below the header:

- **Steps** rendered with inline phase keywords:
  - `Given`, `When`, `Then` as left-aligned labels (gray, bold, fixed-width ~44px) followed by step text on the same line. This replaces the current design where phase labels are separate header divs above the steps.
  - When multiple consecutive steps share the same phase, only the first shows the keyword. Subsequent steps of the same phase show just the text, left-padded to align with the first step's text.
  - Parameter values highlighted inline using the 6-color system.
  - Nested steps: indented with left border, collapsible via ▸/▾.
- **Attachments**: expandable badges (📎 label), click to reveal content in monospace block.
- **Parameter table** (if parameterized): same design as current but adapted to light theme. Column headers colored to match parameter highlights. Failed rows get soft red background.
- **Error block** (if failed): `--color-error-bg` background, `--color-error-border` border, red error message, monospace diff below.

### Auto-expand behavior

Failed scenarios expand automatically on page load so errors are immediately visible.

## Clickable Tag Badges

When a tag badge is clicked on any scenario card:

1. The report filters to show only scenarios with that tag.
2. The sidebar switches to "Tags" browse-by view (if not already).
3. The clicked tag is highlighted/selected in the sidebar tree.
4. A visual indicator shows the active tag filter (e.g., the tag pill gets a solid border or the context header updates to "Tag: billing").
5. Clicking the same tag again, or clearing the search, removes the filter.

This matches JGiven's behavior where clicking a tag in a scenario navigates to the tag view.

## Files Changed

| File | Change |
|------|--------|
| `src/pytest_given/templates/styles.css` | Complete rewrite — new light theme with CSS custom properties |
| `src/pytest_given/templates/report.html.j2` | Update markup for collapsed-by-default cards, clickable tags, inline phase labels, status filter pills |
| `src/pytest_given/renderer.py` | Adjust parameter highlight colors for light backgrounds |

No new files. No new dependencies. No changes to the data model, collector, serializer, or plugin.

## Out of Scope

- Dark mode / theme toggle (can be added later via CSS custom properties).
- Summary dashboard / statistics page.
- Duration display on cards.
- Responsive / mobile layout (report is viewed on desktop).
