# Source Links for Stories and Glossary — Design

## Goal

Extend the existing source-link feature (see [2026-05-30-source-link-design.md](2026-05-30-source-link-design.md)) so that `Story` and `GlossaryTerm` carry a `source: SourceLocation` and the report links to the file/line where each was declared — same presets, same template variables, same UX as the scenario link.

## Background

Today only scenarios have source links: `scenario.source` is populated from pytest's `item.location`, resolved via `_compute_source_urls`, and rendered as a small right-aligned link at the bottom of the expanded scenario card. Stories and glossary terms are declared at module-import time in conftest / test modules and have no source info on the dataclass, so the report can't link to them.

This is a gap noticed in practice: viewers of the report can jump from a scenario to its test, but not from a story or a term back to its declaration site.

## User-facing behavior

- No new config. The existing `given_source_link` ini/CLI option governs all three. Setting it to `none` (or omitting it) leaves all three unlinked.
- Stories: a small right-aligned `<a>` link at the bottom of the story view-main panel, below the per-scenario strip. Same `.scenario-source` styling, just placed under the story body. Visible whenever a story is selected.
- Glossary terms: a small right-aligned `<a>` link inside the expanded card body (the `.refs-content` block). Hidden by default; visible only when the term is expanded — matches the "expand to see references" affordance the rest of the glossary card already uses.

## Data model changes

### `model/schema.py`

```python
@dataclass(frozen=True, kw_only=True)
class GlossaryTerm:
    id: TermId
    kind: Literal['actor', 'object', 'verb']
    canonical: str
    definition: str = ''
    source: SourceLocation | None = None   # new

@dataclass(frozen=True, kw_only=True)
class Story:
    id: StoryId
    title: str
    activities: tuple[Activity, ...]
    source: SourceLocation | None = None   # new
    _by_id: dict[ActivityId, Activity] = ...
```

`SourceLocation` is unchanged. `None` means "not captured" — the file is outside rootdir, rootdir is unset, or frame info is missing. The renderer treats `source=None` exactly like the existing scenario case: no link block emitted.

## Capture flow

### Rootdir threading

`SourceLocation.relpath` is rootdir-relative, but `Story` / `GlossaryTerm` are constructed at user-code import time, not inside a pytest hook. They need rootdir from the plugin.

Add a module-level setter in `capture/source.py` (new module):

```python
# src/pytest_given/capture/source.py
from pathlib import Path
import inspect

from ..model import SourceLocation

_rootdir: Path | None = None

def set_rootdir(path: Path) -> None:
    global _rootdir
    _rootdir = path

def _reset_rootdir() -> None:
    """Test-only — used by integration tests that span pytest sessions."""
    global _rootdir
    _rootdir = None

def capture_caller_source(skip: int = 2) -> SourceLocation | None:
    """Return a SourceLocation for the frame `skip` levels up the call stack.

    `skip=2` is the default: callers invoke this from a one-level-deep wrapper
    (e.g., `_register_kind` called by `_glossary_actor`), so frame 2 is the
    user's code. Pass `skip=1` when called directly from the user-facing API.

    Returns None if rootdir is unset or the caller's file lies outside
    rootdir — both cases mean we can't build a meaningful relpath, and the
    rendered report just omits the link block (matches scenario behavior
    when `item.location` is absent).
    """
    if _rootdir is None:
        return None
    frame = inspect.stack()[skip]
    abs_path = Path(frame.filename).resolve()
    try:
        rel = abs_path.relative_to(_rootdir.resolve())
    except ValueError:
        return None
    return SourceLocation(relpath=rel.as_posix(), line=frame.lineno)
```

The plugin sets rootdir in `pytest_configure`, which runs before conftests and test modules are imported, so registration sites always see a populated rootdir:

```python
# src/pytest_given/plugin.py
from .capture.source import set_rootdir

def pytest_configure(config: pytest.Config) -> None:
    set_rootdir(Path(config.rootpath))
    ...
```

### Story capture

`_register_story` in `capture/story.py` already does `inspect.stack()[2]` for its duplicate-registration error. Reuse that frame, store the registration site on `Story`, and keep the existing duplicate-detection behavior (registry already pinned to first registration via the `_STORY_REGISTRY` dict).

```python
def story(title: str, activities: Sequence[Activity] = ()) -> Story:
    sid = StoryId(id_derive(title))
    _register_story(sid, title)
    source = capture_caller_source(skip=2)  # skip story() and capture_caller_source itself
    numbered = _assign_sequence_numbers(tuple(activities))
    _check_unique_ids(numbered)
    _check_single_glossary(title, numbered)
    return Story(id=sid, title=title, activities=numbered, source=source)
```

(`_register_story` and `capture_caller_source` both inspect frame 2 from inside their respective functions; the two stack walks are independent and both produce the user's frame correctly because the relative depth from each is identical.)

### Glossary term capture (first-registration only)

`_register_kind` in `capture/glossary.py` is idempotent: re-registering the same name returns the existing term. The new field follows that semantics — the **first** registration captures the call site; subsequent calls with the same (kind, name, definition) return the existing term with its original `source` intact.

```python
def _register_kind(self, kind, name, definition) -> GlossaryTerm:
    source = capture_caller_source(skip=3)  # skip _register_kind, _glossary_<kind>, then user
    new = GlossaryTerm(
        id=id_derive(name),
        kind=kind,
        canonical=name,
        definition=definition,
        source=source,
    )
    existing = self.get(new.id)
    if existing is not None:
        if existing == new.__class__(   # compare ignoring source — see note
            id=new.id, kind=new.kind, canonical=new.canonical, definition=new.definition
        ):
            return existing
        raise PytestGivenError(...)
    self._register(new)
    return new
```

**Conflict-comparison subtlety:** the existing equality check `existing == new` would now also compare `source`, which would cause idempotent re-registration from a different file to flag as a conflict. The check needs to compare on the user-visible fields only — `kind`, `canonical`, `definition`. Equivalently: rebuild `new_without_source` for the equality test, or compare field-by-field. The implementation plan picks the smaller diff; the design constraint is **idempotent re-registration must succeed regardless of registration site**.

## Serialization (`model/serde.py`)

`report_to_dict` already serializes new fields via `_asdict_filtered`. The deserialize side needs two small edits:

```python
def _story_from_dict(d: dict[str, Any]) -> Story:
    src = d.get('source')
    return Story(
        id=StoryId(d['id']),
        title=d['title'],
        activities=tuple(_activity_from_dict(a) for a in d.get('activities', [])),
        source=SourceLocation(relpath=src['relpath'], line=src['line']) if src else None,
    )

def _glossary_term_from_dict(d: dict[str, Any]) -> GlossaryTerm:
    src = d.get('source')
    return GlossaryTerm(
        id=TermId(d['id']),
        kind=d['kind'],
        canonical=d['canonical'],
        definition=d.get('definition', ''),
        source=SourceLocation(relpath=src['relpath'], line=src['line']) if src else None,
    )
```

## Renderer (`report/renderer.py`)

Refactor `_compute_source_urls` into a single helper plus three call sites:

```python
def _resolve_url(
    source: SourceLocation | None,
    *,
    template: str | None,
    project: str,
    commit_sha: str | None,
) -> str | None:
    if source is None or template is None:
        return None
    return format_source_link(template, source=source, project=project, commit_sha=commit_sha)

def _compute_url_maps(report, template):
    scn = {i: _resolve_url(s.source, template=template, project=..., commit_sha=...)
           for i, s in enumerate(report.scenarios)}
    story = {s.id: _resolve_url(s.source, template=template, ...) for s in report.stories}
    term = {t.id: _resolve_url(t.source, template=template, ...)
            for t in (report.glossary.terms if report.glossary else ())}
    return scn, story, term
```

Three maps are passed into the template: `source_urls`, `story_source_urls`, `term_source_urls`. Keys mirror what the template already iterates with (`loop.index0` for scenarios, `story.id`, `term.id`).

## Templates (`report/templates/report.html.j2`)

### Story panel

At the bottom of each `<div x-show="selectedStory === '{{ story.id }}'">` block, after the `.scn-act-strip-section`:

```jinja
{% if story.source %}
<div class="scenario-source">
  {%- set url = story_source_urls.get(story.id) -%}
  {%- if url -%}
  <a href="{{ url }}">{{ story.source.relpath }}:{{ story.source.line }}</a>
  {%- else -%}
  <span>{{ story.source.relpath }}:{{ story.source.line }}</span>
  {%- endif -%}
</div>
{% endif %}
```

### Glossary card

Inside `.refs-content` (already gated by `expandedTerms[term.id]`), as the last child after the existing `Stories: …` / `Instances: …` / `Also used as: …` blocks:

```jinja
{% if term.source %}
<div class="scenario-source">
  {%- set url = term_source_urls.get(term.id) -%}
  {%- if url -%}
  <a href="{{ url }}">{{ term.source.relpath }}:{{ term.source.line }}</a>
  {%- else -%}
  <span>{{ term.source.relpath }}:{{ term.source.line }}</span>
  {%- endif -%}
</div>
{% endif %}
```

The existing `.scenario-source` CSS class is reused as-is — the visual treatment (small, muted, right-aligned, no underline until hover) is intentional and is the contract the user asked for ("consistent with existing scenario source code links"). No new CSS.

## Error handling

| Situation | Behavior |
|---|---|
| `pytest_configure` not yet called when registration happens | Should never happen in practice (pytest runs `pytest_configure` before importing test modules), but capture returns `None` if `_rootdir` is unset. No error. |
| Registration site outside rootdir (e.g., a library that ships a glossary) | `source = None` for that term. No link block emitted. Same as scenario behavior when `item.location` resolves outside rootdir. |
| Idempotent glossary registration from a different file than the original | Returns existing term with original `source`. No conflict raised. (Conflict-detection compares user-visible fields only — see capture section.) |
| Glossary conflict with different `definition` or `kind` | Still raises `PytestGivenError` as today. |

## Testing

- `tests/unit/test_capture_source.py` (new):
  - `capture_caller_source` returns a `SourceLocation` whose `relpath` is POSIX and rootdir-relative.
  - Returns `None` when rootdir is unset.
  - Returns `None` when the caller's file is outside rootdir.
  - `skip` argument selects the correct frame (test calls through one and two levels of wrapper).
- `tests/unit/test_glossary.py`:
  - Term registered once carries `source` from the registration site.
  - Idempotent re-registration from a *different* file returns the original term unchanged — `source` does not switch.
  - Idempotent re-registration with the same fields succeeds (i.e., the conflict comparator ignores `source`).
  - Definition / kind mismatch still raises.
- `tests/unit/test_story.py`:
  - `story(...)` populates `source` from the call site.
  - Duplicate `story(...)` still raises (`_register_story` behavior unchanged).
- `tests/unit/test_serde.py`:
  - Round-trip preserves `Story.source` and `GlossaryTerm.source`.
- `tests/unit/test_renderer.py`:
  - URL maps populated for scenarios, stories, terms when template + source are both present.
  - Each map element is `None` when either is missing.
- `tests/integration/test_plugin.py`:
  - End-to-end run with `--given-source-link=vscode`: report HTML contains `<a href="vscode://file/.../conftest.py:N">` for each story and each glossary term (in addition to the existing scenario assertions).
  - Default (`none`): plain `<span>` blocks at the same DOM positions.
- Coverage stays at 100% (project convention).

## Documentation

- **README** — update the "Source links" section to mention stories and glossary terms, alongside the existing scenario coverage. One sentence each is enough; the preset / variable tables don't change.
- **AGENTS.md Architecture section** — mention `capture/source.py` under the file list.

## Out of scope (explicitly)

- Per-`Activity` or per-`ActivityPath` source links. Activities are typically declared one-per-line inside a `story(...)` literal; the story link reaches the same file/region with less DOM noise.
- Per-`ActorInstance` / `WorkObjectInstance` / `InflectedVerb` source links. Instances are values that flow through the test body; their identity is the underlying term, which is what we link.
- Overriding the captured source via an explicit `source=` kwarg on `story(...)` or `g.actor(...)`. Add only if a real use case appears (e.g., a generator function that produces stories on behalf of a different file).
- A separate config option to enable links per kind (`given_source_link_terms` / `..._stories`). Single switch keeps the UX coherent — if the user wants editor jumps, they want them everywhere; if they're archiving for non-developers, they want them nowhere.
- Capturing source for `Activity` even when constructed standalone (outside a `story(...)` literal). Reachable from the story link.
