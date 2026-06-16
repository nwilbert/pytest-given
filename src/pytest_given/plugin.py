"""pytest-given plugin entry point."""

import contextlib
import dataclasses
import functools
import inspect
import json
import time
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path, PurePath
from typing import Any, cast

import pytest
from _pytest.fixtures import SubRequest

from .capture import (
    Collector,
    FixtureInstanceKey,
    Template,
    parse_short_repr,
    set_active_collector,
)
from .capture.decorators import ScenarioDecorator
from .capture.glossary import clear_glossary_registry, get_registered_glossaries
from .capture.source import set_rootdir
from .capture.story import _clear_story_registry
from .model import (
    ActivityEntity,
    ActivityTerm,
    FixtureRecording,
    Glossary,
    Metadata,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    NodeId,
    ParameterCase,
    ParameterTable,
    ParamInfo,
    ParamSpec,
    PytestGivenError,
    ReportData,
    Scenario,
    SourceLocation,
    Step,
    Story,
    TermId,
    report_to_dict,
)
from .report import detect_commit_sha, render_html, resolve_template

collector = Collector()


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup('given', 'pytest-given report generation')
    group.addoption(
        '--given-json',
        default='given-report/report-data.json',
        help='Output path for JSON report data',
    )
    group.addoption(
        '--given-html',
        action='store_true',
        default=False,
        help='Also generate HTML report from JSON data',
    )
    group.addoption(
        '--given-html-output',
        default='given-report/report.html',
        help='Output path for HTML report (default: given-report/report.html)',
    )
    group.addoption(
        '--given-source-link',
        default=None,
        help=(
            'Source-link template or preset (vscode, cursor, zed, pycharm, '
            'github, none). See README for available variables.'
        ),
    )
    parser.addini(
        'given_source_link',
        type='string',
        default='none',
        help='Source-link template or preset name (CLI flag overrides this).',
    )


def pytest_load_initial_conftests(early_config: pytest.Config) -> None:
    """Publish pytest's rootdir to the capture module so `Story` and
    `GlossaryTerm` constructed at user-code import time can compute
    rootdir-relative source paths.

    Uses `pytest_load_initial_conftests` (not `pytest_configure`) so that
    rootdir is set *before* root conftest.py is imported — users commonly
    declare shared glossaries / stories at conftest module level, and that
    code runs during conftest import."""
    set_rootdir(Path(early_config.rootpath))


def pytest_sessionstart(session: pytest.Session) -> None:
    """Reset the collector at the start of each session."""
    global collector
    collector = Collector()
    _clear_story_registry()
    clear_glossary_registry()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Validate Template-named scenarios and story bindings eagerly at collection.

    Three checks:
    1. A Template-named scenario must be parametrized (its substitution source
       is `callspec.params`).
    2. Every Template placeholder must match a parametrize column name —
       catches typos at `pytest --collect-only` rather than at session-finish
       merge, where the error would escape `pytest_sessionfinish` opaquely.
    3. Any activity_ids on the scenario must be valid ids within the story.

    Deferred to collection time (rather than decoration time) because
    @scenario and @pytest.mark.parametrize can appear in either order, and
    decoration-time inspection only sees markers from earlier (bottom-up)
    decorators.
    """
    for item in items:
        marker = _get_scenario_marker(item)
        if marker is None:
            continue
        _validate_scenario_story_binding(item, marker)
        if not isinstance(marker.name, Template):
            continue
        callspec = getattr(item, 'callspec', None)
        if callspec is None:
            raise PytestGivenError(
                f'@scenario(Template(...)) on {item.nodeid!r} requires '
                f'@pytest.mark.parametrize; the substitution source is '
                f'callspec.params only. Use a plain string for static '
                f'scenario names, or add @pytest.mark.parametrize.'
            )
        param_names = list(callspec.params.keys())
        for placeholder in marker.name.get_identifiers():
            if placeholder not in param_names:
                raise PytestGivenError(
                    f"pytest_given.Template placeholder '{{{placeholder}}}' "
                    f'in @scenario(...) on {item.nodeid!r} does not match '
                    f'any parametrize column (have: {sorted(param_names)}).'
                )


def _validate_scenario_story_binding(
    item: pytest.Item, marker: ScenarioDecorator
) -> None:
    """Check scenario.activity_ids against the story; runtime covers step scope."""
    if marker.story is None and marker.activity_ids:
        raise PytestGivenError(
            f'@scenario(activities=...) on {item.nodeid!r} requires story=; '
            f'activity ids are meaningless without a story to look them up in.'
        )
    if marker.story is None:
        return
    valid_ids = {a.id for a in marker.story.activities}
    for aid in marker.activity_ids:
        if aid not in valid_ids:
            raise PytestGivenError(
                f'@scenario(activities=...) on {item.nodeid!r}: activity id '
                f'{aid} not in story {marker.story.title!r} '
                f'(valid: {sorted(valid_ids)}).'
            )


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> Generator[None]:
    scenario_marker = _get_scenario_marker(item)
    if scenario_marker is None:
        # Unannotated test: set the flag so `with given(...)` inside it warns
        # instead of raising. Teardown clears the flag and active collector.
        collector.inside_unannotated_test = True
        set_active_collector(collector)
        yield
        return

    mod = getattr(item, 'module', None)
    module = mod.__name__ if mod else item.nodeid.split('::')[0]
    node_id = NodeId(item.nodeid)
    relpath_raw, lineno0, _ = item.location
    source = SourceLocation(
        relpath=PurePath(relpath_raw).as_posix(),
        line=(lineno0 or 0) + 1,
    )
    collector.start_scenario(
        scenario_id=node_id,
        name=scenario_marker.name,
        module=module,
        tags=scenario_marker.tags,
        source=source,
        story=scenario_marker.story,
        activity_ids=scenario_marker.activity_ids,
    )
    set_active_collector(collector)
    callspec = getattr(item, 'callspec', None)
    if callspec is not None:
        names = list(callspec.params.keys())
        values = [callspec.params[n] for n in names]
        collector.param_info[node_id] = ParamSpec(names=names, values=values)
    # Pre-fixture-setup work done; let pytest run fixture setup here.
    yield
    _graft_fixture_recordings(item)
    collector.start_times[node_id] = time.monotonic()


@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(
    fixturedef: pytest.FixtureDef[object],
    request: pytest.FixtureRequest,
) -> Generator[None]:
    desc = getattr(fixturedef.func, '_step_descriptor', None)
    if desc is None:
        yield
        return
    if desc.phase != 'given':
        raise PytestGivenError(
            f"Fixture '{fixturedef.argname}' is decorated with @{desc.phase}, "
            'but only @given is allowed on fixtures (fixtures are setup). '
            'Use @given(...) on the fixture, or move the step into the test body.'
        )
    if isinstance(desc._source, Template):
        raise PytestGivenError(
            f'@given(Template(...)) on fixture {fixturedef.argname!r} is not '
            'yet supported; use a plain string label, or move the step into a '
            'helper function.'
        )
    if collector.state == 'idle':
        # Fixture is being set up outside any tracked scenario (e.g. unannotated
        # test pulling in a step fixture). Don't record.
        yield
        return
    _ensure_teardown_wrapped(fixturedef)
    recording = FixtureRecording(
        root=Step(
            phase=desc.phase,
            narration=desc.narration,
            fixture_name=fixturedef.argname,
        )
    )
    token = collector.enter_fixture_setup(recording, descriptor=desc)
    try:
        yield
    finally:
        collector.exit_fixture_setup(token)
        key = _fixture_instance_key(fixturedef, request)
        collector.store_recording(key, recording)


def _ensure_teardown_wrapped(fixturedef: pytest.FixtureDef[object]) -> None:
    """Wrap a generator fixture's body once so post-yield code runs in
    fixture_teardown state. Idempotent."""
    func = fixturedef.func
    if getattr(func, '_pytest_given_teardown_wrapped', False):
        return
    if not inspect.isgeneratorfunction(func):
        return
    original = func
    desc = original._step_descriptor  # type: ignore[attr-defined]

    @functools.wraps(original)
    def wrapped(*args: object, **kwargs: object) -> Generator[object]:
        gen = original(*args, **kwargs)
        try:
            value = next(gen)
        except StopIteration:
            return
        yield value
        # Past the yield → teardown
        token = collector.enter_fixture_teardown()
        try:
            with contextlib.suppress(StopIteration):
                next(gen)
        finally:
            collector.exit_fixture_teardown(token)

    wrapped._pytest_given_teardown_wrapped = True  # type: ignore[attr-defined]
    wrapped._step_descriptor = desc  # type: ignore[attr-defined]
    fixturedef.func = wrapped  # type: ignore[misc]


def _fixture_instance_key(
    fixturedef: pytest.FixtureDef[object],
    request: pytest.FixtureRequest,
) -> FixtureInstanceKey:
    return (id(fixturedef), fixturedef.cache_key(cast(SubRequest, request)))


def _get_scenario_marker(item: pytest.Item) -> Any | None:
    """Get the _scenario attribute from a test function, if present.

    Returns None for items without a `.function` (e.g. DoctestItem) — those
    can't carry @scenario, so they're never load-bearing here.
    """
    func = getattr(item, 'function', None)
    if func is None:
        return None
    return getattr(func, '_scenario', None)


def _extract_skip_reason(longrepr: object) -> str | None:
    """Return a human-readable reason from pytest's TestReport.longrepr, or None.

    Pytest emits skipped longrepr as (path, lineno, message), where message is
    typically "Skipped: <reason>" (mark-based) or "<reason>" (call-time).
    Returns None for empty messages, the reasonless `<Skipped instance>`
    placeholder, pytest's default "unconditional skip" (emitted when
    @pytest.mark.skip is used with no reason), or any shape we don't recognise.
    """
    if not isinstance(longrepr, tuple) or len(longrepr) != 3:
        return None
    message = longrepr[2]
    if not isinstance(message, str):
        return None
    if message.startswith('Skipped: '):
        message = message[len('Skipped: ') :]
    message = message.strip()
    if not message or message in ('<Skipped instance>', 'unconditional skip'):
        return None
    return message


def _graft_fixture_recordings(item: pytest.Item) -> None:
    """Graft this item's step-fixture recordings in setup order.

    `collector._recordings` is insertion-ordered by setup time, so iterating it
    preserves narrative order even when `item.fixturenames` lists dependents
    before their dependencies.
    """
    assert hasattr(item, 'fixturenames'), f'expected fixturenames on {item!r}'
    fm = item.session._fixturemanager
    expected: dict[FixtureInstanceKey, str] = {}
    for name in item.fixturenames:
        defs = fm.getfixturedefs(name, item)
        if not defs:
            continue
        fixturedef = defs[-1]
        if getattr(fixturedef.func, '_step_descriptor', None) is None:
            continue
        if fixturedef.cached_result is None:
            continue
        key: FixtureInstanceKey = (id(fixturedef), fixturedef.cached_result[1])
        expected[key] = fixturedef.scope
    # Function-scoped recordings won't be re-consumed; drop after grafting so
    # the recordings dict doesn't grow unboundedly across the session.
    to_drop: list[FixtureInstanceKey] = []
    for key, recording in collector.recordings():
        if key in expected:
            collector.graft_recording(recording)
            if expected[key] == 'function':
                to_drop.append(key)
    for key in to_drop:
        collector.drop_recording(key)


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item: pytest.Item) -> None:
    if collector.inside_unannotated_test:
        collector.inside_unannotated_test = False
        set_active_collector(None)
        return
    if collector.active_scenario_id != NodeId(item.nodeid):
        return
    set_active_collector(None)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> None:
    if collector.active_scenario_id != NodeId(item.nodeid):
        return
    # Capture errors from both setup (fixture exception) and call (test-body
    # failure). Without the setup branch, fixture failures would silently
    # bypass fail_scenario and the scenario would carry no error info.
    if call.when in ('setup', 'call') and call.excinfo is not None:
        error_repr = call.excinfo.getrepr(style='short')
        message = str(call.excinfo.value)
        frames, error_tail = parse_short_repr(str(error_repr))
        collector.fail_scenario(message=message, frames=frames, error_tail=error_tail)


@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    node_id = NodeId(report.nodeid)
    if collector.active_scenario_id != node_id:
        return
    # Tests marked @pytest.mark.skip skip at setup time; fixture exceptions
    # produce a failed setup report and no call report at all; in-body
    # pytest.skip() / failures surface during 'call'. All three terminal cases
    # must reach finish_scenario, otherwise _current_scenario is orphaned
    # (silently dropped from the report, and any later unannotated test's
    # `with given(...)` would push into the orphan since state != 'idle').
    setup_skip = report.when == 'setup' and report.skipped
    setup_fail = report.when == 'setup' and report.failed
    if report.when != 'call' and not setup_skip and not setup_fail:
        return
    elapsed = time.monotonic() - collector.start_times.pop(node_id, time.monotonic())
    duration_ms = int(elapsed * 1000)
    status = 'passed' if report.passed else 'failed' if report.failed else 'skipped'
    skip_reason = _extract_skip_reason(report.longrepr) if status == 'skipped' else None
    collector.finish_scenario(
        status=status, duration_ms=duration_ms, skip_reason=skip_reason
    )


def pytest_sessionfinish(session: pytest.Session) -> None:
    json_path = Path(session.config.getoption('given_json'))
    scenarios = _group_parameterized(collector.scenarios, collector.param_info)
    collector.param_info.clear()
    stories = list(collector._discovered_stories.values())
    glossary = _resolve_glossary(stories, session)
    report = ReportData(
        metadata=Metadata(
            project=session.config.rootpath.name,
            timestamp=datetime.now(tz=UTC).isoformat(),
            pytest_version=pytest.__version__,
            plugin_version='0.1.0',
            commit_sha=detect_commit_sha(),
        ),
        scenarios=scenarios,
        stories=stories,
        glossary=glossary,
    )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report_to_dict(report), indent=2), encoding='utf-8')
    if session.config.getoption('given_html'):
        raw_link = session.config.getoption(
            'given_source_link'
        ) or session.config.getini('given_source_link')
        template = resolve_template(raw_link)
        html_path = Path(session.config.getoption('given_html_output'))
        render_html(json_path, html_path, source_link_template=template)


def _resolve_glossary(stories: list[Story], session: pytest.Session) -> Glossary | None:
    """Pick the Glossary for the report.

    1. If stories were collected, look at which Glossary instances actually
       contain a term referenced by those stories — the rest are irrelevant
       (test-local fixtures, unrelated Glossaries that happen to share the
       process). This works without any side-channel on the Story tree, so
       it round-trips through JSON correctly.
    2. With no stories, fall back to a conftest scan — that catches the case
       where the user declares a Glossary at conftest level but only uses
       term refs in narrations (no stories yet).
    """
    if not stories:
        return _scan_conftests_for_glossary(session)
    used = _term_ids_referenced_by_stories(stories)
    reaching = [
        g for g in get_registered_glossaries() if any(t.id in used for t in g.terms)
    ]
    if len(reaching) > 1:
        raise PytestGivenError(
            f'stories reach {len(reaching)} distinct Glossary instances; '
            f'v1 supports at most one.'
        )
    if reaching:
        return reaching[0]
    return _scan_conftests_for_glossary(session)


def _term_ids_referenced_by_stories(stories: list[Story]) -> set[TermId]:
    used: set[TermId] = set()
    for s in stories:
        for a in s.activities:
            for p in a.paths:
                for part in p.parts:
                    if isinstance(part, ActivityEntity):
                        used.add(part.entity_id)
                    elif isinstance(part, ActivityTerm):
                        used.add(part.term_id)
    return used


def _scan_conftests_for_glossary(session: pytest.Session) -> Glossary | None:
    """Scan registered conftest plugins for Glossary instances."""
    found: list[tuple[str, Glossary]] = []
    for plugin_obj in session.config.pluginmanager.get_plugins():
        plugin_file = getattr(plugin_obj, '__file__', None)
        if plugin_file is None or Path(plugin_file).name != 'conftest.py':
            continue
        for attr_name in dir(plugin_obj):
            attr = getattr(plugin_obj, attr_name, None)
            if isinstance(attr, Glossary):
                found.append((plugin_file, attr))
    distinct: dict[int, tuple[str, Glossary]] = {}
    for fpath, g in found:
        distinct.setdefault(id(g), (fpath, g))
    if len(distinct) > 1:
        details = ', '.join(
            f'{fpath} ({len(g.terms)} term(s))' for fpath, g in distinct.values()
        )
        raise PytestGivenError(
            f'multiple Glossary instances found in conftests ({len(distinct)}): '
            f'{details}. v1 supports at most one glossary per suite.'
        )
    if distinct:
        return next(iter(distinct.values()))[1]
    return None


def _group_parameterized(
    scenarios: list[Scenario],
    param_info: ParamInfo,
) -> list[Scenario]:
    """Group parameterized scenarios into single scenarios with parameter tables."""
    result: list[Scenario] = []
    groups: dict[tuple[str, str], list[Scenario]] = {}
    group_order: list[tuple[str, str]] = []

    for scenario in scenarios:
        if scenario.id in param_info:
            key = (scenario.narration.text, scenario.module)
            if key not in groups:
                groups[key] = []
                group_order.append(key)
            groups[key].append(scenario)
        else:
            result.append(scenario)

    for key in group_order:
        group = groups[key]
        first = group[0]
        param_names, _ = param_info[first.id]

        template_steps = _templatize_steps(first.steps, param_names)
        merged_narration = _templatize_narration(first.narration, param_names)

        cases: list[ParameterCase] = []
        total_duration = 0
        for scenario in group:
            _, values = param_info[scenario.id]
            cases.append(
                ParameterCase(
                    values=values,
                    status=scenario.status,
                    error=scenario.error,
                )
            )
            total_duration += scenario.duration_ms

        if any(c.status == 'failed' for c in cases):
            merged_status = 'failed'
        elif all(c.status == 'skipped' for c in cases):
            merged_status = 'skipped'
        else:
            merged_status = 'passed'

        merged = Scenario(
            id=first.id,
            narration=merged_narration,
            module=first.module,
            tags=first.tags,
            status=merged_status,
            duration_ms=total_duration,
            steps=template_steps,
            parameters=ParameterTable(names=param_names, cases=cases),
            source=first.source,
            story_id=first.story_id,
            activity_ids=first.activity_ids,
        )
        result.append(merged)

    return result


def _templatize_steps(
    steps: list[Step],
    param_names: list[str],
) -> list[Step]:
    """Walk steps and templatize their narration."""
    result: list[Step] = []
    for step in steps:
        new_narration = _templatize_narration(step.narration, param_names)
        new_children = _templatize_steps(step.children, param_names)
        result.append(
            dataclasses.replace(step, narration=new_narration, children=new_children)
        )
    return result


def _templatize_narration(
    narration: Narration,
    param_names: list[str],
) -> Narration:
    """Convert matching NarrationValue entries to NarrationPlaceholder.

    NarrationLiteral parts pass through unchanged. A NarrationValue whose
    `expression` matches a parametrize column becomes a NarrationPlaceholder;
    otherwise it stays verbatim (the rendered value is shared across cases).
    A NarrationPlaceholder must reference a known parametrize column.
    """
    if not narration.parts:
        return narration
    out: list[NarrationPart] = []
    for part in narration.parts:
        match part:
            case NarrationLiteral():
                out.append(part)
            case NarrationValue(expression=expression, format_spec=fs, conversion=conv):
                if expression in param_names:
                    out.append(
                        NarrationPlaceholder(
                            name=expression,
                            format_spec=fs,
                            conversion=conv,
                        )
                    )
                else:
                    out.append(part)
            case NarrationPlaceholder(name=name):
                if name not in param_names:
                    raise PytestGivenError(
                        f"pytest_given.Template placeholder '{{{name}}}' does "
                        f'not match any parametrize column (have: '
                        f'{sorted(param_names)}).'
                    )
                out.append(part)
            case NarrationTermRef(expression=expression):
                if expression in param_names:
                    out.append(dataclasses.replace(part, param_column=expression))
                else:
                    out.append(part)
    return dataclasses.replace(narration, parts=out)
