"""Text rules two packages that cannot import each other have to agree on.

`s_form` is shared so that what a handle's `.s` spells, the report recognizes
as the same term; `plural` so the lint summary and the report count alike;
`name_keys` so a definition ref and the Glossary tab agree on what spells a
term's own name; `definition_ref_text` so capture resolves and the lint flags
the same bold spans.

`id_derive` returns a bare `str`, not a `TermId`: story ids, term ids and
coverage instance ids all derive the same way.
"""

import re

from ..markdown import EmphasisSpan, InlineSpan, PlainSpan, span_text
from .errors import PytestGivenError

_NON_ALNUM = re.compile(r'[^a-z0-9]+')
_SIBILANT_ENDINGS = ('s', 'x', 'z', 'ch', 'sh')
_CONSONANT_Y = re.compile(r'[b-df-hj-np-tv-z]y$')
_NAME_SEPARATORS = re.compile(r'[\s-]+')


def derived_id(name: str) -> str | None:
    """`name` as a slug — lowercased, every non-ASCII-alphanumeric run folded to
    a single `-` — or None if nothing survives the fold.

    The fold runs after `str.lower`, so whether a name has a slug is not the
    same question as whether its characters are ASCII: `'\u212a'` lowercases
    into `'k'`. Callers that need the predicate ask this rather than
    reimplementing it.
    """
    return _NON_ALNUM.sub('-', name.lower()).strip('-') or None


def id_derive(name: str) -> str:
    """`derived_id`, raising instead of returning None."""
    slug = derived_id(name)
    if slug is None:
        raise PytestGivenError(
            f'derived id is empty for {name!r}; provide a name with at least '
            f'one ASCII alphanumeric character.'
        )
    return slug


def plural(count: int, singular: str) -> str:
    """`'1 scenario'` / `'3 stories'` — the noun agreeing with its count."""
    if count == 1:
        return f'{count} {singular}'
    return f'{count} {s_form(singular)}'


def name_key(text: str) -> str:
    """`text` as names compare: lowercased, each run of whitespace and hyphens
    one space, so `parameter-table` in a compound modifier names `Parameter table`."""
    return _NAME_SEPARATORS.sub(' ', text.lower()).strip()


def name_keys(name: str) -> set[str]:
    """The `name_key`s that spell `name`: itself and its S-form, which an
    all-caps name has two of, since only its lowercase takes -es or -ies
    (`SMSs`, `smses`)."""
    return {name_key(name), name_key(s_form(name)), name_key(s_form(name.lower()))}


def definition_ref_text(span: InlineSpan) -> str | None:
    """A bold span's text if it could be a definition ref: one holding a code
    span formats an identifier instead."""
    if not isinstance(span, EmphasisSpan) or not span.strong:
        return None
    if not all(isinstance(part, PlainSpan) for part in span.content):
        return None
    return span_text(span)


def s_form(text: str) -> str:
    """`text` with the regular English -s ending: a plural noun, or a verb's
    third person singular. Only a lowercase ending takes -es or -ies, so an
    acronym takes a plain -s (``APIs``); irregular words are the caller's."""
    if text.endswith(_SIBILANT_ENDINGS):
        return f'{text}es'
    if _CONSONANT_Y.search(text):
        return f'{text[:-1]}ies'
    return f'{text}s'
