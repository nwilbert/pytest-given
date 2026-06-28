"""Caller-frame source-location capture for non-pytest-item objects.

`Story` and `GlossaryTerm` are constructed at user-code import time, not
inside a pytest hook, so their source-location must be reconstructed from
the call stack. The plugin sets rootdir during `pytest_load_initial_conftests`
(before root conftest is imported); capture sites then call
`capture_caller_source(skip=N)` from their user-facing wrappers. Returns
None if rootdir is unset or the caller's file lies outside rootdir — the
renderer treats that as "no link", same as a scenario whose `item.location`
is absent.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from ..model import SourceLocation

_WINDOWS_PATH_RE = re.compile(r'^([A-Za-z]):\\')

# Detecting WSL specifically (rather than "not Windows") keeps the /mnt/<drive>
# rewrite below from ever firing on native Linux or macOS, where a Windows-style
# co_filename should never occur in the first place.
_IS_WSL = (
    sys.platform == 'linux'
    and Path('/proc/version').exists()
    and 'microsoft' in Path('/proc/version').read_text().lower()
)


def _co_filename_to_path(filename: str) -> Path:
    """Normalise a frame's `co_filename` to a Linux path if needed.

    On WSL, co_filename for files on the Windows filesystem is a Windows path
    (e.g. C:\\Users\\...). Path() on Linux treats backslashes as literal
    filename characters, so we normalise to the /mnt/<drive>/... form first.
    """
    match = _WINDOWS_PATH_RE.match(filename)
    if match and _IS_WSL:
        rest = filename[2:].replace('\\', '/')
        return Path(f'/mnt/{match.group(1).lower()}{rest}')
    return Path(filename)


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
    abs_path = _co_filename_to_path(frame.f_code.co_filename).resolve()
    try:
        rel = abs_path.relative_to(_rootdir)
    except ValueError:
        return None
    return SourceLocation(relpath=rel.as_posix(), line=frame.f_lineno)


def file_source(path: Path, line: int) -> SourceLocation | None:
    """SourceLocation for a known file path + line (e.g. a glossary table row).

    Mirrors `capture_caller_source` but for a path we already hold rather than
    a stack frame. Returns None if rootdir is unset or the file is outside it.
    """
    if _rootdir is None:
        return None
    abs_path = path.resolve()
    try:
        rel = abs_path.relative_to(_rootdir)
    except ValueError:
        return None
    return SourceLocation(relpath=rel.as_posix(), line=line)
