"""pytest-given plugin entry point."""

import contextlib
import copy
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
from .capture.kind_inference import infer_glossary_kinds
from .capture.source import (
    current_rootdir,
    item_source,
    restore_rootdir,
    set_rootdir,
)
from .capture.story import (
    clear_story_registry,
    restore_story_registry,
    snapshot_story_registry,
)
from .grouping import group_parametrized
from .lint import (
    Finding,
    apply_config,
    parse_ignore_entries,
    parse_rule_levels,
    run_ast_rules,
    run_runtime_rules,
)
from .model import (
    FixtureRecording,
    Glossary,
    Metadata,
    NodeId,
    ParamSpec,
    PytestGivenError,
    RawParamValue,
    ReportData,
    Scenario,
    Step,
    Story,
    StoryId,
    placeholder_mismatch,
    report_from_dict,
    report_to_dict,
)
from .report import detect_commit_sha, render_html, render_md, resolve_template

_collector_key: pytest.StashKey[Collector] = pytest.StashKey()


def _collector(config: pytest.Config) -> Collector:
    """The collector owned by this session, created at `pytest_sessionstart`.

    Lives in `config.stash` rather than a module global so a nested in-process
    run (pytester, `pytest.main`) gets its own instance instead of rebinding —
    and thereby clobbering — the outer session's.
    """
    return config.stash[_collector_key]


# Module-global state this config displaced when it took over the process —
# put back at `pytest_unconfigure` so a nested in-process run (pytester,
# `pytest.main`) leaves the outer session's state as it found it.
_displaced_rootdir_key: pytest.StashKey[Path | None] = pytest.StashKey()
_displaced_stories_key: pytest.StashKey[dict[StoryId, str]] = pytest.StashKey()
_displaced_active_collector_key: pytest.StashKey[Collector | None] = pytest.StashKey()


_LINT_CHOICES = ('true', 'false')
_lint_findings: pytest.StashKey[list[Finding]] = pytest.StashKey()
_md_stdout: pytest.StashKey[str] = pytest.StashKey()
_grouping_error_message: pytest.StashKey[str] = pytest.StashKey()


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup('given', 'pytest-given report generation')
    group.addoption(
        '--given-json',
        nargs='?',
        const='given-report/report-data.json',
        default=None,
        help=(
            'Write JSON report data. Bare uses the default path; =PATH '
            'overrides. Off when absent.'
        ),
    )
    group.addoption(
        '--given-html',
        nargs='?',
        const='given-report/report.html',
        default=None,
        help=(
            'Write the HTML report. Bare uses the default path; =PATH '
            'overrides. Off when absent.'
        ),
    )
    group.addoption(
        '--given-md',
        nargs='?',
        const='-',
        default=None,
        help=(
            'Write the Markdown report. Bare renders to stdout (fenced); '
            '=PATH writes a file. Off when absent.'
        ),
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
        '--given-title',
        default=None,
        help=(
            'Name the report. Defaults to the rootdir name. Overrides the '
            'given_title ini for one run.'
        ),
    )
    group.addoption(
        '--given-lint',
        default=None,
        choices=_LINT_CHOICES,
        help=(
            'Run the narration lint: true | false. Overrides the given_lint '
            'ini for one run.'
        ),
    )
    parser.addini(
        'given_source_link',
        type='string',
        default='none',
        help='Source-link template or preset name (CLI flag overrides this).',
    )
    parser.addini(
        'given_title',
        type='string',
        default='',
        help='Name the report (CLI flag overrides this).',
    )
    parser.addini(
        'given_lint',
        type='bool',
        default=False,
        help='Run the narration lint (CLI flag overrides this).',
    )
    parser.addini(
        'given_lint_rules',
        type='linelist',
        default=[],
        help='Per-rule severity overrides: rule-id=level (off | warn | error).',
    )
    parser.addini(
        'given_lint_ignore',
        type='linelist',
        default=[],
        help=(
            'Subject globs exempt from lint findings, optionally rule-scoped '
            "with a 'rule-id:' prefix. Entries that suppress nothing fail the "
            'run.'
        ),
    )


def _resolve_title(config: pytest.Config) -> str | None:
    """Resolve the report title: CLI flag (when given) wins over the ini value.

    None when neither is set, which leaves renderers on the rootdir name.
    """
    cli = config.getoption('given_title')
    if cli is not None:
        return cast('str', cli)
    return cast('str', config.getini('given_title')) or None


def _lint_enabled(config: pytest.Config) -> bool:
    """Resolve the lint switch: CLI flag (when given) wins over the ini value."""
    cli = config.getoption('given_lint')
    if cli is not None:
        return cast('str', cli) == 'true'
    return bool(config.getini('given_lint'))


def pytest_configure(config: pytest.Config) -> None:
    # Validate the lint rule config eagerly (fail fast), even when the lint
    # itself is disabled for this run.
    try:
        parse_rule_levels(config.getini('given_lint_rules'))
        parse_ignore_entries(config.getini('given_lint_ignore'))
    except ValueError as error:
        raise pytest.UsageError(str(error)) from error


def pytest_load_initial_conftests(early_config: pytest.Config) -> None:
    """Publish pytest's rootdir to the capture module so `Story` and
    `GlossaryTerm` constructed at user-code import time can compute
    rootdir-relative source paths.

    Uses `pytest_load_initial_conftests` (not `pytest_configure`) so that
    rootdir is set *before* root conftest.py is imported — users commonly
    declare shared glossaries / stories at conftest module level, and that
    code runs during conftest import. The story registry is snapshotted and
    cleared here for the same reason: a nested in-process run's conftests
    import during *its* load-initial-conftests, before its sessionstart, so
    clearing at sessionstart would leave the outer session's registrations
    visible (spurious `already declared` collisions) and let the nested run's
    own registrations leak back into the outer session."""
    early_config.stash[_displaced_rootdir_key] = current_rootdir()
    set_rootdir(Path(early_config.rootpath))
    early_config.stash[_displaced_stories_key] = snapshot_story_registry()
    clear_story_registry()
    # The active-collector ContextVar is process-global too: a nested run's
    # per-test teardown clears it, so remember the outer session's value (the
    # scenario mid-flight when the nested run began, if any) to restore it.
    early_config.stash[_displaced_active_collector_key] = get_active_collector()


def pytest_sessionstart(session: pytest.Session) -> None:
    """Give the session its own collector."""
    collector = Collector()
    collector.capture_step_source = _lint_enabled(session.config)
    session.config.stash[_collector_key] = collector


def pytest_unconfigure(config: pytest.Config) -> None:
    """Put back the module-global state this config displaced, so a nested
    in-process run leaves the outer session's rootdir and story registry as it
    found them. Guarded per key: a run that aborted before the corresponding
    save point has nothing to restore."""
    if _displaced_rootdir_key in config.stash:
        restore_rootdir(config.stash[_displaced_rootdir_key])
    if _displaced_stories_key in config.stash:
        restore_story_registry(config.stash[_displaced_stories_key])
    if _displaced_active_collector_key in config.stash:
        set_active_collector(config.stash[_displaced_active_collector_key])


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Validate Template-named scenarios and story bindings eagerly at collection.

    Four checks:
    1. A Template-named scenario must be parametrized (its substitution source
       is `callspec.params`).
    2. Every Template placeholder must match a parametrize column name —
       catches typos at `pytest --collect-only` rather than at session-finish
       grouping, where the error would escape `pytest_sessionfinish` opaquely.
    3. Any activity_ids on the scenario must be valid ids within the story.
    4. `group_parametrized=False` must have a parametrization to decline —
       otherwise the flag would silently do nothing, since an unparametrized
       scenario never reaches the grouping pass at all.

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
        callspec = getattr(item, 'callspec', None)
        if not marker.group_parametrized and callspec is None:
            raise PytestGivenError(
                f'@scenario(group_parametrized=False) on {item.nodeid!r} has '
                f'nothing to opt out of; the test is not parametrized. Drop '
                f'the argument, or add @pytest.mark.parametrize.'
            )
        if not isinstance(marker.name, Template):
            continue
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
                raise placeholder_mismatch(
                    placeholder,
                    param_names,
                    where=f'in @scenario(...) on {item.nodeid!r}',
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
    collector = _collector(item.config)
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
    # Pre-fixture-setup work done; let pytest run fixture setup here.
    yield
    _capture_param_spec(
        item, collector, node_id, group=scenario_marker.group_parametrized
    )
    _graft_fixture_recordings(item, collector)
    collector.start_times[node_id] = time.monotonic()


def _capture_param_spec(
    item: pytest.Item, collector: Collector, node_id: NodeId, *, group: bool
) -> None:
    """Snapshot the parametrize arguments as the test is about to see them.

    Read from `item.funcargs` rather than `callspec.params`: under
    `indirect=True` the argument is bound to whatever the fixture returned, and
    that — not the parametrize input — is what the test narrates and what the
    case cell has to show, since row hover substitutes a cell into the slot the
    step rendered. `params` still supplies the names, and the value when a
    fixture never got as far as binding one.

    Snapshotted rather than kept live: these values are read again at session
    finish, so a body that mutates one in place would otherwise put the
    post-test state in the table and make the rebound-parameter rule compare
    the narration against a value it never rendered.
    """
    callspec = getattr(item, 'callspec', None)
    if callspec is None:
        return
    funcargs = getattr(item, 'funcargs', {})
    names = list(callspec.params.keys())
    collector.param_info[node_id] = ParamSpec(
        names=names,
        values=[_snapshot(funcargs.get(name, callspec.params[name])) for name in names],
        group=group,
    )


def _snapshot(value: RawParamValue) -> RawParamValue:
    """A shallow copy of a parametrize value, or the value itself when its type
    refuses to be copied or the copy would not render the way it does.

    Best effort by nature: a value that cannot be copied is one whose mutation
    cannot be guarded against either.

    A copy that renders differently is worse than no copy at all. An object
    inheriting the default `__repr__` — or a `MagicMock` — renders its own
    address, so the copy puts a value in the cell that no case ever narrated
    and reads to the rebound-parameter rule as a rebinding that never happened.
    Mutation cannot change such a rendering anyway, so keeping the original
    gives up nothing the copy was there to protect.
    """
    with contextlib.suppress(Exception):
        snapshot = copy.copy(value)
        # Both renderings, since an interpolation may ask for either: `!r`
        # takes `repr` and a bare `{x}` takes `str`, and a type can define one
        # by value and inherit the other from `object`.
        if (str(snapshot), repr(snapshot)) == (str(value), repr(value)):
            return snapshot
    return value


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
    collector = _collector(request.config)
    if collector.state == 'idle':
        # Fixture is being set up outside any tracked scenario (e.g. unannotated
        # test pulling in a step fixture). Don't record.
        yield
        return
    _ensure_teardown_wrapped(fixturedef, collector)
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
    fixturedef: pytest.FixtureDef[object], collector: Collector
) -> None:
    """Wrap a generator fixture's body once so post-yield code runs in
    fixture_teardown state. Idempotent.

    The closure captures the collector directly: fixturedefs live for exactly
    one session, and teardown can fire where no config is reachable (e.g. a
    session-scoped fixture finalized after the last item)."""
    func = fixturedef.func
    if getattr(func, '_pytest_given_teardown_wrapped', False):
        return
    if not inspect.isgeneratorfunction(func):
        return
    original = func
    desc = cast('StepDecorated', original)._step_descriptor
    original_typed = cast('Callable[..., Generator[object]]', original)

    @functools.wraps(original)
    def wrapped(*args: object, **kwargs: object) -> Generator[object]:
        gen = original_typed(*args, **kwargs)
        try:
            value = next(gen)
        except StopIteration:
            return
        yield value
        # Past the yield → teardown. Use the captured collector (not the
        # ContextVar): session-scoped fixtures tear down at session end, after
        # the per-test active collector is cleared.
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
    message = message.removeprefix('Skipped: ').strip()
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
    except Exception:  # noqa: BLE001 — annotations are arbitrary user code; see the docstring
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


def _graft_fixture_recordings(item: pytest.Item, collector: Collector) -> None:
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
    collector = _collector(item.config)
    if collector.inside_unannotated_test:
        collector.inside_unannotated_test = False
        set_active_collector(None)
        return
    if collector.active_scenario_id != NodeId(item.nodeid):
        return
    set_active_collector(None)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> None:
    collector = _collector(item.config)
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
    # This hook's spec carries no config or item, so the session's stash is
    # unreachable here; use the active collector instead. It is set for a
    # tracked scenario's whole runtest protocol, and every terminal report
    # handled below (setup skip/fail, call) arrives before
    # pytest_runtest_teardown clears it.
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
    collector = _collector(session.config)
    try:
        scenarios = group_parametrized(collector.scenarios, collector.param_info)
    except PytestGivenError as error:
        # An exception leaving this hook is neither a test failure nor an
        # INTERNALERROR — pytest lets it out of console_main as a bare
        # traceback. Record it for the terminal summary, write no sink (a
        # report we know to be false is never emitted), and fail the run.
        session.config.stash[_grouping_error_message] = '\n'.join(
            [str(error), *_discard_stale_sinks(session.config)]
        )
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        return
    finally:
        # Both ways out drop the captured parametrize values: they are read
        # only here, and a nested in-process run must not inherit them.
        collector.param_info.clear()
    stories = list(collector._discovered_stories.values())
    glossary = _resolve_glossary(stories, session)
    if glossary is not None:
        glossary = infer_glossary_kinds(glossary, stories)
    report = ReportData(
        metadata=Metadata(
            project=session.config.rootpath.name,
            timestamp=datetime.now(tz=UTC).isoformat(),
            pytest_version=pytest.__version__,
            plugin_version='0.1.0',
            commit_sha=detect_commit_sha(),
            title=_resolve_title(session.config),
        ),
        scenarios=scenarios,
        stories=stories,
        glossary=glossary,
    )
    report_dict = report_to_dict(report)
    report = report_from_dict(report_dict)  # serde round-trip = fidelity guarantee

    json_opt = session.config.getoption('given_json')
    if json_opt is not None:
        json_path = Path(json_opt)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report_dict, indent=2), encoding='utf-8')

    html_opt = session.config.getoption('given_html')
    if html_opt is not None:
        raw_link = session.config.getoption(
            'given_source_link'
        ) or session.config.getini('given_source_link')
        template = resolve_template(raw_link)
        render_html(report, Path(html_opt), source_link_template=template)

    md_opt = session.config.getoption('given_md')
    if md_opt is not None:
        md = render_md(report)
        if md_opt == '-':
            session.config.stash[_md_stdout] = md
        else:
            md_path = Path(md_opt)
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_text(md, encoding='utf-8')

    _run_lint(session, scenarios, glossary, stories)


def _discard_stale_sinks(config: pytest.Config) -> list[str]:
    """Delete the sinks this run would have written, and say which.

    Writing no report leaves the *previous* run's report in place, where it
    reads as current — the one outcome worse than no report at all. Only the
    paths this run was told to write are touched, and each was going to be
    overwritten anyway.
    """
    removed = []
    for option in ('given_json', 'given_html', 'given_md'):
        value = config.getoption(option)
        if value is None or value == '-':
            continue
        path = Path(value)
        if not path.is_file():
            continue
        path.unlink()
        removed.append(f'Removed the previous {path} — it would read as current.')
    return removed


def _run_lint(
    session: pytest.Session,
    scenarios: list[Scenario],
    glossary: Glossary | None,
    stories: list[Story],
) -> None:
    """Run the narration lint; stash the findings for the terminal summary
    and fail the run when any is error-level."""
    config = session.config
    if not _lint_enabled(config):
        return
    findings = apply_config(
        run_runtime_rules(scenarios, glossary, stories)
        + run_ast_rules(scenarios, Path(config.rootpath)),
        parse_rule_levels(config.getini('given_lint_rules')),
        parse_ignore_entries(config.getini('given_lint_ignore')),
    )
    if not findings:
        return
    config.stash[_lint_findings] = findings
    if any(finding.severity == 'error' for finding in findings):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    grouping_error = terminalreporter.config.stash.get(_grouping_error_message, None)
    if grouping_error is not None:
        terminalreporter.write_sep(
            '=', 'pytest-given: parametrize grouping error', red=True
        )
        terminalreporter.line(grouping_error)
    findings = terminalreporter.config.stash.get(_lint_findings, [])
    if findings:
        errors = sum(1 for f in findings if f.severity == 'error')
        title = (
            f'pytest-given: narration lint '
            f'({_count(len(findings), "finding")}, {_count(errors, "error")})'
        )
        terminalreporter.write_sep('=', title, red=errors > 0, yellow=errors == 0)
        rule_width = max(len(f.rule) for f in findings)
        subject_width = max(len(f.subject) for f in findings)
        for f in findings:
            terminalreporter.line(
                f'{f.severity.upper():<5} {f.rule:<{rule_width}}  '
                f'{f.subject:<{subject_width}}  {f.message}'
            )
    md = terminalreporter.config.stash.get(_md_stdout, None)
    if md is not None:
        terminalreporter.write_line('<!-- pytest-given:md:start -->')
        for line in md.splitlines():
            terminalreporter.write_line(line)
        terminalreporter.write_line('<!-- pytest-given:md:end -->')


def _count(n: int, noun: str) -> str:
    return f'{n} {noun}' if n == 1 else f'{n} {noun}s'


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
