"""Finding the one `Glossary` a suite speaks.

Two places can name it — a story that references it, or a conftest that
declares one — and v1 admits exactly one per suite. Kept out of the plugin
because neither question is pytest's: the first reads the live `Story` objects
the run collected, the second reads plain module objects the caller supplies.
"""

from collections.abc import Iterable
from pathlib import Path
from types import ModuleType

from ..model import Glossary, PytestGivenError, Story
from .story import pinned_glossaries, union_glossaries


def resolve_glossary(
    stories: list[Story], modules: Iterable[ModuleType]
) -> Glossary | None:
    """Pick the report's glossary: off the story tree, else off the conftests.

    A story that references a `Glossary` is the authoritative answer — `story()`
    stashes the owning object on the tree at construction, so this depends only
    on the live objects the run was handed, never on a session-global a nested
    run could clear. The stash does not survive JSON; a saved report carries the
    serialized `glossary` field instead.

    With no stories — or stories referencing none — the conftest scan catches
    the suite that declares a glossary and only ever uses term refs in
    narrations.
    """
    reaching = union_glossaries(pinned_glossaries(story) for story in stories)
    if len(reaching) > 1:
        raise PytestGivenError(
            f'stories reach {len(reaching)} distinct Glossary instances; '
            f'v1 supports at most one.'
        )
    if reaching:
        return next(iter(reaching))
    return _glossary_from_modules(modules)


def _glossary_from_modules(modules: Iterable[ModuleType]) -> Glossary | None:
    """The single `Glossary` declared across the given conftest modules.

    Deduped by object identity, so one glossary imported into several conftests
    is still one glossary.
    """
    distinct: dict[Glossary, str] = {}
    for module in modules:
        module_file = getattr(module, '__file__', None)
        if module_file is None or Path(module_file).name != 'conftest.py':
            continue
        for attr_name in dir(module):
            attr = getattr(module, attr_name, None)
            if isinstance(attr, Glossary):
                distinct.setdefault(attr, module_file)
    if len(distinct) > 1:
        details = ', '.join(
            f'{path} ({len(glossary.terms)} term(s))'
            for glossary, path in distinct.items()
        )
        raise PytestGivenError(
            f'multiple Glossary instances found in conftests ({len(distinct)}): '
            f'{details}. v1 supports at most one glossary per suite.'
        )
    if distinct:
        return next(iter(distinct))
    return None
