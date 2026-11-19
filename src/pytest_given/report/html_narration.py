"""Narration, term refs, definitions and clause parts as the HTML pages show
them: the Jinja filters the report page and the delta page both register."""

# A session that renders no HTML never loads MarkupSafe.
__lazy_modules__ = ['markupsafe']

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from markupsafe import Markup, escape

from ..markdown import (
    CodeSpan,
    EmphasisSpan,
    InlineSpan,
    PlainSpan,
    definition_html,
    definition_span_html,
    span_html,
    span_text,
)
from ..model import (
    ClausePart,
    Glossary,
    GlossaryTerm,
    Narration,
    NarrationLiteral,
    NarrationPiece,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    SourceLocation,
    TermId,
    TermKind,
    boolean_phrases,
    definition_part_text,
    placeholder_token,
    read_definition,
    read_narration,
)
from .source_link import compile_source_link
from .step_layout import ParamColorMap, shows_repr

if TYPE_CHECKING:
    from ..delta import Change, Side


def inline_md(text: str | None) -> Markup:
    """Jinja filter: a definition string's inline Markdown, its bold spans
    plain bold rather than definition refs — the delta page's."""
    return Markup(definition_html(text or ''))


def avoid_html(term: GlossaryTerm) -> Markup:
    """A term's avoid entries as written, each rendered by `definition_html`."""
    return Markup(', '.join(definition_html(entry) for entry in term.avoid))


def shown_text(narration: Narration) -> str:
    """A title as the page shows it, its markers rendered away."""
    return ''.join(_piece_text(piece) for piece in read_narration(narration))


def _piece_text(piece: NarrationPiece) -> str:
    match piece:
        case PlainSpan() | CodeSpan() | EmphasisSpan():
            return span_text(piece)
        case NarrationValue(rendered=text) | NarrationTermRef(display=text):
            return text
        case NarrationPlaceholder():
            return placeholder_token(piece)


# Both take the delta page's `side`, which the shared macros always pass, and
# ignore it: a filter built here serves one side.
class _SourceUrlFilter(Protocol):
    def __call__(
        self, source: SourceLocation | None, side: Side | None = None, /
    ) -> str | None: ...


class _NarrationFilter(Protocol):
    def __call__(
        self,
        narration: Narration,
        side: Side | None = None,
        /,
        *,
        before: str = '',
        after: str = '',
    ) -> Markup: ...


def make_source_url_filter(
    *,
    template: str | None,
    project: str,
    commit_sha: str | None,
    root: Path | None,
) -> _SourceUrlFilter:
    """Build a Jinja filter that resolves a SourceLocation to a URL string.

    Returns None when source linking is disabled or the source is absent — the
    template reads that as "render a plain `<span>`". The template itself is
    validated and parsed once here, not per location.
    """
    substitute = (
        None
        if template is None
        else compile_source_link(
            template, project=project, commit_sha=commit_sha, root=root
        )
    )

    def _filter(
        source: SourceLocation | None, _side: Side | None = None, /
    ) -> str | None:
        if source is None or substitute is None:
            return None
        return substitute(source)

    return _filter


@dataclass(frozen=True)
class TermRefTarget:
    """Where a term ref points: `tip`, the key of the term its tooltip shows in
    the page's glossary data, and `entry`, the Glossary card it opens, or None
    for a ref with no card to open."""

    tip: str
    entry: str | None
    change: Change | None = None  # the delta's: the change `entry` lists


type TermRefTargets = Callable[[TermId], TermRefTarget]


def make_narration_filter(
    param_color_map: ParamColorMap | None,
    glossary: Glossary | None,
    *,
    ref_targets: TermRefTargets | None = None,
) -> _NarrationFilter:
    """Jinja filter: renders a `Narration` to HTML, piece by piece.

    Without a colour map no placeholder is coloured. Without `ref_targets` a
    term ref points at its own term's tooltip and card. `before` and `after`
    flank a stretch of a longer line.
    """

    def _render(
        narration: Narration,
        _side: Side | None = None,
        /,
        *,
        before: str = '',
        after: str = '',
    ) -> Markup:
        out = [
            _render_narration_piece(piece, param_color_map, glossary, ref_targets)
            for piece in read_narration(narration, before=before, after=after)
        ]
        return Markup(''.join(out))

    return _render


def _render_narration_piece(
    part: NarrationPiece,
    param_color_map: ParamColorMap | None,
    glossary: Glossary | None,
    ref_targets: TermRefTargets | None,
) -> str:
    """Render one `NarrationPiece` to an HTML fragment."""
    match part:
        case PlainSpan() | CodeSpan() | EmphasisSpan():
            return span_html(part)
        case NarrationValue(rendered=rendered):
            return f'<span class="value-highlight">{escape(rendered)}</span>'
        case NarrationPlaceholder(name=name, column_id=column_id):
            label = placeholder_token(part)
            # `data-param` keys the hover highlight and carries the column *id*
            # — two steps can interpolate the same expression with different
            # values, which would cross-wire if the name were the key. The
            # palette keys on `name` instead, so one parameter reads the same
            # color everywhere. `data-subst` is row-hover substitution's own.
            #
            # Both are plain data-*, read back by the delegated hover listener
            # in `app.js`. No Alpine directive here: interpolating into one
            # would be an injection, since Alpine compiles a directive's
            # *decoded* attribute text as JS.
            safe_id = escape(column_id)
            classes = ' '.join(
                (
                    []
                    if param_color_map is None
                    else [f'param-color-{param_color_map[name]}']
                )
                + (['param-repr'] if shows_repr(part) else [])
            )
            class_attribute = f'class="{classes}" ' if classes else ''
            return (
                f'<span {class_attribute}'
                f'data-param="{safe_id}" '
                f'data-subst="{safe_id}"{_phrase_attributes(part)}'
                f'>{escape(label)}</span>'
            )
        case NarrationTermRef():
            return _render_term_ref(part, glossary, ref_targets)


def _phrase_attributes(part: NarrationPlaceholder) -> str:
    """What row hover shows for a phrased slot, whose cell holds the Boolean."""
    phrases = boolean_phrases(part.format_spec)
    if phrases is None:
        return ''
    true_phrase, false_phrase = phrases
    return (
        f' data-true-phrase="{escape(true_phrase)}"'
        f' data-false-phrase="{escape(false_phrase)}"'
    )


_TERM_KIND_CLASSES: dict[TermKind, str] = {
    'actor': 'term-ref-actor',
    'object': 'term-ref-object',
    'activity': 'term-ref-activity',
}


def _term_kind_class(kind: TermKind | None) -> str:
    """The CSS class for a term's kind, or the fallback for one still deferred
    to inference. `TermKind` is closed, so the lookup is total."""
    return 'term-ref-unknown' if kind is None else _TERM_KIND_CLASSES[kind]


def _unknown_term_span(display: str) -> str:
    """A term the glossary does not hold, as a sentence part.

    No `data-term-id`, so the deep-link handler cannot navigate to a `#term=`
    that does not exist, and no tooltip marker. Sentence parts only:
    `_render_term_ref` answers the same case for a *narration* with bare text,
    because narration prose wraps nothing, while every part of a sentence
    timeline is a span and a bare text node would break its layout.
    """
    return f'<span class="term-ref-unknown">{escape(display)}</span>'


def _term_ref_span(term: GlossaryTerm, display: str, target: TermRefTarget) -> str:
    """One term reference the glossary holds.

    The tooltip's name and definition are *not* written here — `app.js` looks
    them up by `data-term-id` in the glossary `app_data` already ships, which
    is what keeps a term used 900 times from carrying 900 copies of its
    definition. A card that is not the tooltip's key is named apart.
    """
    link = '' if target.entry is None else ' term-ref--link'
    classes = f'{_term_kind_class(term.kind)}{link} has-term-tip'
    entry = (
        ''
        if target.entry in (None, target.tip)
        else f' data-term-entry="{escape(target.entry)}"'
    )
    change = '' if target.change is None else f' data-change="{target.change}"'
    return (
        f'<span class="{classes}" data-term-id="{escape(target.tip)}"{entry}{change}>'
        f'{escape(display)}</span>'
    )


def _own_target(term_id: TermId) -> TermRefTarget:
    return TermRefTarget(tip=term_id, entry=term_id)


def _render_term_ref(
    part: NarrationTermRef,
    glossary: Glossary | None,
    ref_targets: TermRefTargets | None,
) -> str:
    term = glossary.get(part.term_id) if glossary is not None else None
    if term is None:
        return str(escape(part.display))
    target = (ref_targets or _own_target)(part.term_id)
    return _term_ref_span(term, part.display, target)


def make_definition_filter(glossary: Glossary) -> Callable[[GlossaryTerm], Markup]:
    """Jinja filter: a term's definition, each definition ref a term ref.

    Usage: `{{ term | definition_md }}` — the term, not its definition, so a
    reference to the term itself stays plain bold: a link to the card the
    reader is on goes nowhere."""

    def _render(term: GlossaryTerm) -> Markup:
        if term.definition is None:
            return Markup('')
        return Markup(
            ''.join(
                _definition_piece_html(piece, term.id, glossary)
                for piece in read_definition(term.definition)
            )
        )

    return _render


def _definition_piece_html(
    piece: InlineSpan | NarrationTermRef, term_id: TermId, glossary: Glossary
) -> str:
    if not isinstance(piece, NarrationTermRef):
        return definition_span_html(piece)
    if piece.term_id == term_id:
        return definition_html(definition_part_text(piece))
    return _render_term_ref(piece, glossary, None)


def make_clause_part_filter(
    glossary: Glossary | None,
) -> Callable[[ClausePart], Markup]:
    """Jinja filter: renders a single `ClausePart` to HTML.

    Usage: `{{ part | clause_part }}`
    """

    def _render(part: ClausePart) -> Markup:
        match part:
            case NarrationTermRef(term_id=term_id, display=display):
                term = glossary.get(term_id) if glossary is not None else None
                if term is None:
                    return Markup(_unknown_term_span(display))
                return Markup(_term_ref_span(term, display, _own_target(term_id)))
            case NarrationLiteral(value=text):
                return Markup(f'<span class="clause-word">{escape(text)}</span>')

    return _render
