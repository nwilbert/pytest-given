"""What a session keeps in `config.stash`, and the accessors that read it.

Four values, one writer each: `Collector` is the recorder itself, created at
session start; `GivenConfig` is this run's options, parsed once at configure
time; `SessionState` is the bookkeeping the per-item hooks pass between each
other; `SessionOutcome` is what session finish leaves for the terminal summary.
The stash rather than module globals throughout, so a nested in-process run
(pytester, `pytest.main`) gets its own set instead of rebinding — and thereby
clobbering — the outer session's. The keys are private and the two seeders are
the only writers, so "one writer each" is enforced rather than asked for.

`scenario_marker` is here for the same reason the accessors are: it reads what
a test function declared, three of this package's modules ask it, and none of
them owns the answer.
"""

from dataclasses import dataclass, field
from typing import NamedTuple

import pytest

from ..capture import (
    Collector,
    FixtureRecording,
    ScenarioDecorator,
)
from ..capture import (
    scenario_marker as capture_scenario_marker,
)
from ..lint import Finding, LintConfig
from ..model import NodeId, ParamInfo
from ..report import SinkConfig


@dataclass(frozen=True, kw_only=True)
class GivenConfig:
    lint: LintConfig
    lint_enabled: bool
    sinks: SinkConfig
    title: str | None
    all_frames: bool


@dataclass(kw_only=True)
class SessionOutcome:
    """What session finish leaves for the terminal summary to print."""

    report_error: str | None = None
    md_stdout: str | None = None
    findings: list[Finding] = field(default_factory=list)


class FixtureInstanceKey(NamedTuple):
    """One fixture *instance*: the def it came from, plus its cache key.

    Both ends of the graft build this key, and they reach the cache key two
    ways — at setup from the request, at graft from what pytest cached. Named
    rather than a bare `tuple[object, object]`, which said nothing about either
    half and let them be built in the wrong order.
    """

    fixturedef_id: int
    cache_key: object


@dataclass(kw_only=True)
class SessionState:
    """The per-item bookkeeping the hooks pass between each other.

    None of it is the collector's business — nothing in `capture/` reads any of
    it — so it lives in the session's stash beside the recorder rather than as
    attributes on it, which keeps `Collector` to what it records.

    `published_for` is the item whose setup published the collector to the
    ContextVar, so teardown clears only what it published. `fixture_recordings`
    is insertion-ordered by setup time, which is what lets the graft take them
    in dependency order — `item.fixturenames` can list a dependent before its
    dependency.
    """

    param_info: ParamInfo = field(default_factory=dict)
    published_for: NodeId | None = None
    fixture_recordings: dict[FixtureInstanceKey, FixtureRecording] = field(
        default_factory=dict
    )


# Private, so "one writer each" is a property of this module rather than a
# convention its readers are asked to keep: the two seeders below are the only
# way anything gets into the stash.
_collector_key: pytest.StashKey[Collector] = pytest.StashKey()
_given_config_key: pytest.StashKey[GivenConfig] = pytest.StashKey()
_session_outcome_key: pytest.StashKey[SessionOutcome] = pytest.StashKey()
_session_state_key: pytest.StashKey[SessionState] = pytest.StashKey()


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
    """Get the _scenario attribute from a test function, if present.

    Returns None for items without a `.function` (e.g. DoctestItem) — those
    can't carry @scenario, so they're never load-bearing here.
    """
    return capture_scenario_marker(getattr(item, 'function', None))


def session_collector(config: pytest.Config) -> Collector:
    return config.stash[_collector_key]


def given_config(config: pytest.Config) -> GivenConfig:
    return config.stash[_given_config_key]


def session_outcome(config: pytest.Config) -> SessionOutcome:
    return config.stash[_session_outcome_key]


def session_state(config: pytest.Config) -> SessionState:
    return config.stash[_session_state_key]
