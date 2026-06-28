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

from ..model import TracebackFrame

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
        if line.startswith('E   ') or line.startswith('E\t'):
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
    """Collapse an external-dependency frame to a venv-independent path.

    A `site-packages` frame renders with a machine-specific prefix — the venv
    lives in-repo on one machine (`.nox/.../Lib/site-packages/...`) and under
    `$HOME` on another (`/home/me/.../site-packages/...`) — so reports (and the
    committed examples) churn between environments. Truncate to the stable
    `site-packages/...` tail. Project and user frames are already rootdir-relative
    and pass through untouched. `is_internal` is still computed from the full
    path, so classification is unaffected.
    """
    idx = normalized_path.rfind(_SITE_PACKAGES_MARKER)
    if idx != -1:
        return normalized_path[idx + 1 :]
    return normalized_path


def _is_internal(normalized_path: str) -> bool:
    if any(s in normalized_path for s in _INTERNAL_SUBSTRINGS):
        return True
    return any(normalized_path.endswith(s) for s in _INTERNAL_SUFFIXES)
