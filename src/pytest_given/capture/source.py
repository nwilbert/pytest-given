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

_WINDOWS_PATH_RE = re.compile(r'^([A-Za-z]):[\\/]')
_MNT_PATH_RE = re.compile(r'^[\\/]mnt[\\/]([A-Za-z])(?=[\\/]|$)')

# Detecting WSL and native Windows specifically (rather than "not the other")
# keeps each rewrite below from firing on plain Linux or macOS, where /mnt/<drive>
# is a real directory and a Windows-style co_filename should never occur.
_IS_WSL = (
    sys.platform == 'linux'
    and Path('/proc/version').exists()
    and 'microsoft' in Path('/proc/version').read_text().lower()
)
_IS_WINDOWS = sys.platform == 'win32'


def _co_filename_to_path(filename: str) -> Path:
    """Normalise a path string to the running platform's native convention.

    The same file can reach us in either convention regardless of platform: a
    frame's `co_filename` (or a stored rootdir) may be a Windows path
    (``C:\\...``) or a WSL-mount POSIX path (``/mnt/<drive>/...``). A native
    Windows interpreter that loads an assertion-rewritten ``.pyc`` previously
    compiled under WSL, for instance, carries a ``/mnt/c/...`` co_filename for a
    file the rest of the process knows as ``C:\\...``. Comparing the two
    conventions with `relative_to` fails (mismatched drive anchors), so we fold
    whichever foreign form we see into the native one:

    - Under WSL (Linux kernel, Windows filesystem): ``C:\\...`` -> ``/mnt/c/...``
    - Under native Windows: ``/mnt/<drive>/...`` -> ``<drive>:\\...``

    On plain Linux/macOS nothing is rewritten — there ``/mnt/<drive>`` is a real
    directory and must be left alone.
    """
    if _IS_WSL:
        match = _WINDOWS_PATH_RE.match(filename)
        if match:
            rest = filename[2:].replace('\\', '/')
            return Path(f'/mnt/{match.group(1).lower()}{rest}')
    elif _IS_WINDOWS:
        match = _MNT_PATH_RE.match(filename)
        if match:
            rest = filename[match.end() :] or '/'
            return Path(f'{match.group(1).upper()}:{rest}')
    return Path(filename)


_rootdir: Path | None = None


def set_rootdir(path: Path) -> None:
    """Called by the plugin in `pytest_load_initial_conftests`.

    Folded into the native convention first (see `_co_filename_to_path`) so the
    rootdir and the captured `co_filename`s always share a drive anchor — e.g. a
    ``/mnt/c/...`` rootdir on native Windows resolves to ``C:\\mnt\\c\\...``
    rather than the real ``C:\\...`` and would never match.
    """
    global _rootdir
    _rootdir = _co_filename_to_path(str(path)).resolve()


def _reset_rootdir() -> None:
    """Test-only — reset module state between cases."""
    global _rootdir
    _rootdir = None


def _relativize(abs_path: Path) -> str | None:
    """rootdir-relative POSIX string for an absolute path. Returns None if
    rootdir is unset or the path lies outside it. Callers that start from a
    `co_filename` must normalise via `_co_filename_to_path` first.
    """
    if _rootdir is None:
        return None
    try:
        return abs_path.resolve().relative_to(_rootdir).as_posix()
    except ValueError:
        return None


def capture_caller_source(skip: int = 1) -> SourceLocation | None:
    """Return a SourceLocation for the frame `skip` levels up the call stack.

    `skip=1` (default) returns the immediate caller of `capture_caller_source`.
    Use `skip=2` when called from a one-level-deep user-facing wrapper (e.g.
    `g.actor("Guest")` -> wrapper -> this helper) so frame 2 is the user's
    code.

    Returns None if rootdir is unset, or if the caller's file resolves to a
    path outside rootdir.
    """
    frame = sys._getframe(skip)
    rel = _relativize(_co_filename_to_path(frame.f_code.co_filename))
    if rel is None:
        return None
    return SourceLocation(relpath=rel, line=frame.f_lineno)


def to_relpath(raw: str) -> str:
    """Normalise a path string and make it rootdir-relative when possible.

    Folds the path into the native convention (see `_co_filename_to_path`) and,
    if it is then an absolute path inside rootdir, returns it relative to rootdir;
    otherwise returns it unchanged as posix. Used for both scenario
    `item.location` paths and traceback frame paths so neither leaks an absolute,
    machine-specific path — the same file can surface absolute (and in the wrong
    convention) when a `.pyc` compiled by the other interpreter is reused across
    a shared WSL+Windows checkout.
    """
    path = _co_filename_to_path(raw)
    if path.is_absolute():
        rel = _relativize(path)
        if rel is not None:
            return rel
    return path.as_posix()


def item_source(relpath_raw: str, line: int) -> SourceLocation:
    """Build a SourceLocation from a pytest `item.location` path + 1-based line.

    `item.location[0]` is normally already rootdir-relative, but under WSL pytest
    cannot relativize a Windows-style `co_filename` (e.g. ``C:\\Users\\...``)
    against the POSIX ``/mnt/<drive>`` rootdir and falls back to the absolute
    Windows path. `to_relpath` rewrites it to the native convention and
    re-relativizes against rootdir. Unlike `capture_caller_source`, this always
    returns a location: an absolute path outside rootdir (or unset rootdir)
    degrades to the path as given rather than to "no link", matching the prior
    behaviour where every scenario carried a source.
    """
    return SourceLocation(relpath=to_relpath(relpath_raw), line=line)


def file_source(path: Path, line: int) -> SourceLocation | None:
    """SourceLocation for a known file path + line (e.g. a glossary table row).

    Mirrors `capture_caller_source` but for a path we already hold rather than
    a stack frame. Returns None if rootdir is unset or the file is outside it.
    """
    rel = _relativize(path)
    if rel is None:
        return None
    return SourceLocation(relpath=rel, line=line)
