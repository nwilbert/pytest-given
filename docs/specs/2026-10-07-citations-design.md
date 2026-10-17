# Citations — Design Spec

✅ [spec/citations](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html#tag=spec/citations) (10 ✅)

## Goal

Let a Markdown document — a design spec first of all — cite a scenario, a tag or a story by a link
that stays true:

1. **Copy buttons** in the HTML report put a one-line Markdown citation on the clipboard: a status
   glyph, a link to the cited thing in the report, and for a tag or story a short summary.
2. **`pytest-given citations check`** verifies every link into the report in a set of Markdown
   files against a JSON report, for CI, and `citations update` rewrites the citations to match it.
3. **A bundled skill** lets an agent repair what `citations update` cannot — a citation whose
   target is gone — and write new citations.

## Background

A spec states what a change must do, and the scenarios that test it are its acceptance criteria.
Today a spec can only name them in prose or paste a source path: nothing tells the reader whether
the behavior is in place yet, and nothing notices when the test is renamed or deleted.

The report already has the pieces. Scenario cards and story headers carry a copy-link button
(`copyAnchor` in `app.js`), the URL fragment addresses a scenario, a tag filter and a story, and the
Markdown sink renders a scenario's glyph and narration. What is missing is a citation format that
survives the cited thing's later life, and a check that holds documents to it.

A spec written test-first is the case this is built around. A spec under `docs/specs/proposed/`
cites the xfail scenarios its implementation will make pass, and the tag they share. Each citation
shows 🔵 until its scenarios pass, and the check flags it stale the moment they do. A spec whose
citations all read ✅ is implemented.

## Citations and report links

```markdown
- ✅ [One xfailed case makes its parametrized scenario an expected failure, with that case's reason](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html#scenario=tests/unit/test_grouping.py::test_one_xfailed_case_makes_the_group_xfailed)
- 🔵 [spec/citations](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html#tag=spec/citations) (5 ✅ · 2 🔵)
```

A **report link** is a Markdown link to a scenario, tag or story in the report (see
[Which links it reads](#which-links-it-reads)). The check verifies that every report link's target
exists.

A **citation** is a report link led by a glyph, where the glyph starts the line's content (after
any list marker or `>`) or follows whitespace or `(` — so a question mark ending a
sentence is never read as one. Between glyph and link the check reads any whitespace, a line break
included, so a citation can sit in a bullet, a table cell or a hard-wrapped sentence. The glyph and
link must stand bare: formatted (`**✅** […](…)`, `✅ *[…](…)*`), they no longer read as a citation
— the glyph turns into frozen text and the link into a plain one. The check owns three parts of a
citation, and nothing else on the line:

- **Glyph** — `CITATION_GLYPH`: `✅` passed, `❌` failed, `🟠` skipped, `🔵` xfailed, after the
  report's status colours; plus `❓` for a citation whose target is not in the report. Markdown has
  no portable way to colour text, so a citation's colour comes from emoji. A trailing variation
  selector (U+FE0F), which some keyboards type after an emoji, is read as part of the glyph. The
  check also reads the Markdown sink's text glyphs (`✓ ✗ ○ ⊗`) and a typed `?`, and
  `citations update` rewrites them as stale, so a hand-typed placeholder works either way.
- **Link text** — what the target is called: a scenario title, a tag, a story's title.
- **Summary** — a parenthesized suffix one space after the link; more spaces, or a hard wrap,
  still read as one. Only text of a summary's shape counts as one — status counts or
  `(no scenarios)` — so a parenthetical of the author's own after a citation stays theirs. A scenario citation has no summary, so one after it is a finding that
  `update` leaves to the author rather than delete text it cannot be sure it wrote. A citation
  takes no `attr_list` block (`{ target=_blank }`), since the summary has to follow the link
  directly.

A report link without a glyph is a *plain* one, the form for a sentence that wants its own wording
("rejecting [divergent cases](…#scenario=…) keeps the tree honest"). The check owns none of its
text.

The check owns a citation's text because the citation *claims* something about its target — its
name and state — that the report can contradict. A plain report link claims only that the target
exists.

### Link text

Link text renders inline. A title's code spans (`` `--given-md` ``) are meant as code, as the
Markdown sink renders them; everything else must render as the literal text. So for every kind:

- Outside code spans, every character CommonMark or GFM gives inline meaning is backslash-escaped:
  `\ [ ] * ~ < & | $`, which would close the link early, emphasize, strike through, open raw HTML
  (`<title>` would vanish), resolve an entity, split a table cell or open GitHub math. `_` is
  escaped too, except between two letters or digits, where it never emphasizes, so `snake_case`
  stays readable. A backtick no other one closes is escaped as well, or it would pair with one
  later on the line and swallow the link.
- Inside a code span nothing is escaped: a code span binds tighter than link brackets, and a
  backslash there would render literally. The one exception is `|` in a table row, which GFM
  lets an escape keep from splitting the cell.
- A newline folds to a space.
- A term ref renders as its plain display text, without the `«»` the Markdown sink wraps it in.

Escaping is not sanitizing: the rendered text stays the title, character for character, which is
what stale detection and repointing by title compare. The check compares link text with escapes
resolved and whitespace folded, so a hand-written citation without escapes, or one whose text a
hard-wrapped paragraph breaks across lines, stays current; `citations update` writes a stale text
escaped and on one line.

A scenario title that interpolates a value differing between runs — a temporary path — would make
its citation stale on every run. Such a scenario is cited by a plain report link.

### Status and summary of a tag or story

A tag or story stands for several scenarios, so its citation sums theirs up:

- **Glyph** — `❌` if any failed, else `🔵` if any is xfailed, else `✅` if any passed, else `🟠` —
  all skipped, or a story no scenario belongs to yet.
- **Summary** — the scenario count per status, each as `<count> <glyph>`, in glyph order
  (`✅ ❌ 🟠 🔵`), zeros left out, joined by ` · `: `(5 ✅ · 2 🔵)`. A story no scenario belongs to
  yet reads `(no scenarios)`.

### The URL

The report's URL (`given_report_url`, see [Configuration](#configuration)) with the target in its
fragment. A fragment value is percent-encoded except for `A–Z a–z 0–9 - . _ ~ / :`, so a typical
node id or tag stays readable, and `URLSearchParams` decodes it to the same string Python's
`urllib.parse.parse_qs` does.

A document on a versioned site links the report relatively (`../examples/self-report.html#tag=…`),
so each version of the page opens its own version's report — an absolute link would pair one
version's glyph with another's report. The copy buttons copy absolute URLs, since they cannot know
where the document sits; shortening the base to a relative path is a one-time edit, and
`citations update` only ever rewrites a URL's fragment.

## Citation kinds

### Scenario

```markdown
✅ [One xfailed case makes its parametrized scenario an expected failure, with that case's reason](…#scenario=tests/unit/test_grouping.py::test_one_xfailed_case_makes_the_group_xfailed)
```

- **Fragment** — `scenario=<node id>`. A grouped scenario is cited as a whole, as the report shows
  it, by the base id without a `[case]` suffix; a case of a `group_parametrized=False` test is a
  scenario of its own and keeps its suffix.
- **Link text** — the scenario title, a grouped scenario's templated one with its placeholders.
- **Glyph** — the scenario's status.
- **Summary** — none.

`#scenario=` accepts a node id as well as a slug. A grouped scenario's `id` is its first case's, so
the report data gains a map from each cited node id to the scenario's `id`; any case's node id opens
the group too, in the page as in the check. The existing copy-link button keeps copying slugs: it
serves a reader passing a link around today, not a document.

#### Why the node id

A scenario citation identifies its target by the node id, with the scenario title as its text, so it
carries two independent anchors and either one alone recovers it exactly: a reworded title leaves
the node id resolving, and a renamed or moved test leaves the link text matching (see
[Findings](#findings-and-what-update-writes)). A node id changes only when its own test is
renamed or moved, is unique by construction, and greps straight to the test. For all but a
per-case scenario it is also the anchor the Markdown sink writes under a scenario's heading with
`given_md_lines` off, and pasted after `pytest` it runs the scenario.

The two other candidates lose that:

- **The slug** (`#scenario=<slug>`, what the copy-link button writes) depends on the whole report:
  `build_scenario_slug_index` resolves collisions across it, so adding an unrelated test can
  lengthen a slug.
- **A slug of the scenario title** would tie the URL to the text, so rewording — the most frequent
  edit — would break both, and recovering would mean matching similar titles, which often state
  opposite behavior ("…is refused" beside "…is grouped").

A node id is relative to pytest's rootdir, so a suite run from another rootdir shifts every
scenario citation at once. A project's rootdir is fixed in practice; the docs page says so.

### Tag

```markdown
🔵 [spec/citations](…#tag=spec/citations) (5 ✅ · 2 🔵)
```

- **Fragment** — a single `tag=<tag>`, the tag filter the report already reads.
- **Link text** — the tag.
- **Scenarios** — the ones the link opens: those carrying the tag or a tag below it (`/` separates
  levels), the prefix rule of the Tags sidebar's `underPrefix`. The sidebar's no-tags bucket is not
  a tag and cannot be cited.

Every scenario that later gets the tag changes the summary, so a tag citation suits a tag that
belongs to one piece of work — a spec's `spec/<slug>`, shaped like the ticket tags the authoring
skill recommends — and settles once that work is done. A broad area tag is better linked by a plain
report link.

### Story

```markdown
🔵 [Cancel a Booking](…#view=stories&story=cancel-a-booking) (3 ✅ · 1 🔵)
```

- **Fragment** — `view=stories&story=<story id>`, what the story header's copy-link button writes.
- **Link text** — the story's title. The story id derives from the title, so renaming the story
  breaks the citation the way renaming a test does.
- **Scenarios** — the ones its Stories-view panel lists.

Sentence coverage stays out of the summary: a covered sentence means a step talks about it, not
that its behavior is tested, so a ratio of covered sentences in a spec would misread as test
completeness.

## Copy buttons

| Kind | Button sits |
|---|---|
| Scenario | on the card, beside its copy-link button — and on the card clones the Stories view borrows |
| Tag | on the tag's row in the Tags sidebar, at every level of the tree `app.js` builds |
| Story | in the story header, beside its copy-link button |

Each is labelled "Copy Markdown citation", with a tooltip adding that `pytest-given citations check`
and `update` keep the citation current. It has an icon of its own, the Markdown mark's "M↓", so it
cannot be mistaken for the link icon beside it; the `frontend-design` skill shapes the icon and the button's place in the
card, header and sidebar row. The tick on success and the `navigator.clipboard` → `execCommand`
fallback are `copyAnchor`'s, through the shared `_copyText`.

The renderer writes each citation's line into the report data, split either side of the report
URL so the data carries the URL once — for tags, one per level of every tag, since the tree is
built client-side — and only in a report that shows the buttons, so the others carry no extra
weight. JS only joins and copies it, so Python stays the one place a citation is rendered, and the
check recomputes exactly what a button copied.

### When the buttons show

Only in a report written with `given_report_url` (see [Configuration](#configuration)), and their
URL is that one. The setting is the toggle:

- **A citation is only worth copying from a report with a public address.** A report a developer
  opens from `file://`, with `vscode` or `pycharm` source links for jumping into their editor, has
  no URL a document could carry. There the buttons would only copy dead links.
- **The URL comes from the setting, not from `window.location`,** because the report a spec is
  drafted against is seldom the hosted one: a spec on a branch cites scenarios the hosted report
  does not have yet, from a report opened locally.

A report without the setting stays as it is today.

## `pytest-given citations check` / `update`

```bash
pytest-given citations check docs/specs/ README.md --report report.json \
    [--report-url URL] [--report-path PATH]
pytest-given citations update …   # same arguments
```

`check` writes nothing and reports every finding; `update` rewrites what the
[findings table](#findings-and-what-update-writes) says and reports what remains. The verb, not a
flag, says whether a command line writes files.

Positional arguments are Markdown files and directories. A directory is searched recursively for
`*.md`: the shell cannot be trusted to expand globs, since PowerShell does not for native commands.

Neither command runs tests: both read a JSON report an earlier pytest run wrote, so a document can
be checked again after an edit without rerunning the suite. The check compares against that local
JSON report, never against the report the links point to.
The hosted report shows `main`, while a document on a branch cites what the branch's own run
reports, and a document's citations are a snapshot of its commit's report.

The report has to hold every scenario a document may cite: the check cannot tell a test the run
never collected from a deleted one, so a partial run (a subset of paths, `-k`) reads every target
outside it as not in the report, and `update` marks those citations `❓`. The report holds only
scenarios, so a CI job writes it from all of them without running the plain tests:
`pytest -m pytest_given --given-json=report.json`.

### Which links it reads

An inline link `[text](url)` is a report link when — its URL read as it renders, backslash escapes
and entity references resolved —

- its URL without the fragment is the report's — an absolute URL equal to the report URL
  (`--report-url` if given, otherwise the one stored in the report), or a relative URL that
  resolves, from the document's directory, to `--report-path` — and
- its fragment has one of the three shapes under [Citation kinds](#citation-kinds), in any parameter
  order. A link to the report with any other fragment (`#q=…`, two tags) is an ordinary link —
  unless a glyph leads it, which marks it as a citation whose fragment is mistyped (a finding).

`--report-path` names where the report sits in the repository once the docs build has placed it.
The file need not exist, since only paths are compared; without the flag, relative links are
ordinary links, as is a URL no URL parser reads. With neither a report URL nor a report path, the
check cannot tell report links from others and exits 2.

Whether a report link is a citation, and where its summary is, follow the rules under
[Citations and report links](#citations-and-report-links).

Fenced code blocks, indented code blocks and code spans are skipped, so a document can show a
citation as an example without the check reading it as one. Reference-style links are not read.

### Findings and what `update` writes

| Finding | Applies to | `update` writes | Remains a finding |
|---|---|---|---|
| Unknown node id, but the link text is exactly one scenario's title — a renamed or moved test | scenario citation | that scenario's node id | no |
| Target not in the report — unknown node id, a tag no scenario carries at or below, unknown story | citation | glyph `❓`, summary removed | yes |
| Target not in the report | plain report link | — | yes |
| Stale glyph, link text or summary, or a missing summary | citation | the current value | no |
| Slug, or a `[case]` suffix on a grouped scenario's node id, in a scenario fragment | any report link | the cited node id | no |
| Failed target — a cited scenario, tag or story with a failure | citation | — (its glyph is already `❌`) | yes |
| Mistyped citation — a glyph-led link to the report whose fragment has none of the three shapes | link to the report | — | yes |
| Summary after a scenario citation — often left behind by repointing a tag or story citation | scenario citation | — | yes |

`update` never leaves a stale value behind: after it, every citation is either current or marked
`❓`. A cited failure stays a finding, because a document citing broken behavior is the thing most
worth stopping a merge for. A plain report link claims only that its target exists, so its target
failing is not a finding.

A citation marked `❓` keeps its target in the URL and its last confirmed text, so it recovers on its
own: once the target is back — the test restored, a branch merged — the next `update` writes its
glyph, text and summary. Repairing a renamed target means editing only the URL — or, for a renamed
test whose scenario title survived, nothing, by the first row.

That row repoints only on an exact match with exactly one scenario: two scenarios sharing the title,
or a title that differs at all, leave the citation marked `❓`. Similarity is for suggestions, never
for writes.

Each finding prints as `path:line: message`. A stale part adds a before → after line. An unknown
target lists the closest candidates in the report — for a scenario, by node id and by scenario
title — and the author picks one by editing the URL.

### Exit codes and writes

- `0` no findings remain; `1` findings remain; `2` the report or a document is unreadable, or
  neither a report URL nor a report path is known, and nothing is written.
- `update` rewrites only the parts in the table. Every other byte of a file stays as it was,
  line endings included, and a file nothing changed in is not rewritten.

Citations are snapshots: a document read at a commit says what that commit's report said. What
keeps the snapshot on `main` current is the check sitting in a required CI gate; the docs page says
so, since a check nothing enforces only decorates.

## Citing skill

A finding `citations update` cannot resolve — a target not in the report — needs someone to find
what the citation should point to now. A new bundled skill, `pytest-given-citing`, lets an agent do
it, and covers writing citations in the first place. Its trigger is a `citations check` finding, or
a document to cite scenarios, tags or stories from.

### Triage

| Finding | What the agent does |
|---|---|
| Stale glyph, text or summary; slug or `[case]` in a fragment | run `citations update` |
| Failed target | nothing in the document: the test fails, and that is the problem to fix or report |
| Summary after a scenario citation | delete it, unless the author wrote it as prose — then reword it so it no longer reads as a summary |
| Target not in the report | first check that the report comes from a run of every scenario, then the repair below |

### Repair

1. **Read the claim.** The citation's link text is the last text the check confirmed, and the prose
   around it says why the document cites it. Together they are what the new target must state.
2. **Gather candidates.** `citations check` lists the closest by node id and by scenario title. Git
   history finds a renamed or moved test in the commit that changed it (`git log -S` for a
   function, `--diff-filter=R` for a file). The report answers the rest — the navigating skill's
   `jq` queries by narration words, term and tag; for a tag or story, the report's tags and story
   titles.
3. **Verify, don't match.** Read each candidate's steps and test body. It qualifies only if it
   states the claim — not a similar one, and not its opposite, which a similar title often is.
4. **Repoint.** Edit only the URL's fragment, run `citations update` to write glyph, text and
   summary, and read the new link text against the prose around it: a reworded scenario title can
   stop fitting the sentence that cites it.
5. **No candidate states the claim.** Leave the citation marked `❓` and tell the human: the
   behavior is gone or untested. The choices — drop the citation, rewrite the prose, or write a
   scenario for it (the authoring skill) — are theirs.

The agent reports every repoint as old target → new target with the evidence it used, so a human
reviews the change rather than repeats the search.

### Writing citations

An agent cannot click a copy button. It writes `? [](<report URL>#<fragment>)` — a citation with
an empty text and a typed `?` glyph — and runs `citations update`, which finds the target present and
writes the glyph, text and summary. The same placeholder works for a human with no report open.
The target is chosen as in a repair: verified against the prose that cites it, not picked by a
matching scenario title. The skill also carries the habits that keep citations quiet: a relative
URL on a versioned site, and one tag per piece of work (`spec/<slug>`) rather than citing a broad
area tag.

## Configuration

| Option | Kind | Default | Effect |
|---|---|---|---|
| `--given-report-url` / `given_report_url` | CLI flag / ini | unset | The public URL the HTML report will be served from, stored as `report_url` in the report metadata. The copy buttons show only with it, and link to it; `citations check` reads links to it. |

`pytest-given report` passes the stored value through when it re-renders.

## In this repo

- **Spec tags.** The scenarios a spec introduces carry `spec/<slug>`, the spec's filename without
  the date and `-design`. The spec opens with that tag's citation as its progress line and cites
  its scenarios one by one under its acceptance criteria. These are the self-report's first tags.
  The [acceptance-criteria extension](#future-extension-acceptance-criteria) would replace them.
- **Cite what exists.** The gate fails on a citation to a scenario the committed report lacks, so a
  spec cites its scenarios from the commit that adds them as xfail tests, not before.
- **Moving a spec.** AGENTS.md's spec workflow gains one condition: a spec leaves `proposed/` once
  its citations read ✅.
- **Gate.** The `self_report` nox session passes
  `--given-report-url=https://nwilbert.github.io/pytest-given/dev/examples/self-report.html` — the
  `/dev/` docs publish on every push to `main`, so a citation resolves as soon as its scenarios
  merge. A `citations` session in the default gate runs `pytest-given citations check docs/specs/`
  against the committed `examples/self-report/self-report-data.json`. CI runs `reports_current`
  instead, which a stale committed report cannot pass: it regenerates every report, with the
  `citations update` runs below, and fails if a tracked Markdown file changed or a finding remains.
- **Refresh.** The regeneration sessions run `citations update` right after writing their reports:
  `self_report` over `docs/specs/`, and both `self_report` and `examples` over `docs/site/` for
  each report they write. A commit that regenerates a report then carries its refreshed citations,
  and both sessions run every scenario they report on, so a `❓` they write marks a target really
  gone. The gate still catches a cited test changed without regenerating its report.
- **Site pages.** A `docs/site/` page citing an example report links it relatively, as the site's
  existing report links do. The `citations` session adds a run over `docs/site/` per cited report,
  with `--report-path docs/site/examples/<report>.html`. A cited failure fails that run, so a page
  cites nothing an example fails on purpose (coffeeshop's `test_failing`, hotel-booking's "Book a
  Group Trip" story) and shows such a citation only in a code block.
- **Stories.** The self-report has none, so story citations are demonstrated on the
  `hotel-booking` example. The `examples` session writes every example report with its own `/dev/`
  URL, so each shows the buttons. A released version of the site keeps those `/dev/` URLs: a
  citation copied there is for a spec on `main`, which cites `/dev/`, and a site page shortens it
  to a relative link anyway.

## Implementation touch points

- `model/schema.py`, `model/report_url.py` — `report_url` on the report metadata, typed
  `ReportUrl`: only `resolve_report_url` mints one, so the URL is checked where it is configured and
  where a report is read back from JSON, and nowhere downstream.
- `plugin/` — the `--given-report-url` option and `given_report_url` ini.
- `report/citation_index.py` (new) — renders the citation of each kind from the scenarios, tags
  and stories a report holds. A story's scenarios come from `scenarios_by_story`; tag matching
  has no Python counterpart yet, so the index files each scenario under every prefix of its tags,
  and a unit test counts each tag citation against the Tags sidebar's prefix rule, restated in
  Python. That the page applies the same rule is a frontend behavior, verified in the browser like
  the rest.
- `citations/` (new package, on `model/` and `report/`) — reads report links out of Markdown,
  resolves what each names — a slug or case suffix to the cited node id, suggestions for a
  target the report lacks — and computes findings and updates. `citations.check_citations`
  exposes the whole job, the way `emit_sinks` does. Reading is a hand-written scanner — fences,
  indented code, backtick runs, glyph, link, summary, table rows — because `update` needs each
  part's exact source position, which no Markdown parser's inline tokens carry; a parser would only
  take over block structure, at the cost of a runtime dependency.
- `report/text.py` — `CITATION_GLYPH` beside `STATUS_GLYPH`, which the Markdown sink keeps.
- `report/html_renderer.py` — each citation's line, and the scenario node ids, in the report data.
- `report/templates/_macros.html.j2`, `report.html.j2`, `app.js` — the three buttons,
  `copyCitation`, and the node-id lookup for `#scenario=`.
- `cli/citations.py` (new) — argv, output and exit codes; registered in `cli/__init__.py`.
- `noxfile.py` — `--given-report-url` and the `citations update` runs in `self_report` and
  `examples`, a `citations` session in the default gate, and a `reports_current` session, which
  `.github/workflows/ci.yml` runs as a job of its own.
- `AGENTS.md` — the default gate's session list, the spec-moving condition, and under the
  regeneration rules: the sessions also refresh citations, and the changed documents are committed
  with the report.
- `GLOSSARY.md` — **Citation** and **Report link** under the report terms.
- Docs: a new `docs/site/guide/citations.md` (in the `zensical.toml` nav), `docs/site/cli.md`, and
  `docs/site/configuration/pytest-options.md`. The page says the check belongs in a required CI
  gate, fed by a run of every scenario (`-m pytest_given`, no narrower selection), that a
  versioned site links its reports relatively, that a citation's glyph and link stand unformatted,
  and that scenario citations assume a fixed rootdir.
- `src/pytest_given/.agents/skills/pytest-given-citing/` (new) — the citing skill, mirrored into
  `.claude/skills/` by `pytest-given skills install`; `nox -s build` checks its discovery like the
  other bundled skills'. The navigating skill gains a pointer to it, and
  `docs/site/ai-agents.md` lists it with the others.
- The authoring skill's "Vocabulary and tags" (`references/scenarios.md`), and its mirror in the
  reviewing skill's layer 4 — a work-item tag (`ticket/…`, `spec/…`) means "added by this piece of
  work", not "describes this behavior". It need not cut across modules, and other scenarios of the
  same behavior lacking it is not a finding.
- `CHANGELOG.md` — under Added: the copy buttons, `pytest-given citations check` and `update`,
  `given_report_url`, and the `pytest-given-citing` skill.

## Test coverage

- **Unit** — rendering per kind: each glyph, the tag/story status and summary rule, link-text
  escaping (each escaped character, an intraword `_` left alone, an unpaired backtick, a code span
  untouched, `|` in a code span in a table row, an unescaped hand-written text compared as current)
  and term refs, a grouped scenario's templated title, a per-case scenario's suffixed node id kept
  while a grouped one's is stripped, tag prefix matching, a story with no
  scenarios, fragment encoding round-tripping through `parse_qs`. Reading: each code-block form
  skipped, the report URL from the flag and from the report, relative links resolved from the
  document's directory with and without `--report-path`, exit 2 with neither URL nor path, citation
  versus plain report link, a sentence's `?` before a link not read as a glyph, an author's
  parenthetical after a citation not read as its summary, an unrecognized fragment on a plain link
  left alone, a citation in a bullet and in a table cell, a line break between glyph and link, link
  text wrapped across lines and current, a formatted glyph not read as one, each text glyph and a
  typed `?` read and rewritten as emoji. One
  test per row of the findings table, plus a marked citation recovering, the `? []()` placeholder
  filled, repointing refused for a title two scenarios share and for a near match, and suggestions
  ranked by node id and by scenario title; `update` idempotent, a plain link's text never
  rewritten, line endings preserved, an unchanged file not rewritten.
- **Scanner oracle** — a differential test runs the scanner and `markdown-it-py` (added to the
  `test` dependency group only; it is already locked, through `pip-audit` and `library-skills`)
  over every Markdown file git tracks and the fixtures, and asserts both find the same links, href
  and text with escapes resolved. A deliberate difference is listed in the test. Fixtures add a
  line break between glyph and link, link text wrapped inside a blockquote, and a citation in a
  table row.
- **Integration** — `--given-report-url` reaches the JSON and survives `pytest-given report`;
  `citations check` exit codes end to end.
- **Skills** — `pytest-given-citing` in `tests/unit/test_skills_data.py`'s bundled list, and any
  `python` block it carries run by `tests/unit/test_skills_scripts.py`.
- **Self-report** — scenarios for the citation rule, the report-link rule and the `❓` marking,
  tagged `spec/citations` and cited from this spec once they exist.
- **Playwright** — each button, including a Stories-view card clone and a tag below the top level;
  no buttons in a report without `given_report_url`; a `#scenario=<node id>` link opening its card.

## Acceptance criteria

- ✅ [`citations update` rewrites a stale citation to its target's glyph, text and summary](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html#scenario=tests/unit/citations/test_check.py::test_update_rewrites_a_stale_citation)
- ✅ [A plain report link claims only that its target exists](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html#scenario=tests/unit/citations/test_check.py::test_a_plain_report_link_claims_only_that_its_target_exists)
- ✅ [A citation whose target left the report is marked ❓ and recovers once it is back](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html#scenario=tests/unit/citations/test_check.py::test_a_citation_to_a_gone_target_is_marked_and_recovers)

## Out of scope

- **Citing a sentence.** `#sentence-filter=<story>:<n>` addresses one, but sentence ids are
  positions, so inserting a sentence would repoint every later citation. A stable one needs the
  fragment to accept a sentence's name.
- **Live badges** — a summary served by the hosted report and drawn by an image service. They would
  show `main`'s state in every commit's copy of a document, depend on a third party, and lag behind
  image-proxy caches.
- **Updating from CI** — a job that runs `citations update` and commits the result.
- **Citing a glossary term.** Terms have deep links (`#view=glossary&term=…`), but a term states
  vocabulary, not behavior, so it has no status for a document to track.
- Embedding a scenario's steps or parameter table; citing a single case of a grouped scenario;
  generating citation lists from a tag, term or story; links combining several filters; checking
  against several reports in one run.

## Future extension: acceptance criteria

The reverse link — tests naming the document — is a separate feature, sketched here so this design
leaves room for it. A spec's acceptance criteria load as a vocabulary from the spec file, the way a
`FileGlossary` loads `GLOSSARY.md`, and scenarios bind to them the way `pins=` binds story
sentences (`criteria=[acceptance['A citation survives a renamed test']]`). The binding is explicit,
so a criterion no scenario binds is a real gap in the tests, unlike an uncovered story sentence. It
meets this design in two places: a spec gets its own report view and becomes a fourth citation
kind, summarized by criterion coverage (`(5/7 criteria covered)`); and the `spec/<slug>` tag
retires, since the binding names a spec's scenarios exactly.
