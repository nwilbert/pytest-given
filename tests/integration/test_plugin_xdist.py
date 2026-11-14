import json
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from pytest_given import given, scenario, then, when
from pytest_given.model import SessionCapture, session_capture_to_dict
from pytest_given.plugin.state import WorkerOutput
from tests.ubiquitous_language import pg

_SUITE = """
    from pytest_given import scenario, given, when, then

    @scenario('Buy coffee')
    def test_buy():
        with given('a machine'):
            machine = []
        with when('I insert money'):
            machine.append('coin')
        with then('I get coffee'):
            assert machine == ['coin']
"""

# The scheduler xdist picks shows only under -v; the header shows the mode the
# run settled on, after pytest-given's configure.
_DIST_HEADER = """
    def pytest_report_header(config):
        return f"dist mode: {config.getoption('dist')}"
"""

_USAGE_ERROR = pytest.ExitCode.USAGE_ERROR.value
_OK = pytest.ExitCode.OK.value


@scenario(
    t'Under pytest-xdist, a {pg["Report"].l} or the {pg["Narration lint"].l} '
    t'runs on --dist loadfile, which pytest-given picks when no --dist is given',
    tags=['spec/xdist-reports'],
)
@pytest.mark.parametrize(
    ('args', 'dist'),
    [
        ('-n 2 --given-json=report.json', 'loadfile'),
        ('-n 2 --dist loadfile --given-lint', 'loadfile'),
        ('-n 2 --no-given-lint', 'load'),
    ],
    ids=['bare', 'loadfile', 'neither'],
)
def test_a_report_or_lint_under_xdist_runs_on_loadfile(pytester, args, dist):
    """loadfile keeps a test's parametrize cases on one worker, which grouping
    needs: their raw values cannot leave the worker. pytest-given settles the
    mode at configure time, so a run that only collects shows it, and starts no
    worker."""
    with given('a suite that would otherwise pass'):
        pytester.makepyfile(_SUITE)
        pytester.makeconftest(_DIST_HEADER)
    with when(t'pytest starts with {args}'):
        result = pytester.runpytest(*args.split(), '--collect-only')
    with then(t'the run settles on --dist {dist}'):
        assert result.ret == _OK
        assert f'dist mode: {dist}' in result.stdout.str()


@scenario(
    t'Under pytest-xdist, a {pg["Report"].l} or the {pg["Narration lint"].l} '
    t'stops before it collects when another --dist is chosen',
    tags=['validation', 'spec/xdist-reports'],
)
@pytest.mark.parametrize(
    'args',
    [
        '-n 2 --dist load --given-json=report.json',
        '-n 2 --dist worksteal --given-lint',
        '-n 2 -d --given-json=report.json',
    ],
    ids=['load', 'worksteal', 'distload'],
)
def test_a_report_or_lint_under_another_dist_stops(pytester, args):
    with given('a suite that would otherwise pass'):
        pytester.makepyfile(_SUITE)
    with when(t'the suite runs with {args}'):
        result = pytester.runpytest(*args.split())
    with then('it stops with a usage error, before any test runs'):
        assert result.ret == _USAGE_ERROR
        assert 'passed' not in result.stdout.str()


def test_a_dist_in_addopts_counts_as_chosen(pytester):
    pytester.makeini(
        """
        [pytest]
        addopts = --dist load
        """
    )
    pytester.makepyfile(_SUITE)
    result = pytester.runpytest('-n', '2', '--given-json=report.json')
    assert result.ret == _USAGE_ERROR


def test_a_dist_without_workers_runs_serially(pytester):
    pytester.makeini(
        """
        [pytest]
        addopts = --dist loadscope
        """
    )
    pytester.makepyfile(_SUITE)
    result = pytester.runpytest('--given-json=report.json')
    assert result.ret == _OK
    assert (pytester.path / 'report.json').exists()


def test_a_plugin_loaded_from_a_conftest_picks_loadfile_for_a_bare_n(
    pytester, monkeypatch
):
    """With autoload off, xdist arrives by `-p` and pytest-given by a conftest,
    and pytest-given still reads the --dist the user gave."""
    monkeypatch.setenv('PYTEST_DISABLE_PLUGIN_AUTOLOAD', '1')
    pytester.makeconftest(
        "pytest_plugins = ['pytest_given.plugin']\n" + textwrap.dedent(_DIST_HEADER)
    )
    pytester.makepyfile(_SUITE)
    result = pytester.runpytest(
        '-p', 'xdist', '-n', '2', '--given-json=report.json', '--collect-only'
    )
    assert result.ret == _OK
    assert 'dist mode: loadfile' in result.stdout.str()


def test_the_dist_refusal_names_loadfile(pytester):
    pytester.makepyfile(_SUITE)
    result = pytester.runpytest('-n', '2', '--dist', 'load', '--given-md=report.md')
    result.stderr.fnmatch_lines(['*not with --dist load*--dist loadfile*'])
    assert not (pytester.path / 'report.md').exists()


# test_a.py declares the story and its glossary itself, so the main process —
# which never imports a test module — can only learn of them from a worker. Its
# enum tag and parameters are `str` subclasses, which execnet refuses to carry.
# Its then-only scenario has an ignore entry, and test_b.py has an empty step:
# unless both files' scenarios reach the lint, it finds the entry stale or
# misses the step. The empty-step rule reads the step's source, which the JSON
# report leaves out, so its finding shows that the source crossed too.
_SPLIT_SUITE = {
    'test_a': """
        import enum

        import pytest
        from pytest_given import Glossary, scenario, sentence, story, given, when, then

        class Size(enum.StrEnum):
            SMALL = 'small'
            LARGE = 'large'

        class Tag(enum.StrEnum):
            ORDERING = 'ordering'

        g = Glossary()
        guest = g.actor('Guest')
        orders = g.activity('orders')
        coffee = g.work_object('Coffee')
        ordering = story('Ordering', [sentence(guest, orders, coffee)])

        def _pour(size):
            with when(t'the barista pours a {size} cup'):
                assert size

        @scenario(t'A {guest} {orders} {coffee}', stories=ordering, tags=[Tag.ORDERING])
        @pytest.mark.parametrize('size', [Size.SMALL, Size.LARGE])
        def test_order(size):
            with when(t'the {guest} {orders} a {size} {coffee}'):
                _pour(size)
            with then('it is served'):
                assert True

        @scenario('Only a check')
        def test_only_then():
            with then('it holds'):
                assert True
    """,
    'test_b': """
        from pytest_given import scenario, given, when, then

        @scenario('Pay at the counter')
        def test_pay():
            with given('an order'):
                assert True
            with when('the guest pays'):
                assert True
            with then('the order is paid'):
                assert True

        @scenario('Leave a tip', tags=['extra'])
        def test_tip():
            with given('a paid order'):
                pass
            with when('the guest tips'):
                assert True
            with then('the tip is recorded'):
                assert True
    """,
}

_IGNORE_TEST_A_ONLY_THEN = """
    [pytest]
    given_lint_ignore = missing-phase: *::test_only_then
"""


def _workers_by_file(lines: list[str]) -> dict[str, set[str]]:
    """Which workers ran each file, from xdist's `-v` lines:
    `[gw0] [ 25%] PASSED test_a.py::test_order[small]`."""
    workers: dict[str, set[str]] = {}
    for line in lines:
        match = re.match(r'\[(gw\d+)\] .* PASSED (\S+?)::', line)
        if match:
            workers.setdefault(match[2], set()).add(match[1])
    return workers


def _comparable(path: Path) -> dict:
    """A report without what differs between any two runs: the timestamp and
    the durations."""
    report = json.loads(path.read_text(encoding='utf-8'))
    report['metadata']['timestamp'] = ''
    for recorded in report['scenarios']:
        recorded['duration_ms'] = 0
    return report


@scenario(
    t'Under pytest-xdist, the {pg["Report"].l} and the {pg["Narration lint"].l} '
    t'see the same {pg["Scenario"].l}s, {pg["Story"].l}s and '
    t'{pg["Glossary"].l} as a serial run',
    tags=['spec/xdist-reports'],
)
def test_an_xdist_run_reports_and_lints_like_a_serial_one(pytester):
    """The one test here that starts real workers, as each costs a second."""
    with given('two test files, one declaring a story and its glossary'):
        pytester.makepyfile(**_SPLIT_SUITE)
    with given('an ignore entry for test_a.py and an empty step in test_b.py'):
        pytester.makeini(_IGNORE_TEST_A_ONLY_THEN)
    with when('the suite runs with --given-lint without -n, and on 2 xdist workers'):
        serial = pytester.runpytest('--given-lint', '--given-json=serial.json')
        distributed = pytester.runpytest(
            '-n', '2', '-v', '--given-lint', '--given-json=xdist.json'
        )
    with then('each file ran on a worker of its own'):
        # The lint's failure counts as one error.
        distributed.assert_outcomes(passed=5, errors=1)
        workers = _workers_by_file(distributed.stdout.lines)
        assert set(workers) == {'test_a.py', 'test_b.py'}
        assert sorted(map(sorted, workers.values())) == [['gw0'], ['gw1']]
    with then('both reports hold the same scenarios, stories and glossary'):
        expected = _comparable(pytester.path / 'serial.json')
        assert expected['scenarios']
        assert expected['stories']
        assert expected['glossary']
        assert _comparable(pytester.path / 'xdist.json') == expected
    with then(
        'both runs flag the empty step in test_b.py, and neither finds the '
        'ignore entry stale'
    ):
        for result in (serial, distributed):
            assert result.ret == pytest.ExitCode.TESTS_FAILED
            result.stdout.fnmatch_lines(['*ERROR*empty-step*test_b.py::test_tip*'])
            assert 'stale-ignore' not in result.stdout.str()


_REFUSED = """
    import pytest
    from pytest_given import scenario, then

    @scenario('Differs per case')
    @pytest.mark.parametrize('flag', [True, False])
    def test_differs(flag):
        if flag:
            with then('one thing holds'):
                assert True
        else:
            with then('another thing holds'):
                assert True
"""


@pytest.fixture
def previous_report(pytester) -> Path:
    """A report.json a run that writes none must leave as it is."""
    path = pytester.path / 'report.json'
    path.write_text('previous', encoding='utf-8')
    return path


class _AsWorker:
    """Marks the inner run's config as an xdist worker's, as xdist does, so the
    worker side runs in this process where coverage sees it."""

    def __init__(self) -> None:
        self.workeroutput: dict[str, object] = {}

    def pytest_configure(self, config: pytest.Config) -> None:
        config.workerinput = {'workerid': 'gw0'}
        config.workeroutput = self.workeroutput


def test_a_worker_sends_its_capture_instead_of_writing(pytester):
    pytester.makepyfile(_SUITE)
    worker = _AsWorker()
    result = pytester.runpytest('--given-json=report.json', plugins=[worker])
    assert result.ret == _OK
    assert not (pytester.path / 'report.json').exists()
    output = worker.workeroutput['pytest_given']
    assert output['refusal'] is None
    capture = json.loads(output['capture'])
    [scenario] = capture['scenarios']
    assert scenario['id'].endswith('.py::test_buy')
    assert capture['collection_index'] == {scenario['id']: 0}


def test_a_worker_sends_its_refusal(pytester):
    pytester.makepyfile(_REFUSED)
    worker = _AsWorker()
    result = pytester.runpytest('--given-json=report.json', plugins=[worker])
    assert result.ret == _OK
    output = worker.workeroutput['pytest_given']
    assert output['capture'] is None
    assert output['refusal']


def test_a_worker_with_no_report_and_no_lint_sends_nothing(pytester):
    pytester.makepyfile(_SUITE)
    worker = _AsWorker()
    pytester.runpytest('--no-given-lint', plugins=[worker])
    assert 'pytest_given' not in worker.workeroutput


@dataclass(frozen=True)
class _Worker:
    """A worker the fake main process hears from: it comes up, then goes down
    once per entry of `downs`, with that error, or None for a clean finish."""

    id: str
    output: WorkerOutput | None = None
    downs: tuple[str | None, ...] = (None,)


class _AsController:
    """Makes the inner run's process an xdist main process, as far as
    pytest-given can tell, and feeds its node hooks the events of workers that
    never start. The main-process side then runs in this process, where
    coverage sees it, without a worker's start-up cost."""

    def __init__(self, *workers: _Worker, interrupted: bool = False) -> None:
        self.workers = workers
        self.interrupted = interrupted

    def pytest_configure(self, config: pytest.Config) -> None:
        config.pluginmanager.register(object(), 'dsession')

    @pytest.hookimpl(trylast=True)
    def pytest_sessionstart(self, session: pytest.Session) -> None:
        hook = session.config.hook
        for worker in self.workers:
            output = {} if worker.output is None else {'pytest_given': worker.output}
            node = SimpleNamespace(
                config=session.config,
                workerinput={'workerid': worker.id},
                workeroutput=output,
            )
            hook.pytest_testnodeready(node=node)
            for error in worker.downs:
                hook.pytest_testnodedown(node=node, error=error)

    @pytest.hookimpl(tryfirst=True)
    def pytest_sessionfinish(self, session: pytest.Session) -> None:
        if self.interrupted:
            session.exitstatus = pytest.ExitCode.INTERRUPTED


def _empty_capture() -> WorkerOutput:
    capture = SessionCapture(
        scenarios=[], collection_index={}, stories=[], glossary=None
    )
    return WorkerOutput(
        capture=json.dumps(session_capture_to_dict(capture)), refusal=None
    )


def _line_after(lines: list[str], header: str) -> str:
    return lines[next(i for i, line in enumerate(lines) if header in line) + 1]


def test_a_worker_refusal_fails_the_run_like_a_serial_one(pytester):
    pytester.makepyfile(_REFUSED)
    worker = _AsWorker()
    pytester.runpytest('--given-json=report.json', plugins=[worker])
    serial = pytester.runpytest('--given-json=report.json')
    refused = _Worker('gw0', output=worker.workeroutput['pytest_given'])
    distributed = pytester.runpytest(
        '--given-json=report.json', plugins=[_AsController(refused)]
    )
    assert distributed.ret == pytest.ExitCode.TESTS_FAILED
    header = 'pytest-given: report not written'
    assert _line_after(distributed.stdout.lines, header) == _line_after(
        serial.stdout.lines, header
    )
    assert not (pytester.path / 'report.json').exists()


@pytest.mark.parametrize(
    ('workers', 'message'),
    [
        (['gw1'], 'pytest-xdist worker gw1 went down before sending its scenarios'),
        (
            ['gw1', 'gw2'],
            'pytest-xdist workers gw1, gw2 went down before sending their scenarios',
        ),
    ],
)
def test_a_crashed_worker_fails_the_report(pytester, previous_report, workers, message):
    pytester.makepyfile(_SUITE)
    crashed = [_Worker(worker, downs=('crashed',)) for worker in workers]
    result = pytester.runpytest(
        '--given-json=report.json', plugins=[_AsController(*crashed)]
    )
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines([f'*{message}*'])
    assert not previous_report.exists()


def test_an_interrupted_xdist_run_keeps_the_previous_report(pytester, previous_report):
    """On Ctrl-C the main process stops reading the workers' events, so a
    worker still up never goes down."""
    pytester.makepyfile(_SUITE)
    still_up = _Worker('gw0', downs=())
    finished = _Worker('gw1', output=_empty_capture())
    controller = _AsController(still_up, finished, interrupted=True)
    result = pytester.runpytest('--given-json=report.json', plugins=[controller])
    result.stdout.fnmatch_lines(['*interrupted before every pytest-xdist worker*'])
    result.stdout.no_fnmatch_line('*went down before sending*')
    assert previous_report.read_text(encoding='utf-8') == 'previous'


def test_a_worker_hit_by_ctrl_c_keeps_the_capture_it_sent(pytester, previous_report):
    """xdist reports such a worker down twice: with its output, then with an
    error."""
    pytester.makepyfile(_SUITE)
    hit = _Worker('gw0', output=_empty_capture(), downs=(None, 'keyboard-interrupt'))
    controller = _AsController(hit, interrupted=True)
    pytester.runpytest('--given-json=report.json', plugins=[controller])
    report = json.loads(previous_report.read_text(encoding='utf-8'))
    assert report['scenarios'] == []
