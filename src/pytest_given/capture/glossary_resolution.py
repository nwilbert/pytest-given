"""Finding the one `Glossary` a suite speaks: every user-facing glossary
registers itself when constructed, and v1 admits exactly one per suite.
"""

from collections.abc import Mapping

from ..model import Glossary, PytestGivenError, SourceLocation, Story
from .definition_refs import resolve_definition_refs
from .kind_inference import infer_glossary_kinds
from .source import site_text


def session_glossary(
    stories: list[Story], registered: Mapping[Glossary, SourceLocation | None]
) -> Glossary | None:
    """The suite's glossary as the report carries it: found, its kinds
    inferred, its definition refs resolved."""
    glossary = resolve_glossary(registered)
    if glossary is None:
        return None
    return resolve_definition_refs(infer_glossary_kinds(glossary, stories))


def resolve_glossary(
    registered: Mapping[Glossary, SourceLocation | None],
) -> Glossary | None:
    if len(registered) > 1:
        sites = ', '.join(site_text(site) for site in registered.values())
        raise PytestGivenError(
            f'found {len(registered)} distinct glossaries, constructed at {sites}; '
            f'v1 supports one per suite. Construct it once and import it '
            f'wherever it is used.'
        )
    return next(iter(registered), None)
