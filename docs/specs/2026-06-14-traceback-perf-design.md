# Traceback Capture Performance — Design Spec

## Goal

Cut the per-failure cost of pytest-given's traceback capture so a suite with thousands of failing scenarios completes in seconds rather than minutes. The expensive AST work that pytest's `getrepr(style='short')` does on each frame must run for *at most* the user-visible frames, never for the implementation-noise frames the renderer collapses by default.

## Scope

- In: the `pytest_runtest_makereport` path in `src/pytest_given/plugin.py` that captures failure tracebacks for the JSON report.
- In: a behavioral change to the parser/classifier (`src/pytest_given/capture/traceback.py`) and the storage shape (`ErrorInfo.frames`) so internal frames don't ride in the JSON by default.
- In: an opt-in CLI flag to retain all frames (debugging escape hatch).
- Out: rendering changes. The renderer already collapses `is_internal=True` frames; once they're dropped at capture, the renderer needs no change.
- Out: skip-reason rendering (already structured, no traceback).
- Out: switching away from pytest's `excinfo.getrepr(style='short')` to a fully custom traceback formatter (deeper change, separate decision — see Alternatives).

## Background

Profiling a suite of 374 items with ~326 failures (`benchmarks/test_large_scenarios.py` at `--count 100` with simulated failures, cf. `benchmarks/bench.py`):

```
27.85s total
  └─ pytest_runtest_makereport               26.77s   (96%)
     └─ excinfo.getrepr(style='short')       26.35s
        └─ repr_traceback_entry × 2445       26.23s
           └─ _getentrysource                25.60s
              └─ getstatementrange_ast       25.04s
                 └─ ast.walk × 8.5M          15.77s
                 └─ ast.iter_child_nodes × 17M
```

Per-failure, `getrepr(style='short')` invokes `getstatementrange_ast` once **per frame** — pytest walks the AST of each frame's source file to find the enclosing statement's line range (needed for multi-line statement display in short-style output). For the same failure, pytest's `tbfilter=True` (the default) only filters frames carrying `__tracebackhide__`. Pluggy dispatchers and pytest-given's `@scenario` wrapper do not consistently set that marker, so they survive into the formatter and each pays the full AST cost.

The test file's AST size scales with the number of scenarios (`benchmarks/test_large_scenarios.py` is ~1.6 MB / ~50k lines at the full 12k-item size). The number of failures also scales with the suite size. The combination produces an effective O(N²) cliff: at N=100 the plugin adds 10s of overhead (`--tb=no` baseline: 0.6s without plugin → 10.55s with plugin); at N=12k the same path took ~80 minutes of CPU and never completed.

Vanilla pytest with `--tb=no` does *not* pay this cost — pytest skips traceback formatting entirely when the user opts out. pytest-given calls `getrepr(style='short')` unconditionally to populate the JSON report, so it pays the cost regardless of `--tb`.

The existing [Traceback Verbosity](2026-06-07-traceback-verbosity-design.md) spec landed structured frames with an `is_internal` flag and a renderer toggle. Internal frames are classified but still stored. This spec proposes to drop them at capture time and, while we're at it, drop them *before* pytest formats them — which is what eliminates the AST cost.

## Approach

Two changes, both inside `src/pytest_given/capture/traceback.py` and `src/pytest_given/plugin.py`. They compound: change A is the perf fix; change B is the storage/size cleanup. Either alone reduces wall time; together they make the plugin's overhead near-zero on failures.

### A. Pre-filter `excinfo.traceback` before calling `getrepr`

`ExceptionInfo.traceback` is a `_pytest._code.code.Traceback` of `TracebackEntry` objects. It's iterable, indexable, and its `.cut()` / `.filter()` mutators are part of pytest's public surface (used by pytest itself for `tbfilter`). Each `TracebackEntry` exposes `.path`, `.lineno`, and `.frame.code` cheaply — without triggering AST work. AST work happens later, inside `getrepr` → `repr_traceback_entry` → `_getentrysource` → `getstatementrange_ast`, **once per surviving entry**.

The fix: drop internal entries from the traceback *before* `getrepr` ever sees them.

```python
# pytest_given/capture/traceback.py
def _is_internal_entry(entry: TracebackEntry) -> bool:
    path = str(entry.path).replace('\\', '/')
    return _is_internal(path)  # reuse the existing classifier

def filter_internal_frames(excinfo: ExceptionInfo) -> None:
    """Mutate excinfo.traceback so getrepr only formats user frames."""
    excinfo.traceback = excinfo.traceback.filter(
        lambda entry: not _is_internal_entry(entry)
    )
```

`_is_internal` (already in `capture/traceback.py`) is the single source of truth for both pre-filtering and post-parsing classification. `filter_internal_frames` lives in the same module, so `_is_internal` stays module-private — only `filter_internal_frames` is imported by `plugin.py`. Both callers pass a full normalized path: `_flush` already classifies on the pre-`_portable_path` path, and the pre-filter classifies on `entry.path`, so the two views agree.

Call from `pytest_runtest_makereport` before `getrepr`:

```python
if call.when in ('setup', 'call') and call.excinfo is not None:
    if not item.config.getoption('given_all_frames'):
        filter_internal_frames(call.excinfo)
    error_repr = call.excinfo.getrepr(style='short')
    ...
```

This cuts AST work proportional to the share of internal frames in each failure's stack — in the benchmark suite, ~5 of 7 frames per failure are internal (pluggy + `_pytest/runner.py` + `_pytest/python.py` + pytest-given's `decorators.py`), so the AST cost drops by roughly 70%.

The pre-filter inherits `_is_internal`'s classification rule: it matches `_pytest`/`pluggy` frames by their `/site-packages/` prefix (plus the `capture/decorators.py` suffix). This holds for the uv-managed benchmark venv where those dependencies live under `site-packages`; a source/editable checkout of pytest itself would not be classified internal, but that is not the target environment and the same limitation already governs post-parse classification today.

Pytest's own filtering (`tbfilter=True`) is not enough because pytest's heuristic does not match pluggy dispatchers or our `@scenario` wrapper. The plugin already classifies these correctly via `_is_internal`; we just need to apply that classification *earlier*.

**Safety:** `Traceback.filter` returns a new `Traceback`; assigning back is the documented pattern (pytest itself does this in `ExceptionInfo._getreprcrash`). Mutating `excinfo.traceback` does not affect the exception's `__traceback__` (Python's native one) — only pytest's view of it.

### B. Drop internal frames at storage; opt-in flag to retain

`parse_short_repr` already classifies frames as `is_internal`. With change A applied, the parsed frames are already user-only — so this becomes "internal frames don't ride in the JSON at all by default."

If A and B both ship: internal frames are filtered before `getrepr`, so the parser never sees them, so the JSON never contains them. The opt-in path (described below) skips A's filter, lets all frames through to the parser, and stores them all with their `is_internal` flag intact.

Surface a CLI flag and matching ini key:

```
--given-all-frames     Store internal pluggy/_pytest/pytest-given frames in the
                       JSON report. Slower on large failing suites — only set
                       when debugging the plugin or pytest itself.
```

Default: off. When off, both A's pre-filter and the parser's post-classification cooperate to keep internals out of storage entirely.

When on:
- A's pre-filter is skipped → `getrepr` formats all frames → AST cost returns.
- The parser still classifies, so the renderer's existing "Show internal frames" toggle continues to work on the full set.

This is the smallest surface that preserves the existing debugging affordance (frames are *available* in the report when asked for) without paying for it by default.

### C. Short-circuit skips before `getrepr`

The Scope line "skips already structured, no traceback" was aspirational, not actual: a skip raises `Skipped` (at setup for `mark.skip`/`skipif`, at call for an in-body `pytest.skip()`), which arrives at `pytest_runtest_makereport` as `call.excinfo` and was formatted like any failure. Its traceback is entirely skip machinery (`pluggy` → `_pytest/skipping.py`), so A's pre-filter reduced it to empty and the keep-original guard restored *all* of it — the scenario ended up `skipped` yet carried a full internal traceback, and every skip paid the `getrepr` AST cost (measured: ~112s of `getrepr` for 2000 skips, 18k `getstatementrange_ast` calls).

Fix: detect the skip in `makereport` (`call.excinfo.errisinstance(pytest.skip.Exception)`) and return before `getrepr`. Not gated on `--given-all-frames` — a skip never wants a traceback. The scenario's structured `skip_reason` (set in `logreport`) is unaffected; `error` is now `None`. This makes the Scope line true and removes the skip-path collapse (`getrepr` for skips drops to zero).

### Schema impact

`TracebackFrame.is_internal` becomes vestigial in the default-storage shape (always `False`). Two options:

1. Keep the field. Cheap, preserves round-trip parity with the opt-in path. Renderer continues to treat `is_internal=True` specially.
2. Drop the field and re-derive at render time when the opt-in flag is set.

Recommend option 1 — the field costs nothing on the wire (one bool per frame) and removing it complicates the opt-in path. Pre-release status [[project-prerelease-status]] would allow either; option 1 is just smaller.

## Verification

`benchmarks/bench.py` already drives the relevant matrix. Acceptance:

- At N=4000 functions with 5 fixed failures, total time stays within 1.5× the all-passing baseline (currently the failing run at full size takes a half-hour+; fixed should be a couple of seconds over the all-passing 8s).
- `pytest_runtest_makereport` cumulative time in the cProfile output drops below the noise floor on the all-passing suite, and below 1s on a suite with ~50 failures.
- The handful of fixed-failure scenarios in `benchmarks/test_large_scenarios.py` still render in `benchmarks/large-scenarios.html` with the expected user frames present and internals absent.
- With `--given-all-frames`, the JSON for those failures contains internal frames classified as `is_internal=True` and the renderer's "Show internal frames" toggle reveals them.

Playwright verification on `benchmarks/large-scenarios.html` after regenerating: open one of the `test_fixed_failure_*` scenarios in each rendering site (step error, parametrize-case error, scenario error) and confirm the user-frame display unchanged.

### Measured outcome

Change A landed. Measured on a suite of **5000 failing `@scenario` tests spread across 200 normal-sized files** (the realistic shape — failures across many small modules, not one giant file):

| run | wall |
|---|---|
| vanilla pytest, `--tb=no`, no plugin | 20.5s |
| pytest-given, `--given-all-frames` (pre-filter off) | **278.5s** |
| pytest-given, default (pre-filter on) | **19.9s** |

The plugin's failure-path overhead drops from **~14× vanilla to parity with vanilla** — the collapse is gone. Per-failure the pre-filter removes ~5 of every ~7 formatted frames; at N=2000 in the project benchmark, `repr_traceback_entry` calls fall 132→41 and `getstatementrange_ast` calls 125→34.

The one case where change A alone leaves a residual is the *benchmark's own* single-giant-file shape: with all failing frames pointing into one ~1 MB module, the retained user frames still cost one whole-file AST parse each (O(failures), 407s→242s = 1.68×). That residual is precisely what the "build our own frame list" alternative below would remove; it does not appear in realistically-structured suites, where the retained per-failure user frame is a cheap small-file parse.

## Alternatives considered

**Build our own frame list from `excinfo.traceback` without calling `getrepr`.** Iterate the traceback, read `.path`/`.lineno`/`.frame.code`, fetch one source line via `linecache`. Eliminates AST work entirely (not just for internal frames). Trade-off: we lose pytest's statement-range detection — multi-line statements display as a single line — and we duplicate enough of pytest's formatting that future pytest changes (e.g. better tokenization) wouldn't carry over. Worth revisiting if A doesn't go far enough; out of scope here.

**Limit frames via `getrepr` kwargs.** `getrepr` accepts no "stop after N user frames" parameter. The existing `tbfilter` is the only knob and it's already on. No leverage here without touching the traceback object.

**Cache the AST per source file.** Pytest's `getstatementrange_ast` parses each file on every call (`compile` shows up in the profile with 3.9s tottime over 1500 calls — once per call site, not per file). Memoizing would help but lives in pytest's code, not ours; we'd need a monkeypatch. Pre-filtering achieves the same effect with less coupling.

**Move work to `pytest_sessionfinish`.** Defer all `getrepr` calls until session end. Doesn't help — the same work still runs, just later. And it would block sessionfinish on AST work for every failure, making interactive feedback worse.
