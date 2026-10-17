# Listing Report Links — Design Spec

✅ [spec/citations-list](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html#tag=spec/citations-list) (3 ✅)

## Goal

Let `pytest-given citations check` show every report link it holds to the report, not only the
ones with findings, and narrow that list to the links that cite one scenario. An agent that changed
what a scenario does can then find each sentence making a claim about it, through the same link
reading `check` does, instead of a grep that misreads code fences, relative links and tag
membership.

## Background

`check` prints findings and nothing else; a clean run prints one line. That answers "is every
citation current?" but not "what does this document cite?" or "which documents cite this
scenario?". The second question matters most when a test's behavior changes while its title and
status stay: every citation of it still reads ✅, `check` stays silent, and the sentence citing it
may no longer hold.

Reading a document's report links takes `markdown_links.scan_links` (fences, HTML blocks, list
items, table cells, escapes, glyphs) and `_ReportLocation` (which URLs, absolute or relative, name
the report). Whether a tag or story citation counts a scenario takes `CitationIndex`, whose tags
include their prefixes as the report's `#tag=` filter does. All of it is already in `citations/`
and `report/`; this design only exposes it.

## Command line

Two options on `check`; `update` takes neither.

### `--list`

`check --list` prints one line per report link, in document order, documents in the order
`markdown_documents` returns them. A link's findings follow it, indented: the finding's message
without its `path:line:`, its details one level deeper. The summary line and the exit code are the
ones `check` prints and returns without `--list`, which leaves its output unchanged.

```
$ pytest-given citations check --list docs/specs --report self-report-data.json
docs/specs/2026-10-07-citations-design.md:3: ✅ tag spec/citations
docs/specs/2026-10-07-citations-design.md:494: ✅ scenario tests/unit/citations/test_check.py::test_update_rewrites_a_stale_citation
docs/specs/2026-10-07-citations-design.md:495: ✅ scenario tests/unit/citations/test_check.py::test_a_plain_report_link_claims_only_that_its_target_exists
    scenario tests/unit/citations/test_check.py::test_a_plain_report_link_claims_only_that_its_target_exists is not in the report
        closest by node ID: tests/unit/citations/test_check.py::test_a_plain_link_claims_its_target_exists
docs/specs/2026-10-10-parameter-table-case-ids-design.md:3: ✅ tag spec/parameter-table-case-ids
    stale summary
        (1 ✅) → (3 ✅)
docs/specs/2026-10-11-inline-markdown-design.md:3: ✅ tag spec/inline-markdown
citations: 2 findings; `citations update` fixes 1
```

Every unindented line is a link, so `grep -v '^ '` keeps the bare list.

**Which links are listed:** every citation — a typed `?` placeholder and a mistyped citation
included — and every plain report link. A link to the report whose fragment names no scenario, tag
or story and that carries no glyph is not a report link (a glossary term link, say), so it is not
listed, as `check` does not check it.

**What a line says:** `<path>:<line>: <glyph> <kind> <key>`.

- The glyph is the one the document wrote, the Markdown sink's or a typed `?` alike; a plain report
  link shows `link` in its place. Whether it is current is the job of a `stale` finding, not of the
  list: a line states what the document says.
- The kind and key are the target as the document's fragment names it — a slug or a `[case]` node
  ID included, with a `fragment` finding under the line that names its current form. A mistyped
  citation shows its fragment instead: `✅ #view=glossary&term=guest`.

### `--covering NODE_ID`

`--covering` narrows the list to the links that cite a scenario, and implies `--list`: findings are
always counted in full, so without the list it would have nothing to narrow. It may be repeated; a
link is kept when it covers any of the named scenarios.

A link **covers** a scenario when its resolved target is that scenario, or a tag or story whose
summary counts it — a tag through its prefixes too, so `#tag=spec` covers a scenario tagged
`spec/citations`. A link `check` cannot resolve — its target is not in the report, or its citation
is mistyped — is always kept: it may be the scenario under a name it no longer has.

The node ID resolves as a scenario fragment does, so a case's node ID or a slug names its grouped
scenario. One the report does not hold is an error (exit 2) listing the closest node IDs: the
command was asked about something that does not exist, unlike a link whose target is gone.

A link left out takes its findings with it. The summary still counts every finding, and says how
many sit on links `--covering` left out; the exit code still follows all of them, so a run that
lists nothing can still exit 1.

```
$ pytest-given citations check --covering tests/unit/citations/test_check.py::test_update_rewrites_a_stale_citation docs/specs --report self-report-data.json
docs/specs/2026-10-07-citations-design.md:3: ✅ tag spec/citations
docs/specs/2026-10-07-citations-design.md:494: ✅ scenario tests/unit/citations/test_check.py::test_update_rewrites_a_stale_citation
docs/specs/2026-10-07-citations-design.md:495: ✅ scenario tests/unit/citations/test_check.py::test_a_plain_report_link_claims_only_that_its_target_exists
    scenario tests/unit/citations/test_check.py::test_a_plain_report_link_claims_only_that_its_target_exists is not in the report
        closest by node ID: tests/unit/citations/test_check.py::test_a_plain_link_claims_its_target_exists
citations: 2 findings, 1 of them on a link --covering leaves out; `citations update` fixes 1
```

### What `--covering` cannot find

It matches against the node IDs in the current report. A citation still naming a renamed test's
old node ID cannot be attributed to the new one: it is listed as unresolved, beside every other
unresolved link, and `check` reports it as `missing`. Running `citations update` first repoints a
renamed test whose title one scenario still has, so the list shrinks to the links nothing can
place. The documentation and the skills say so plainly: once `check` is clean, `--covering` is
exact; until then it lists what it cannot rule out.

## Implementation touch points

- `citations/check.py` — `_LinkCheck` records each report link as a `ReportLink` (path, line, the
  glyph as written or None, the target as written or the raw fragment, the resolved target or
  None, its own findings, `covered`). A finding belongs to the link object rather than being
  matched to it by `path:line`, since two links can share a line. `CitationsResult` gains `links`;
  `findings` stays the flat list `update` and plain `check` read. `check_citations` takes
  `covering: list[str]` (empty: every link covered), resolves each through `TargetResolver`, raises
  `PytestGivenError` with suggestions for one the report lacks, and sets `covered` from
  `CitationIndex.tags` and `.stories`.
- `cli/citations.py` — `--list` and `--covering` (`action='append'`) on the `check` parser alone;
  `_report_check` prints the list branch and the summary's left-out count.
- `docs/site/cli.md` — the two options in the Citations section.
- `docs/site/guide/citations.md` — under *Keeping the check accurate*: finding the documents that
  cite a changed scenario, and what `--covering` cannot find.
- Skills (canonical copy, then `pytest-given skills install`):
  - `pytest-given-citing` — `check --list` shows every report link, `--covering` narrows it to one
    scenario.
  - `pytest-given-reviewing` and `pytest-given-authoring` — where a scenario's behavior changed:
    run `citations update`, then `citations check --covering <node ID>`, and reread each sentence
    listed, the unresolved ones included.
- `CHANGELOG.md` — under Added: `citations check --list` prints every report link with its
  findings, and `--covering` narrows the list to the links that cite a scenario.

## Test coverage

- `tests/unit/citations/test_check.py` — `CitationsResult.links`: a link per citation and per
  plain report link, none for a link elsewhere or a plain link naming no target; each finding on
  its own link, two links on one table row included; `covered` for a direct citation, a tag, a
  prefix tag, a story, a case node ID and a slug passed as `covering`, an unresolved target and a
  mistyped citation; an unknown `covering` node ID raises with suggestions.
- `tests/integration/test_cli_citations.py` — the `--list` line shape and exit codes; output
  without `--list` unchanged; `--covering` implying `--list`; a repeated `--covering` keeping the
  union; the summary's left-out count; an unknown node ID exiting 2.
- Self-report scenarios tagged `spec/citations-list`, one per rule:
  - `check --list` prints every report link, its findings under it.
  - `--covering` keeps the links whose target counts the scenario, and every link it cannot rule
    out.
  - The summary and the exit code count the findings on links `--covering` leaves out.

## Out of scope

- `--list` and `--covering` on `update`, whose output is what it rewrote and what remains.
- Narrowing by a tag or story (`--covering spec/x`): a document's tag citations are found by
  reading its list.
- A JSON output: the line format is stable and parseable.
- Attributing a citation of a renamed test's old node ID to its new one; the acceptance-criteria
  extension in the [citations design](2026-10-07-citations-design.md) binds scenarios to a spec
  by name and would make the lookup exact.
