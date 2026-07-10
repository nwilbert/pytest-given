"""pytest-given plugin entry point."""

import contextlib
import dataclasses
import functools
import inspect
import json
import time
from collections.abc import Callable, Generator
from datetime import UTC, datetime
from pathlib import Path
from string import templatelib
from typing import Any, cast, get_type_hints

import pytest
from _pytest.fixtures import SubRequest

from .capture import (
    Collector,
    FixtureInstanceKey,
    Template,
    filter_internal_frames,
    get_active_collector,
    parse_short_repr,
    set_active_collector,
)
from .capture.decorators import (
    ScenarioDecorator,
    StepDecorated,
    StepDescriptor,
)
from .capture.file_glossary import FileGlossary
from .capture.kind_resolution import resolve_glossary_kinds
from .capture.source import item_source, set_rootdir
from .capture.story import clear_story_registry
from .model import (
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
    Step,
    Story,
    report_to_dict,
)
from .report import (
    PhaseViolation,
    detect_commit_sha,
    find_violations,
    render_html,
    resolve_template,
)

_PHASE_CHECK_LEVELS = ('off', 'warn', 'error')
_phase_check_violations: pytest.StashKey[list[PhaseViolation]] = pytest.StashKey()
_collector_key: pytest.StashKey[Collector] = pytest.StashKey()


def _get_collector(session: pytest.Session) -> Collector:
    """Return the session-scoped Collector, creating it on first access.

    Stored on ``session.stash`` rather than a module global so there is no
    mutable singleton read by ~25 hookimpl sites; the active-collector signal
    for the capture layer (``with given(...)`` etc.) is the ``ContextVar``
    in ``capture.collector``, set/cleared per test in setup/teardown.
    """
    collector = session.stash.get(_collector_key, None)
    if collector is None:
        collector = Collector()
        session.stash[_collector_key] = collector
    return collector


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
        '--given-all-frames',
        action='store_true',
        default=False,
        help=(
            'Store internal pluggy/_pytest/pytest-given frames in the JSON '
            'report. Slower on large failing suites — only set when debugging '
            'the plugin or pytest itself.'
        ),
    )
    group.addoption(
        '--given-source-link',
        default=None,
        help=(
            'Source-link template or preset (vscode, cursor, zed, pycharm, '
            'github, none). See README for available variables.'
        ),
    )
    group.addoption(
        '--given-phase-check',
        default=None,
        choices=_PHASE_CHECK_LEVELS,
        help=(
            'Report scenarios missing a Given/When/Then phase: off | warn | '
            'error (error fails the run). Overrides the given_phase_check ini.'
        ),
    )
    parser.addini(
        'given_source_link',
        type='string',
        default='none',
        help='Source-link template or preset name (CLI flag overrides this).',
    )
    parser.addini(
        'given_phase_check',
        type='string',
        default='off',
        help='Phase-check level: off | warn | error (CLI flag overrides this).',
    )
    parser.addini(
        'given_phase_check_ignore',
        type='linelist',
        default=[],
        help='Node-id globs exempt from the phase check (fnmatch patterns).',
    )


def _phase_check_level(config: pytest.Config) -> str:
    """Resolve the phase-check level: CLI flag wins over the ini value."""
    level = config.getoption('given_phase_check') or config.getini('given_phase_check')
    return cast('str', level)


def pytest_configure(config: pytest.Config) -> None:
    level = _phase_check_level(config)
    if level not in _PHASE_CHECK_LEVELS:
        raise pytest.UsageError(
            f'invalid given_phase_check value {level!r}; '
            f'expected one of {", ".join(_PHASE_CHECK_LEVELS)}.'
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
    session.stash[_collector_key] = Collector()
    clear_story_registry()


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
    collector = _get_collector(item.session)
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
    source = item_source(relpath_raw, (lineno0 or 0) + 1)
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
    if not isinstance(desc, StepDescriptor):
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
    collector = get_active_collector()
    if collector is None or collector.state == 'idle':
        # Fixture is being set up outside any tracked scenario (e.g. unannotated
        # test pulling in a step fixture). Don't record.
        yield
        return
    _ensure_teardown_wrapped(fixturedef, request.session)
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


def _ensure_teardown_wrapped(
    fixturedef: pytest.FixtureDef[object], session: pytest.Session
) -> None:
    """Wrap a generator fixture's body once so post-yield code runs in
    fixture_teardown state. Idempotent.

    The session is captured so the wrapped closure can resolve the
    session-scoped collector at teardown time (including session-end teardown of
    session-scoped generators, when the active-collector ContextVar is already
    cleared).
    """
    func = fixturedef.func
    if getattr(func, '_pytest_given_teardown_wrapped', False):
        return
    if not inspect.isgeneratorfunction(func):
        return
    original = func
    desc = cast('StepDecorated', original)._step_descriptor
    original_typed = cast('Callable[..., Generator[object]]', original)

    @functools.wraps(original)
    def wrapped(
        *args: object, _session: pytest.Session = session, **kwargs: object
    ) -> Generator[object]:
        gen = original_typed(*args, **kwargs)
        try:
            value = next(gen)
        except StopIteration:
            return
        yield value
        # Past the yield → teardown. Resolve the collector off the session
        # stash rather than the ContextVar: session-scoped fixtures tear down
        # at session end, after the per-test active collector is cleared.
        collector = _get_collector(_session)
        token = collector.enter_fixture_teardown()
        try:
            with contextlib.suppress(StopIteration):
                next(gen)
        finally:
            collector.exit_fixture_teardown(token)

    wrapped_typed = cast('StepDecorated', wrapped)
    wrapped_typed._pytest_given_teardown_wrapped = True  # type: ignore[attr-defined]
    wrapped_typed._step_descriptor = desc
    fixturedef.func = wrapped  # type: ignore[misc]


def _fixture_instance_key(
    fixturedef: pytest.FixtureDef[object],
    request: pytest.FixtureRequest,
) -> FixtureInstanceKey:
    return (id(fixturedef), fixturedef.cache_key(cast(SubRequest, request)))


def _get_scenario_marker(item: pytest.Item) -> ScenarioDecorator | None:
    """Get the _scenario attribute from a test function, if present.

    Returns None for items without a `.function` (e.g. DoctestItem) — those
    can't carry @scenario, so they're never load-bearing here.
    """
    func = getattr(item, 'function', None)
    if func is None:
        return None
    marker = getattr(func, '_scenario', None)
    return marker if isinstance(marker, ScenarioDecorator) else None


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


def _annotated_given_descriptors(func: object) -> dict[str, StepDescriptor]:
    """Map each parameter carrying ``Annotated[..., given(...)]`` to its
    descriptor.

    Reads type hints off the unwrapped function (past the ``@scenario``
    wrapper). Best-effort: if the annotations cannot be resolved, returns an
    empty mapping rather than failing the test. Rejects the forbidden forms —
    ``when(...)`` / ``then(...)``, a t-string label, or more than one
    descriptor on a single parameter.
    """
    target = inspect.unwrap(cast(Any, func))
    try:
        hints = get_type_hints(target, include_extras=True)
    except Exception:
        return {}
    out: dict[str, StepDescriptor] = {}
    for name, hint in hints.items():
        if name in ('self', 'cls', 'return'):
            continue
        metadata = getattr(hint, '__metadata__', None)
        if metadata is None:
            continue
        descriptors = [m for m in metadata if isinstance(m, StepDescriptor)]
        if not descriptors:
            continue
        if len(descriptors) > 1:
            raise PytestGivenError(
                f'multiple given()/when()/then() in Annotated metadata for '
                f'parameter {name!r} — use exactly one.'
            )
        desc = descriptors[0]
        if desc.phase != 'given':
            raise PytestGivenError(
                f'only given() is supported inside Annotated; parameter '
                f"{name!r} carries {desc.phase}(). Use 'with when(...)' / "
                f"'with then(...)' in the test body for the action and outcome."
            )
        if isinstance(desc._source, templatelib.Template):
            raise PytestGivenError(
                f'Annotated given(t"...") on parameter {name!r} is not '
                f'supported: a t-string evaluates at function-definition time, '
                f'where the parameter value is not in scope. Use '
                f'given(Template("... {{{name}}} ...")) for a per-case '
                f'placeholder, or a plain string label.'
            )
        out[name] = desc
    return out


def _graft_fixture_recordings(item: pytest.Item) -> None:
    """Graft this item's fixture step-recordings and Annotated `given` labels.

    Phase 1: fixture recordings in `collector.recordings()` setup order
    (`_recordings` is insertion-ordered by setup time, so this stays correct
    even though `item.fixturenames` can list a dependent before its
    dependency). Each recording may take an Annotated override narration,
    matched to the recording by its parameter name. Phase 2: Annotated-only
    leaves (parametrize values, built-in / undecorated fixtures) in
    test-signature order.
    """
    assert hasattr(item, 'fixturenames'), f'expected fixturenames on {item!r}'
    collector = _get_collector(item.session)
    func = getattr(item, 'function', None)
    descriptors = _annotated_given_descriptors(func) if func is not None else {}

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

    # Phase 1: fixture recordings in setup order, with optional override.
    # Function-scoped recordings won't be re-consumed; drop after grafting so
    # the recordings dict doesn't grow unboundedly across the session.
    grafted_names: set[str | None] = set()
    to_drop: list[FixtureInstanceKey] = []
    for key, recording in collector.recordings():
        if key not in expected:
            continue
        name = recording.root.fixture_name
        descriptor = descriptors.get(name) if name is not None else None
        override = descriptor.narration if descriptor is not None else None
        collector.graft_recording(recording, override_narration=override)
        grafted_names.add(name)
        if expected[key] == 'function':
            to_drop.append(key)
    for key in to_drop:
        collector.drop_recording(key)

    # Phase 2: Annotated-only leaves (parametrize values, built-in /
    # undecorated fixtures) in test-signature order.
    for name, descriptor in descriptors.items():
        if name in grafted_names:
            continue
        defs = fm.getfixturedefs(name, item)
        fdef = defs[-1] if defs else None
        # A decorated fixture is phase-1 territory; skip it here so its
        # recorded body is never replaced by a bodyless leaf.
        if (
            fdef is not None
            and getattr(fdef.func, '_step_descriptor', None) is not None
        ):
            continue
        collector.graft_leaf_given(descriptor.narration)


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item: pytest.Item) -> None:
    collector = _get_collector(item.session)
    if collector.inside_unannotated_test:
        collector.inside_unannotated_test = False
        set_active_collector(None)
        return
    if collector.active_scenario_id != NodeId(item.nodeid):
        return
    set_active_collector(None)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> None:
    collector = _get_collector(item.session)
    if collector.active_scenario_id != NodeId(item.nodeid):
        return
    # Capture errors from both setup (fixture exception) and call (test-body
    # failure). Without the setup branch, fixture failures would silently
    # bypass fail_scenario and the scenario would carry no error info.
    if call.when in ('setup', 'call') and call.excinfo is not None:
        # A skip raises Skipped (at setup for mark.skip/skipif, at call for an
        # in-body pytest.skip()). Its traceback is pure skip machinery — the
        # scenario carries a structured skip_reason instead (set in logreport).
        # Short-circuit before getrepr, whose per-frame AST scan would otherwise
        # run for every skipped scenario. Not gated on --given-all-frames: a skip
        # never wants a traceback regardless.
        if call.excinfo.errisinstance(pytest.skip.Exception):
            return
        if not item.config.getoption('given_all_frames'):
            filter_internal_frames(call.excinfo)
        error_repr = call.excinfo.getrepr(style='short')
        message = str(call.excinfo.value)
        frames, error_tail = parse_short_repr(str(error_repr))
        collector.fail_scenario(message=message, frames=frames, error_tail=error_tail)


@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    node_id = NodeId(report.nodeid)
    collector = get_active_collector()
    if collector is None or collector.active_scenario_id != node_id:
        # No active collector: either outside any tracked scenario, or the
        # teardown phase (whose logreport returns early below anyway). Every
        # phase that reaches finish_scenario — call, setup-skip, setup-fail —
        # runs while the ContextVar is still set.
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
    collector = _get_collector(session)
    json_path = Path(session.config.getoption('given_json'))
    scenarios = _group_parameterized(collector.scenarios, collector.param_info)
    collector.param_info.clear()
    stories = list(collector._discovered_stories.values())
    glossary = _resolve_glossary(stories, session)
    if glossary is not None:
        glossary = resolve_glossary_kinds(glossary, stories)
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
    _run_phase_check(session, scenarios)


def _run_phase_check(session: pytest.Session, scenarios: list[Scenario]) -> None:
    """Flag scenarios missing a phase; stash the result for the terminal
    summary and fail the run in `error` mode."""
    level = _phase_check_level(session.config)
    if level == 'off':
        return
    violations = find_violations(
        scenarios, session.config.getini('given_phase_check_ignore')
    )
    session.config.stash[_phase_check_violations] = violations
    if violations and level == 'error':
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    violations = terminalreporter.config.stash.get(_phase_check_violations, [])
    if not violations:
        return
    terminalreporter.write_sep(
        '=', f'pytest-given: incomplete scenarios ({len(violations)})', yellow=True
    )
    for violation in violations:
        terminalreporter.line(
            f'{violation.node_id}  missing: {", ".join(violation.missing)}'
        )


def _resolve_glossary(stories: list[Story], session: pytest.Session) -> Glossary | None:
    """Pick the Glossary for the report.

    1. If any collected story references a Glossary, read it straight off the
       story tree — `story()` stashes the owning Glossary object(s) there at
       construction time. This is deterministic: it depends only on the live
       Story objects we were handed, not on any mutable session-global that
       could be cleared per-test or shared across the process. (The stash is a
       side-channel that does not survive JSON, but resolution runs on the live
       in-memory stories, never on deserialized ones — the renderer reads the
       serialized `glossary` field instead.)
    2. With no stories (or stories that reference no glossary), fall back to a
       conftest scan — that catches the case where the user declares a Glossary
       at conftest level but only uses term refs in narrations (no stories yet).
    """
    reaching: dict[int, Glossary] = {}
    for story in stories:
        reaching.update(getattr(story, '_glossaries', {}))
    if len(reaching) > 1:
        raise PytestGivenError(
            f'stories reach {len(reaching)} distinct Glossary instances; '
            f'v1 supports at most one.'
        )
    if reaching:
        return next(iter(reaching.values()))
    return _scan_conftests_for_glossary(session)


def _scan_conftests_for_glossary(session: pytest.Session) -> Glossary | None:
    """Scan registered conftest plugins for Glossary instances."""
    found: list[tuple[str, Glossary]] = []
    for plugin_obj in session.config.pluginmanager.get_plugins():
        plugin_file = getattr(plugin_obj, '__file__', None)
        if plugin_file is None or Path(plugin_file).name != 'conftest.py':
            continue
        for attr_name in dir(plugin_obj):
            attr = getattr(plugin_obj, attr_name, None)
            if isinstance(attr, FileGlossary):
                found.append((plugin_file, attr.glossary))
            elif isinstance(attr, Glossary):
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


def _function_base(node_id: NodeId) -> str:
    """The node id without its parametrize tail, e.g.
    'tests/t.py::test_x[1-2]' -> 'tests/t.py::test_x'. Two cases of one
    parametrized function share this; two different functions never do, so it
    keys grouping without merging same-named tests."""
    return node_id.split('[', 1)[0]


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
            key = (_function_base(scenario.id), scenario.narration.text)
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
