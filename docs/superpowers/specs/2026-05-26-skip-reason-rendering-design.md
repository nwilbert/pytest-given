# Skip Reason Rendering — Design Spec

## Goal

When a scenario is skipped (via `@pytest.mark.skip`, `@pytest.mark.skipif`, or an in-body `pytest.skip()`), surface the human-readable reason in the report's expanded body. Today, skipped scenarios render with a status pill but no expandable body — the reader can see *that* a scenario was skipped, but not *why*.

## Scope

- In: `@pytest.mark.skip(reason=...)`, `@pytest.mark.skipif(..., reason=...)`, and `pytest.skip("...")` called inside the test body or a fixture.
- In: a targeted fix to the parametrized-status aggregation (`_group_parameterized`) so a merged scenario whose cases are all skipped surfaces as `'skipped'`, not `'passed'`.
- Out: `xfail`/`xpassed` handling. These reach `pytest_runtest_logreport` with `report.skipped=True` or `report.passed=True` plus `report.wasxfail`, and would need their own status taxonomy — deferred.
- Out: per-case skip reasons inside parameter tables. Deferred to a follow-up alongside other per-case enrichment.

## Background

`pytest_runtest_logreport` in `src/pytest_given/plugin.py:282` already routes both setup-time skips (`@pytest.mark.skip*`) and call-time skips (`pytest.skip()`) into `Collector.finish_scenario(status='skipped', ...)`. The collector stores the status on `Scenario` but has no field for an accompanying reason, so renderer and JSON consumers have nothing to surface.

The HTML template at `src/pytest_given/templates/report.html.j2:104` computes `has_body = scenario.steps or scenario.parameters or scenario.error`. For a skipped scenario none of these are populated, so the chevron is suppressed (`scenario-chevron-placeholder`) and the body block stays empty — the recent change in commit `455ecc1`.

For parametrized scenarios, `_group_parameterized` in `src/pytest_given/plugin.py:321` aggregates per-case statuses with `'failed' if any_failed else 'passed'`. A scenario whose cases are all skipped therefore shows as passed in the merged view, which misrepresents reality.

## Approach

### Data model

Add a single optional field to `Scenario` in `src/pytest_given/model.py`:

```python
@dataclass
class Scenario:
    ...
    skip_reason: str | None = None
```

No new dataclass. The reason is a plain string; reusing `ErrorInfo` would be semantically wrong (a skip is not a failure with a diff), and introducing a generic `note` field is YAGNI for a single consumer.

### Capturing the reason

Extend the skipped branch in `pytest_runtest_logreport` to parse `report.longrepr` and pass the reason through to the collector. Pytest's `TestReport.longrepr` for a skip is normally a `(path: str, lineno: int, message: str)` 3-tuple, where `message` is typically `"Skipped: <reason>"` (mark-based skip) or `"<reason>"` (call-time `pytest.skip("...")`). When no reason is supplied at all, pytest emits a placeholder like `"Skipped: <Skipped instance>"`.

Add a small helper, e.g. `_extract_skip_reason(longrepr: object) -> str | None`:

1. If `longrepr` is a 3-tuple whose third element is a string, take that string.
2. Strip a leading `"Skipped: "` prefix if present.
3. If the result is empty, or equals `"<Skipped instance>"` (pytest's reasonless placeholder), return `None`.
4. Otherwise return the trimmed reason.

The helper returns `None` for any shape it doesn't recognise — we surface a reason when we have one and stay silent otherwise.

Thread the reason through:

- `Collector.finish_scenario(status, duration_ms, skip_reason=None)` — new optional kwarg, sets `self._current_scenario.skip_reason` before append.
- `pytest_runtest_logreport` passes `skip_reason=_extract_skip_reason(report.longrepr)` only when `status == 'skipped'`.

### Parametrized status fix

In `_group_parameterized`, replace `status='failed' if any_failed else 'passed'` with the three-way rule:

```python
if any_failed:
    merged_status = 'failed'
elif all(c.status == 'skipped' for c in cases):
    merged_status = 'skipped'
else:
    merged_status = 'passed'
```

This change is independent of skip-reason rendering — it's correct on its own merits and naturally surfaces when this feature lands an all-skipped parametrize.

Per-case skip *reasons* still don't appear in the parameter table; the table's status column shows `○` for skipped, but the reason text is not rendered next to it in this iteration.

### Rendering

In `src/pytest_given/templates/report.html.j2`:

1. Extend `has_body` to include `scenario.skip_reason`:

   ```jinja
   {%- set has_body = scenario.steps or scenario.parameters or scenario.error or scenario.skip_reason -%}
   ```

   Effect: a skipped scenario with a reason gets a chevron and an expandable body; a reasonless skip stays collapsed/empty as today.

2. Add a `.skip-reason` block at the top of the expanded body (before steps, parameters, and any error block):

   ```jinja
   {% if scenario.skip_reason %}
   <div class="skip-reason">
     <span class="skip-reason-label">Skipped:</span>
     <span class="skip-reason-text">{{ scenario.skip_reason }}</span>
   </div>
   {% endif %}
   ```

3. Add styling in `src/pytest_given/templates/styles.css`. The block reuses the existing `--color-skipped` token for the accent, with a muted background — distinct from `.error-block` (which carries failure semantics):

   ```css
   .skip-reason {
     padding: var(--space-md) var(--space-lg);
     background: #fffbe6;
     border-left: 3px solid var(--color-skipped);
     color: #555;
     font-size: 0.95em;
   }
   .skip-reason-label {
     font-weight: 600;
     color: #856404;
     margin-right: var(--space-sm);
   }
   ```

   (Exact colors are illustrative — the implementation will pick tones consistent with the existing palette in `styles.css`.)

### JSON shape

`skip_reason` is serialized as a top-level key on each scenario object, alongside `error`. Consumers reading the JSON gain a new optional field; absent or `null` means no surfaced reason (either the scenario didn't skip, or skipped without a usable reason). No version bump needed — additive change.

## Components touched

- `src/pytest_given/model.py` — add `skip_reason: str | None` field to `Scenario`.
- `src/pytest_given/collector.py` — extend `finish_scenario` signature.
- `src/pytest_given/plugin.py` — add `_extract_skip_reason` helper, wire it into the logreport handler, fix `_group_parameterized` status rule.
- `src/pytest_given/templates/report.html.j2` — update `has_body`, add `.skip-reason` block.
- `src/pytest_given/templates/styles.css` — add `.skip-reason*` rules.
- `examples/test_examples.py` — keep the existing `test_skipped` example (already supplies a `reason=`), and add a parametrized-all-skipped scenario so the merged-status fix is visible in the rendered report.
- `README.md` — add a "Skipped scenarios with reason" bullet to the feature tour under `## Examples`.
- `examples/report-data.json` and `examples/report.html` — regenerate via `uv run nox -s examples` and commit the updates.

## Error handling

- `_extract_skip_reason` is defensive: any shape of `longrepr` that isn't the expected 3-tuple with a string message returns `None`. Pytest's shape has been stable, but the cost of being lenient is one extra `isinstance` check.
- HTML escaping in the Jinja template handles arbitrary reason text (no raw rendering); the reason is rendered as plain text inside a `<span>`, no special characters need to be filtered upstream.

## Testing

- **Unit** in `tests/unit/`:
  - `_extract_skip_reason` parses the canonical `(path, lineno, "Skipped: foo")` tuple to `"foo"`.
  - Strips empty / `<Skipped instance>` placeholder to `None`.
  - Returns `None` for non-tuple shapes (string, `None`, malformed tuple).
  - `_group_parameterized` returns merged status `'skipped'` when all cases skipped, `'passed'` when mixed pass/skip, `'failed'` when any failed (regardless of skip presence).
- **Integration** in `tests/integration/`:
  - A scenario with `@pytest.mark.skip(reason='because')` produces a `Scenario` with `skip_reason='because'` and `status='skipped'` in the JSON.
  - A scenario with `@pytest.mark.skip` (no reason) produces `skip_reason=None`.
  - A scenario with in-body `pytest.skip('mid-test')` produces `skip_reason='mid-test'`.
  - A parametrized scenario where every case is marked skip produces a merged scenario with `status='skipped'`.
- **Renderer** in `tests/unit/test_renderer.py` or `test_template.py`:
  - A skipped scenario with a reason renders the `.skip-reason` block and a chevron.
  - A skipped scenario without a reason renders neither chevron nor block.
- **Coverage gate** remains at 100% — `_extract_skip_reason` branches must all be exercised.
