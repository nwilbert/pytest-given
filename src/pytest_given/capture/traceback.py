"""Parse pytest `excinfo.getrepr(style='short')` output into structured frames.

The short-style output is a sequence of frame blocks, each opened by a header
line of the form `<path>:<lineno>: in <funcname>`, followed by indented code
(and optionally a caret-highlight row). After the last frame, lines starting
with `E   ` carry the exception summary.

The renderer wants frames classified into "user" vs "internal" — pluggy
dispatchers, pytest's own runner, and pytest-given's `@scenario` wrapper are
implementation noise the reader almost never needs.
"""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from ..model import TracebackFrame
from .source import to_relpath

if TYPE_CHECKING:
    from _pytest._code.code import TracebackEntry

_FRAME_HEADER_RE = re.compile(r'^(?P<path>.+?):(?P<lineno>\d+): in (?P<func>.+)$')

# Substrings (after backslash → forward-slash normalization) that mark a
# frame as internal. Suffix entries use endswith; others use substring.
# Kept strict on purpose: a missed internal frame is uglier output, but a
# user frame wrongly hidden is a real bug.
_INTERNAL_SUBSTRINGS = (
    '/site-packages/_pytest/',
    '/site-packages/pluggy/',
)
_INTERNAL_SUFFIXES = ('/pytest_given/capture/decorators.py',)

_SITE_PACKAGES_MARKER = '/site-packages/'


def filter_internal_frames(excinfo: pytest.ExceptionInfo[BaseException]) -> None:
    """Drop internal frames from ``excinfo.traceback`` before ``getrepr`` runs.

    ``getrepr(style='short')`` runs pytest's per-frame AST statement-range scan
    once per surviving entry, so pruning the pluggy/``_pytest``/decorator frames
    here — rather than after parsing — is what removes the O(N²) traceback cost
    on large failing suites. Only pytest's view of the traceback is rewritten;
    the exception's native ``__traceback__`` is left intact.

    Reuses ``_is_internal`` (the classifier ``parse_short_repr`` applies to the
    formatted output) so the pre-filter and post-parse classification agree. If
    every entry classifies as internal — e.g. a failure raised entirely within
    plugin/library code — the original traceback is kept so ``getrepr`` still has
    a crash frame to format.
    """
    filtered = excinfo.traceback.filter(lambda entry: not _is_internal_entry(entry))
    if len(filtered) > 0:
        excinfo.traceback = filtered


def _is_internal_entry(entry: TracebackEntry) -> bool:
    return _is_internal(str(entry.path).replace('\\', '/'))


@dataclass
class _Pending:
    path: str
    lineno: int
    func: str
    code: list[str] = field(default_factory=list)


def parse_short_repr(text: str) -> tuple[list[TracebackFrame], str | None]:
    """Parse short-style traceback text into structured frames + error tail.

    Returns `([], None)` for empty input, `([], text)` when no frame headers
    are found (degraded but lossless — the original text lands in the tail).
    """
    if not text:
        return [], None

    frames: list[TracebackFrame] = []
    tail_lines: list[str] = []
    pending: _Pending | None = None
    in_tail = False

    def _flush(p: _Pending) -> None:
        normalized = p.path.replace('\\', '/')
        frames.append(
            TracebackFrame(
                path=_portable_path(normalized),
                lineno=p.lineno,
                func=p.func,
                code='\n'.join(p.code),
                is_internal=_is_internal(normalized),
            )
        )

    for line in text.splitlines():
        if in_tail:
            tail_lines.append(line)
            continue
        match = _FRAME_HEADER_RE.match(line)
        if match is not None:
            if pending is not None:
                _flush(pending)
            pending = _Pending(
                path=match.group('path'),
                lineno=int(match.group('lineno')),
                func=match.group('func'),
            )
            continue
        if line.startswith(('E   ', 'E\t')):
            if pending is not None:
                _flush(pending)
                pending = None
            in_tail = True
            tail_lines.append(line)
            continue
        if pending is not None:
            pending.code.append(line)

    if pending is not None:
        _flush(pending)

    if not frames and not tail_lines:
        return [], text

    tail = '\n'.join(tail_lines) if tail_lines else None
    return frames, tail


def _portable_path(normalized_path: str) -> str:
    """Rewrite a frame path to a stable, machine-independent form.

    Two cases churn between environments (and can surface absolute when a `.pyc`
    compiled by the other interpreter is reused across a shared WSL+Windows
    checkout):

    - A `site-packages` dependency frame carries a machine-specific venv prefix
      (`.nox/.../Lib/site-packages/...` vs `/home/me/.../site-packages/...`);
      truncate it to the stable `site-packages/...` tail.
    - A project/user frame can arrive absolute and in the wrong path convention;
      `to_relpath` folds it to the native convention and back to rootdir-relative.

    `is_internal` is still computed from the full path, so classification is
    unaffected.
    """
    idx = normalized_path.rfind(_SITE_PACKAGES_MARKER)
    if idx != -1:
        return normalized_path[idx + 1 :]
    return to_relpath(normalized_path)


def _is_internal(normalized_path: str) -> bool:
    if any(s in normalized_path for s in _INTERNAL_SUBSTRINGS):
        return True
    return any(normalized_path.endswith(s) for s in _INTERNAL_SUFFIXES)
