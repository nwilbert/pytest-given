"""Caller-frame source-location capture for non-pytest-item objects.

`Story` and `GlossaryTerm` are constructed at user-code import time, not
inside a pytest hook, so their source-location must be reconstructed from
the call stack. The plugin sets rootdir during `pytest_configure`; capture
sites then call `capture_caller_source(skip=N)` from their user-facing
wrappers. Returns None if rootdir is unset or the caller's file lies
outside rootdir — the renderer treats that as "no link", same as a scenario
whose `item.location` is absent.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ..model import SourceLocation

_rootdir: Path | None = None


def set_rootdir(path: Path) -> None:
    """Called by the plugin in `pytest_load_initial_conftests`."""
    global _rootdir
    _rootdir = path.resolve()


def _reset_rootdir() -> None:
    """Test-only — reset module state between cases."""
    global _rootdir
    _rootdir = None


def capture_caller_source(skip: int = 1) -> SourceLocation | None:
    """Return a SourceLocation for the frame `skip` levels up the call stack.

    `skip=1` (default) returns the immediate caller of `capture_caller_source`.
    Use `skip=2` when called from a one-level-deep user-facing wrapper (e.g.
    `g.actor("Guest")` -> wrapper -> this helper) so frame 2 is the user's
    code.

    Returns None if rootdir is unset, or if the caller's file resolves to a
    path outside rootdir.
    """
    if _rootdir is None:
        return None
    frame = sys._getframe(skip)
    abs_path = Path(frame.f_code.co_filename).resolve()
    try:
        rel = abs_path.relative_to(_rootdir)
    except ValueError:
        return None
    return SourceLocation(relpath=rel.as_posix(), line=frame.f_lineno)
