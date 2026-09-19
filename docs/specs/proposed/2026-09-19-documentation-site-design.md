# Documentation site — Design Spec

## Problem

The README is two documents in one file. Its first 72 lines are the pitch: live example
links, quick start, why pytest-given. The remaining ~450 lines are a reference manual —
the full public API, pytest options, the narration lint's rule table, source links, the
CLI, agent skills. `pyproject.toml` sets `readme = "README.md"`, so the whole thing is also
the PyPI long description, which has to stand alone with absolute links only.

That shape has three costs. A reader evaluating the plugin scrolls past a manual to find out
what it is. A reader looking something up has one flat page and browser search. And the
example reports are served through raw.githack, a third-party proxy of the GitHub raw view,
because nothing in the project publishes HTML.

## Goal

A versioned documentation site at `https://nwilbert.github.io/pytest-given/`, built from
Markdown pages under `docs/site/`, serving the example reports itself. The README shrinks to
the pitch and links into the site. Content moves; it is not rewritten.

## Stack

- **Zensical** (the Material-for-MkDocs team's successor project) as the static site
  generator. Material for MkDocs is in maintenance mode until May 2027 and MkDocs 2.0 drops
  the plugin system, so a new site starts on Zensical rather than on MkDocs 1.x. Zensical
  reads the MkDocs configuration shape, so a move to ProperDocs (the MkDocs 1.x continuation)
  would be a theme swap, not a content migration.
- **mike**, in the [squidfunk fork](https://github.com/squidfunk/mike) that calls
  `zensical build`, for versioning. mike commits each built version into the `gh-pages`
  branch under `/<version>/` with alias directories and a `versions.json` the theme's
  version selector reads. The fork is a declared bridge until Zensical ships native
  versioning; nothing in the site content depends on it, so replacing it later touches one
  nox session. It is git-only (not on PyPI) and is pinned to a commit.
- **GitHub Pages**, serving the `gh-pages` branch. No Read the Docs: it would add a second
  build pipeline and PR previews the project does not need.
- **No plugins beyond what Zensical ships.** No mkdocstrings — the API pages are hand-written
  prose with examples, moved from the README, which reads better than generated signatures.

Dependencies land in a `docs` dependency group (`zensical`, the pinned mike fork), included in
`dev` like the other groups.

## Layout

`docs_dir = "docs/site"`. Zensical builds every file under `docs_dir` and has no
`exclude_docs`, so the site source cannot share `docs/` with the design specs, the
superpowers material, and the contributor how-tos. Those stay where they are.

```
zensical.toml                  site config, repo root
docs/site/
  index.md                     Home
  getting-started.md
  guide/
    scenarios.md               @scenario, given/when/then, when_then
    step-text.md               step text & placeholders
    parametrized.md
    domain-storytelling.md
    attachments.md
  configuration/
    pytest-options.md
    narration-lint.md          owns the lint rule table
    source-links.md            source links & traceback frames
  cli.md
  examples.md                  one entry per report, linking into examples/ (same URL prefix, on purpose)
  ai-agents.md                 working with AI agents, incl. the skills install section
  assets/pytest-given-diagram.png   staged copy, gitignored (see Build)
  examples/*.html              staged copies, gitignored
  changelog.md                 staged copy, gitignored
site/                          build output, gitignored
```

`docs/pytest-given-diagram.png` stays where it is: the 0.1.0 and 0.2.0 READMEs frozen on
PyPI load it from `main/docs/` at view time, so moving it would break those pages.

The nav is a flat left sidebar with `Guide` and `Configuration` as sections; no top-level
tabs for ~14 pages. Theme features: search, code copy buttons, light/dark toggle, repository
link, edit-this-page link into GitHub. `extra.version.provider = "mike"` enables the version
selector.

### Content mapping

Each page is the corresponding README section (line ranges as of `c9346ee`) with heading
levels shifted up and intra-README anchors turned into cross-page links:

| Page | README source |
|---|---|
| `index.md` | title, live example links, Why pytest-given? + diagram (1–72, minus quick start) |
| `getting-started.md` | Quick start (11–56) |
| `guide/scenarios.md` | `@scenario`, `given`/`when`/`then`, `when_then` (75–175) |
| `guide/step-text.md` | Step text & placeholders (176–192) |
| `guide/parametrized.md` | Parametrized scenarios (193–232) |
| `guide/domain-storytelling.md` | Domain Storytelling (233–331) |
| `guide/attachments.md` | `attach` (332–346) |
| `configuration/pytest-options.md` | pytest options (347–368) |
| `configuration/narration-lint.md` | Narration lint (369–412) |
| `configuration/source-links.md` | Traceback frames + Source links (413–458) |
| `cli.md` | Standalone CLI (459–473) |
| `examples.md` | Examples (474–484) |
| `ai-agents.md` | Working with AI agents + Agent skills (485–512) |

Editing is confined to the seams: an opening sentence where a section relied on the text
before it, and link rewrites. Pages link to each other with relative paths only, so a page
renders the same under `/dev/`, `/0.3/`, or `/latest/`. The Development section (513–516)
becomes a link to `AGENTS.md` on the Home page; it is not a site page.

## Build

Two nox sessions are the only entry points, locally and in CI:

- **`docs_build`** — stages the build inputs, then runs `zensical build --strict`. Staging copies
  `examples/<name>/<name>.html` to `docs/site/examples/<name>.html`, `CHANGELOG.md` to
  `docs/site/changelog.md`, and `docs/pytest-given-diagram.png` to `docs/site/assets/`. All
  three targets are gitignored so each file stays single-sourced. `--strict` fails the build
  on an unresolved link, which is the test that the cross-page links survived the move.
- **`docs_deploy -- <version> [alias]`** — runs the `docs_build` steps first, so a site that
  fails `--strict` is never deployed, then
  `mike deploy --push --update-aliases <version> [alias]`. When the alias is `latest` it also
  runs `mike set-default --push latest`; when the version is `dev` and `mike list` shows no `latest` alias yet,
  `mike set-default --push dev`. Versions are `major.minor` (`0.3`), so a patch release
  replaces its minor's docs rather than adding an entry to the selector.

Local preview is `uv run --group docs zensical serve` after `uv run nox -s docs_build` has staged
the copies; documented in `AGENTS.md`, not wrapped.

If Zensical does not copy `.html` files from `docs_dir` verbatim, staging targets
`site/examples/` after the build instead. The published URLs are the same either way.

Feasibility checked on 2026-09-19: `zensical` (0.0.61) and the mike fork (commit `2d4ad79`)
resolve and install under Python 3.14 on Windows.

## Deployment

**`docs.yml`** (new workflow):

- `pull_request` → `nox -s docs_build`. Build check only.
- `push` to `main` → `nox -s docs_deploy -- dev`.
- `workflow_dispatch` with `version` and `alias` inputs → `nox -s docs_deploy -- <inputs>`,
  for repairs. Not part of the normal path.

The deploy job needs `contents: write` and a checkout that keeps its credentials, because mike
pushes to `gh-pages`. Every other job in the repository checks out with
`persist-credentials: false`; the exception is confined to the two jobs that run
`docs_deploy`. Each of them also fetches the `gh-pages` branch before mike runs (a shallow
single-branch checkout would otherwise make mike start an orphan branch whose push is
rejected), sets a git identity (`github-actions[bot]`) for mike's commits, and runs under a
`concurrency` group (`gh-pages`, no cancellation) so two deploys in quick succession queue
rather than race on the branch.

**`release.yml`** gains a `docs` job: `needs: github-release`, `if: inputs.target == 'pypi'`,
runs `nox -s docs_deploy -- <major.minor> latest` from the tagged commit, with the same
permissions, checkout, fetch, identity and concurrency group as the `docs.yml` deploy job.
TestPyPI rehearsals do not touch the site.

**One-time repository setting:** GitHub Pages source set to the `gh-pages` branch. Noted in
`docs/releasing.md`.

**Resulting URLs:** `/dev/` tracks `main`; `/<major.minor>/` per release; `/latest/` aliases
the newest release; the site root redirects to the default alias.

### Bootstrap

No release version is deployed retroactively. The first push publishes `/dev/` and sets it as
the default, so the site root resolves. The 0.3.0 release creates `/0.3/` and `/latest/` and
moves the default to `latest`.

Until then every external link into the site — README, `--help`, skills — points at
`/dev/…`. The change that introduces those links (step 2 below) also adds a checklist item to
`docs/releasing.md` under *Prepare the bump*: repoint them from `/dev/` to `/latest/` as part
of the 0.3.0 release, then delete the checklist item. There is no automated guard; the
checklist is the mechanism.

## README

After the site is live, the README becomes the pitch (~90 lines):

1. Title, one-liner, JGiven credit
2. Live example links → `…/pytest-given/dev/examples/<name>.html` (later `/latest/`)
3. Quick start — unchanged, the one deliberate duplication with `getting-started.md`, because
   the PyPI page needs it standalone
4. Why pytest-given? + diagram, image URL unchanged
5. Features: six one-line bullets (step context managers, `Annotated` fixture labels,
   parametrization, Domain Storytelling, narration lint, agent skills), each ending in a link
   to its site page
6. "Full documentation" link
7. License

Everything else moves out. The README says what and why; the site says how.

### Repointing

Landing in the same change as the trim:

- `tests/unit/lint/test_config.py` — the rule-table check parses
  `docs/site/configuration/narration-lint.md` instead of `README.md`.
- `src/pytest_given/cli/report.py` and `src/pytest_given/plugin/options.py` — the `--help`
  text's "See README for variables" becomes the source-links page URL.
- `src/pytest_given/.agents/skills/pytest-given-authoring/SKILL.md`, `references/api.md`,
  `references/scenarios.md` — "the project README" becomes the site URL. These ship in the
  wheel, so the change is user-facing and gets a CHANGELOG entry.
- `AGENTS.md` — the README↔skill sync duty becomes docs↔skill; the `README.md#narration-lint`
  link moves to the site page.
- `pyproject.toml` — the sdist allowlist is unchanged; `docs/` stays out of the sdist.
- `CHANGELOG.md` — one *Added* entry naming the site URL, which also covers the skills'
  repointed links.
- `docs/releasing.md` — the `/dev/` → `/latest/` checklist item from *Bootstrap*.

## Sequencing

Two pushes to `main` (the project works on `main` directly; each push is one coherent commit):

1. **Site.** `docs/site/` pages, `zensical.toml`, the `docs` group, the nox sessions,
   `docs.yml`, the `release.yml` job, gitignore entries, the Pages-setting note in
   `releasing.md`, and a paragraph under `AGENTS.md`'s Quality gates covering the
   `docs_build` session, the staged copies, and local preview. The README is untouched. After the push: flip
   the Pages setting, confirm `/dev/` resolves and the root redirects to it.
2. **Trim.** The README cut-down plus every repointing item above. Pushed once the `/dev/`
   URLs it links to exist.

## Verification

- Step 1: `nox -s docs_build` passes `--strict` locally, then again in CI as the first step of
  `docs_deploy`. After deploy, a Playwright pass over `/dev/`: every nav entry opens, search finds a term, the four example reports open and are
  interactive, the changelog renders, the version selector shows `dev`.
- Step 2: the existing suite, with the moved rule-table test; `nox -s build` confirms the wheel
  still carries the skills; the README rendered on GitHub with every link resolving. The PyPI rendering is
  checked at the next TestPyPI rehearsal, as `releasing.md` already prescribes.

## Out of scope

- Publishing the design specs (`docs/specs/`) or any contributor documentation on the site.
- An auto-generated API reference.
- Versioning anything before 0.3.0.
- Custom domain, analytics, or announcement banners.
