"""Parse pytest `excinfo.getrepr(style='short')` output into structured frames.

The short-style output is a sequence of frame blocks, each opened by a header
line of the form `<path>:<lineno>: in <funcname>`, followed by indented code
(and optionally a caret-highlight row). After the last frame, lines starting
with `E   ` carry the exception summary.

`is_internal_path` classifies a frame as user or internal — pluggy dispatchers,
pytest's runner and pytest-given's own machinery are noise the reader almost
never needs. The plugin applies it to pytest's traceback entries before
`getrepr` runs, so the pre-filter and this post-parse pass agree.

`_INTERNAL_SUFFIXES` names whole modules: every module whose functions a test
body calls, and that can refuse the call, belongs there — otherwise a failure's
innermost frame is our `raise` rather than the line that made the mistake.
"""

import re
from dataclasses import dataclass, field

from .. import model
from ..model import TracebackFrame
from . import (
    collector,
    file_glossary,
    glossary,
    markdown_glossary,
    scenario,
    steps,
    story,
    template,
)
from .source import to_relpath

# `\S` anchors the path, so an indented source line inside a frame body
# cannot pass for a new frame header.
_FRAME_HEADER_RE = re.compile(r'^(?P<path>\S.*?):(?P<lineno>\d+): in (?P<func>.+)$')

# Substrings (after backslash → forward-slash normalization) that mark a
# frame as internal. Suffix entries use endswith; others use substring.
# Kept strict on purpose: a missed internal frame is uglier output, but a
# user frame wrongly hidden is a real bug.
_INTERNAL_SUBSTRINGS = (
    '/site-packages/_pytest/',
    '/site-packages/pluggy/',
)
# Derived from the modules themselves, so moving or renaming one is an import
# error here rather than a suffix that silently stops matching and puts our
# own frames back into every user traceback. A `model` module is named, since
# a sibling package is imported only through its root; a test holds each name
# to a module that exists.
_INTERNAL_MODEL_MODULES = ('narration', 'text')
_INTERNAL_SUFFIXES = tuple(
    f'/{module.replace(".", "/")}.py'
    for module in (
        collector.__name__,
        file_glossary.__name__,
        glossary.__name__,
        markdown_glossary.__name__,
        scenario.__name__,
        steps.__name__,
        story.__name__,
        template.__name__,
        *(f'{model.__name__}.{name}' for name in _INTERNAL_MODEL_MODULES),
    )
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


def is_internal_path(path: str) -> bool:
    """Whether a traceback frame's file, in either separator convention, is
    ours or the machinery's."""
    normalized = path.replace('\\', '/')
    if any(s in normalized for s in _INTERNAL_SUBSTRINGS):
        return True
    return any(normalized.endswith(s) for s in _INTERNAL_SUFFIXES)
