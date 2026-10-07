# Citations — Design Spec

## Goal

Let a Markdown document — a design spec first of all — cite a scenario, a tag or a story by a link
that stays true:

1. **Copy buttons** in the HTML report put a one-line Markdown citation on the clipboard: a status
   glyph, a link to the cited thing in the report, and for a tag or story a short summary.
2. **`pytest-given check-docs`** verifies every link into the report in a set of Markdown files
   against a JSON report, for CI, and `--update` rewrites the citations to match it.
3. **A bundled skill** lets an agent repair what `--update` cannot — a citation whose target is
   gone — and write new citations.

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
shows ⊗ until its scenarios pass, and the check flags it stale the moment they do. A spec whose
citations all read ✓ is implemented.

## Citations and report links

```markdown
- ✓ [One xfailed case makes its parametrized scenario an expected failure, with that case's reason](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html#scenario=tests/unit/test_grouping.py::test_one_xfailed_case_makes_the_group_xfailed)
- ⊗ [spec/citations](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html#tag=spec/citations) (5 ✓ · 2 ⊗)
```

A **report link** is a Markdown link to a scenario, tag or story in the report (see
[Which links it reads](#which-links-it-reads)). The check verifies that every report link's target
exists.

A **citation** is a report link led by a glyph and one space, where the glyph starts the line's
content (after any list marker or `>`) or follows whitespace or `(` — so a question mark ending a
sentence is never read as one. The check owns three parts of a citation, and nothing else on the
line:

- **Glyph** — `STATUS_GLYPH`, the glyphs the Markdown sink uses: `✓` passed, `✗` failed, `○`
  skipped, `⊗` xfailed; plus `?` for a citation whose target is no longer in the report.
- **Link text** — what the target is called: a scenario's narration, a tag, a story's title.
- **Summary** — a parenthesized suffix one space after the link, or after an `attr_list` block
  directly following it (`{ target=_blank }`, as the docs site writes report links). Only text of a
  summary's shape counts as one — status counts, sentence coverage, `(no tracked sentences)` or
  `(not in report)` — so a parenthetical of the author's own after a citation stays theirs.

A report link without a glyph is a *plain* one, the form for a sentence that wants its own wording
("rejecting [divergent cases](…#scenario=…) keeps the tree honest"). The check owns none of its
text but a `(not in report)` marker after it.

The check owns a citation's text because the citation *claims* something about its target — its
name and state — that the report can contradict. A plain report link claims only that the target
exists.

### Link text

Link text renders inline, so three rules apply to every kind:

- Outside code spans, `\`, `[` and `]` are backslash-escaped, so the text cannot close the link
  early. Inside one they stay as they are: a code span binds tighter than link brackets, and a
  backslash there would render literally. Narration often carries code spans (`` `--given-md` ``).
- A newline folds to a space.
- A term ref renders as its plain display text, without the `«»` the Markdown sink wraps it in.

A narration that interpolates a value differing between runs — a temporary path — would make its
citation stale on every run. Such a scenario is cited by a plain report link.

### Status of a tag or story

A tag or story stands for several scenarios, so its glyph summarizes theirs: `✗` if any failed,
else `⊗` if any is xfailed, else `✓` if any passed, else `○` — all skipped, or a story no scenario
belongs to yet.

### The URL

The report's URL (`given_report_url`, see [Configuration](#configuration)) with the target in its
fragment. A fragment
value is percent-encoded except for `A–Z a–z 0–9 - . _ ~ / :`, so a typical node id or tag stays
readable, and `URLSearchParams` decodes it to the same string Python's `urllib.parse.parse_qs` does.

A document on a versioned site links the report relatively (`../examples/self-report.html#tag=…`),
so each version of the page opens its own version's report — an absolute link would pair one
version's glyph with another's report. The copy buttons copy absolute URLs, since they cannot know
where the document sits; shortening the base to a relative path is a one-time edit, and `--update`
only ever rewrites a URL's fragment.

## Citation kinds

### Scenario

```markdown
✓ [One xfailed case makes its parametrized scenario an expected failure, with that case's reason](…#scenario=tests/unit/test_grouping.py::test_one_xfailed_case_makes_the_group_xfailed)
```

- **Fragment** — `scenario=<node id>`, the base id without a `[case]` suffix: a grouped scenario is
  cited as a whole, as the report shows it.
- **Link text** — the narration, a grouped scenario's templated one with its placeholders.
- **Glyph** — the scenario's status.
- **Summary** — none.

`#scenario=` accepts a node id as well as a slug; the report data gains the node ids beside
`scenario_slugs`. The existing copy-link button keeps copying slugs: it serves a reader passing a
link around today, not a document.

#### Why the node id

A scenario citation identifies its target by the node id, with the narration as its text, so it
carries two independent anchors and either one alone recovers it exactly: reworded narration
leaves the node id resolving, and a renamed or moved test leaves the link text matching (see
[Findings](#findings-and-what---update-writes)). A node id changes only when its own test is
renamed or moved, is unique by construction, and greps straight to the test.

The two other candidates lose that:

- **The slug** (`#scenario=<slug>`, what the copy-link button writes) depends on the whole report:
  `build_scenario_slug_index` resolves collisions across it, so adding an unrelated test can
  lengthen a slug.
- **A narration slug** would make the URL and the text one anchor, broken together by the most
  frequent edit — rewording, which the lint and the reviewing skill both prompt. Recovering would
  mean matching similar narration, and similar narration often states opposite behavior ("…is
  refused" beside "…is grouped"): an update that repoints an acceptance criterion to its opposite
  is worse than a `?`. Narration is not unique either, so a narration slug would need the same
  collision suffixes as the slug, and the t-string it comes from (`t'{g["Room"]} is booked'`) does
  not grep.

A node id is relative to pytest's rootdir, so a suite run from another rootdir shifts every
scenario citation at once. A project's rootdir is fixed in practice; the docs page says so.

### Tag

```markdown
⊗ [spec/citations](…#tag=spec/citations) (5 ✓ · 2 ⊗)
```

- **Fragment** — a single `tag=<tag>`, the tag filter the report already reads.
- **Link text** — the tag.
- **Glyph** — the tag's status, over the scenarios the link opens: those carrying the tag or a tag
  below it (`/` separates levels), the prefix rule of the Tags sidebar's `underPrefix`. The sidebar's
  no-tags bucket is not a tag and cannot be cited.
- **Summary** — the scenario count per status, in glyph order (`✓ ✗ ○ ⊗`), zeros left out.

Every scenario that later gets the tag changes the summary, so a tag citation suits a tag that
belongs to one piece of work — a spec's `spec/<slug>`, shaped like the ticket tags the authoring
skill recommends — and settles once that work is done. A broad area tag is better linked by a plain
report link.

### Story

```markdown
⊗ [Cancel a Booking](…#view=stories&story=cancel-a-booking) (4/6 sentences covered)
```

- **Fragment** — `view=stories&story=<story id>`, what the story header's copy-link button writes.
- **Link text** — the story's title. The story id derives from the title, so renaming the story
  breaks the citation the way renaming a test does.
- **Glyph** — the story's status, over the scenarios its Stories-view panel lists.
- **Summary** — covered sentences out of tracked ones, from the same rollup the Stories view shows;
  an untracked sentence (too few glossary terms to match) counts in neither number. A story with no
  tracked sentence reads `(no tracked sentences)`.

A story summary moves less than a tag's: another scenario covering an already covered sentence
leaves it as it was. It changes when a sentence gains its first coverage, when the story gains a
sentence, or — through the glyph — when a scenario's status changes.

## Copy buttons

| Kind | Button sits |
|---|---|
| Scenario | on the card, beside its copy-link button — and on the card clones the Stories view borrows |
| Tag | on the tag's row in the Tags sidebar, at every level of the tree `app.js` builds |
| Story | in the story header, beside its copy-link button |

Each is titled "Copy Markdown citation". The tick on success and the `navigator.clipboard` →
`execCommand` fallback are `copyAnchor`'s, through the shared `_copyText`.

The renderer writes each citation's glyph, link text, fragment and summary into the report data —
for tags, one per level of every tag, since the tree is built client-side — and only in a report
that shows the buttons, so the others carry no extra weight. JS only joins them with
the URL, so Python stays the one place a citation is rendered, and the check recomputes exactly
what a button copied.

### When the buttons show

Only in a report written with `given_report_url` (see [Configuration](#configuration)), and their
URL is that one. The setting is the toggle:

- **A citation is only worth copying from a report with a public address.** A report a developer
  opens from `file://`, with `vscode` or `pycharm` source links for jumping into their editor, has
  no URL a document could carry. There the buttons would only copy dead links.
- **The URL comes from the setting, not from `window.location`,** because the report a spec is
  drafted against is seldom the hosted one: a spec on a branch cites scenarios the hosted report
  does not have yet, from a report opened locally.
- **Nothing in the citation is specific to GitHub.** It is a plain CommonMark link, which GitLab,
  Gitea, Bitbucket, IDE previews and the docs site render alike; what differs between hosts is
  only where the report is served, and the setting names that, whatever the host — GitHub Pages,
  GitLab Pages, or an internal server.

A report without the setting stays as it is today.

## `pytest-given check-docs`

```bash
pytest-given check-docs docs/specs/ README.md --report report.json \
    [--report-url URL] [--report-path PATH] [--update]
```

Positional arguments are Markdown files and directories. A directory is searched recursively for
`*.md`: the shell cannot be trusted to expand globs, since PowerShell does not for native commands.

### Which links it reads

An inline link `[text](url)` is a report link when:

- its URL without the fragment is the report's — an absolute URL equal to the report URL
  (`--report-url` if given, otherwise the one stored in the report; a report that stores none
  matches any absolute URL), or a relative URL that resolves, from the document's directory, to
  `--report-path` — and
- its fragment has one of the three shapes under [Citation kinds](#citation-kinds), in any parameter
  order. A link to the report with any other fragment (`#q=…`, two tags) is an ordinary link.

`--report-path` names where the report sits in the repository once the docs build has placed it.
The file need not exist, since only paths are compared; without the flag, relative links are
ordinary links.

Whether it is a citation, and where its summary is, follow the rules under
[Citations and report links](#citations-and-report-links).

Fenced code blocks, indented code blocks and code spans are skipped, so a document can show a
citation as an example without the check reading it as one. Reference-style links are not read.

### Findings and what `--update` writes

Without `--update`, the check writes nothing and reports every finding. With it, it rewrites what
the table says and reports what remains.

| Finding | Applies to | `--update` writes | Remains a finding |
|---|---|---|---|
| Unknown node id, but the link text is exactly one scenario's narration — a renamed or moved test | scenario citation | that scenario's node id | no |
| Target not in the report — unknown node id, a tag no scenario carries at or below, unknown story | citation | glyph `?`, summary `(not in report)` | yes |
| Target not in the report | plain report link | ` (not in report)` after the link | yes |
| Stale glyph | citation | the current glyph | no |
| Stale link text | citation | the current text | no |
| Stale or missing summary | tag or story citation | the current summary | no |
| Slug or `[case]` suffix in a scenario fragment | any report link | the base node id | no |
| Failed target — a cited scenario, tag or story with a failure, or a plain link to a failed scenario | any report link | — (a citation's glyph is already `✗`) | yes |

`--update` never leaves a stale value behind: after it, every citation is either current or marked
`?`. A cited failure stays a finding, because a document citing broken behavior is the thing most
worth stopping a merge for. A plain link to a tag or story claims no status, so its scenarios
failing is not a finding.

A marked report link keeps its target in the URL, so it recovers on its own: once the target is
back — the test restored, a branch merged — the next `--update` writes a citation's glyph, text and
summary back, and drops the `(not in report)` from a scenario citation or plain link. Repairing a
renamed target means editing only the URL — or, for a renamed test whose narration survived,
nothing, by the first row.

That row repoints only on an exact match with exactly one scenario: two scenarios sharing the
narration, or a narration that differs at all, leave the citation marked `?`. Similarity is for
suggestions, never for writes.

Each finding prints as `path:line: message`. A stale part adds a before → after line. An unknown
target lists the closest candidates in the report — for a scenario, by node id and by narration —
and the author picks one by editing the URL.

### Exit codes and writes

- `0` no findings remain; `1` findings remain; `2` the report or a document is unreadable, and
  nothing is written.
- `--update` rewrites only the parts in the table. Every other byte of a file stays as it was,
  line endings included, and a file nothing changed in is not rewritten.

Citations are snapshots: a document read at a commit says what that commit's report said. What
keeps the snapshot on `main` current is the check sitting in a required CI gate; the docs page says
so, since a check nothing enforces only decorates.

## Citing skill

A finding `--update` cannot resolve — a target not in the report — needs someone to find what the
citation should point to now. A new bundled skill, `pytest-given-citing`, lets an agent do it, and
covers writing citations in the first place. Its trigger is a `check-docs` finding, or a document
to cite scenarios, tags or stories from.

### Triage

| Finding | What the agent does |
|---|---|
| Stale glyph, text or summary; slug or `[case]` in a fragment | run `--update` |
| Failed target | nothing in the document: the test fails, and that is the problem to fix or report |
| Target not in the report | the repair below |

### Repair

1. **Read the claim.** The citation's link text is the last narration the check confirmed, and the
   prose around it says why the document cites it. Together they are what the new target must
   state.
2. **Gather candidates.** `check-docs` lists the closest by node id and by narration. Git history
   finds a renamed or moved test directly, in the commit that changed it: `git log -S'def
   test_old_name'` for a renamed or moved function; `git log --name-status --diff-filter=R`, searched
   for the old path, for a renamed file — whose rename pairs the two paths with unchanged content,
   so `-S` sees nothing there. The report answers the rest — the
   navigating skill's `jq` queries by narration words, term and tag; for a tag or story, the
   report's tags and story titles.
3. **Verify, don't match.** Read each candidate's steps and test body. It qualifies only if it
   states the claim — not a similar one, and not its opposite, which similar narration often is.
4. **Repoint.** Edit only the URL's fragment, run `--update` to write glyph, text and summary, and
   read the new link text against the prose around it: a rewritten narration can stop fitting the
   sentence that cites it.
5. **No candidate states the claim.** Leave the citation marked `?` and tell the human: the
   behavior is gone or untested. The choices — drop the citation, rewrite the prose, or write a
   scenario for it (the authoring skill) — are theirs.

The agent reports every repoint as old target → new target with the evidence it used, so a human
reviews the change rather than repeats the search.

### Writing citations

An agent cannot click a copy button. It writes `? [](<report URL>#<fragment>)` — a citation with
an empty text and a `?` glyph — and runs `--update`, which finds the target present and writes the
glyph, text and summary. The same placeholder works for a human with no report open. The target
is chosen as in a repair: verified against the prose that cites it, not picked by a matching
narration. The skill
also carries the habits that keep citations quiet: a relative URL on a versioned site, and one tag
per piece of work (`spec/<slug>`) rather than citing a broad area tag.

## Configuration

| Option | Kind | Default | Effect |
|---|---|---|---|
| `--given-report-url` / `given_report_url` | CLI flag / ini | unset | The public URL the HTML report will be served from, stored as `report_url` in the report metadata. The copy buttons show only with it, and link to it; `check-docs` reads links to it. |

`pytest-given report` passes the stored value through when it re-renders.

## In this repo

- **Spec tags.** The scenarios a spec introduces carry `spec/<slug>`, the spec's filename without
  the date and `-design`. The spec opens with that tag's citation as its progress line and cites
  its scenarios one by one under its acceptance criteria. These are the self-report's first tags.
  The [acceptance-criteria extension](#future-extension-acceptance-criteria) would replace them.
- **Cite what exists.** The gate fails on a citation to a scenario the committed report lacks, so a
  spec cites its scenarios from the commit that adds them as xfail tests, not before.
- **Moving a spec.** AGENTS.md's spec workflow gains one condition: a spec leaves `proposed/` once
  its citations read ✓, and `--update` has refreshed them in the same commit.
- **Gate.** The `self_report` nox session passes
  `--given-report-url=https://nwilbert.github.io/pytest-given/dev/examples/self-report.html` — the
  `/dev/` docs publish on every push to `main`, so a citation resolves as soon as its scenarios
  merge — then runs `pytest-given check-docs docs/specs/` against the report it just wrote. The
  default gate runs the same check against the committed `examples/self-report/self-report-data.json`.
- **Site pages.** A `docs/site/` page citing an example report links it relatively, as the site's
  existing report links do. The gate then adds a run over `docs/site/` per cited report, with
  `--report-path docs/site/examples/<report>.html`.
- **Stories.** The self-report has none, so story citations are demonstrated on the
  `hotel-booking` example. The `examples` session writes every example report with its own `/dev/`
  URL, so each shows the buttons.

## Implementation touch points

- `model/schema.py` — `report_url: str | None` on the report metadata.
- `plugin/` — the `--given-report-url` option and `given_report_url` ini.
- `report/citations.py` (new) — renders the citation of each kind, reads report links out of
  Markdown, computes findings and updates. `report.check_citations` exposes the whole job, the way
  `emit_sinks` does. The story status and summary reuse `build_story_rollups`; tag matching has no
  Python counterpart yet, so it ports `underPrefix` from `app.js`, and a unit test holds the two to
  the same cases.
- `report/html_renderer.py` — each citation's parts, and the scenario node ids, in the report data.
- `report/templates/_macros.html.j2`, `report.html.j2`, `app.js` — the three buttons,
  `copyCitation`, and the node-id lookup for `#scenario=`.
- `cli/check_docs.py` (new) — argv, output and exit codes; registered in `cli/__init__.py`.
- `noxfile.py` — the `self_report` additions, and a `check_docs` session in the default gate.
- `AGENTS.md` — the default gate's session list, and the spec-moving condition.
- `GLOSSARY.md` — **Citation** and **Report link** under the report terms.
- Docs: a new `docs/site/guide/citations.md` (in the `zensical.toml` nav), `docs/site/cli.md`, and
  `docs/site/configuration/pytest-options.md`. The page says the check belongs in a required CI
  gate, that a versioned site links its reports relatively, and that scenario citations assume a
  fixed rootdir.
- `src/pytest_given/.agents/skills/pytest-given-citing/` (new) — the citing skill, mirrored into
  `.claude/skills/` by `pytest-given skills install`; `nox -s build` checks its discovery like the
  other bundled skills'. The navigating skill points to it from its `check-docs` mention, and
  `docs/site/ai-agents.md` lists it with the others.
- The authoring skill's "Vocabulary and tags" (`references/scenarios.md`), and its mirror in the
  reviewing skill's layer 4 — a work-item tag (`ticket/…`, `spec/…`) means "added by this piece of
  work", not "describes this behavior". It need not cut across modules, and other scenarios of the
  same behavior lacking it is not a finding.
- `CHANGELOG.md` — under Added: the copy buttons, `check-docs`, `given_report_url`, and the
  `pytest-given-citing` skill.

## Test coverage

- **Unit** — rendering per kind: each glyph and the tag/story status rule, link-text escaping and
  term refs, grouped narration, tag prefix matching, story coverage with untracked sentences and
  with none tracked, fragment encoding round-tripping through `parse_qs`. Reading: each code-block
  form skipped, report URL matching with and without a stored URL, relative links resolved from
  the document's directory with and without `--report-path`, citation versus plain report link, an
  `attr_list` block between a citation and its summary, a sentence's `?` before a link not read as
  a glyph, an author's parenthetical after a citation not read as its summary, an unrecognized
  fragment left alone. One test per row of the findings table, plus a marked citation recovering,
  the `? []()` placeholder filled, repointing refused for a narration two scenarios share and for a
  near match, and suggestions ranked by node id and by narration; `--update` idempotent, line
  endings preserved, an unchanged file not rewritten.
- **Integration** — `--given-report-url` reaches the JSON and survives `pytest-given report`;
  `check-docs` exit codes end to end.
- **Skills** — `pytest-given-citing` in `tests/unit/test_skills_data.py`'s bundled list, and any
  `python` block it carries run by `tests/unit/test_skills_scripts.py`.
- **Self-report** — scenarios for the citation rule, the report-link rule and the `?` marking,
  tagged `spec/citations` and cited from this spec once they exist.
- **Playwright** — each button, including a Stories-view card clone and a tag below the top level;
  no buttons in a report without `given_report_url`; a `#scenario=<node id>` link opening its card.

## Out of scope

- **Citing a sentence.** `#sentence-filter=<story>:<n>` addresses one, but sentence ids are
  positions, so inserting a sentence would repoint every later citation. A stable one needs the
  fragment to accept a sentence's name.
- **Live badges** — a summary served by the hosted report and drawn by an image service. They would
  show `main`'s state in every commit's copy of a document, depend on a third party, and lag behind
  image-proxy caches.
- **Updating from CI** — a job that runs `--update` and commits the result.
- **Citing a glossary term.** Terms have deep links (`#view=glossary&term=…`), but a term states
  vocabulary, not behavior, so it has no status for a document to track.
- Embedding a scenario's steps or parameter table; citing a single case; generating citation lists
  from a tag, term or story; links combining several filters; checking against several reports in
  one run.

## Future extension: acceptance criteria

Citations link a document to the report. The reverse link, tests naming the document, is a
separate feature that complements them; it is sketched here so this design leaves room for it.

A spec's acceptance criteria become a vocabulary loaded from the spec file, the way a
`FileGlossary` loads `GLOSSARY.md`, and scenarios bind to them the way `pins=` binds story
sentences:

```python
acceptance = FileSpec('docs/specs/proposed/2026-10-07-citations-design.md')

@scenario('A renamed test is repointed by its narration',
          criteria=[acceptance['A citation survives a renamed test']])
```

What it adds over citations alone:

- **Completeness.** A criterion no scenario binds shows as uncovered in the report, the way an
  uncovered story sentence does. A citation checks only the links a document already makes, so
  nothing tells it a criterion lacks a test.
- **The link lives in code.** A criterion reworded in the spec fails collection until the tests
  follow, as a renamed glossary term does — before any report exists.

How it meets this design:

- **A fourth citation kind.** The report gains a view per spec, and a spec citation summarizes it
  the way a story citation does: `⊗ [Citations](…#view=specs&spec=citations) (5/7 criteria
  covered)`.
- **The `spec/<slug>` tag retires.** The binding names a spec's scenarios exactly, which the tag
  only approximates.

To decide first:

- **Living or point-in-time.** Bindings that outlive the implementation keep a spec in force: a
  later behavior change must update it. Either `docs/specs/` becomes living documentation, or the
  bindings go when a spec leaves `proposed/`, and completeness is checked only while it is built.
- **Loading by slug.** A spec's path changes when it leaves `proposed/`, so tests that load it by
  path break on the move. Loading by slug (`citations`) survives it.
- **Criterion keys.** Full criterion text makes long lookups that break on every rewording. A short
  name per criterion, like the name a sentence carries for pinning, keeps tests readable at the
  cost of a second identifier.
- **Where criteria sit in the file** — under a fixed heading, or behind a marker.

## Open questions

- **Markdown scanning.** The links in question are a narrow syntax, but skipping code reliably means
  handling fences, indentation and backtick runs. A hand-written scanner keeps the dependency list
  as it is; `markdown-it-py` gets the edge cases right for free. Leaning scanner, with the
  code-block tests as its contract.
- **Two buttons or one.** A scenario card and a story header would carry two copy buttons side by
  side. The likely best shape is one: the existing link icon, opening a small menu on hover —
  "Copy link", "Copy Markdown citation" — that also opens on focus and click, since a hover-only
  menu shuts out keyboard and touch. To settle in Playwright against the real header.
