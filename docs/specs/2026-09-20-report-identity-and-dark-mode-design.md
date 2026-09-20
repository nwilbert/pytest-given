# Report identity and dark mode — design

**Date:** 2026-09-20
**Status:** implemented 2026-09-20; palette settled on a side-by-side mockup

## Goal

Give the HTML report a visual identity of its own — modern, clean, and at home in
a business context — without changing what it does or how it is used, and add a
dark theme with a viewer-side toggle and a configured default. The docs site
switches to the same typefaces so the two surfaces read as one product.

## Non-goals

- No change to the report's information architecture or behaviour: the three
  views (Scenarios / Stories / Glossary), the sidebar filters, the resizable
  sidebar, hash routing, term tooltips, the parametrize table, the traceback
  block's expand/collapse, and every Alpine behaviour work as they do today.
  Only their appearance changes.
- No new motion. The theme switch does not animate colours.
- No Markdown or JSON output change.
- No dark theme for the docs site beyond what Zensical's `slate` scheme already
  provides; only the fonts change there.

## Design

### Subject and job

A report is read by developers *and* the domain people who wrote the scenarios
with them. Its content is prose — Given/When/Then sentences with the domain's
vocabulary highlighted — plus one hard question: what failed, and why. The
report should read like a typeset document, not an admin dashboard. The
narration is the hero; the chrome stays quiet. Boldness is spent in exactly one
place: the dark theme, where the aubergine brand becomes the environment rather
than an accent.

### Colour tokens

Every colour in `styles.css` becomes a custom property on `:root`, redefined
under `[data-theme="dark"]`. No hex literal survives below the token blocks
(the sweep covers the 37 that do today: term-ref washes and inks, kind
swatches, status pills, error and skip tints, table stripes, shadows). There
is no `@media (prefers-color-scheme)` block: the head script (see *First
paint*) always resolves the theme and sets `data-theme`, so "system" is
decided once in JS rather than twice. The report needs scripting for
everything else already, so a no-script light render is the accepted
fallback.

Values were settled on a side-by-side mockup (light neutrals were pushed from
violet-grey to cool blue-grey so aubergine reads as a signal, not a tint; the
failed tint was leaned toward orange so it does not read as pink).

| Token | Light | Dark |
|---|---|---|
| `--bg-page` | `#f4f6f9` | `#16121b` |
| `--bg-surface` | `#ffffff` | `#1f1a27` |
| `--bg-traceback` (traceback block only) | `#f4f6f9` | `#412c36` |
| `--text-primary` | `#1a1d24` | `#ece8f1` |
| `--text-secondary` | `#58606d` | `#a9a2b5` |
| `--border` | `#e1e5eb` | `#332b3e` |
| `--color-accent` | `#5b2c6f` | `#c9a6dc` |
| `--color-accent-tint` (active state) | `#ece6f1` | `#2f2439` |
| `--color-passed` / tint | `#1a6f43` / `#dcefe4` | `#6fcf97` / `#2c3739` |
| `--color-failed` / tint | `#b3261e` / `#fdeee4` | `#f28b82` / `#412c36` |
| `--color-skipped` / tint | `#9a5300` / `#fbecd5` | `#f0b45c` / `#40332f` |
| actor ink / wash | `#8a4310` / `#fde5d3` | `#f5b47a` / `#47302b` |
| work-object ink / wash | `#0f6e64` / `#d5f2ee` | `#7fded0` / `#21383f` |
| verb ink / wash | `#5f2d9a` / `#ece0f7` | `#cbb5f7` / `#372e4d` |
| kindless ink / wash | `#545962` / `#e9ecf0` | `#b8b2c2` / `#312c38` |

The light accent is the docs site's `--md-primary-fg-color`; the dark accent is
its `slate` counterpart. The accent marks interaction and active state only:
tabs, active filters, links, focus rings, the resize seam, the theme control.
It never fills a surface in the light theme.

Fills stay neutral; meaning lives in the rule and the ink. The traceback block
sits on `--bg-traceback` with the failed colour as its left rule, not as a
fill; its dark value is the failed tint, its light value the page grey. Other
code-like surfaces (attachment panels, inline `code` in definitions) sit on
`--bg-page` in both themes and never take the traceback token. The one
exception to neutral fills is the failed parametrize row, where a fill has to
pick one row out of several, and it takes the failed tint. Tag chips stay
neutral; only the active tag takes `--color-accent-tint`.

Every text/background pair in both themes meets WCAG AA at 4.5:1 (verified
for the table above; the tightest is light secondary-on-page at 5.86). The
existing `--color-accent-text` split is no longer needed: `#5b2c6f` is 9.5:1
on the page. 1px dividers are decorative and exempt from the 3:1 rule.

Term-ref kinds keep their hue identities (actor warm, work object teal, verb
violet, kindless stone). In the dark theme the wash is the kind hue blended
into the surface (the values above are the pre-blended results) and the ink
lightens; the "wash says it is a term, ink says which kind" rule in the
current CSS comment still holds.

### Column colours

`palette.param_column_colors` gains a second CIELAB lightness for dark
surfaces, sharing the hue ring and offset with the light set so column *N* is
the same hue in both themes. It is chosen the way the light one is — as *dark*
as WCAG AA allows on every dark background a value lands on, the failed-row
tint `#412c36` being the tightest — so the hue keeps as much chroma as it can.
The template emits both rule sets, the dark one under `[data-theme="dark"]`.
The AA contrast test in `test_palette.py` gains the dark surfaces (page,
surface, hovered row, failed-row tint) as backgrounds.

### Typography

- **Source Sans 3** — UI and narration. Variable weight, latin subset.
- **Source Code Pro** — tracebacks, file:line anchors, inline code. Variable
  weight, latin subset.

Both upright faces only. The report's one italic — the skip-reason text —
drops the italic and relies on its amber box, so no italic face is embedded
and the browser never synthesises a slant. The two woff2 files
come from the Fontsource variable packages (OFL 1.1) and ship in
`report/templates/fonts/`. `_bundled_assets` reads them beside the CSS and JS
and the template emits each as a `data:font/woff2;base64,…` `@font-face`
source, so the source files stay binary and the report stays self-contained
(~110 KB added per report). The OFL notice for both families is appended to
`THIRD-PARTY-LICENSES`, which the wheel already carries. System fallbacks
follow in each stack.

Scale: 12 / 13 / 14 / 17 / 22 px. Narration steps go from 13 px to 14 px at
1.6 line-height — the one place type gets room. Counts, timings, and line
numbers use `font-variant-numeric: tabular-nums`.

### Layout

Structure is unchanged: topbar, tabs, resizable sidebar, content, three views.
Left-aligned throughout.

```
┌ Hotel Booking Example ─── pytest 9.0.3  pytest-given 0.2.0  Sep 20 09:16  Light|Dark|Sys ┐
│ Scenarios   Stories   Glossary                                                          │
├───────────┬─────────────────────────────────────────────────────────────────────────────┤
│ search    │ 4 scenarios   All scenarios                                   Expand all ⌄ │
│           │ ┌───────────────────────────────────────────────────────────────────────┐ │
│ Status    │ ▌ Carol picks a suite for the group                      ✓ passed   0ms │ │
│ ✓ 3  ✗ 1  │ ├───────────────────────────────────────────────────────────────────────┤ │
│           │ ▌ Payment is declined — the booking is not finalized     ✗ failed  31ms │ │
│ Browse by │ │     Given  our organizer [Carol]                                      │ │
│ Modules   │ │            our guest [Alice]                                          │ │
│ Terms     │ │     When   [Carol] submits the [Payment] by {payment_method}          │ │
│ Tags      │ │     Then   the [Booking System] [declines] the [Payment]              │ │
│           │ ├───────────────────────────────────────────────────────────────────────┤ │
└───────────┴─────────────────────────────────────────────────────────────────────────────┘
```

Changes, each of them a removal of dashboard chrome:

- **One surface per list, not a card per item.** Scenario rows, a story's
  activities, a story's covering scenarios, and the terms within one glossary
  kind group each sit on a single surface separated by 1px rules. The status stripe stays as a row's left edge — it is information. An
  expanded scenario keeps the same surface; its body is set off by indentation,
  not by a nested box. Border radius survives on controls (inputs, chips,
  buttons, the toggle) and on the outer surface only.
- **Given / When / Then in a fixed left gutter**, set in the text ink at
  medium weight; steps align beside the keyword. Structure comes from
  alignment, not from colour, so the accent stays reserved for interaction.
- **Sidebar labels in sentence case**, no letter-spacing: "Status", "Browse
  by", "Show kinds", "Definitions", "Stories".
- **Meta strings separated by space, not `·`**, everywhere the templates
  and `app.js` join counts today (topbar run meta, story and glossary
  subtitles, activity coverage badges): "1 instance  1 story  3 scenarios".
  Each item is its own element with a gap.
- **Theme toggle** in the topbar after the run meta.

### Theme toggle

A three-state control: light, dark, follow system. Its label is text, not an
icon alone, so the current state is readable without hovering: a segmented
control reading "Light | Dark | System". Selecting a state:

- writes `localStorage['pytest-given-theme']` = `light` | `dark` | `system`;
- sets `data-theme` on `<html>` immediately.

All three are stored explicitly, so a viewer's "System" beats a report
configured `dark` — the absent key, not "system", is what means "use the
configured default". Until a viewer has ever chosen, the control highlights
the state the configured default resolves to (`auto` → "System").

"System" follows `prefers-color-scheme` live via a `matchMedia` listener. The
saved choice wins over the report's configured default in every pytest-given
report opened in that browser. Storage access is wrapped in try/catch; when it
throws (privacy modes, `file://` restrictions), the toggle still works for the
page and simply does not persist.

### First paint

The resolution order — saved choice, then configured default, where `auto`
means system — runs
in a ~15-line inline script in `<head>` *before* the `<style>` block, with no
Alpine dependency, so a dark report never flashes light. The script reads the
configured default from `<html data-theme-default="…">`.

## Configuration

- `--given-theme=light|dark|auto` flag and `given_theme` ini (`type='string'`,
  default `auto`), resolved through `_cli_over_ini` like `given_title` and
  `given_source_link`.
- Any other value is a `PytestGivenError` at configure time, surfaced as a
  `UsageError` quoting the spelling the user used (`_setting_spelling`), in
  the same `try` as the source-link resolution. Unlike the source link it is
  validated on every run, not only HTML runs — the check is a set lookup with
  no side effects, and a typo should fail fast.
- The value travels `GivenConfig` → `SinkConfig.theme` → `render_html_string`
  → template, and is emitted as `data-theme-default` on `<html>`.
- Documented as a row in `docs/site/configuration/pytest-options.md`.

## Docs site fonts

`docs/site/assets/fonts/` swaps the four Inter / JetBrains Mono files for the
Source Sans 3 and Source Code Pro latin variable subsets (upright and italic —
the docs do set italic). `extra.css` updates the `@font-face` rules and the
`--md-text-font` / `--md-code-font` tokens; `LICENSES.txt` names the new
families and copyright holders. No other docs change.

## Testing

Python tests cover the data-shaped contract only, per AGENTS.md:

- `tests/integration/test_plugin.py`: `--given-theme=dark` and the
  `given_theme` ini each reach the rendered `data-theme-default`; the flag wins
  over the ini; an unknown value is a usage error naming the spelling used;
  absent means `auto`.
- `tests/unit/report/test_palette.py`: the dark set has one colour per column,
  shares hues with the light set index for index, and clears 4.5:1 on every
  dark background it lands on.
- `tests/unit/report/test_html_renderer.py`: both `.param-color-N` rule sets
  are emitted, the dark one scoped to `[data-theme="dark"]`.

Everything visual is verified in Playwright and captured to the scratchpad,
never asserted in Python: three views × two themes, expanded scenario with a
failure and a parametrize table, the glossary term card, the toggle changing
theme and surviving a reload, "System" tracking a `prefers-color-scheme`
emulation, no flash on load, and `browser_console_messages` clean after init.
`examples/` and the embedded docs copies are regenerated (`uv run nox -s
examples`), with `__pycache__` cleared first.

## Files touched

- `src/pytest_given/plugin/options.py` — option, ini, validation, plumbing
- `src/pytest_given/report/sinks.py` — `theme` on `SinkConfig`
- `src/pytest_given/report/html_renderer.py` — pass theme; dark colour rules
- `src/pytest_given/report/palette.py` — dark lightness
- `src/pytest_given/report/templates/report.html.j2` — head script, toggle,
  label and meta changes
- `src/pytest_given/report/templates/styles.css` — tokens, both themes, fonts,
  layout changes
- `src/pytest_given/report/templates/app.js` — toggle state and listener
- `src/pytest_given/report/templates/fonts/` — two woff2 files
- `THIRD-PARTY-LICENSES` — OFL notice
- `docs/site/configuration/pytest-options.md` — new row
- `docs/site/assets/fonts/`, `docs/site/stylesheets/extra.css` — site fonts
- `CHANGELOG.md`
