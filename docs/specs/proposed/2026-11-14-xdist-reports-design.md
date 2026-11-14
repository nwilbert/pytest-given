# Reports and Lint under pytest-xdist — Design Spec

## Goal

A `pytest -n N` run writes the same report and runs the same narration lint as a serial run. Today
such a run stops with a usage error, because each worker records the scenarios it runs and none of
them reach the main process.

## Report order

The report lists scenarios in a fixed order, the same for a serial and an xdist run, instead of the
order they ran in. A reordering plugin (pytest-randomly, pytest-order) or the order of paths on the
command line no longer changes it. The sort key, applied after grouping:

1. **File** — the path in the scenario's node id, compared by path parts
   (`('tests', 'unit', 'x.py')`), case-sensitively, so every platform agrees. This is pytest's own
   default directory walk.
2. **Line** — `Scenario.source.line`, the test function's definition, so a class's methods keep
   their place in the file. A scenario whose source is in another file than its node id (a test
   inherited from a base class elsewhere) or that has no source sorts after the file's own
   scenarios.
3. **Collection index** — the scenario's position as collected, recorded in `pytest_itemcollected`
   before a reordering plugin rearranges `session.items`. It breaks the ties that remain: the cases
   of a parametrize with `group_parametrized=False`, which share a line, and the scenarios step 2
   sends to the end. Within one file the collection order does not depend on the command line. An
   item a plugin adds after collection has no index and sorts after the rest of its ties.

This lands as its own commit, before the xdist support.

## Distribution mode: `loadfile` only

Grouping a parametrized scenario needs all of its cases in one process: it re-applies each
interpolation's conversion and format spec to the raw parameter object, and turns raw values into
table cells. Raw values are arbitrary Python objects, so they cannot travel between processes.
pytest-given therefore needs a distribution mode that keeps a test function's cases on one worker.

`--dist loadfile` does: it sends whole files to a worker, splitting the node id at its first `::`.
The other modes do not:

- `load`, `worksteal` and `loadgroup` (for unmarked tests) send single tests anywhere.
- `loadscope` splits at the *last* `::`, and pytest does not escape `::` in a parametrize id, so
  `test_x[a::b]` and `test_x[c]` land in different scopes.
- `each` runs every test on every worker, often one per interpreter, so the copies can disagree on
  an outcome the report has no way to show.

When a run writes a report or lints (the condition the usage error checks today):

- **No `--dist` given** — a bare `-n N`, which xdist would turn into `load`: pytest-given switches
  it to `loadfile`. xdist prints `scheduling tests via LoadFileScheduling`, so the switch is visible.
- **`--dist loadfile` given** — runs as given.
- **Any other `--dist` given** (including `-d` / `--distload`, and a `--dist` in `addopts`) — a
  usage error before collection, naming `--dist loadfile` and that dropping `--dist` selects it.

A run that asks for neither is untouched, whatever its mode.

**Detecting "no `--dist` given".** xdist rewrites `dist` from `no` to `load` in its own
`pytest_cmdline_main`. A `pytest_cmdline_main` hook wrapper sees the option before any
implementation runs, so it records whether the user chose a mode; `pytest_configure`, once the
options are resolved, rewrites `load` to `loadfile` only when the user did not. xdist reads `dist`
again when it builds the scheduler at the end of collection, so the rewrite takes effect. pytest-given
does not import xdist for any of this.

## Data flow

**On a worker** (`hasattr(config, 'workerinput')`), session finish groups the worker's scenarios as
it does today, then — only when the run writes a report or lints — puts a JSON-shaped payload into
`config.workeroutput` instead of writing sinks or linting:

- the grouped scenarios, *including* `Step.source`, each with its collection index for the
  report order's last tie-break (every worker collects the same items in the same order);
- the registered stories and the resolved glossary;
- or, when grouping refused, the error message instead of the scenarios.

xdist's own session-finish wrapper sends `workeroutput` to the main process after pytest-given's hook
has run.

**On the main process**, an `optionalhook` implementation of `pytest_testnodedown(node, error)`
keeps each worker's payload. Session finish then merges them and continues down the existing path —
the undeclared-story warning, `ReportData`, `emit_sinks`, `run_lint` — unchanged:

- scenarios from all workers, sorted by the report order above;
- stories as the union by id, in payload order;
- the glossary from the first payload (every worker resolves it from the same modules).

The report's metadata is built on the main process, as today.

## Failure handling

- **A worker's grouping refused** — the main process reports the first worker's message as the
  report error, writes no report, and fails the run, exactly as a serial refusal does.
- **A worker went down without a payload** (a crash, or `pytest_testnodedown` with an `error`) — the
  report would miss its scenarios, so the main process refuses to write it: a report error naming
  the crashed worker, the run fails, and a previous report is discarded as for any report error.
- **"No test was selected"** is read from `session.testscollected` instead of `session.items`.
  xdist sets it on the main process from the workers' collections, whose `session.items` is always
  empty there; a serial run sets it to the same count.

## Serde

What a worker sends is a `SessionCapture` (`model/session_capture.py`): its grouped scenarios, their
collection index, the stories and the glossary. One pair in `model/serde.py` converts it —
`session_capture_to_dict`, which keeps the `serde_exclude` fields so `Step.source` travels, and
`session_capture_from_dict`, built on the private per-class readers, whose step reader reads a
`source` when present. A JSON report never carries one, so reading it there changes nothing, and
`Step.source` stays out of the report.

Not pickle: a worker's stories and glossary are `capture` subclasses that reference the user's
glossary objects, possibly of classes declared in test modules, which the main process never
imports. The dict carries the model shape only, as the JSON report does.

One pair rather than public per-class readers, so the report-schema-validation design (Pydantic,
on the `delta-report` branch) replaces exactly one reader with a `SessionCaptureDocument`; that
spec already describes it.

## Non-goals

- Distribution modes other than `loadfile` — `load`/`worksteal` would need grouping split into a
  per-case phase on the worker and a cross-case phase on the main process.
- Grouping refusals on a `-n` run that asks for no report and no lint: workers ship nothing then,
  as today.

## Touch points

- `plugin/options.py` — the cmdline wrapper, the `load` → `loadfile` rewrite, the narrowed refusal.
- A new `plugin/` module for the worker payload and the main-process merge, and
  `plugin/session.py` calling it.
- `model/session_capture.py` and `model/serde.py` — the capture and its pair.
- `docs/site/configuration/pytest-options.md` (the pytest-xdist section), the citing skill's
  "without xdist's `-n`" line, `TODO.md`, and `CHANGELOG.md` under Unreleased: an Added entry for
  this feature (it relaxes the refusal 0.5.1 shipped, so it is not breaking) and a Changed entry
  for the report order.
- `plugin/session.py` — the report-order sort, for both paths.
- Scenarios tagged `spec/xdist-reports`: the report order ignores the command-line order of paths;
  a `-n` report holds the serial run's scenarios in the same order; a bare `-n` with a report distributes by file; an explicit other `--dist` stops
  before collection; the lint sees every worker's scenarios.
