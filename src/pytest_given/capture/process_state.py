"""The process-global state `capture` keeps, and the one way to swap it.

Three globals back a recording run: the rootdir `source` relativizes paths
against, the story registry that catches a story declared twice, and the
ContextVar naming the collector currently recording. All three are
process-wide, so a nested in-process run (pytester, `pytest.main`) has to
displace every one of them on the way in and put every one back on the way
out.

They are saved and restored together rather than a call site at a time because
missing one is a silent bug the *outer* session pays for: a stranded rootdir
makes every later step record `source=None`, which quietly takes the lint's
whole AST surface down with it.

The state itself stays where it is used, because the rootdir carries a resolve
cache and the path-form folding that keeps it correct (see `source.py`).
"""

from dataclasses import dataclass
from pathlib import Path

from ..model import StoryId
from .collector import Collector, get_active_collector, set_active_collector
from .source import current_rootdir, restore_rootdir, set_rootdir
from .story import restore_story_registry, snapshot_story_registry


@dataclass(frozen=True)
class CaptureState:
    """Everything `capture` holds process-wide, as one value."""

    rootdir: Path | None
    stories: dict[StoryId, str]
    collector: Collector | None


def capture_snapshot() -> CaptureState:
    return CaptureState(
        rootdir=current_rootdir(),
        stories=snapshot_story_registry(),
        collector=get_active_collector(),
    )


def restore_capture_state(state: CaptureState) -> None:
    """Reinstate a `capture_snapshot`.

    The rootdir goes back as-is rather than through `set_rootdir`: it was
    already normalized and resolved when first set.
    """
    restore_rootdir(state.rootdir)
    restore_story_registry(state.stories)
    set_active_collector(state.collector)


def begin_capture_session(rootdir: Path) -> None:
    """Point capture at a session's rootdir, on a cleared story registry and
    with no collector active.

    Take a `capture_snapshot` first when the caller may be nested inside
    another run, and `restore_capture_state` when this one is done.

    All three globals, symmetrically with `restore_capture_state`: leaving the
    collector alone left an *outer* session's collector active across a nested
    run's conftest import and collection, so anything that run recorded in that
    window landed in the outer session's open scenario.
    """
    set_rootdir(rootdir)
    restore_story_registry({})
    set_active_collector(None)
