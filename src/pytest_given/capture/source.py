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

import re
import sys
import types
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
    and 'microsoft' in Path('/proc/version').read_text(encoding='utf-8').lower()
)
_IS_WINDOWS = sys.platform == 'win32'


def _co_filename_to_path(filename: str) -> Path:
    """Normalize a path string to the running platform's native convention.

    The same file can reach us in either convention regardless of platform: a
    frame's `co_filename` (or a stored rootdir) may be a Windows path
    (``C:\\...``) or a WSL-mount POSIX path (``/mnt/<drive>/...``), most often
    when a ``.pyc`` compiled by the other interpreter is reused across a shared
    WSL+Windows checkout. Comparing the two conventions with `relative_to`
    fails on mismatched drive anchors, so we fold whichever foreign form we see
    into the native one:

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

# path string -> rootdir-relative result, valid only for the current _rootdir.
# `Path.resolve` lstats every path component, and with the lint enabled it runs
# once per captured step — memoizing per file keeps that O(distinct files)
# instead of O(steps), which matters on slow mounts (WSL 9p: ~2ms per resolve).
_relpath_cache: dict[str, str | None] = {}


def set_rootdir(path: Path) -> None:
    """Point capture at a session's rootdir.

    Folded into the native convention first (see `_co_filename_to_path`) so the
    rootdir and the captured `co_filename`s always share a drive anchor — e.g. a
    ``/mnt/c/...`` rootdir on native Windows resolves to ``C:\\mnt\\c\\...``
    rather than the real ``C:\\...`` and would never match.
    """
    global _rootdir
    _rootdir = _co_filename_to_path(str(path)).resolve()
    _relpath_cache.clear()


def current_rootdir() -> Path | None:
    return _rootdir


def restore_rootdir(previous: Path | None) -> None:
    """Reinstate a rootdir captured with `current_rootdir`, as-is — it was
    already normalized and resolved when first set. Clears the relpath cache,
    whose entries are valid only for the rootdir they were computed against."""
    global _rootdir
    _rootdir = previous
    _relpath_cache.clear()


def _relativize(abs_path: Path) -> str | None:
    """rootdir-relative POSIX string for an absolute path. Returns None if
    rootdir is unset or the path lies outside it. Callers that start from a
    `co_filename` must normalize via `_co_filename_to_path` first.
    """
    if _rootdir is None:
        return None
    key = str(abs_path)
    if key in _relpath_cache:
        return _relpath_cache[key]
    try:
        rel: str | None = abs_path.resolve().relative_to(_rootdir).as_posix()
    except ValueError:
        rel = None
    _relpath_cache[key] = rel
    return rel


# Frames whose file starts with this are ours, and never the answer
# `capture_caller_source` is looking for.
_PACKAGE_ROOT = f'{Path(__file__).parent.parent}/'


def file_source(path: Path, line: int) -> SourceLocation | None:
    """SourceLocation for an absolute path, or None when it can't be made
    rootdir-relative (rootdir unset or path outside it) — i.e. "no link". The
    counterpart to `to_relpath`, which instead degrades to the path as given.
    """
    rel = _relativize(path)
    return None if rel is None else SourceLocation(relpath=rel, line=line)


def capture_caller_source() -> SourceLocation | None:
    """A SourceLocation for the nearest frame outside this package.

    Walks out rather than counting in. Every call site used to pass its own
    depth — `skip=2` from a direct caller, `skip=3` from one behind a shared
    helper — and getting it wrong did not raise: the frame landed inside
    `pytest_given/`, `_relativize` returned None, and the term or story
    silently recorded `source=None`, losing its report link and, with it, the
    lint's whole AST surface. Inserting one wrapper anywhere in a call chain
    was enough to do that. The walk cannot be wrong that way, and adding a
    frame costs nothing.

    Returns None if the stack never leaves the package, or if the frame it
    lands on cannot be made rootdir-relative.
    """
    frame: types.FrameType | None = sys._getframe(1)
    while frame is not None and frame.f_code.co_filename.startswith(_PACKAGE_ROOT):
        frame = frame.f_back
    if frame is None:
        return None
    abs_path = _co_filename_to_path(frame.f_code.co_filename)
    return file_source(abs_path, frame.f_lineno)


def to_relpath(raw: str) -> str:
    """Normalize a path string and make it rootdir-relative when possible.

    Folds the path into the native convention (see `_co_filename_to_path`) and,
    if it is then an absolute path inside rootdir, returns it relative to rootdir;
    otherwise returns it unchanged as posix. Used for both scenario
    `item.location` paths and traceback frame paths, so neither leaks an
    absolute, machine-specific path.
    """
    path = _co_filename_to_path(raw)
    if path.is_absolute():
        rel = _relativize(path)
        if rel is not None:
            return rel
    return path.as_posix()


def item_source(relpath_raw: str, line: int) -> SourceLocation:
    """Build a SourceLocation from a pytest `item.location` path + 1-based line.

    `item.location[0]` is normally already rootdir-relative, but pytest cannot
    relativize a foreign-convention `co_filename` and falls back to the absolute
    path; `to_relpath` folds and re-relativizes it. Unlike
    `capture_caller_source`, this always returns a location: a path outside
    rootdir (or unset rootdir) degrades to the path as given rather than to "no
    link", so every scenario carries a source.
    """
    return SourceLocation(relpath=to_relpath(relpath_raw), line=line)


def code_source(code: types.CodeType) -> SourceLocation | None:
    """SourceLocation for a code object's definition site (used to anchor
    decorated step-helper functions for the narration lint).

    `co_firstlineno` points at the function's first decorator line when it has
    decorators; the lint's AST index accounts for that. Returns None if rootdir
    is unset or the file lies outside it.
    """
    abs_path = _co_filename_to_path(code.co_filename)
    return file_source(abs_path, code.co_firstlineno)
