"""What a session keeps in `config.stash`, and the accessors that read it.

Four values, one writer each: `Collector` is the recorder itself, created at
session start; `GivenConfig` is this run's options, parsed once at configure
time; `SessionState` is the bookkeeping the per-item hooks pass between each
other; `SessionOutcome` is what session finish leaves for the terminal
summary. The stash rather than module globals throughout, so a
nested in-process run (pytester, `pytest.main`) gets its own set instead of
rebinding — and thereby clobbering — the outer session's.

Nothing here is underscored. Every name in this module is read by a sibling —
that is what the module is for — so a leading underscore would claim a privacy
none of them has and that every import already contradicts. Package-internal
is what they are, and the package boundary is what states it: `plugin/` has no
`__all__` beyond its hook surface, and nothing outside it imports from here.
Names genuinely private to one module (`_sink_config`, `_run_lint`) keep the
underscore, which is then worth something.
"""

from dataclasses import dataclass, field

import pytest

from ..capture import (
    Collector,
)
from ..lint import (
    Finding,
    IgnoreEntry,
    Level,
    RuleId,
)
from ..model import (
    NodeId,
    ParamInfo,
)

collector_key: pytest.StashKey[Collector] = pytest.StashKey()


def session_collector(config: pytest.Config) -> Collector:
    """The collector owned by this session, created at `pytest_sessionstart`.

    Lives in `config.stash` rather than a module global so a nested in-process
    run (pytester, `pytest.main`) gets its own instance instead of rebinding —
    and thereby clobbering — the outer session's.
    """
    return config.stash[collector_key]


@dataclass(frozen=True, kw_only=True)
class GivenConfig:
    """This run's pytest-given options, parsed once.

    Parsed eagerly in `pytest_configure` — a typo in a rule name or a
    source-link preset is a `UsageError` before the suite runs, not a surprise
    after it — and read from session start onwards. One bundle rather than a
    key apiece, so the parse seam is a single object with a single writer:
    every option this plugin takes is resolved here once, including the two
    that read a CLI flag over an ini value (`title`, `lint_enabled`). Resolving
    either at its read site instead would put the precedence rule in as many
    places as there are readers — `lint_enabled` alone has two.
    """

    rule_levels: dict[RuleId, Level]
    ignore_entries: list[IgnoreEntry]
    source_link_template: str | None
    title: str | None
    lint_enabled: bool


@dataclass(kw_only=True)
class SessionOutcome:
    """What session finish leaves for the terminal summary to print.

    Filled at up to three points on the way out — a report that could not be
    written, the lint's findings, the Markdown destined for stdout — and read
    in one place. Mutable and stashed once at configure time, so the summary
    never has to distinguish "nothing happened" from "the hook never ran".
    """

    report_error: str | None = None
    md_stdout: str | None = None
    findings: list[Finding] = field(default_factory=list)


@dataclass(kw_only=True)
class SessionState:
    """The per-item bookkeeping the hooks pass between each other.

    Neither field is the collector's business — nothing in `capture/` reads
    them — so they live in the session's stash beside it rather than as
    attributes on the recorder, which keeps `Collector` to what it records.

    `published_for` is the item whose setup published the collector to the
    ContextVar, so teardown clears only what it published. Not
    `active_scenario_id`: that is already None by teardown (the call report
    finished the scenario), which is how the clear came to be skipped entirely.
    """

    param_info: ParamInfo = field(default_factory=dict)
    published_for: NodeId | None = None


given_config_key: pytest.StashKey[GivenConfig] = pytest.StashKey()


session_outcome_key: pytest.StashKey[SessionOutcome] = pytest.StashKey()


session_state_key: pytest.StashKey[SessionState] = pytest.StashKey()


def session_state(config: pytest.Config) -> SessionState:
    """This session's hook bookkeeping, created at `pytest_sessionstart`
    alongside its collector."""
    return config.stash[session_state_key]
