"""Writing a set of files so that none of them is ever seen half-written."""

import os
import shutil
from collections.abc import Callable, Iterable
from pathlib import Path


def write_all_or_none(
    files: Iterable[tuple[Path, str]],
    *,
    newline: str | None = None,
    before_replace: Callable[[], None] | None = None,
) -> None:
    """Stage each file beside its target, then rename every one into place.

    Nothing is renamed until all are staged and `before_replace` returned; an
    exception from either removes what was staged. A failing rename cannot
    undo the ones before it, but leaves no temporary behind. A symlinked target
    is replaced through its link, and an existing one keeps its permission bits.
    """
    staged: list[tuple[Path, Path]] = []
    replaced = 0
    try:
        for path, text in files:
            target = path.resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f'.{target.name}.{os.getpid()}.tmp')
            temporary.write_text(text, encoding='utf-8', newline=newline)
            if target.exists():
                shutil.copymode(target, temporary)
            staged.append((temporary, target))
        if before_replace is not None:
            before_replace()
        for temporary, target in staged:
            temporary.replace(target)
            replaced += 1
    except BaseException:
        for temporary, _target in staged[replaced:]:
            temporary.unlink(missing_ok=True)
        raise
