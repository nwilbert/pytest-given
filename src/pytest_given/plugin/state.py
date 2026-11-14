"""What a session keeps in `config.stash`, and the accessors that read it.

Five values, one writer each: `Collector` is the recorder itself, created at
session start; `GivenConfig` is this run's options, parsed once at configure
time; `SessionState` is the bookkeeping the per-item hooks pass between each
other; `SessionOutcome` is what session finish leaves for the terminal summary;
the capture-bootstrap mark says capture was prepared for this run. The stash
rather than module globals throughout, so a nested in-process run
(pytester, `pytest.main`) gets its own set instead of rebinding — and thereby
clobbering — the outer session's.

`scenario_marker` is here for the same reason the accessors are: it reads what
a test function declared, and none of the hooks that ask owns the answer. It
adds only the `.function` hop — reading the marker itself is `capture`'s.
"""

from dataclasses import dataclass, field
from typing import TypedDict

import pytest

from ..capture import (
    Collector,
    FixtureRecording,
    ScenarioDecorator,
)
from ..capture import (
    scenario_marker as capture_scenario_marker,
)
from ..lint import LintConfig, LintFinding
from ..model import NodeId, ParamInfo, ReportUrl
from ..report import SinkConfig


@dataclass(frozen=True, kw_only=True)
class GivenConfig:
    lint: LintConfig
    lint_enabled: bool
    sinks: SinkConfig
    title: str | None
    report_url: ReportUrl | None
    all_frames: bool

    @property
    def writes_or_lints(self) -> bool:
        return self.sinks.writes_anything() or self.lint_enabled


@dataclass(kw_only=True)
class SessionOutcome:
    """What session finish leaves for the terminal summary to print."""

    report_error: str | None = None
    lint_error: str | None = None
    md_stdout: str | None = None
    # Why a run that configured sinks wrote none (`--collect-only` and kin).
    report_note: str | None = None
    # None when the lint did not run, so a clean run can still say it ran.
    findings: list[LintFinding] | None = None


class WorkerOutput(TypedDict):
    """What a pytest-xdist worker leaves in its `workeroutput`: its session
    capture as JSON text, or the message its grouping refused with. Text, since
    execnet refuses a `str` or `int` subclass, such as an enum parameter, that
    a dict would carry through."""

    capture: str | None
    refusal: str | None


@dataclass(kw_only=True)
class SessionState:
    """The per-item bookkeeping the hooks pass between each other.

    None of it is the collector's business — nothing in `capture/` reads any of
    it — so it lives in the session's stash beside the recorder rather than as
    attributes on it, which keeps `Collector` to what it records.

    `published_for` is the item whose setup published the collector to the
    ContextVar, so teardown clears only what it published. `fixture_recordings`
    holds the latest recording per fixturedef — pytest caches one instance per
    def, so that is the one its cached value came from — and is
    insertion-ordered by setup time, which is what lets the graft take them in
    dependency order: `item.fixturenames` can list a dependent before its
    dependency. `collection_order` is each item's position as collected, before
    a reordering plugin rearranges `session.items`.
    """

    param_info: ParamInfo = field(default_factory=dict)
    published_for: NodeId | None = None
    fixture_recordings: dict[pytest.FixtureDef[object], FixtureRecording] = field(
        default_factory=dict
    )
    collection_order: dict[NodeId, int] = field(default_factory=dict)
    # The main process of a pytest-xdist run: each worker that came up, by id,
    # with its output, or None until it sends one.
    workers: dict[str, WorkerOutput | None] = field(default_factory=dict)


# Private, so "one writer each" is a property of this module rather than a
# convention its readers are asked to keep: the two seeders below are the only
# way anything gets into the stash.
_collector_key: pytest.StashKey[Collector] = pytest.StashKey()
_given_config_key: pytest.StashKey[GivenConfig] = pytest.StashKey()
_session_outcome_key: pytest.StashKey[SessionOutcome] = pytest.StashKey()
_session_state_key: pytest.StashKey[SessionState] = pytest.StashKey()
_capture_bootstrapped_key: pytest.StashKey[bool] = pytest.StashKey()


def mark_capture_bootstrapped(config: pytest.Config) -> None:
    config.stash[_capture_bootstrapped_key] = True


def capture_bootstrapped(config: pytest.Config) -> bool:
    return config.stash.get(_capture_bootstrapped_key, False)


def store_given_config(config: pytest.Config, given: GivenConfig) -> None:
    """Publish the resolved options. `pytest_configure`'s, and only its —
    there is one such hook per plugin, and everything else reads the result."""
    config.stash[_given_config_key] = given


def init_session_stash(config: pytest.Config) -> None:
    """Seed the three values a session owns. `pytest_sessionstart`'s.

    The collector is built from `GivenConfig`, so this runs after
    `store_given_config` — which the real lifecycle guarantees, since
    `pytest_configure` precedes `pytest_sessionstart`.
    """
    config.stash[_collector_key] = Collector(
        capture_step_source=given_config(config).lint_enabled
    )
    config.stash[_session_state_key] = SessionState()
    config.stash[_session_outcome_key] = SessionOutcome()


def scenario_marker(item: pytest.Item) -> ScenarioDecorator | None:
    """The `@scenario` marker on an item's test function, or None — also for
    items without a `.function` (e.g. DoctestItem), which cannot carry one."""
    return capture_scenario_marker(getattr(item, 'function', None))


def session_collector(config: pytest.Config) -> Collector:
    return config.stash[_collector_key]


def given_config(config: pytest.Config) -> GivenConfig:
    return config.stash[_given_config_key]


def session_outcome(config: pytest.Config) -> SessionOutcome:
    return config.stash[_session_outcome_key]


def session_state(config: pytest.Config) -> SessionState:
    return config.stash[_session_state_key]
