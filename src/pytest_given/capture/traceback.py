"""Parse pytest `excinfo.getrepr(style='short')` output into structured frames.

The short-style output is a sequence of frame blocks, each opened by a header
line of the form `<path>:<lineno>: in <funcname>`, followed by indented code
(and optionally a caret-highlight row). After the last frame, lines starting
with `E   ` carry the exception summary.

`is_internal_path` classifies a frame as user or internal — pluggy dispatchers,
pytest's runner and pytest-given's own machinery are noise the reader almost
never needs. The plugin applies it to pytest's traceback entries before
`getrepr` runs, so the pre-filter and this post-parse pass agree.

`_INTERNAL_SUFFIXES` names whole modules: a function that raises at test time
belongs in one of them, or its frame reaches the reader.
"""

import re
from dataclasses import dataclass, field

from ..model import TracebackFrame
from .source import to_relpath

_FRAME_HEADER_RE = re.compile(r'^(?P<path>.+?):(?P<lineno>\d+): in (?P<func>.+)$')

# Substrings (after backslash → forward-slash normalization) that mark a
# frame as internal. Suffix entries use endswith; others use substring.
# Kept strict on purpose: a missed internal frame is uglier output, but a
# user frame wrongly hidden is a real bug.
_INTERNAL_SUBSTRINGS = (
    '/site-packages/_pytest/',
    '/site-packages/pluggy/',
)
_INTERNAL_SUFFIXES = (
    '/pytest_given/capture/steps.py',
    '/pytest_given/capture/scenario.py',
)

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
                is_internal=is_internal_path(normalized),
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

    Two cases churn between environments:

    - A `site-packages` dependency frame carries a machine-specific venv prefix;
      truncate it to the stable `site-packages/...` tail.
    - A project/user frame can arrive absolute and in the wrong path convention;
      `to_relpath` folds it back to rootdir-relative.

    `is_internal` is still computed from the full path, so classification is
    unaffected.
    """
    idx = normalized_path.rfind(_SITE_PACKAGES_MARKER)
    if idx != -1:
        return normalized_path[idx + 1 :]
    return to_relpath(normalized_path)


def is_internal_path(normalized_path: str) -> bool:
    if any(s in normalized_path for s in _INTERNAL_SUBSTRINGS):
        return True
    return any(normalized_path.endswith(s) for s in _INTERNAL_SUFFIXES)
