"""The pytest-xdist half of a session: what a worker sends, and what the main
process gathers from it.

pytest-given never imports xdist. Its xdist hooks are optional, so the plugin
registers whether xdist is installed or not.
"""

import json
from collections.abc import Callable
from typing import Protocol

import pytest

from ..model import (
    PytestGivenError,
    SessionCapture,
    merge_captures,
    session_capture_from_dict,
    session_capture_to_dict,
)
from .state import WorkerOutput, given_config, session_state

_OUTPUT_KEY = 'pytest_given'


class _WorkerNode(Protocol):
    """The parts of xdist's `WorkerController` the hook reads. `workeroutput`
    is missing on a worker that died before finishing, so it is read with
    `getattr`."""

    config: pytest.Config
    workerinput: dict[str, object]


def is_xdist_worker(config: pytest.Config) -> bool:
    return hasattr(config, 'workerinput')


def is_xdist_controller(config: pytest.Config) -> bool:
    return config.pluginmanager.has_plugin('dsession')


def ship_capture(config: pytest.Config, capture: Callable[[], SessionCapture]) -> None:
    """Leave the capture, or the message grouping refused with, in
    `workeroutput`, which xdist sends the main process after session finish."""
    if not given_config(config).writes_or_lints:
        return
    try:
        output = WorkerOutput(
            capture=json.dumps(session_capture_to_dict(capture())), refusal=None
        )
    except PytestGivenError as error:
        output = WorkerOutput(capture=None, refusal=str(error))
    workeroutput = getattr(config, 'workeroutput', None)
    assert isinstance(workeroutput, dict)
    workeroutput[_OUTPUT_KEY] = output


@pytest.hookimpl(optionalhook=True)
def pytest_testnodeready(node: _WorkerNode) -> None:
    config = node.config
    if given_config(config).writes_or_lints:
        session_state(config).workers[_worker_id(node)] = None


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node: _WorkerNode, error: object | None) -> None:
    """A worker that finished goes down with its output. One that crashed goes
    down with an `error` and keeps the None it came up with: xdist may restart
    it under a new id, but what it had run is gone. A worker hit by Ctrl-C goes
    down twice, with its output and then with an error, and keeps the output."""
    config = node.config
    output = getattr(node, 'workeroutput', {}).get(_OUTPUT_KEY)
    if given_config(config).writes_or_lints and error is None and output is not None:
        session_state(config).workers[_worker_id(node)] = output


def interrupted_before_capture(session: pytest.Session) -> str | None:
    """Why the main process holds no full capture, when the run was interrupted
    before it had them all: on Ctrl-C it stops reading the workers' events, so a
    worker still up never sends its capture."""
    config = session.config
    if (
        is_xdist_controller(config)
        and None in session_state(config).workers.values()
        and session.exitstatus == pytest.ExitCode.INTERRUPTED
    ):
        return (
            'the run was interrupted before every pytest-xdist worker sent its '
            'scenarios'
        )
    return None


def merged_capture(config: pytest.Config) -> SessionCapture:
    workers = session_state(config).workers
    for output in workers.values():
        if output is not None and output['refusal'] is not None:
            raise PytestGivenError(output['refusal'])
    if lost := [worker for worker, output in workers.items() if output is None]:
        noun, its = ('worker', 'its') if len(lost) == 1 else ('workers', 'their')
        raise PytestGivenError(
            f'pytest-xdist {noun} {", ".join(lost)} went down before sending '
            f'{its} scenarios, so the report would miss them.'
        )
    captures = []
    for output in workers.values():
        assert output is not None
        assert output['capture'] is not None
        captures.append(session_capture_from_dict(json.loads(output['capture'])))
    return merge_captures(captures)


def _worker_id(node: _WorkerNode) -> str:
    return str(node.workerinput['workerid'])
