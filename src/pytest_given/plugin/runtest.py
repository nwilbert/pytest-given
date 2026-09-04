"""The per-item hooks — what happens around one test.

Setup publishes the collector and opens the scenario, teardown unpublishes it,
and the two report hooks put a failure behind the right phase and close the
scenario out.
"""

from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest

from ..capture import (
    Collector,
    get_active_collector,
    is_internal_path,
    item_source,
    parse_short_repr,
    set_active_collector,
    snapshot_param_value,
)
from ..model import (
    ErrorInfo,
    NodeId,
    ParamSpec,
    Status,
)
from .fixtures import graft_fixture_recordings
from .state import given_config, scenario_marker, session_collector, session_state

if TYPE_CHECKING:
    from _pytest._code.code import TracebackEntry


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> Generator[None]:
    collector = session_collector(item.config)
    marker = scenario_marker(item)
    if marker is None:
        # Unannotated test: `with given(...)` inside it warns instead of
        # raising. Teardown returns the collector to idle and unpublishes it.
        collector.enter_unannotated_test()
        session_state(item.config).published_for = NodeId(item.nodeid)
        set_active_collector(collector)
        yield
        return

    # A @scenario marker was read off `item.function`, so the item is a
    # Function collected from a Module and `.module` is always there.
    assert isinstance(item, pytest.Function)
    module = item.module.__name__
    node_id = NodeId(item.nodeid)
    relpath_raw, lineno0, _ = item.location
    source = item_source(relpath_raw, (lineno0 or 0) + 1)
    collector.start_scenario(
        scenario_id=node_id,
        name=marker.name,
        module=module,
        tags=marker.tags,
        source=source,
        story=marker.story,
        activity_ids=marker.activity_ids,
    )
    session_state(item.config).published_for = node_id
    set_active_collector(collector)
    # Pre-fixture-setup work done; let pytest run fixture setup here.
    #
    # `finally`, because all three of these matter most when setup *failed*: a
    # fixture exception is recorded onto the scenario by `makereport`, and the
    # scenario still needs the `given` steps its fixtures recorded before the
    # failure. Old-style `hookwrapper` runs post-yield code after a raising
    # inner hook anyway; `wrapper=True` throws in at the yield instead, so
    # without this the migration pytest recommends would silently drop them.
    try:
        yield
    finally:
        _finish_setup(item, node_id, collector, group=marker.group_parametrized)


def _finish_setup(
    item: pytest.Item, node_id: NodeId, collector: Collector, *, group: bool
) -> None:
    _capture_param_spec(item, node_id, group=group)
    graft_fixture_recordings(item, collector)
    # The clock starts past fixture setup, so a scenario's duration is its own.
    collector.begin_timing()


def _capture_param_spec(item: pytest.Item, node_id: NodeId, *, group: bool) -> None:
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
    session_state(item.config).param_info[node_id] = ParamSpec(
        names=names,
        values=[
            snapshot_param_value(funcargs.get(name, callspec.params[name]))
            for name in names
        ],
        group=group,
    )


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item: pytest.Item) -> None:
    """Undo what `pytest_runtest_setup` published for this item.

    Keyed on `published_for`, not on `active_scenario_id`: the call-phase
    logreport has already run `finish_scenario`, so an annotated scenario's id
    is None here and a guard reading it would never match — leaving the whole
    finished session reachable from the process-global ContextVar. `trylast`
    puts this after the finalizers, which still need the collector.
    """
    state = session_state(item.config)
    if state.published_for != NodeId(item.nodeid):
        return
    session_collector(item.config).exit_unannotated_test()
    state.published_for = None
    set_active_collector(None)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> None:
    """Put the error behind a failing phase on the scenario.

    Setup (a fixture exception) and call (a test-body failure) fail the
    *active* scenario. Teardown is the odd one out: the call report has already
    run `finish_scenario`, so there is no active scenario left and the one with
    that node id is amended instead — otherwise a fixture raising past its
    `yield` leaves a green scenario behind a run pytest counted as an error.
    """
    if call.excinfo is None or call.when not in ('setup', 'call', 'teardown'):
        return
    collector = session_collector(item.config)
    node_id = NodeId(item.nodeid)
    # Checked before any traceback work: `getrepr` below is the expensive
    # per-frame scan, and an item this plugin recorded nothing for — an
    # undecorated test in a suite that merely installs pytest-given — would
    # otherwise pay it on every teardown error only to discard the result.
    if not collector.records(node_id):
        return
    # A skip's traceback is pure skip machinery — the scenario carries a
    # structured skip_reason instead. Short-circuited before getrepr, whose
    # per-frame AST scan would otherwise run for every skipped scenario. Not
    # gated on --given-all-frames: a skip never wants a traceback regardless.
    if call.excinfo.errisinstance(pytest.skip.Exception):
        return
    if not given_config(item.config).all_frames:
        _filter_internal_frames(call.excinfo)
    error_repr = call.excinfo.getrepr(style='short')
    message = str(call.excinfo.value)
    frames, error_tail = parse_short_repr(str(error_repr))
    collector.fail(
        node_id,
        ErrorInfo(message=message, frames=frames, error_tail=error_tail),
    )


@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    # This hook's spec carries no config or item, so the session's stash is
    # unreachable here; the active collector stands in. It is set for a tracked
    # scenario's whole runtest protocol, and every terminal report handled
    # below arrives before pytest_runtest_teardown clears it.
    node_id = NodeId(report.nodeid)
    collector = get_active_collector()
    if collector is None or collector.active_scenario_id != node_id:
        return
    # Three terminal cases: a setup-time skip (@pytest.mark.skip), a failed
    # setup report with no call report at all (a fixture exception), and the
    # call report. All three must reach finish_scenario, or _current_scenario is
    # orphaned — silently dropped from the report, and still not 'idle', so a
    # later unannotated test's `with given(...)` would push into it.
    setup_skip = report.when == 'setup' and report.skipped
    setup_fail = report.when == 'setup' and report.failed
    if report.when != 'call' and not setup_skip and not setup_fail:
        return
    status: Status = (
        'passed' if report.passed else 'failed' if report.failed else 'skipped'
    )
    skip_reason = _extract_skip_reason(report.longrepr) if status == 'skipped' else None
    collector.finish_scenario(status=status, skip_reason=skip_reason)


def _filter_internal_frames(excinfo: pytest.ExceptionInfo[BaseException]) -> None:
    """Drop internal frames from ``excinfo.traceback`` before ``getrepr`` runs.

    ``getrepr(style='short')`` runs pytest's per-frame AST statement-range scan
    once per surviving entry, so pruning the pluggy/``_pytest``/decorator frames
    here — rather than after parsing — is what removes the O(N²) traceback cost
    on large failing suites. Only pytest's view of the traceback is rewritten;
    the exception's native ``__traceback__`` is left intact.

    Lives here rather than beside the parser because rewriting a pytest object
    would otherwise make ``capture/`` import pytest and the private ``_pytest``
    traceback type. It applies ``capture``'s own ``is_internal_path``, so the
    pre-filter and the post-parse classification stay one rule. If every entry
    classifies as internal, the original traceback is kept so ``getrepr`` still
    has a crash frame to format.
    """
    filtered = excinfo.traceback.filter(lambda entry: not _is_internal_entry(entry))
    if len(filtered) > 0:
        excinfo.traceback = filtered


def _is_internal_entry(entry: TracebackEntry) -> bool:
    return is_internal_path(str(entry.path))


def _extract_skip_reason(longrepr: object) -> str | None:
    """Return a human-readable reason from pytest's TestReport.longrepr, or None.

    Pytest emits skipped longrepr as (path, lineno, message), where message is
    typically "Skipped: <reason>" (mark-based) or "<reason>" (call-time).
    Returns None for empty messages, the reasonless `<Skipped instance>`
    placeholder, pytest's default "unconditional skip" (emitted when
    @pytest.mark.skip is used with no reason), or any shape we don't recognize.
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
