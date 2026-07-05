# Markdown Report Output — Design Spec

## Goal

An agent-facing Markdown rendering of the report, so an AI agent (or a human at a
terminal) can **read back a run's narration in one command** without opening a
browser or parsing JSON. The narration — not the code — is pytest-given's
product, and today it's only legible as HTML. Markdown closes the agent's
feedback loop: run the tests you just touched, read the prose the plugin
produced, confirm it reads as an honest spec.

```bash
pytest tests/test_hotel_booking.py::test_select_suite --given-md    # → fenced MD on stdout
pytest --given-md=report.md                                          # → written to a file
```

Selection is **pytest's job**, not the renderer's: whatever the run collected
(`node-id`, `-k`, `--lf`) is what gets narrated. The renderer has no filter flags
of its own in v1 (see [Out of Scope](#out-of-scope)).

## Background

pytest-given emits an interactive HTML report and a JSON data file. HTML is the
right artifact for humans; JSON is machine-readable but unreadable as a *story*.
Neither serves an agent that has just generated or edited a test and wants to
verify the resulting narration reads truthfully. Doing that today means
regenerating HTML and driving it in a browser (Playwright) — a browser-shaped
loop for what is fundamentally a text question.

Markdown fills that gap: it is the one form an agent can produce and read in the
same step. It also diffs cleanly, so the same rendering doubles as a
human-readable behavioural diff in review, though the committed-artifact use is
not the focus here — the agent self-check loop is.

This feature ships alongside two related changes that share its motivation
(reducing overhead on ordinary runs):

- **Outputs become opt-in.** Today the JSON file is written on *every* run the
  plugin is loaded for. Most runs are ordinary test runs that want no report at
  all, so the new default is **silent**: bare `pytest` writes nothing.
- **One rendering pipeline.** MD must not become a second code path. All
  renderers consume the same in-memory model, so HTML and MD stay aligned and
  the JSON *file* becomes an independent, optional persistence step.

## Approach

### One pipeline, three sinks

The canonical intermediate is the report **dict** (`report_to_dict(report)`),
exactly as today. Every renderer consumes the typed model
(`report_from_dict(dict) -> ReportData`); the JSON file is just that dict dumped
to disk. There is deliberately **no** `json_renderer`: JSON is the serialized
model (`model/serde.py`), not a derived view. HTML and MD are the two renderers,
each consuming that serialization — so a JSON file on disk can be re-rendered to
either format after the fact (see [Standalone CLI](#standalone-cli)).

At `pytest_sessionfinish` the plugin already builds the in-memory `ReportData`
(plugin.py:561). The new flow:

1. Build `ReportData` in memory (unchanged).
2. Compute `report_dict = report_to_dict(report)` once.
3. For fidelity, renderers run on `report_from_dict(report_dict)` — i.e. the
   model is round-tripped through serde even in-memory, so an in-run render is
   byte-identical to a render of the saved JSON via the standalone CLI. This is
   what keeps HTML, MD, and the CLI from drifting apart. The round-trip is cheap
   (scenarios have few steps).
4. Each requested sink fires independently:
   - `--given-json[=PATH]` → write `report_dict` to disk.
   - `--given-html[=PATH]` → `render_html(report)` (now fed the in-memory model,
     no longer re-reading the JSON file).
   - `--given-md[=PATH|­stdout]` → `render_md(report)`.

Sinks are independent and combinable: `pytest --given-json --given-html
--given-md=report.md` produces all three in one run. (The nox `examples` session
relies on this — it writes HTML and JSON together.)

`render_html` is refactored to take a `ReportData` (or the dict) rather than a
`json_path`; loading-from-file moves to the standalone CLI, which is the only
caller that starts from a file.

### Rendering — always on; writing — opt-in (depth 1)

Step capture (the `given`/`when`/`then` recording, source capture, placeholder
validation, phase check) stays **on for every run**, unchanged. Only the
*writes and renders* are gated: when no output flag is set, sessionfinish builds
the model and stops. This keeps all validation (broken t-strings, misplaced
`Template`, phase violations) live on ordinary runs — the plugin is silent about
*output*, not about *misuse*. Skipping capture itself was considered and
rejected (it would defer validation to render time); see
[Out of Scope](#out-of-scope).

### Stdout vs. file

`--given-md` takes an optional value:

- **bare `--given-md`** → render to **stdout**, wrapped in HTML-comment fences so
  an agent can slice the block out of pytest's surrounding terminal noise
  (progress, captured output, tracebacks):

  ```
  <!-- pytest-given:md:start -->
  # pytest-given — hotel-booking
  ...
  <!-- pytest-given:md:end -->
  ```

  The fences are invisible when the Markdown is rendered. Emitted from
  `pytest_terminal_summary` (like the phase-check summary), so it lands *after*
  pytest's own end-of-run output as a clean trailing block.
- **`--given-md=PATH`** → write the same content (no fences) to a file; nothing
  on stdout.

This is the "option 3" resolution: fenced stdout is the agent default (one
command, no file to clean up), the file is the escape hatch when stdout is too
noisy or the render should persist.

## Markdown format

One heading per scenario. A run spanning the interesting cases:

```markdown
# pytest-given — hotel-booking

## ✓ Buy coffee
`tests/test_coffeeshop.py::test_buy_coffee` · billing, happy-path

- **given** a coffee machine
- **when** I insert $2
- **then** I get a coffee
  - 📎 Machine state — `{"coffees": 9, "price": 2}`

## ✓ Pricing · 3 cases
`tests/test_coffeeshop.py::test_pricing`

- **when** I insert ${euros}
- **then** can_buy is {expect}

  | euros | expect | |
  |---|---|---|
  | 1 | False | ✓ |
  | 2 | True | ✓ |
  | 3 | True | ✓ |

## ✗ Sold out is rejected
`tests/test_coffeeshop.py::test_sold_out`

- **given** a machine that has sold its last coffee
- **when** a customer tries to buy a coffee
- **then** the machine reports it is sold out  **← FAILED**
  > ValueError: not sold out
  > test_coffeeshop.py:88 in test_sold_out

## ⤼ Carol selects a suite · skipped
`tests/test_hotel_booking.py::test_select_suite` — reason: needs fixture data

- **when** «Carol» searches for a «Room»
```

Rules:

- **Heading** = status glyph + scenario name. `✓` passed, `✗` failed, `⤼`
  skipped. Glyph + word (`· skipped`, `· N cases`) is scannable *and* greppable.
- **Subtitle line** = backticked node id, then ` · ` tags (omitted when none).
- **Steps** = one bullet each, phase in bold, narration as plain text; nested
  steps indent one level per depth.
- **Placeholders** resolved exactly as the HTML renderer resolves them: t-string
  values filled in; a `Template` in a parametrized scenario shows `{col}` in the
  merged/heading view and the concrete value per row.
- **Glossary term refs** render as `«Term»` — plain text, but the guillemets
  preserve that it *was* a term (HTML shows a kind-coloured pill; MD has no
  tooltip). Markers only; no kind/definition inline.
- **Parameter table** = a GFM pipe table (`|` delimiters), one row per case,
  with a trailing status gutter (blank header) carrying the per-case glyph.
- **Attachments** = a `📎 label — \`value\`` bullet nested under their step;
  strings verbatim, other types as compact JSON.
- **Failure** = the failing step is marked `**← FAILED**`; beneath it a
  *minimal* blockquote — the exception's type+message and the single
  user-frame `file:line in func` where it raised. The full (frame-filtered)
  traceback stays in pytest's own output and the HTML report; the MD carries the
  narrative, not the debugger. (See [Open Questions](#open-questions).)
- **Skip** = ` — reason: <text>` on the subtitle line; steps recorded before the
  skip still list.
- **Stories / Glossary** tabs from the HTML report are **not** rendered as MD
  sections in v1 — the per-run agent report is scenario-narration only (see
  [Out of Scope](#out-of-scope)).

## Standalone CLI

The same renderer is reachable from `pytest-given report`, fed by
`report_from_dict` from a saved JSON file (this is the one path that legitimately
starts from disk):

```bash
pytest-given report given-report/report-data.json --format md          # → stdout
pytest-given report given-report/report-data.json -o report.md         # → file (format inferred from .md)
```

`--format` defaults to inference from the `-o` extension (`.html` / `.md`),
falling back to `html` when writing to stdout without `-o` for back-compat, and
is overridable explicitly. This falls out of the shared `render_md(report)`
function almost for free and enables the self-report attachment idea (below).

## Configuration

All output sinks become opt-in and share one option shape: each takes an
optional value — **bare** turns the sink on at its default target, **`=PATH`**
redirects it, **absent** leaves it off. This collapses the current two-option
HTML surface (`--given-html` toggle + `--given-html-output` path) into a single
option, and drops `--given-html-output` entirely.

| Flag | Bare | `=PATH` | Absent |
|---|---|---|---|
| `--given-md` | render to **stdout** (fenced) | write file | off |
| `--given-json` | write `given-report/report-data.json` | write file | off (**was: always written**) |
| `--given-html` | write `given-report/report.html` | write file | off |

Notes:

- **`--given-md` bare goes to stdout**; `--given-json`/`--given-html` bare go to
  their default file paths. The asymmetry is deliberate: MD's purpose is the
  one-command stdout self-check, while HTML (a large self-contained blob) and
  JSON are artifacts you persist. A future `--given-json=-` could add
  stdout-for-piping; not in v1.
- `--given-html` no longer implies a JSON file — it renders from the in-memory
  model. Ask for JSON explicitly with `--given-json` if you also want the data
  file.
- Mechanically each is a pytest `parser.addoption` with argparse
  `nargs='?'` and a `const` sentinel distinguishing "given bare" from "absent"
  (`default`). `--given-html` changes from `store_true` to this shape.
- Project-level defaults via ini keys (`given_md = ...`) are **out of scope**
  for v1; the CLI flags suffice, and this repo's nox sessions pass them
  explicitly. Add later if wanted, mirroring `given_source_link`.

## Implementation Touch Points

| File | Change |
|---|---|
| `src/pytest_given/report/md_renderer.py` (new) | `render_md(report: ReportData) -> str`. Walks the same typed dataclasses as the HTML renderer; a single narration formatter dispatching on the `NarrationPart` variants (`match`/`case`), mirroring the HTML `narration` filter but emitting `«term»` / plain text. Pure, no pytest imports, under `report/` (depends only on leaf `model/`). |
| `src/pytest_given/report/html_renderer.py` (**renamed** from `renderer.py`) | Rename `report/renderer.py` → `report/html_renderer.py` for symmetry with `md_renderer.py`; update the `render_html` import in `plugin.py`, the `cli.py` import, and the Architecture bullet in `AGENTS.md`. Refactor `render_html` to accept a `ReportData` (or dict) instead of a `json_path`; drop the internal file read. |
| `src/pytest_given/plugin.py` | `pytest_addoption`: put `--given-json`, `--given-html`, and new `--given-md` on the shared `nargs='?'` opt-in shape; **remove `--given-html-output`** (its path folds into `--given-html=PATH`). `pytest_sessionfinish`: build the model, compute the dict once, round-trip through serde, then fire each requested sink; write nothing when none requested. `pytest_terminal_summary`: emit the fenced MD block when `--given-md` is bare (stdout). |
| `src/pytest_given/report/cli.py` | Add `--format {html,md}` (default inferred from `-o` extension); dispatch to `render_md` / `render_html`. |
| `README.md` | Document `--given-md`; update the "JSON report is **always written**" language to opt-in; note `--given-html` no longer writes JSON and that `--given-html-output` is gone (path folds into `--given-html=PATH`). Rework the pytest-options table for the unified opt-in shape and the new MD row. |
| `AGENTS.md` | New "Handling report output" section aimed at agents: the `--given-md` stdout loop as the primary way to read a run's narration; the `jq`-on-`--given-json` fallback for filtering (see below). Note the outputs are now opt-in. |
| `noxfile.py` | The `examples` / `self_report` sessions keep writing HTML+JSON explicitly — now `--given-html=<path> --given-json=<path>` (the old `--given-html-output` is gone), since neither sink is implied. The committed JSON is **deliberately retained** even though HTML no longer needs it on disk: it is the human-readable serialization of the output schema, so a schema change surfaces as a legible diff in review (the HTML diff is an opaque blob). No MD is committed for the examples — MD is the ephemeral agent view, not an example artifact. |

### Agent guidance (AGENTS.md)

Short section, MD-first:

- **Read a run's narration:** `pytest <selection> --given-md` → slice the block
  between the `pytest-given:md:*` fences. Select scenarios with pytest's own
  args; the renderer narrates whatever collected.
- **Filter by tag / glossary term / status:** not an MD feature — drop to the
  structured data. `pytest --given-json` then `jq` over `report-data.json`
  (scenarios carry `tags`, `status`, and term refs). MD is the readable view;
  JSON is the queryable one.

## Test Coverage

Unit tests for `report/md_renderer.py` (`tests/unit/report/test_md_renderer.py`)
— build `ReportData` / `Scenario` models directly and assert on the string:

- Scenario heading carries the right glyph per status; tags appended, omitted
  when empty.
- Nested steps indent per depth; phase bolded; narration text present.
- A t-string step renders resolved values; a `Template` parametrized step shows
  `{col}` in the heading view and per-row values in the table.
- Glossary term refs render as `«Term»`.
- Parametrized scenario renders a GFM table with a per-row status gutter.
- Attachments render nested under their step (string verbatim; dict as JSON).
- A failing step is marked and carries the minimal exception line + source
  location; no full traceback.
- A skipped scenario shows its reason and lists any pre-skip steps.

Integration tests (`tests/integration/test_plugin.py`, via `pytester`):

- Bare `pytest` (no output flag) writes **no** files and prints no MD.
- `--given-md` prints the fenced block on stdout; content matches the model.
- `--given-md=PATH` writes an unfenced file and prints nothing.
- `--given-html` alone produces HTML and **no** JSON file; `--given-json` alone
  produces the JSON file.
- Capture/validation still runs when silent: a misplaced `Template` / broken
  t-string still raises on a bare `pytest` run.

Serde round-trip: an in-run MD render equals a CLI render of the saved JSON for
the same suite (guards the fidelity claim).

CLI tests (`tests/unit/report/test_cli.py`): `--format md` to stdout and to a
`.md` file; format inferred from the `-o` extension.

## Out of Scope

- **Renderer-side filter flags** (`--given-md-tag`, `--given-md-term`,
  status filters). pytest's own selection covers node/name/last-failed; the two
  things it *can't* express — tag and glossary term — are the only candidates,
  and even those defer to the `jq`-on-JSON fallback for v1. Documented as future
  work: add `--given-md-tag` / `--given-md-term` if the fallback proves
  insufficient.
- **Stories / Glossary MD sections.** The HTML report's Stories and Glossary
  tabs are not rendered in the per-run agent MD. Could be added as trailing
  sections later; the agent self-check loop is about scenario narration.
- **Full tracebacks in MD.** Only the minimal exception line + source location.
  The full frame-filtered traceback lives in pytest output and the HTML report.
- **Skipping capture on silent runs (depth 2).** Rejected: it would defer
  placeholder/phase validation to render time. Capture stays on; only writes are
  gated.
- **Committed-artifact workflow.** MD is designed for the ephemeral stdout
  self-check. Committing a `report.md` and diffing it in review is a natural
  by-product (`--given-md=PATH`) but not a design driver; deterministic ordering
  guarantees beyond what the model already provides are not pursued here.
- **ini defaults for the output flags.** CLI-only in v1.

## Open Questions

1. **Self-report attachment (dogfooding).** Once `render_md` exists, the
   self-report's `then` steps could `attach(...)` the MD rendering of the very
   scenario being narrated — the report describing its own output. Appealing but
   recursive and scope-adjacent; deferred to a follow-up once the format is
   settled.
2. **Failure fidelity.** v1 renders a one-line exception + single source
   location. If agents find they routinely need more (the assertion's compared
   values, a couple of frames), a `--given-md-traceback` opt-in could add the
   frame-filtered trace. Start minimal.
3. **Status gutter header.** The parameter table's status column ships with a
   blank header (reads as a gutter). A literal `status` header is the
   alternative if the blank cell renders oddly in some viewers.
4. **Stdout emission hook.** Emitting from `pytest_terminal_summary` places the
   MD after pytest's summary. If that ordering interleaves awkwardly under `-v`
   or plugins that also write late, printing from `sessionfinish` (before the
   summary) is the alternative. Terminal-summary chosen to match the phase-check
   precedent.
