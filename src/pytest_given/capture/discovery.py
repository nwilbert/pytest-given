"""Finding the one `Glossary` a suite speaks.

Two places can name it — a story that references it, or a conftest that
declares one — and v1 admits exactly one per suite. Kept out of the plugin
because neither question is pytest's: the first reads the live `Story` objects
the run collected, the second reads plain module objects the caller supplies.
"""

from collections.abc import Iterable
from pathlib import Path

from ..model import Glossary, PytestGivenError, Story
from .file_glossary import FileGlossary


def resolve_glossary(
    stories: list[Story], modules: Iterable[object]
) -> Glossary | None:
    """Pick the report's glossary: off the story tree, else off the conftests.

    A story that references a `Glossary` is the authoritative answer — `story()`
    stashes the owning object on the tree at construction, so this depends only
    on the live objects the run was handed, never on a mutable session-global
    that a nested run could clear. (The stash is a side-channel that does not
    survive JSON; resolution only ever runs on live in-memory stories, and the
    renderer reads the serialized `glossary` field instead.)

    With no stories — or stories referencing none — the conftest scan catches
    the suite that declares a glossary and only ever uses term refs in
    narrations.
    """
    reaching: dict[int, Glossary] = {}
    for story in stories:
        reaching.update(story._glossaries)
    if len(reaching) > 1:
        raise PytestGivenError(
            f'stories reach {len(reaching)} distinct Glossary instances; '
            f'v1 supports at most one.'
        )
    if reaching:
        return next(iter(reaching.values()))
    return _glossary_from_modules(modules)


def _glossary_from_modules(modules: Iterable[object]) -> Glossary | None:
    """The single `Glossary` declared across the given conftest modules.

    Deduped by object identity, so one glossary imported into several conftests
    is still one glossary. A `FileGlossary` contributes the `Glossary` it wraps.
    """
    found: list[tuple[str, Glossary]] = []
    for module in modules:
        module_file = getattr(module, '__file__', None)
        if module_file is None or Path(module_file).name != 'conftest.py':
            continue
        for attr_name in dir(module):
            attr = getattr(module, attr_name, None)
            if isinstance(attr, FileGlossary):
                found.append((module_file, attr.glossary))
            elif isinstance(attr, Glossary):
                found.append((module_file, attr))
    distinct: dict[int, tuple[str, Glossary]] = {}
    for path, glossary in found:
        distinct.setdefault(id(glossary), (path, glossary))
    if len(distinct) > 1:
        details = ', '.join(
            f'{path} ({len(glossary.terms)} term(s))'
            for path, glossary in distinct.values()
        )
        raise PytestGivenError(
            f'multiple Glossary instances found in conftests ({len(distinct)}): '
            f'{details}. v1 supports at most one glossary per suite.'
        )
    if distinct:
        return next(iter(distinct.values()))[1]
    return None
