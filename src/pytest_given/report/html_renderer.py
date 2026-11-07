"""Rendering the HTML report: the Jinja environment, the context its
templates read, and the filters that turn model parts into markup.

Everything the page displays is rendered into the markup here; the one
JSON blob beside it is what `app.js` seeds its state from.
"""

# A pytest session or CLI command that renders no HTML never loads Jinja or
# MarkupSafe.
__lazy_modules__ = ['jinja2', 'markupsafe']

import base64
import json
import re
from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypedDict

import jinja2
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
    AttachmentRef,
    CellValue,
    ClausePart,
    ClauseTermRef,
    ClauseWord,
    ColumnId,
    Glossary,
    GlossaryTerm,
    Narration,
    NarrationPiece,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    ParameterColumn,
    ReportData,
    Scenario,
    SourceLocation,
    Step,
    TermId,
    TermKind,
    avoided_word,
    boolean_phrases,
    case_id,
    definition_part_text,
    iter_steps,
    placeholder_token,
    plural,
    read_definition,
    read_narration,
)
from .citation_index import (
    CitationIndex,
    CitationTemplate,
    Target,
    TargetKind,
    citation_templates,
)
from .coverage import build_coverage_map
from .glossary_view import build_glossary_view, section_keys
from .glyphs import STATUS_GLYPH, STATUS_LABEL
from .palette import param_column_colors
from .slugs import build_scenario_slug_index
from .source_link import compile_source_link
from .story_view import (
    build_scenario_sentence_index,
    build_sentence_labels,
    build_story_rollups,
    sentence_key,
)
from .theme import DEFAULT_THEME, Theme

if TYPE_CHECKING:
    from ..model import Change, Side

_TEMPLATES_DIR = Path(__file__).parent / 'templates'

# Maps parameter name to its color index. The index resolves to a color via
# `palette.param_column_colors`, which never runs out.
type ParamColorMap = dict[str, int]


class CitationData(TypedDict):
    templates: dict[str, CitationTemplate]
    scenario: list[list[str]]
    tag: dict[str, list[str]]
    story: dict[str, list[str]]
    term: dict[str, list[str]]


@dataclass(frozen=True)
class TabVisibility:
    """Which browse tabs a report has anything to show in."""

    stories: bool
    glossary: bool

    @property
    def visible_count(self) -> int:
        """Scenarios is always one of them, so the other two are the count."""
        return 1 + self.stories + self.glossary


def tab_visibility(report: ReportData) -> TabVisibility:
    return TabVisibility(
        stories=bool(report.stories),
        glossary=bool(report.glossary is not None and report.glossary.terms),
    )


def _inline_md(text: str | None) -> Markup:
    """Jinja filter: a definition string's inline Markdown, its bold spans
    plain bold rather than definition refs — the delta page's."""
    return Markup(definition_html(text or ''))


def render_html_string(
    report: ReportData,
    source_link_template: str | None,
    theme: Theme = DEFAULT_THEME,
    source_root: Path | None = None,
) -> str:
    """Render a report model to a self-contained HTML document.

    `source_link_template` is the already-resolved template string (preset
    expansion happens before this point). None disables source linking.
    `source_root` is what `{path}` resolves against (see
    `compile_source_link`). `theme` is the default the page opens in until the
    viewer picks one.

    Returns the document rather than writing it — `sinks` owns the writing.
    """
    # Built once and handed to both: the narration filter colors placeholders
    # with it, and the template emits the matching `.param-color-N` rules.
    param_color_map = build_param_color_map(report.scenarios)
    env = _build_env(report, source_link_template, source_root, param_color_map)
    return env.get_template('report.html.j2').render(
        **_render_context(report, param_color_map, theme)
    )


def _build_env(
    report: ReportData,
    source_link_template: str | None,
    source_root: Path | None,
    param_color_map: ParamColorMap,
) -> jinja2.Environment:
    """The Jinja environment: the shared one plus every filter the report's
    own data feeds."""
    env = base_env()
    # The sentence key's format lives in `story_view`; the template emits it
    # for the jump button and `app.js` looks the label up by it, so both sides
    # go through the one constructor.
    env.globals['sentence_key'] = sentence_key
    env.filters['source_url'] = make_source_url_filter(
        template=source_link_template,
        project=report.metadata.project,
        commit_sha=report.metadata.commit_sha,
        root=source_root,
    )
    env.filters['narration'] = make_narration_filter(
        param_color_map, glossary=report.glossary
    )
    env.filters['clause_part'] = _make_clause_part_filter(report.glossary)
    env.filters['definition_md'] = _make_definition_filter(
        report.glossary or Glossary()
    )
    env.filters['param_color_class'] = _make_param_color_class(param_color_map)
    return env


def base_env() -> jinja2.Environment:
    """The template loader and the filters and tests that read no report, which
    the report page and the delta page share."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
    )
    # The status filter's pills, in order; `app.js` reads the same table from
    # its data, so a new status touches neither.
    env.globals['statuses'] = tuple(STATUS_LABEL)
    # The step-tree macro branches on this: an AttachmentRef has no content to
    # expand, only a column to point at.
    env.tests['attachment_ref'] = lambda value: isinstance(value, AttachmentRef)
    env.filters['inline_md'] = _inline_md
    env.filters['plural'] = plural
    env.filters['avoid_html'] = _avoid_html
    env.filters['status_glyph'] = lambda status: STATUS_GLYPH.get(status, '')
    env.filters['status_label'] = lambda status: STATUS_LABEL.get(status, status)
    env.filters['phase_blocks'] = phase_blocks
    env.filters['column_phase_blocks'] = column_phase_blocks
    env.filters['repr_columns'] = repr_columns
    env.filters['case_id'] = case_id
    env.filters['value_cell'] = _value_cell
    # No column coloured until a page passes its colour map.
    env.filters['param_color_class'] = _make_param_color_class(None)
    env.globals['data_url'] = _data_url
    return env


def _make_param_color_class(
    param_color_map: ParamColorMap | None,
) -> Callable[[ParameterColumn], str]:
    """Jinja filter: a column's colour class, or empty for an attachment
    column or without a map — the one place that decides which columns are
    coloured."""

    def _class(column: ParameterColumn) -> str:
        if param_color_map is None or column.kind == 'attachment':
            return ''
        return f'param-color-{param_color_map[column.name]}'

    return _class


def phase_blocks(steps: list[Step]) -> list[list[Step]]:
    """Top-level steps in runs sharing a phase: one keyword each in the
    narration, and what a phase hover outlines."""
    blocks: list[list[Step]] = []
    for step in steps:
        if blocks and blocks[-1][0].phase == step.phase:
            blocks[-1].append(step)
        else:
            blocks.append([step])
    return blocks


def column_phase_blocks(scenario: Scenario) -> dict[ColumnId, int]:
    """Each parameter-table column's phase block: the one a reader first meets
    it in. A column no step narrates joins the block beside it, the one before
    or, leading the table, the first."""
    assert scenario.parameters is not None
    met_in: dict[ColumnId, int] = {}
    for index, block in enumerate(phase_blocks(scenario.steps)):
        for step in iter_steps(block):
            for part in step.narration.parts:
                if isinstance(part, NarrationPlaceholder):
                    met_in.setdefault(part.column_id, index)
            for attachment in step.attachments:
                if isinstance(attachment, AttachmentRef):
                    met_in.setdefault(attachment.column_id, index)
    columns = scenario.parameters.columns
    known = [met_in[column.id] for column in columns if column.id in met_in]
    if not known:
        return {}
    current = known[0]
    blocks: dict[ColumnId, int] = {}
    for column in columns:
        current = met_in.get(column.id, current)
        blocks[column.id] = current
    return blocks


_REPR_CONVERSIONS = ('r', 'a')


def repr_columns(scenario: Scenario) -> set[ColumnId]:
    """The columns a slot shows as a repr, which its author narrated that way
    because the exact value matters: a padded string, an empty one."""
    step_narrations = (step.narration for step in iter_steps(scenario.steps))
    return {
        part.column_id
        for narration in (scenario.narration, *step_narrations)
        for part in narration.parts
        if isinstance(part, NarrationPlaceholder) and _shows_repr(part)
    }


def _shows_repr(part: NarrationPlaceholder) -> bool:
    return part.conversion in _REPR_CONVERSIONS


def _value_cell(
    column: ParameterColumn,
    value: CellValue,
    block: int | None,
    change: Change | None = None,
    shows_repr: bool = False,
) -> Markup:
    """A parameter table's `<td>` for any column but an attachment one. A
    filter, not a macro: a table has one per cell, and a macro call each cost
    the large report's render a twentieth.

    `data-subst` only where the cell has something to substitute: a generated
    column is blank for a case that recorded no value, and substituting that
    blank would erase the step's {token} instead of replacing it. A `param`
    cell always substitutes, as `None` there is a real parametrize value."""
    column_id = escape(column.id)
    substitutes = column.kind == 'param' or value is not None
    repr_class = 'class="param-repr" ' if shows_repr else ''
    parts = [f'<td {repr_class}data-param="{column_id}"']
    if block is not None:
        parts.append(f' data-block="{block}"')
    if substitutes:
        parts.append(f' data-subst="{column_id}"')
    if isinstance(value, bool):
        parts.append(f' data-boolean="{value}"')
    if change:
        parts.append(f' data-change="{change}"')
    parts.append(f'>{escape(value) if substitutes else ""}</td>')
    return Markup(''.join(parts))


def _render_context(
    report: ReportData, param_color_map: ParamColorMap, theme: Theme
) -> dict[str, object]:
    """Everything `report.html.j2` reads, in three groups: the report model
    itself, the precomputed aggregations, and the JSON blobs the page's Alpine
    state is seeded from."""
    glossary_view = build_glossary_view(report)
    coverage = build_coverage_map(report)
    scn_covers = build_scenario_sentence_index(coverage)
    sentence_labels = build_sentence_labels(report)
    scenario_slugs = build_scenario_slug_index(report.scenarios)
    story_rollups = build_story_rollups(report, coverage)
    citation_index = CitationIndex(
        report,
        {story_id: rollup.scenarios for story_id, rollup in story_rollups.items()},
        glossary_view.term_scenarios,
    )
    term_ids = [term.id for term in report.glossary.terms] if report.glossary else []
    return {
        'metadata': report.metadata,
        'theme_default': theme,
        'scenarios': report.scenarios,
        'stories': report.stories,
        'glossary': report.glossary,
        'glossary_view': glossary_view,
        'tab_visibility': tab_visibility(report),
        'story_rollups': story_rollups,
        'scn_covers': scn_covers,
        'scenario_index': {scn.id: index for index, scn in enumerate(report.scenarios)},
        'scenario_slugs': scenario_slugs,
        'citations': report.metadata.report_url is not None,
        # The colors themselves, one (light, dark) pair per column, emitted as
        # `--param-color-N` tokens beside the stylesheet. They are generated
        # per report rather than sitting in styles.css, because how many a
        # report needs is a property of the report.
        'param_colors': list(
            zip(
                param_column_colors(len(param_color_map), 'light'),
                param_column_colors(len(param_color_map), 'dark'),
                strict=True,
            )
        ),
        'app_data_js': script_json_parse(
            _app_data(report)
            | {
                'story_ids': [story.id for story in report.stories],
                'term_ids': term_ids,
                'term_scenarios': glossary_view.term_scenarios,
                'scenario_sentences': scn_covers,
                'sentence_labels': sentence_labels,
                'scenario_slugs': {
                    slug: node_id for node_id, slug in scenario_slugs.items()
                },
                'citations': _citation_data(report, citation_index),
                'cited_scenario_ids': {
                    cited: scenario.id
                    for cited, scenario in citation_index.scenarios.items()
                    if cited != scenario.id
                },
            }
        ),
        **bundled_assets(),
    }


def _neutralize_script_data(text: str) -> str:
    """Escape the two sequences that let text embedded in an inline `<script>`
    steer the HTML tokenizer out of plain script-data state.

    - `</` closes the tag outright.
    - `<!--` opens script-data-*escaped* state; a `<script` after it reaches
      double-escaped state, where the template's own `</script>` no longer
      terminates the element and the rest of the document — the Alpine bundle
      included — is swallowed as script text.

    `\\/` and `\\u003C` are both valid JSON *and* JS escapes, so the blob stays
    parseable and the parsed value is unchanged, while the HTML parser sees
    neither sequence."""
    return text.replace('</', '<\\/').replace('<!--', '\\u003C!--')


def script_json_parse(value: object) -> Markup:
    """Serialize `value` as a `JSON.parse(...)` call rather than a JS object
    literal: an engine reads a JSON string faster than the equivalent source,
    and this is the largest blob on the page.

    The tokenizer-steering sequences are neutralized on the way out —
    `json.dumps` escapes neither inside a string literal, and this blob carries
    user-controlled node IDs and sentence prose.
    """
    payload = json.dumps(json.dumps(value, separators=(',', ':')))
    return Markup('JSON.parse(' + _neutralize_script_data(payload) + ')')


def _avoid_html(term: GlossaryTerm) -> Markup:
    """A term's avoid entries as written, each rendered by `definition_html`."""
    return Markup(', '.join(definition_html(entry) for entry in term.avoid))


def _app_data(report: ReportData) -> dict[str, object]:
    """The projection of the report that `app.js` seeds its state from.

    Not the whole report: everything the page displays is already rendered into
    the markup, and a second copy would dominate a large report's size."""
    keys = section_keys(report.glossary.terms) if report.glossary else {}
    return {
        'metadata': {'timestamp': report.metadata.timestamp},
        'status_labels': STATUS_LABEL,
        'glossary': (
            {
                'terms': [
                    term_app_data(term, keys[term.id]) for term in report.glossary.terms
                ]
            }
            if report.glossary is not None
            else None
        ),
        'scenarios': [
            {
                'id': scenario.id,
                'module': scenario.module,
                'tags': scenario.tags,
                'status': scenario.status,
                'search_text': shown_text(scenario.narration),
            }
            for scenario in report.scenarios
        ],
    }


def term_app_data(
    term: GlossaryTerm, section_key: str | None = None
) -> dict[str, object]:
    return {
        'id': term.id,
        'canonical': term.canonical,
        'kind': term.kind,
        'definition': term.definition_text,
        # Pre-rendered once per term, for the hover tooltip. `definition_html`
        # escapes the text and re-admits only <br>/<code>/<strong>/<em>, which
        # is what lets app.js assign it as innerHTML.
        'definition_html': definition_html(term.definition_text or ''),
        'section_key': section_key,
        'avoid': [avoided_word(entry) for entry in term.avoid],
    }


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


def _citation_data(report: ReportData, index: CitationIndex) -> CitationData | None:
    """What each copy button copies: the forms, and a row for each target, keyed
    as the page finds it: a scenario's by its card's position, a tag's at every
    level of the tree `app.js` builds, a story's and a term's by id. Only a
    report with a public URL carries it."""
    report_url = report.metadata.report_url
    if report_url is None:
        return None

    def row(kind: TargetKind, key: str) -> list[str]:
        return index.citation(Target(kind, key)).template_row()

    return {
        'templates': citation_templates(report_url),
        # `index.scenarios` holds every scenario, in the report's order.
        'scenario': [row('scenario', cited) for cited in index.scenarios],
        'tag': {tag: row('tag', tag) for tag in index.tags},
        'story': {story_id: row('story', story_id) for story_id in index.stories},
        'term': {term_id: row('term', term_id) for term_id in index.terms},
    }


def bundled_assets(*extra_stylesheets: str) -> dict[str, Markup]:
    """The stylesheets and scripts inlined into the page — the whole reason the
    report needs no server and no external asset. The vendored Alpine bundle
    is already minified and keeps its licence line."""
    return {
        'css': Markup('').join(
            bundled_script(name) for name in ('styles.css', *extra_stylesheets)
        ),
        'app_js': bundled_script('app.js'),
        'alpine_js': Markup(
            (_TEMPLATES_DIR / 'alpine.min.js').read_text(encoding='utf-8')
        ),
    }


def bundled_script(filename: str) -> Markup:
    """One of our own stylesheets or scripts, without its comments."""
    source = (_TEMPLATES_DIR / filename).read_text(encoding='utf-8')
    return Markup(_strip_comments(source))


_DATA_URL_MIME = {'.woff2': 'font/woff2', '.svg': 'image/svg+xml'}


def _data_url(filename: str) -> Markup:
    """Jinja global: a binary asset under `templates/` as a `data:` URL, so
    the template names each font and the logo beside the rule that uses it.
    The files stay the only copies to update — the docs site stages its logo
    and favicon from the same SVG, see noxfile.py."""
    path = _TEMPLATES_DIR / filename
    encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    return Markup(f'data:{_DATA_URL_MIME[path.suffix]};base64,{encoded}')


_BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)
_COMMENT_LINE = re.compile(r'^[ \t]*//.*$', re.MULTILINE)


def _strip_comments(source: str) -> str:
    """Drops the block comments and the comment-only lines of our own CSS and
    JS — about a third of each file is prose meant for a maintainer, not a
    report. Every comment is replaced by the newlines it spanned, so a line
    number in a browser stack trace still points at the same line of the
    source file. A trailing `//` stays: telling it from one inside a string
    takes a tokenizer, and those notes are short. Assumes no string literal
    contains `/*` and no template literal has a line starting with `//`."""
    without_blocks = _BLOCK_COMMENT.sub(
        lambda match: '\n' * match.group().count('\n'), source
    )
    return _COMMENT_LINE.sub('', without_blocks)


def build_param_color_map(scenarios: list[Scenario]) -> ParamColorMap:
    """One color per column *name* across the report, so a parameter reads the
    same color in every scenario. Attachment columns are excluded — a badge
    needs no value color."""
    color_map: ParamColorMap = {}
    color_idx = 0
    for scenario in scenarios:
        if scenario.parameters is None:
            continue
        for column in scenario.parameters.columns:
            if column.kind == 'attachment':
                continue
            if column.name not in color_map:
                color_map[column.name] = color_idx
                color_idx += 1
    return color_map


class _SourceUrlFilter(Protocol):
    def __call__(self, source: SourceLocation | None, /) -> str | None: ...


class _NarrationFilter(Protocol):
    def __call__(
        self, narration: Narration, /, *, before: str = '', after: str = ''
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
    validated and parsed once here, not per location. The `side` the shared
    macros pass is ignored: this filter serves one side.
    """
    substitute = (
        None
        if template is None
        else compile_source_link(
            template, project=project, commit_sha=commit_sha, root=root
        )
    )

    def _filter(source: SourceLocation | None) -> str | None:
        if source is None or substitute is None:
            return None
        return substitute(source)

    return _filter


def make_narration_filter(
    param_color_map: ParamColorMap | None,
    glossary: Glossary | None,
    *,
    term_side: Side | None = None,
    linked_terms: Collection[TermId] | None = None,
) -> _NarrationFilter:
    """Jinja filter: renders a `Narration` to HTML, piece by piece.

    Without a colour map no placeholder is coloured. `term_side` stamps each
    term ref with the side whose glossary it was read against. Given
    `linked_terms`, a ref to any other term has its tooltip but no link.
    `before` and `after` flank a stretch of a longer line.
    """

    def _render(narration: Narration, *, before: str = '', after: str = '') -> Markup:
        out = [
            _render_narration_piece(
                piece, param_color_map, glossary, term_side, linked_terms
            )
            for piece in read_narration(narration, before=before, after=after)
        ]
        return Markup(''.join(out))

    return _render


def _render_narration_piece(
    part: NarrationPiece,
    param_color_map: ParamColorMap | None,
    glossary: Glossary | None,
    term_side: Side | None,
    linked_terms: Collection[TermId] | None,
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
                + (['param-repr'] if _shows_repr(part) else [])
            )
            class_attribute = f'class="{classes}" ' if classes else ''
            return (
                f'<span {class_attribute}'
                f'data-param="{safe_id}" '
                f'data-subst="{safe_id}"{_phrase_attributes(part)}'
                f'>{escape(label)}</span>'
            )
        case NarrationTermRef():
            return _render_term_ref(part, glossary, term_side, linked_terms)


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


def _term_ref_span(
    term: GlossaryTerm,
    term_id: TermId,
    display: str,
    side: Side | None = None,
    linked: bool = True,
) -> str:
    """One term reference the glossary holds.

    The tooltip's name and definition are *not* written here — `app.js` looks
    them up by id in the glossary `_app_data` already ships, which is what
    keeps a term used 900 times from carrying 900 copies of its definition.
    """
    link = ' term-ref--link' if linked else ''
    classes = f'{_term_kind_class(term.kind)}{link} has-term-tip'
    sided = '' if side is None else f' data-term-side="{side}"'
    return (
        f'<span class="{classes}" data-term-id="{escape(term_id)}"{sided}>'
        f'{escape(display)}</span>'
    )


def _render_term_ref(
    part: NarrationTermRef,
    glossary: Glossary | None,
    side: Side | None,
    linked_terms: Collection[TermId] | None,
) -> str:
    term = glossary.get(part.term_id) if glossary is not None else None
    if term is None:
        return str(escape(part.display))
    linked = linked_terms is None or part.term_id in linked_terms
    return _term_ref_span(term, part.term_id, part.display, side, linked)


def _make_definition_filter(glossary: Glossary) -> Callable[[GlossaryTerm], Markup]:
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
    return _render_term_ref(piece, glossary, None, None)


def _make_clause_part_filter(
    glossary: Glossary | None,
) -> Callable[[ClausePart], Markup]:
    """Jinja filter: renders a single `ClausePart` to HTML.

    Usage: `{{ part | clause_part }}`
    """

    def _render(part: ClausePart) -> Markup:
        match part:
            case ClauseTermRef(term_id=term_id, display=display):
                term = glossary.get(term_id) if glossary is not None else None
                if term is None:
                    return Markup(_unknown_term_span(display))
                return Markup(_term_ref_span(term, term_id, display))
            case ClauseWord(text=text):
                return Markup(f'<span class="clause-word">{escape(text)}</span>')

    return _render
