# Delta Report — Design Spec

## Goal

Show what changed in a suite's scenarios between two commits, typically two releases, as a report
of its own: a JSON file and an HTML page that look and work like the normal report but hold only
the added, removed and changed scenarios and glossary terms. A changed scenario shows what changed
inside it, down to the word.

## Intent

The normal report answers "what does the system do now?". Developers and stakeholders reviewing a
release ask a different question: "what did this release change about what the system does?".
Today the only answer is reading two reports side by side, or a code diff that buries a reworded
rule among refactors. The delta report answers it in the vocabulary the scenarios already use.

Its readers are anyone who reads the normal report: developers checking a release, and
stakeholders who want the behavioral changes without reading code.

## Goals, non-goals, anti-goals

**Goals**

- `pytest-given delta BEFORE.json AFTER.json` builds a delta from two ordinary JSON reports and
  writes a delta JSON and/or a delta HTML page.
- Scenarios are listed as added, removed or changed. A changed scenario shows what changed in its
  title, steps, tags, status and parameter table.
- The glossary gets the same treatment: added, removed and changed terms.
- Grouped parametrized scenarios are fully supported, including added and removed cases, columns
  and cell values. Per-case scenarios pair case by case (see [Scenario identity](#scenario-identity)).
- A committed rename log pairs an old scenario, case or term with its new identity when automatic
  matching can't, so a renamed or moved test reads as changed rather than as removed plus added.
- A bundled agent skill teaches the loop of building a delta, finding renames with `git` between the
  two reports' commit SHAs, and recording them in the rename log.

**Non-goals**

- Stories. Story changes are left out of this version. A story edit can still, rarely, change a
  term's kind, since kind inference reads story slots (see [Terms](#terms)).
- Turning `group_parametrized` on or off. A scenario that does it between the two reports reads as
  removed and added, since a grouped scenario's identity is its `node_base` and a per-case
  scenario's is its full node ID.
- A CI gate. The delta never fails a run because something changed. Releases keep one instead (see
  [pytest-given's own release deltas](#pytest-givens-own-release-deltas)).
- A Markdown delta. It would suit release notes and pull request descriptions, and can follow later
  from the same delta JSON.
- Splits and merges. A rename log entry pairs one old identity with one new one. A scenario split in
  two shows as one removed and two added.
- Reading reports of another schema. The delta reads two reports of its own `schema_version` only
  (see [Inputs](#inputs)). No readers or migrations for other shapes, as for `pytest-given report`.
- Attachments. Their changes don't make a scenario changed, and the delta doesn't diff them. Each
  scenario and step shows its attachments from the side it is shown from (see
  [Which side is shown](#which-side-is-shown)), unmarked. Attachment content is often a dumped
  object whose timestamps and generated IDs differ on every run.
- Renaming a parameter column by hand. A renamed parametrize argname is paired automatically when
  its values didn't change (see [Cases and columns](#cases-and-columns)), and otherwise reads as one
  column removed and one added.

**Anti-goals**

- A delta HTML page that looks like a different tool. It reuses the normal report's layout,
  typography, tokens and interactions. Readers who know one know the other.
- Colour that means two things. In the delta HTML, green, red and amber mean added, removed and
  changed, and nothing else, so the normal report's status colours, *parameter coloring* and term
  kind colours step back (see [Colour](#colour)).
- Hand-written knowledge kept in a generated file. Renames live in the rename log, never in the
  delta JSON, which is generated output even when a project keeps it.

## Inputs

Two JSON reports, *before* and *after*, as `--given-json` writes them. Each carries
`metadata.commit_sha`, which the delta shows in its header and which the skill uses for
`git diff BEFORE_SHA..AFTER_SHA`. A report without a SHA still works. The delta then shows the
report's timestamp in place of the SHA, and the skill tells the agent that `git` can't help.

Both reports should come from full runs of the same suite (as `citations` requires). A scenario
missing from a partial run reads as removed.

Both should also come from the same pytest-given and pytest versions. A newer pytest-given can
narrate the same test differently, and a newer pytest can generate different case IDs for the same
values (pytest 9.2 hashes a long value into its ID). The delta can't tell either from a change to
the suite. When the two reports' `plugin_version` or `pytest_version` differ, the delta warns and
names both.

**Schema version.** The report JSON gains `metadata.schema_version`, an integer starting at `1`.
It is bumped by every change to the JSON's shape, in the same commit, with the CHANGELOG entry that
change already needs. An added optional field bumps it too: an older report would read the field's
default, and the delta would list every scenario whose newer side sets it as changed. A test
fingerprints the report schema's dataclasses, so a shape change without a bump fails.

The delta needs both reports at its own schema version, and otherwise exits 2 naming both versions
and pointing at the skill. An integer rather than semver, because the only question is "same shape
or not": the project supports no older shape, so a minor version would promise compatibility
nothing keeps. Reports from before `schema_version` existed have none, and are refused the same way.
Only computing a delta checks the version. `pytest-given report` and `citations` read a report as
they do today, and re-rendering a delta JSON reads it the same way.

So a *before* report written by an older pytest-given works as long as the schema hasn't changed
since. When it has, the skill regenerates it: check out the *before* commit in a git worktree and
run its suite under the current pytest-given.

**Exit status.** `pytest-given delta` exits 0 whether or not anything changed. It exits 2, as
`citations` does on an error, when it can't build or render the delta: a usage error, an input it
can't read, a report where a delta JSON is expected or the reverse, a schema version mismatch, a
`--renames` file that doesn't exist, or a malformed rename log. A working directory without
`given-renames.toml` is no error, since a project that renamed nothing has none.

Every subcommand follows one rule: 0 when it did its job with nothing to report, 1 when it found
something to act on (a citation finding, skills that drifted from the installed copy), and 2 when it
couldn't do its job. `pytest-given report` and `pytest-given skills` move to it, since both exit 1
on an error today. The delta reports nothing to act on, so it never exits 1.

**Outputs.** `--json` and `--html` default to `given-report/delta-data.json` and
`given-report/delta.html`, beside the normal report's defaults in `given-report/`. With neither
flag, two inputs write both, and one input writes the HTML. The rename log stays in the working
directory itself, since it is committed source and `given-report/` is disposable output.

## Matching

### Scenario identity

A scenario's *identity* is its node ID without the parametrize tail (`node_base`). A grouped
scenario's stored `id` is its first case's node ID, so its identity survives a case being added,
removed or reordered.

A *per-case scenario*, one case of a scenario with `group_parametrized` off, has a parametrize tail
but no parameter table. Its identity is its full node ID instead, even as its function's only case,
so a second case doesn't change the first one's identity. Having no parameter table, per-case
scenarios never pair by values. An argname added to one renames every case, and reads as every case
removed and added unless rename log entries map them.

### Pairing

Each scenario of *before* pairs with at most one scenario of *after*, in two steps, the second
working only on what the first left unpaired:

1. **Same identity**, after the rename log has rewritten the *before* side's identities (see
   [Applying the rename log](#applying-the-rename-log)).
2. **Same scenario title**, when exactly one unpaired scenario on each side has it. This covers a
   moved file. Titles compare as narration does (see [What counts as a change](#what-counts-as-a-change)),
   with their term refs rewritten, except that a placeholder compares by its name, since columns
   pair only once their scenarios have.

What's left unpaired on the *before* side is removed, and on the *after* side added. Every pairing
records how it was made: `rename-log` when the rename log rewrote the identity, otherwise
`node-id` or `title`.

Pairing on the rewritten identity keeps a reused ID honest. When `A` was renamed to `B` and a new
test later took the name `A`, the old `A` pairs with `B`, and the new `A` reads as added.

### Applying the rename log

From each *before* identity, the delta follows the chain of entries in file order (`A → B`, then a
later `B → C`), leaving out entries whose `rev` predates the range. It stops at the last identity
along the chain that exists in *after*, and rewrites the *before* identity to it. Comparing v1 to v3
rewrites `A` to `C`, and comparing v1 to v2 rewrites `A` to `B`.

Case IDs follow the same rule inside the paired scenario. From each *before* case ID, the delta
follows the `cases` maps of the entries up to the identity's stop, and stops at the last case ID
along that chain that exists in the paired *after* scenario. So a `cases` map from a later release,
whose entry keeps the identity, leaves an earlier range alone.

- A chain that reaches nothing in *after* past its start rewrites nothing, and is skipped silently,
  so one log serves every comparison range.
- A chain only moves forward through the file, so a rename and its reversal (`A → B`, later
  `B → A`) end. A swap therefore goes through a name neither test has: `A → tmp`, `B → A`,
  `tmp → B`. Written as `A → B` then `B → A`, both chains end at `A`, which is a merge.
- For per-case scenarios, an entry rewrites the `node_base` they share, and its `cases` map
  rewrites their tails. A `node_base` exists in *after* when any scenario there has it.
- When two *before* identities would end at the same one, whether both are rewritten or one already
  has it (a merge, which the log doesn't model), no *before* identity is rewritten to it, and the
  delta warns naming the entries involved.

### Cases and columns

Inside a paired parametrized scenario, columns pair first, then cases, then the columns that are
still unpaired:

1. **Columns by name and kind.** A column's name is its header: a `param` column's argname, a
   `derived` column's expression or placeholder name. Its ID never pairs it, since a `derived`
   column's generated ID (`derived:0`) shifts when another derived column comes or goes.
   `attachment` columns take no part (see [What counts as a change](#what-counts-as-a-change)).
2. **Cases by custom case ID**, and by a case ID the rename log's `cases` maps rewrote.
3. **Cases by values.** Two unpaired cases pair when each is the only unpaired case on its side
   with those values in the `param` columns both tables share. This keeps a table paired case by
   case when an added column changed every generated case ID (`1-False` to `1-small-False`), and
   when an inserted case shifted the positional IDs pytest generates for objects (`order0`,
   `order1`).
4. **Cases by generated case ID**, for what is still unpaired: cases whose values repeat, or a
   positional ID whose object changed.
5. **Renamed columns.** When exactly one unpaired column of a kind on each side has cells that
   agree in every paired case, the two pair as one renamed column.

Values compare as cells do (see [What counts as a change](#what-counts-as-a-change)). Order takes
no part: columns or cases that only moved leave a table unchanged.

A case whose value changed under a generated case ID (`2-True` to `3-True`) reads as one removed and
one added unless an entry maps it. A scenario that gains or loses grouped parametrization keeps its
identity and pairs as changed, its parameter table shown as added or removed.

A pairing records how it was made: `rename-log`, `case-id` or `values` for a case, `name` or
`values` for a column.

### Terms

Glossary terms pair the same way, and before scenarios do. The rename log's `[[term]]` entries
rewrite the *before* term IDs, with chains, `rev` and the stop rule as for scenarios. Terms then
pair by term ID, unless their kinds differ. A term whose kind changed, which is rare, reads as
removed under its old kind and added under its new one. The term refs in *before* narration are
rewritten with the term IDs, so scenario titles and steps compare with their term refs rewritten,
whatever the kinds. A term pairing records `rename-log` or `term-id`.

A file glossary derives a term's ID from its canonical name, so a renamed term never pairs without
an entry. Suggestions are what surface it.

### Suggestions

A *suggested match* is a removed and an added item that look like one renamed item:

- a removed scenario and an added scenario whose steps are nearly the same
- a removed case and an added case of one paired scenario that differ in one `param` value
- a removed term and an added term whose term refs take each other's place in a modified step of a
  paired scenario
- a removed term and an added term of the same kind whose definitions are nearly the same

A suggestion is never applied. The delta JSON records it so an agent or a person can confirm it
into the rename log. The similarity measures and thresholds are the builder's to choose (see
[Left to the builder](#left-to-the-builder)).

## The rename log

`given-renames.toml` in the working directory, or the file `--renames PATH` names. It is
authored, committed, and reviewed like any other source file. It grows over the project's life,
like `.git-blame-ignore-revs`. The delta reads the log of the checkout it runs in, so it runs in the
current checkout, never in a worktree of an older commit.

```toml
# Identity changes pytest-given can't detect by itself.
# Read by `pytest-given delta`. Entries apply in file order, so chains work.

[[scenario]]
old = "examples/hotel-booking/test_hotel_booking.py::test_declined_payment"
new = "examples/hotel-booking/test_payments.py::test_declined_payment_holds_booking"
rev = "v0.6.0"

[[scenario]]  # renamed, and one case's generated ID changed with its value
old = "examples/coffeeshop/test_coffeeshop.py::test_pricing"
new = "examples/coffeeshop/test_coffeeshop.py::test_price_list"
cases = { "1.5-True" = "2.0-True" }
rev = "v0.6.0"

[[scenario]]  # only cases changed: `new` left out means the identity stayed
old = "examples/coffeeshop/test_coffeeshop.py::test_price_list"
cases = { "happy-hour" = "happy-hour-weekdays" }
rev = "v0.7.0"

[[term]]
old = "room"
new = "suite"
rev = "v0.6.0"
```

- `[[scenario]]` holds a scenario's identity (see [Scenario identity](#scenario-identity)). For
  per-case scenarios, it holds the `node_base` they share.
- `new` is optional when `cases` is given. One entry records one rename of a scenario together with
  its cases, so a scenario and its cases renamed in the same commit are one entry, and no ordering
  between separate entries can disagree.
- `cases` maps old *case IDs* to new ones, relative to the entry. A case it doesn't name keeps its
  case ID under the new identity.
- `[[term]]` holds term IDs.
- `rev`, optional, is any git revision (a tag or a SHA) at which the rename had already happened.
  An entry whose `rev` is an ancestor of, or equal to, the *before* report's commit is skipped: the
  rename predates the range, so a later test that reuses the old ID isn't paired by mistake. The
  check runs `git merge-base --is-ancestor <rev> <before SHA>` once per distinct `rev`, before
  chains are followed. When the answer is unknown, the entry applies as if it had no `rev`, and the
  delta warns: once for each `rev` that doesn't resolve, naming it, and once in all when no ancestry
  answer is possible. That happens without git, without a *before* SHA, in a shallow clone, or when
  git can't resolve the *before* SHA (see [The `git/` package](#the-git-package)).
- There is no upper-bound check. `rev` only bounds the rename from above (it happened at or before
  `rev`), so a `rev` that isn't an ancestor of *after* proves nothing: the rename may still lie
  inside the range. An entry from the future is harmless anyway, since its old identity and old
  case IDs still exist in *after*, and both chains stop at their start.
- The skill writes the tightest lasting `rev` it can find: the earliest release tag containing the
  commit that made the rename (`git tag --contains`), otherwise that commit's SHA when it is on the
  default branch. When it can't find that commit, the *after* report's release tag or
  default-branch SHA is a looser bound that still holds. The tighter the `rev`, the fewer ranges
  consider the entry. A pull request run's SHA is never written. A branch commit vanishes in a
  squash merge, and on GitHub a pull request run's `GITHUB_SHA` names a temporary merge commit that
  no later clone resolves. An entry written by hand in the pull request that does the rename may
  leave `rev` out too.
- `rev` also makes the log prunable: an entry whose `rev` is older than the oldest *before* the
  project still compares against can never apply again and may be deleted. Pruning is manual.
- A malformed file exits 2 naming the entry. Malformed means bad TOML, an entry missing `old`, an
  entry with neither `new` nor `cases`, an `old` or `new` with a parametrize tail (a case is renamed
  through `cases`), a `rev` that starts with `-`, or an unknown key or table. A well-formed entry
  that doesn't apply is not an error.

## What counts as a change

A paired scenario is *changed* when any of these differ, and *unchanged* otherwise:

- its scenario title
- its steps: phase, narration and nesting, compared after grouping
- its tags
- its status, or its skip or xfail reason
- its parameter table, after pairing: its columns and their names, its cases, cell values and case
  statuses, and a case's ID when either side's is custom

A generated case ID is made from its case's values, so the cells and columns already tell its
change, and it doesn't count by itself. The case ID that ends a per-case scenario's title compares
the same way. Cell values compare by type as well as value, so `1`, `1.0` and `True` all differ, as
they do in the JSON.

Narration compares as it reads:

- Its literal text, and its values as rendered. A value's source expression doesn't count.
- Its placeholders by the column they point at, after column pairing. A placeholder's column ID
  and format spec don't count. The format shows in its column's cells, which compare as rendered.
- Its term refs by term, after the rename log, and by form (bare, `.l`, `.s`, an instance or an
  inflection, with the instance's or inflection's own text).

So a display that changed only because its term's canonical name changed doesn't count. A renamed
term shows on the Glossary tab, not in every scenario that mentions it.

Nothing else makes a scenario changed: its node ID, module, source location, duration, error
message and traceback, fixture names, story membership, pins and attachments. That includes the
`attachment` columns of a parameter table, which are left out of the table comparison.

Values that differ on every run, such as a rendered timestamp or an object's default `str()` with
its memory address, read as changed in every delta, as they differ between any two normal reports.
The skill has the agent fix them at their source.

A paired term is *changed* when its canonical name or definition differs (a changed kind unpairs it,
see [Terms](#terms)). Derived facts, such as its other forms and how many scenarios refer to it, are
shown for a listed term but never make one changed on their own.

## The delta JSON

The delta JSON holds enough to render either an inline or a side-by-side view of every change. It
stores both full versions of each listed scenario and term, plus the computed alignment between
them, so a renderer only has to lay them out. Its exact field names are the builder's. Its shape:

```jsonc
{
  "metadata": {
    "kind": "delta",
    "schema_version": 1,
    "before": { /* the before report's metadata, commit_sha included, plus its label */ },
    "after": { /* the after report's metadata, plus its label */ },
    "plugin_version": "…",
    "timestamp": "…"
  },
  "scenarios": [
    {
      "change": "changed",            // "added" | "removed" | "changed"
      "paired_by": "rename-log",      // absent for added and removed
      "before": { /* Scenario, as in a report */ },
      "after": { /* Scenario */ },
      "steps": [ /* alignment: equal | modified | added | removed, per step,
                    recursing into children; a modified step carries a
                    word-level diff of its narration */ ],
      "parameters": { /* column alignment and case alignment, each with its
                        paired_by, and per-cell before/after values */ }
    }
  ],
  "unchanged": ["…identity pairs…"],
  "suggestions": [
    { "of": "scenario", "before": "…identity…", "after": "…identity…" },
    { "of": "case", "scenario": "…identity pair…", "before": "…case ID…", "after": "…case ID…" }
  ],
  "glossary": {
    "before": { /* Glossary */ },
    "after": { /* Glossary */ },
    "terms": [ { "change": "changed", "paired_by": "term-id", "before": { }, "after": { } } ],
    "unchanged": ["…term ID pairs…"]
  }
}
```

- Each side is stored as its report wrote it: node IDs, case IDs and term refs unrewritten, each
  resolved against its own side's glossary. The rename log shows only in the pairings and
  alignments.
- Both glossaries are carried whole, so every term ref in either version of a scenario renders with
  its underline and tooltip.
- Derived term facts the HTML shows (other forms, reference counts on each side) are stored, since
  a delta JSON doesn't hold every scenario they're computed from. They are computed from the full
  reports, the same way the normal report computes them.
- Each side's module names are stored, for the same reason, so Browse by can tell an added or
  removed module from a changed one.
- A word-level diff of a narration keeps term refs, placeholders and inline Markdown spans
  (emphasis, code spans, links) whole: a change inside one marks the whole of it. A term ref that
  compares equal is unchanged, even when its display changed with its term's canonical name, and
  shows its *after* display.
- Both `unchanged` lists hold the pairs that matched with no change, so the counts can be checked
  and a consumer can tell "unchanged" from "absent".
- `metadata.schema_version` counts the delta's own shape, separately from the report's, whose
  version stays in the `before` and `after` metadata. The fingerprint test covers the delta's
  dataclasses too. Re-rendering a delta JSON checks neither version, and reads it as
  `pytest-given report` reads a report. The check guards computing a delta, where a defaulted field
  would read as a change. Rendering one computes nothing.
- The delta JSON is the source of truth for the delta HTML, as the report JSON is for the report
  HTML. `pytest-given delta DELTA.json`, with one input, re-renders the HTML from a delta JSON
  without the two reports. `metadata.kind` is what tells a delta JSON from a report, which has
  none. `pytest-given report` and `citations` refuse a delta JSON by it, with an error that points
  at `pytest-given delta`.

## The delta HTML

The normal report's page, with the differences below.

### Which side is shown

A listed scenario or term is shown from its *after* side, or from its *before* side when it was
removed. That side supplies its module and terms for Browse by, its status for the Status filter,
its source link, its attachments and its error, which shows as in the normal report. Search matches
the text of both sides.

### Header

The *after* report's title (its project's name without one), then two tabs, Scenarios and Glossary.
There is no Stories tab, and the Glossary tab appears only when a term is listed. The header's right
side shows the range in place of the run's pytest and plugin versions:
`v0.5.0 a1b2c3d to v0.6.0 e4f5a6b`. Each side shows a version label and the short SHA. The label is
the git tag pointing at that SHA (the highest by version order when several do), or a `--before-label` /
`--after-label` the caller passes. Without either, the side shows only its SHA, since
`metadata.plugin_version` is pytest-given's version, not the project's.

### Scenarios tab

```
┌ sidebar ───────────┐ ┌ 4 changes   1 added, 2 changed, 1 removed ──────────────────────────┐
│ Search             │ │▌› A booking can be cancelled only before…  changed  tag +tag  ✓ passed │
│ Change             │ │▌› A declined payment keeps the booking…    changed  mapped by hand    │
│ [+Added 1]         │ │    was A declined payment leaves the booking pending   ✗ failed → ✓ passed │
│ [~Changed 2]       │ │▌› A group booking splits the bill per guest  added            ✓ passed │
│ [−Removed 1]       │ │▌› R̶e̶b̶o̶o̶k̶i̶n̶g̶ ̶r̶e̶s̶t̶o̶r̶e̶s̶…                     removed  was ⊗ expected failure │
│ 3 unchanged        │ └──────────────────────────────────────────────────────────────────────┘
│ Status · Browse by │
└────────────────────┘
```

- **Sidebar.** Search and Browse by work as in the normal report. A new *Change* filter (Added,
  Changed, Removed, each with its count) sits above the Status filter. Under it, a muted line gives
  the number of unchanged scenarios.
- **Modules.** Under Browse by, only the modules of listed scenarios appear, each with a change
  glyph and colour: added when only *after* has it, removed when only *before* has it, and changed
  when both have it. A test file that only moved, its scenarios unchanged, doesn't appear.
- **List.** Only listed scenarios appear, each led by a coloured bar for its kind of change, where the
  normal report's bar shows status. A small label repeats the change in words (`added`, `changed`,
  `removed`) for readers who don't rely on colour. With nothing listed, the tab says there are no
  changes.
- **Title.** A renamed title shows the new title, with `was <old title>` struck through beneath it.
  A removed scenario's title is struck through.
- **Rename log pairing.** A scenario paired by the rename log carries a small `mapped by hand`
  badge.
- **Tags.** All of a scenario's tags are shown. An added tag is marked `+` in green, and a removed
  one is struck through in red.
- **Status.** Shown by its glyph and word in muted ink, never in its status colour. A changed status
  shows both: `✗ failed → ✓ passed`. A removed scenario shows `was <status>`. A changed skip or
  xfail reason shows where the normal report shows it, with `was <old reason>` struck through
  beneath it.
- **Source link.** A listed scenario's source link fills the template with the SHA of the side it
  is shown from. A template without `{sha}`, such as an editor's, resolves against the current
  checkout, so a removed scenario's link works only once its commit is checked out.
- **Fragments.** Every listed scenario has its own URL fragment and element ID, even when a removed
  scenario's *before* node ID equals an added scenario's *after* node ID.
- **No citation copy menu.** Citations point into the normal report, not into a delta.

### A changed scenario's steps: inline

The scenario reads as it does in the normal report, with its changes marked in place:

```
      Given  our guest Alice
  ~   When   Alice checks in to the [-Deluxe Suite-][+Garden Suite+]
  −   Then   t̶h̶e̶ ̶l̶a̶t̶e̶r̶ ̶b̶o̶o̶k̶i̶n̶g̶ ̶i̶s̶ ̶c̶a̶n̶c̶e̶l̶l̶e̶d̶
  +   Then   the later Booking is cancelled and refunded in full
      When   she tries to cancel the stay she has checked in to
```

- A modified step gets an amber tint and a `~` in the margin. Its removed words are struck through on
  red, and its added words follow on green. A changed phase shows the old one struck through before
  the new one.
- A removed step gets a red tint, `−`, and struck-through text. An added step gets a green tint and
  `+`.
- Unchanged steps are plain. Term refs keep their underlines throughout.
- Added and removed scenarios expand to their steps without marks: the row's colour already says it
  all.

A side-by-side view of steps was considered and rejected for this version: steps are prose, and
reading the new scenario as one story with its edits marked suits stakeholders better. The delta
JSON keeps a side-by-side step view possible.

### A changed parameter table: side by side

Unlike steps, a parameter table is shown side by side, because added and removed columns break a
merged table:

```
 Before: v0.5.0 a1b2c3d                       After: v0.6.0 e4f5a6b
 case ID       euros expect status            case ID       euros +size expect status
 a-euro-short  1     False  ✓                 a-euro-short  1     small False  ✓
 −3̶-̶T̶r̶u̶e̶        3     True   ✓                 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
 ~happy-hour   [1.5] True   [⊗]               ~happy-hour   [2.0] small True   [✓]
 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░               +large-cup    4     large True   ✓
```

- Two complete tables, each captioned with its side's label and short SHA, with a gap between them.
- Rows line up by case, in the *after* table's case order, a removed case placed after the case that
  preceded it on the *before* side. A hatched row marks a case missing on that side.
- Both tables always show the case ID column and the status column, whether or not any case ID is
  custom or the statuses are mixed.
- A removed case's row is tinted red and led by `−`, its case ID struck through. An added case's
  row is tinted green and led by `+`. A changed case's row is led by `~`.
- A changed cell is tinted on both sides, red before and green after, so the old and new values face
  each other. A changed custom case ID and a changed case status are changed cells, a status glyph
  in muted ink like any status. Generated case IDs that differ stay unmarked (see
  [What counts as a change](#what-counts-as-a-change)).
- Each table opens its own failed cases' errors, as in the normal report.
- An added column's header is marked `+` and its cells tinted green. A removed column's header is
  struck through on the *before* side. A renamed column shows its new name, with `was <old name>`
  beneath it.
- `attachment` columns appear in each side's table, unmarked.
- Hovering a placeholder in a step highlights its column in both tables. Hovering an *after* row
  previews its values in the steps, as in the normal report. A *before* row previews nothing, since
  the steps read from the *after* side.
- A table that only changed in case statuses still renders both sides. A table that didn't change
  at all renders once, as in the normal report. A table that was added or removed with its
  scenario's parametrization renders once, under its side's caption, tinted as added or removed.

### Glossary tab

The same structure as the normal Glossary tab, grouped by kind under the kinds' headings (muted,
see [Colour](#colour)), listing only added, changed and removed terms:

- The left bar shows the kind of change, as on the Scenarios tab. The term's kind comes from the
  section it sits in.
- The sidebar gets the same *Change* filter and unchanged count. Show kinds and the definitions
  filter stay.
- A changed definition shows a word-level diff. A renamed term shows `was <old name>` and, when the
  rename log paired it, `mapped by hand`.
- Other forms are shown, with added ones marked `+` and removed ones struck through. Changed
  scenario counts show as `5 → 7 scenarios`. Neither makes a term changed by itself. Story counts
  are left out with stories.
- A term card links only the listed scenarios that refer to it. The unchanged ones it counts but
  doesn't link, since they aren't on the page.
- A term whose kind changed is listed twice: removed under its old kind, added under its new one.

### Colour

New theme tokens, in light and dark variants like every colour in the report:
`--added-ink/tint/line`, `--removed-ink/tint/line`, `--changed-ink/tint/line`, plus stronger tints
for word-level marks. Added is green, removed red, changed amber.

To keep those meanings unambiguous:

- Status colours don't appear. A status, changed or not, is its glyph and word in muted ink, and the
  left bar no longer encodes it. That includes the tint on failed and xfailed table rows. The suites
  a delta compares normally pass throughout, so a scenario's change matters more than its status.
- *Parameter coloring* is off. Placeholders and column headers render in plain bold, as a *value
  highlight* does. Values in cells are plain text.
- Term kind colours are muted. Term ref underlines and the glossary's section headings take the
  kindless grey, since an actor's orange sits near amber and a Work Object's teal near green. A
  term's kind still reads from its section heading on the Glossary tab.

Most changes are also marked without colour, by a `+` / `−` / `~` glyph, strike-through or a text
label. Added words and changed cells are marked by their tint alone. That is accepted: a reader who
can't tell red from green still sees the tint, and strike-through or the table's side says which
way the change went. Media that drop background colours, such as print or a high-contrast mode,
lose those two marks.

## The agent skill

A new bundled skill, `pytest-given-delta`, installed by `pytest-given skills install` with the
others. Unlike the other skills' names, its name isn't a gerund. That is accepted: it takes the
feature's name. It covers:

- Picking the range. A project that keeps its deltas starts each one where the last kept one ended,
  at its *after* SHA, and keeps a delta only when it lists a change. So a patch release that
  changed no scenario adds none, and the next delta starts at the same commit. Without a kept
  delta, the range starts at the previous release tag.
- Building a delta: getting the two JSON reports (from CI artifacts, or by checking out each commit
  in a git worktree and running its suite with `--given-json`), then running `pytest-given delta`
  from the current checkout, so it reads the current rename log.
- Running a suite in a worktree with the CI commit variables (`GITHUB_SHA`, `CI_COMMIT_SHA`,
  `BUILDKITE_COMMIT`) unset. `detect_commit_sha` reads them before `git rev-parse HEAD`, so a
  report built in a worktree inside CI would otherwise carry the current commit's SHA. The worktree
  directory takes the project's name, since a report's `project` is its rootdir's name.
- Keeping both reports on one pytest-given and one pytest version. A schema-version refusal or a
  version warning means regenerating the older report in its worktree under the current versions, in
  place of the versions its lockfile pins. When the older suite can't run under the current
  pytest-given, because the public API changed in between, no delta spans that change, and the skill
  says so rather than comparing reports of two versions.
- Triage: every suggested match, every removed scenario with an added one in the same module, and
  every removed term with an added one of the same kind is a rename candidate. Resolving one means
  reading `git diff --find-renames BEFORE_SHA..AFTER_SHA` and `git log --follow` on the test file,
  then adding a `[[scenario]]` or `[[term]]` entry for a confirmed rename and leaving a genuine
  removal alone.
- The same for cases: a suggested case match, or a removed and an added case whose generated case
  IDs differ, becomes a `cases` entry once confirmed.
- Writing `rev` as [the rename log](#the-rename-log) describes.
- Re-running the delta until each remaining removed/added pair is genuine.
- Fixing a value that differs on every run at its source, such as with a fixed clock or a stable
  `__str__`, when a step or cell reads as changed in every delta.

It shares the repair technique of the citing skill's [repair guide](../../../src/pytest_given/.agents/skills/pytest-given-citing/references/repair.md)
for renamed tests. The builder decides whether to share a reference file or restate it.

## Architecture

- **`model/`** gains the delta schema and its serde, so `report/` can render a delta without
  importing the code that computes it. `Metadata` gains `schema_version`, which the plugin writes.
  It defaults to none, so `pytest-given report` and `citations` keep reading reports that lack it.
  The term rollups `report/` computes today (other forms, reference counts) move to `model/`, since
  `delta/` needs them and may not import `report/`.
- **`delta/`**, a new package on `model/` and `markdown/`, computes a delta: matching, the rename
  log, step and table alignment, word-level diffs, suggestions. It needs `markdown/` for word diffs
  that keep inline Markdown spans whole. It imports no pytest and runs no git, so it is
  unit-testable without a session or a repository.
- **`report/`** renders the delta HTML and writes the delta JSON through the same staged-write path
  as `emit_sinks`, so a failure leaves no half-written file. The delta page reuses the report's
  templates, CSS and `app.js` wherever it can, rather than forking them.
- **`git/`**, a new leaf package like `markdown/`, imports none of the others, and any of them may
  import it. It holds every git call the package makes (see [The `git/` package](#the-git-package)).
- **`cli/`** adds the `delta` subcommand and wires `delta/`, `report/` and `git/` together. It asks
  `git/` for the `rev` ancestry answers and the tag labels, and hands them to `delta/`.

### The `git/` package

`git/` runs the `git` executable through `subprocess`, with no git library. A library would add a
dependency for a handful of calls, and the ones with native bindings don't read all of git's
configuration (worktrees, `safe.directory`). The existing helpers move here from
`report/source_link.py`: `detect_commit_sha` (CI variables, then `git rev-parse HEAD`) and the
GitHub remote detection behind the `github` source-link preset.

The delta adds three queries:

| Query | Command | What is read |
|---|---|---|
| Is `rev` an ancestor of the *before* SHA? | `git merge-base --is-ancestor` | the exit code only |
| Which tags point at a SHA? | `git tag --points-at <sha> --sort=-version:refname` | one ref name per line |
| Does a revision resolve? | `git rev-parse --verify --quiet <rev>^{commit}` | the exit code and one SHA |

Nothing parses prose output, so the locale and the git version's wording don't matter. What keeps
the answers honest:

- An ancestry answer has three values: yes (exit 0), no (exit 1), and unknown (any other exit, no
  `git` executable, a repository `git` refuses to read). Exit 1 and exit 128 must never be
  confused, since reading "unknown" as "no" applies an entry that should have been skipped.
- A shallow clone (`git rev-parse --is-shallow-repository`) answers "unknown" for every ancestry
  query, since a truncated history can't show a rev as an ancestor.
- Before the ancestry queries, `git/` checks that the *before* SHA and each `rev` resolve, so a
  warning can name the revision that doesn't.
- A `rev` that starts with `-` is a malformed entry, so no revision from the rename log can be read
  as an option.
- Every call runs with `-C` on the working directory's repository, the checkout whose rename log
  the delta reads, and never through a shell.

Its tests build a throwaway repository with `git` itself, so they run wherever the suite does.

## pytest-given's own release deltas

From the release after the one that ships the delta report on, every pytest-given release that
changes its self-report keeps a delta of it, as `docs/deltas/<version>.html` and
`docs/deltas/<version>.json`, named after the release it ends at. The release checklist in
`docs/releasing.md` gains the step, beside its `self_report` regeneration. The release's tag doesn't
exist yet at that point, so the step passes `--after-label v<version>`.

- The range follows the skill's rule: it starts where the last kept delta ended, and a delta that
  lists nothing isn't kept.
- pytest-given's suite tests the plugin that narrates it, and its tests import the plugin's
  internals. So the *before* self-report comes from the older pytest-given: the `self_report`
  session run in a worktree of the *before* commit, with that commit's own environment. The version
  warning is expected here, since the plugin's behavior is what the delta compares. That includes
  the commit's own pytest: when the lockfile moved pytest in between, a case whose ID pytest now
  generates differently reads as removed and added. That drift is accepted, since forcing the newer
  pytest on the older plugin could misread its case IDs instead.
- A `schema_version` bump inside the range makes the delta impossible. So the range starts at the
  later of two commits: where the last kept delta ended, and the earliest release whose committed
  self-report has the current `schema_version`. A release that bumps the version keeps no delta,
  and the chain picks up from it. The release that ships the delta report is the first such
  release, since the reports before it carry no `schema_version`.
- Before a delta is kept, the skill's triage adds the rename log entries it needs.
- A kept delta's JSON is written once, since a later pytest-given can't rebuild it from the two
  commits. Its HTML is re-rendered from the JSON by the `self_report` session, so kept deltas follow
  renderer and template changes like every other report. Re-rendering rewrites nothing the JSON
  holds, so an HTML diff means the renderer changed. A JSON that a later shape change leaves
  unreadable keeps its last HTML, and the session names it rather than failing.
- The documentation site publishes every kept delta's HTML, staged into the build the way the
  example reports are. The release's `CHANGELOG.md` section links its delta at the site's `/latest/`
  URL, which works on GitHub, on PyPI and on the site's own changelog page alike.

## Documentation and examples

- A documentation site page for the delta report and the rename log, and a `pytest-given delta`
  entry in the CLI reference.
- `GLOSSARY.md` gains *Delta report*, *Rename log*, *Scenario identity*, *Per-case scenario*,
  *Pairing* and *Suggested match*.
- An example delta under `examples/delta/`, regenerated by the `examples` session. It holds a
  committed *before* and *after* version of one example test file and its glossary, kept out of
  normal collection. The session stages each version into a scratch directory under the same
  relative path, so their node IDs agree, runs both under a fixed `given_title`, and builds the
  delta with fixed labels. Both runs see the same commit, so the example's rename log entries leave
  `rev` out, and the delta renders without source links, since the staged paths don't exist at that
  commit. Its changes cover every surface: an added, removed, reworded and hand-mapped scenario, tag
  and status changes, a parameter table with added and removed cases, columns and values, and
  glossary changes. It serves as the Playwright-verification page and as the site's example delta.
- A delta has no Markdown to read a regeneration's real change from. So `reports_current` also
  compares the example delta JSON without the fields every regeneration rewrites (`metadata`,
  `duration_ms`). It fails on a difference, as a changed `.md` does, and contributors read that
  comparison where they would read a `.md` diff.
- Self-report scenarios for the user-facing rules: identity and pairing order, the rename log's
  chains, stop rule and skipping, case and column pairing, how narration compares, and what counts
  as a change.
- `CHANGELOG.md` entries under *Added*: the delta report, the `pytest-given-delta` skill, and
  `schema_version` in the JSON report's metadata. Under *Changed*, a **Breaking** entry: `pytest-given
  report` and `pytest-given skills` exit 2 on an error, where a script checking for 1 needs to check
  for 2. The CLI reference states the exit rule once for every subcommand.
- `docs/releasing.md` gains the release-delta step and the CHANGELOG link to it (see
  [pytest-given's own release deltas](#pytest-givens-own-release-deltas)). `_build_docs` stages
  `docs/deltas/*.html` into the site.
- AGENTS.md's Conventions gain the rule to bump `schema_version` with every change to the JSON's
  shape, and its Quality gates note that `self_report` also re-renders the kept deltas. Its
  Architecture section gains `delta/` and the `git/` leaf in the package list and the dependency
  diagram.
- The skill's mirror under `.claude/skills/` is regenerated with the others. The navigating skill
  points at the delta skill for "what changed between releases?".

## Left to the builder

- The delta JSON's exact field names, and how alignment is encoded.
- The step alignment algorithm (an LCS over sibling steps by phase and narration, recursing into
  children, is the obvious start) and when an unequal pair counts as *modified* rather than as one
  removed and one added.
- How a term ref's form is told from its display text. Forms can coincide (a lowercase canonical
  name reads the same bare and as `.l`), so a display matching several forms matches any of them.
- The similarity measures and thresholds for suggested matches.
- How URL fragments and element IDs keep a removed and an added scenario of one node ID apart.
- The CLI's flag names beyond `--json`, `--html`, `--renames`, `--source-link`, `--theme` and the two
  label flags. A delta writes both outputs at once, hence `--json` and `--html` where
  `pytest-given report` has one `-o`.
- How the delta page shares templates with the report page.
