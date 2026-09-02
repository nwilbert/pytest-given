"""What a session keeps in `config.stash`, and the accessors that read it.

Four values, one writer each: `Collector` is the recorder itself, created at
session start; `GivenConfig` is this run's options, parsed once at configure
time; `SessionState` is the bookkeeping the per-item hooks pass between each
other; `SessionOutcome` is what session finish leaves for the terminal summary.
The stash rather than module globals throughout, so a nested in-process run
(pytester, `pytest.main`) gets its own set instead of rebinding — and thereby
clobbering — the outer session's.
"""

from dataclasses import dataclass, field

import pytest

from ..capture import Collector
from ..lint import Finding, LintConfig
from ..model import FixtureRecording, NodeId, ParamInfo
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


# One fixture *instance*: the def it came from, plus its cache key. Both ends
# of the graft build this key, and they reach the cache key two ways — at setup
# from the request, at graft from what pytest cached.
type FixtureInstanceKey = tuple[object, object]


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


collector_key: pytest.StashKey[Collector] = pytest.StashKey()
given_config_key: pytest.StashKey[GivenConfig] = pytest.StashKey()
session_outcome_key: pytest.StashKey[SessionOutcome] = pytest.StashKey()
session_state_key: pytest.StashKey[SessionState] = pytest.StashKey()


def session_collector(config: pytest.Config) -> Collector:
    return config.stash[collector_key]


def given_config(config: pytest.Config) -> GivenConfig:
    return config.stash[given_config_key]


def session_outcome(config: pytest.Config) -> SessionOutcome:
    return config.stash[session_outcome_key]


def session_state(config: pytest.Config) -> SessionState:
    return config.stash[session_state_key]
