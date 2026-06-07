# Traceback Verbosity — Design Spec

## Goal

Failure tracebacks in the HTML report currently dump every frame pytest's `excinfo.getrepr(style='short')` produces, including pluggy hook dispatchers, pytest's own runner internals, and pytest-given's `@scenario` wrapper. The user-relevant frame is buried at the bottom under ~15 lines of plumbing.

Trim these "internal" frames by default, and expose a per-error "Show internal frames" toggle. The trailing `E   <error>` summary stays visible at all times.

## Scope

- In: failure tracebacks captured in `pytest_runtest_makereport` (`call.excinfo`) — both call-time test failures and setup-time fixture errors.
- In: structured frames in the JSON schema (replacing the opaque `diff` string).
- In: per-error Alpine toggle at every render site (step error, parametrize-case error, scenario error).
- Out: skip-reason rendering — already structured separately, no traceback involved.
- Out: configurable internal-frame patterns. Strict hardcoded list for v1; revisit if real cases demand it.
- Out: source links from frame lines. The scenario-level source link already covers the common case, and pluggy/site-packages paths are not useful targets.

## Background

`src/pytest_given/plugin.py:326-330` captures failures with:

```python
if call.when in ('setup', 'call') and call.excinfo is not None:
    error_repr = call.excinfo.getrepr(style='short')
    message = str(call.excinfo.value)
    diff = str(error_repr)
    collector.fail_scenario(message=message, diff=diff)
```

`diff` is the full short-style repr — a multi-line string with one block per frame:

```
<path>:<lineno>: in <funcname>
    <code line>
    <optional caret line>
```

…followed by a trailing `E   <error message>` block (one or more lines).

`ErrorInfo.diff` (`src/pytest_given/model/schema.py:93-95`) stores this opaquely. The template (`src/pytest_given/report/templates/report.html.j2`) renders it via `<pre class="error-diff">{{ ... }}</pre>` at three sites: step error (line 110), parametrize-case error (line 188), scenario error (line 201).

Pytest's `tbfilter=True` (the `getrepr` default) only removes frames whose locals or modules carry `__tracebackhide__`. Pluggy and pytest's runner do not consistently mark these in the path our wrapper takes, so frames leak through. Adding `__tracebackhide__ = True` to the `@scenario` wrapper would hide that single frame but not the pluggy/_pytest cascade — structured parsing + classification is the durable fix.

Pre-release status ([[project-prerelease-status]]) permits dropping `ErrorInfo.diff` outright; no migration hedge.

## Approach

### Data model (`src/pytest_given/model/schema.py`)

Add a frame dataclass and restructure `ErrorInfo`:

```python
@dataclass(frozen=True)
class TracebackFrame:
    path: str          # POSIX-normalized; relative to rootdir when possible, else as-emitted
    lineno: int
    func: str          # the name after "in "
    code: str          # the code/caret lines for this frame, joined with '\n', no trailing newline
    is_internal: bool

@dataclass
class ErrorInfo:
    message: str
    frames: list[TracebackFrame] = field(default_factory=list)
    error_tail: str | None = None   # the trailing `E   ...` block, joined with '\n'
```

`diff` is removed. Re-export `TracebackFrame` from `src/pytest_given/model/__init__.py`.

### Parser (`src/pytest_given/capture/traceback.py`, new module)

```python
def parse_short_repr(text: str) -> tuple[list[TracebackFrame], str | None]: ...
```

Algorithm:
1. Split `text` into lines (preserve indentation).
2. Iterate; a line matching `^(?P<path>.+?):(?P<lineno>\d+): in (?P<func>.+)$` opens a frame.
3. Subsequent lines that do not start with `E   ` and are not another frame header become the frame's `code` (joined with `\n`, leading whitespace preserved — pytest emits the failing source indented).
4. A run of lines starting with `E   ` (after the last frame) becomes `error_tail` (joined verbatim, including the `E   ` prefix).
5. If no frame headers match, return `([], text)` — empty frames, full text as tail. Information is preserved.

`is_internal(path)` (private helper, normalize backslashes to `/` before matching):
- `/site-packages/_pytest/` substring
- `/site-packages/pluggy/` substring
- endswith `/pytest_given/capture/decorators.py`

Path normalization for storage: also convert backslashes to `/` in the stored `path` field. The report is consumed cross-platform; consistent separators simplify the renderer and any future analysis.

### Capture (`src/pytest_given/plugin.py`)

Replace the body of the failure branch in `pytest_runtest_makereport`:

```python
if call.when in ('setup', 'call') and call.excinfo is not None:
    error_repr = call.excinfo.getrepr(style='short')
    message = str(call.excinfo.value)
    frames, tail = parse_short_repr(str(error_repr))
    collector.fail_scenario(message=message, frames=frames, error_tail=tail)
```

### Collector (`src/pytest_given/capture/collector.py`)

Replace `diff: str | None = None` parameters with `frames` + `error_tail`:

```python
def fail_scenario(
    self,
    message: str,
    frames: list[TracebackFrame] | None = None,
    error_tail: str | None = None,
) -> None: ...

def fail_current_step(
    self,
    message: str,
    frames: list[TracebackFrame] | None = None,
    error_tail: str | None = None,
) -> None: ...
```

Internally construct `ErrorInfo(message=..., frames=frames or [], error_tail=error_tail)`.

### Serde (`src/pytest_given/model/serde.py`)

Encode/decode `ErrorInfo` with the new shape:

```json
{
  "message": "assert 10 == 20",
  "frames": [
    {"path": "examples/test_examples.py", "lineno": 143, "func": "test_failing",
     "code": "    assert machine['coffees'] == 20", "is_internal": false}
  ],
  "error_tail": "E   assert 10 == 20"
}
```

`frames` always present (possibly empty); `error_tail` is `null` when absent.

### Rendering (`src/pytest_given/report/templates/report.html.j2`)

Introduce a `{% macro render_error(error) %}` at the top of the template, alongside the existing `render_step` macro. Replace all three inline `error-block` snippets (step, parametrize-case, scenario) with a `{{ render_error(...) }}` call.

```jinja
{% macro render_error(error) -%}
  {%- set internal_count = error.frames | selectattr('is_internal') | list | length -%}
  <div class="error-block"{% if internal_count %} x-data="{ showInternal: false }"{% endif %}>
    <div class="error-message">{{ error.message }}</div>
    {%- if internal_count -%}
      <button class="error-toggle" type="button" @click="showInternal = !showInternal">
        <span x-show="!showInternal">Show {{ internal_count }} internal frame{{ '' if internal_count == 1 else 's' }}</span>
        <span x-show="showInternal" x-cloak>Hide internal frames</span>
      </button>
    {%- endif -%}
    {%- if error.frames -%}
      <div class="error-frames">
        {%- for f in error.frames -%}
          <div class="error-frame{% if f.is_internal %} error-frame-internal{% endif %}"
               {%- if f.is_internal %} x-show="showInternal" x-cloak{% endif -%}>
            <div class="error-frame-loc">{{ f.path }}:{{ f.lineno }}: in {{ f.func }}</div>
            <pre class="error-frame-code">{{ f.code }}</pre>
          </div>
        {%- endfor -%}
      </div>
    {%- endif -%}
    {%- if error.error_tail -%}<pre class="error-tail">{{ error.error_tail }}</pre>{%- endif -%}
  </div>
{%- endmacro %}
```

Notes:
- `x-data` is only emitted when there's at least one internal frame, so error blocks with no plumbing (parser fell back) don't pay for an Alpine scope.
- `x-cloak` prevents a flash of internal-frame content before Alpine mounts.
- The macro takes only `error`; no scenario-loop indices are needed because Alpine `x-data` scopes the `showInternal` state per element.

### Styles (`src/pytest_given/report/templates/styles.css`)

Add:
- `.error-toggle` — small inline button, muted accent, hover state. Reuses an existing button style if one exists.
- `.error-frames` — vertical stack with consistent spacing.
- `.error-frame` — user-frame container; subtle background, left border accent.
- `.error-frame-internal` — internal-frame container; lower-contrast text, dashed-or-thinner border to visually de-emphasize.
- `.error-frame-loc` — monospace, slightly bolder than code.
- `.error-frame-code` — monospace `<pre>` for the code/caret block; preserves whitespace.
- `.error-tail` — monospace `<pre>` for the `E   ...` block, accented with the error color to draw the eye.

Exact tones are picked from existing palette tokens in `styles.css`; this spec doesn't pin RGB values.

### JSON shape change

The serialized `error` object now carries `frames` (array) and `error_tail` (string or null) instead of `diff` (string). External JSON consumers must update — acceptable per pre-release status.

## Components touched

- `src/pytest_given/model/schema.py` — `TracebackFrame` dataclass, `ErrorInfo` field changes.
- `src/pytest_given/model/serde.py` — encode/decode the new fields, drop `diff`.
- `src/pytest_given/model/__init__.py` — export `TracebackFrame`.
- `src/pytest_given/capture/traceback.py` — new module: `parse_short_repr`, internal-frame classifier.
- `src/pytest_given/capture/__init__.py` — re-export `parse_short_repr` if other modules need it (likely just the plugin).
- `src/pytest_given/capture/collector.py` — `fail_scenario` / `fail_current_step` signature changes.
- `src/pytest_given/plugin.py` — call parser, pass structured fields through.
- `src/pytest_given/report/templates/report.html.j2` — `render_error` macro, three call-site replacements.
- `src/pytest_given/report/templates/styles.css` — new error-frame and toggle rules.
- `examples/report-data.json` and `examples/report.html` — regenerate via `uv run nox -s examples`.

## Error handling

- Parser fallback: when `parse_short_repr` cannot find any frame headers, it returns `([], text)` — the original text lands in `error_tail` and renders verbatim. No silent data loss.
- The classifier is total: every parsed frame gets a boolean `is_internal`. Unknown paths default to `is_internal=False` (user-visible) — the safer default; a missed internal frame is uglier output, but never a hidden bug.
- Template branches handle `error.frames == []` (no frames block rendered) and `error.error_tail is None` (no tail block) independently.

## Testing

- **Unit** `tests/unit/capture/test_traceback_parser.py` (new):
  - Multi-frame short-style repr with trailing `E   ` tail → exact expected `(frames, tail)`.
  - Single-frame repr → one frame, correct tail.
  - Caret/highlight rows inside a frame's code block are preserved verbatim.
  - Multi-line `E   ` tail (assertion-rewriting expanded output) is captured fully.
  - No frame headers (e.g. degenerate input) → `([], original_text)`.
  - Empty string → `([], None)`.
- **Unit** `tests/unit/capture/test_traceback_parser.py` classifier cases:
  - `/site-packages/_pytest/runner.py` → internal.
  - `/site-packages/pluggy/_hooks.py` → internal.
  - Windows-style path `...\site-packages\_pytest\...` → internal (normalized).
  - Path ending in `/pytest_given/capture/decorators.py` → internal.
  - User path `tests/test_billing.py` → not internal.
  - Sibling third-party path `/site-packages/hypothesis/strategies.py` → not internal (strict patterns only).
- **Unit** `tests/unit/model/test_schema.py` and `test_serde.py`:
  - `ErrorInfo(message=..., frames=[...], error_tail=...)` roundtrips through serde.
  - Default `ErrorInfo(message='boom')` serializes with empty `frames` and `null` `error_tail`.
  - Existing tests referencing `diff='...'` are rewritten against the new shape.
- **Unit** `tests/unit/capture/test_collector.py`:
  - `fail_current_step` and `fail_scenario` accept and store `frames`/`error_tail`; old `diff=` keyword references are removed.
- **Unit** `tests/unit/report/test_renderer.py`:
  - Render input with mixed user/internal frames asserts the data-shape contract reaches the template: presence of `error-frame` blocks, `error-frame-internal` class on internals, `error-toggle` button only when internal frames exist, `error-tail` block when `error_tail` is set. Per [[feedback-no-frontend-markup-tests]], assertions stay on structural data classes — not exact HTML or CSS values.
- **Integration** `tests/integration/test_plugin.py`:
  - A failing example produces a JSON `error` object with non-empty `frames`, at least one `is_internal: false` frame pointing at the test file, and an `error_tail` containing the assertion message.
- **Coverage gate** stays at 100%; new parser and classifier branches exercised by the unit tests above. Pragma-free per [[feedback-assert-over-pragma]].
- **Visual** verification per [[feedback-no-frontend-markup-tests]]: regenerate `examples/report.html`, open in Playwright (or browser) to confirm the toggle works and the default view shows only user frames.
