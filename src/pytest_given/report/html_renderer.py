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
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

import jinja2
from markupsafe import Markup, escape

from ..markdown import CodeSpan, EmphasisSpan, InlineSpan, PlainSpan, span_text
from ..model import (
    AttachmentRef,
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
    boolean_phrases,
    case_id,
    definition_ref_text,
    iter_steps,
    placeholder_token,
    plural,
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
from .glossary_view import build_glossary_view
from .inline_markdown import render_definition, render_span
from .palette import param_column_colors
from .slugs import build_scenario_slug_index
from .source_link import compile_source_link
from .story_view import (
    build_scenario_sentence_index,
    build_sentence_labels,
    build_story_rollups,
    sentence_key,
)
from .text import STATUS_GLYPH, STATUS_LABEL
from .theme import DEFAULT_THEME, Theme

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
    param_color_map = _build_param_color_map(report.scenarios)
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
    """The Jinja environment: the template loader plus every filter and test
    the report templates call."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
    )
    # The sentence key's format lives in `story_view`; the template emits it
    # for the jump button and `app.js` looks the label up by it, so both sides
    # go through the one constructor.
    env.globals['sentence_key'] = sentence_key
    # The status filter's pills, in order; `app.js` reads the same table from
    # its data, so a new status touches neither.
    env.globals['statuses'] = tuple(STATUS_LABEL)
    # The step-tree macro branches on this: an AttachmentRef has no content to
    # expand, only a column to point at.
    env.tests['attachment_ref'] = lambda value: isinstance(value, AttachmentRef)
    env.filters['source_url'] = _make_source_url_filter(
        template=source_link_template,
        project=report.metadata.project,
        commit_sha=report.metadata.commit_sha,
        root=source_root,
    )
    env.filters['narration'] = _make_narration_filter(
        param_color_map,
        glossary=report.glossary,
    )
    env.filters['clause_part'] = _make_clause_part_filter(report.glossary)
    env.filters['definition_md'] = _make_definition_filter(
        report.glossary or Glossary()
    )
    env.filters['plural'] = plural
    env.filters['status_glyph'] = lambda status: STATUS_GLYPH.get(status, '')
    env.filters['status_label'] = lambda status: STATUS_LABEL.get(status, status)
    env.filters['param_color_class'] = _make_param_color_class(param_color_map)
    env.filters['phase_blocks'] = _phase_blocks
    env.filters['column_phase_blocks'] = _column_phase_blocks
    env.filters['repr_columns'] = _repr_columns
    env.filters['case_id'] = case_id
    env.globals['data_url'] = _data_url
    return env


def _make_param_color_class(
    param_color_map: ParamColorMap,
) -> Callable[[ParameterColumn], str]:
    """Jinja filter: a column's colour class, or empty for an attachment
    column — the one place that decides which columns are coloured."""

    def _class(column: ParameterColumn) -> str:
        if column.kind == 'attachment':
            return ''
        return f'param-color-{param_color_map[column.name]}'

    return _class


def _phase_blocks(steps: list[Step]) -> list[list[Step]]:
    """Top-level steps in runs sharing a phase: one keyword each in the
    narration, and what a phase hover outlines."""
    blocks: list[list[Step]] = []
    for step in steps:
        if blocks and blocks[-1][0].phase == step.phase:
            blocks[-1].append(step)
        else:
            blocks.append([step])
    return blocks


def _column_phase_blocks(scenario: Scenario) -> dict[ColumnId, int]:
    """Each parameter-table column's phase block: the one a reader first meets
    it in. A column no step narrates joins the block beside it, the one before
    or, leading the table, the first."""
    assert scenario.parameters is not None
    met_in: dict[ColumnId, int] = {}
    for index, block in enumerate(_phase_blocks(scenario.steps)):
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


def _repr_columns(scenario: Scenario) -> set[ColumnId]:
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
    scenario_slugs = build_scenario_slug_index(report)
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
        'app_data_js': _script_json_parse(
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
        **_bundled_assets(),
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


def _script_json_parse(value: object) -> Markup:
    """Serialize `value` as a `JSON.parse(...)` call rather than a JS object
    literal: an engine reads a JSON string faster than the equivalent source,
    and this is the largest blob on the page.

    The tokenizer-steering sequences are neutralized on the way out —
    `json.dumps` escapes neither inside a string literal, and this blob carries
    user-controlled node IDs and sentence prose.
    """
    payload = json.dumps(json.dumps(value, separators=(',', ':')))
    return Markup('JSON.parse(' + _neutralize_script_data(payload) + ')')


def _app_data(report: ReportData) -> dict[str, object]:
    """The projection of the report that `app.js` seeds its state from.

    Not the whole report: everything the page displays is already rendered into
    the markup, and a second copy would dominate a large report's size."""
    return {
        'metadata': {'timestamp': report.metadata.timestamp},
        'status_labels': STATUS_LABEL,
        'glossary': (
            {
                'terms': [
                    {
                        'id': term.id,
                        'canonical': term.canonical,
                        'kind': term.kind,
                        'definition': term.definition,
                        # Pre-rendered once per term, for the hover tooltip.
                        # `render_definition` escapes the text and re-admits
                        # only <br>/<code>/<strong>/<em>, which is what lets
                        # app.js assign it as innerHTML.
                        'definition_html': render_definition(term.definition or ''),
                    }
                    for term in report.glossary.terms
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
                'search_text': _shown_text(scenario.narration),
            }
            for scenario in report.scenarios
        ],
    }


def _shown_text(narration: Narration) -> str:
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


def _bundled_assets() -> dict[str, Markup]:
    """The stylesheet and scripts inlined into the page — the whole reason the
    report needs no server and no external asset. Our own two lose their
    comments; the vendored Alpine bundle is already minified and keeps its
    licence line."""
    css, app_js, alpine_js = (
        (_TEMPLATES_DIR / filename).read_text(encoding='utf-8')
        for filename in ('styles.css', 'app.js', 'alpine.min.js')
    )
    return {
        'css': Markup(_strip_comments(css)),
        'app_js': Markup(_strip_comments(app_js)),
        'alpine_js': Markup(alpine_js),
    }


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


def _build_param_color_map(scenarios: list[Scenario]) -> ParamColorMap:
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


def _make_source_url_filter(
    *,
    template: str | None,
    project: str,
    commit_sha: str | None,
    root: Path | None,
) -> Callable[[SourceLocation | None], str | None]:
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

    def _filter(source: SourceLocation | None) -> str | None:
        if source is None or substitute is None:
            return None
        return substitute(source)

    return _filter


def _make_narration_filter(
    param_color_map: ParamColorMap,
    glossary: Glossary | None,
) -> Callable[[Narration], Markup]:
    """Jinja filter: renders a `Narration` to HTML, piece by piece.

    Usage: `{{ step.narration | narration }}`.
    """

    def _render(narration: Narration) -> Markup:
        out = [
            _render_narration_piece(piece, param_color_map, glossary)
            for piece in read_narration(narration)
        ]
        return Markup(''.join(out))

    return _render


def _render_narration_piece(
    part: NarrationPiece,
    param_color_map: ParamColorMap,
    glossary: Glossary | None,
) -> str:
    """Render one `NarrationPiece` to an HTML fragment."""
    match part:
        case PlainSpan() | CodeSpan() | EmphasisSpan():
            return render_span(part)
        case NarrationValue(rendered=rendered):
            return f'<span class="value-highlight">{escape(rendered)}</span>'
        case NarrationPlaceholder(name=name, column_id=column_id):
            color_idx = param_color_map[name]
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
            repr_class = ' param-repr' if _shows_repr(part) else ''
            return (
                f'<span class="param-color-{color_idx}{repr_class}" '
                f'data-param="{safe_id}" '
                f'data-subst="{safe_id}"{_phrase_attributes(part)}'
                f'>{escape(label)}</span>'
            )
        case NarrationTermRef():
            return _render_term_ref(part, glossary)


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


def _term_ref_span(term: GlossaryTerm, term_id: TermId, display: str) -> str:
    """One term reference the glossary holds.

    The tooltip's name and definition are *not* written here — `app.js` looks
    them up by id in the glossary `_app_data` already ships, which is what
    keeps a term used 900 times from carrying 900 copies of its definition.
    """
    classes = f'{_term_kind_class(term.kind)} term-ref--link has-term-tip'
    return (
        f'<span class="{classes}" data-term-id="{escape(term_id)}">'
        f'{escape(display)}</span>'
    )


def _render_term_ref(part: NarrationTermRef, glossary: Glossary | None) -> str:
    term = glossary.get(part.term_id) if glossary is not None else None
    if term is None:
        return str(escape(part.display))
    return _term_ref_span(term, part.term_id, part.display)


def _make_definition_filter(glossary: Glossary) -> Callable[[GlossaryTerm], Markup]:
    """Jinja filter: a term's definition, each definition ref a term ref.

    Usage: `{{ term | definition_md }}` — the term, not its definition, so a
    reference to the term itself stays plain bold: a link to the card the
    reader is on goes nowhere."""

    def _render(term: GlossaryTerm) -> Markup:
        def _ref(span: InlineSpan) -> str | None:
            text = definition_ref_text(span)
            if text is None:
                return None
            target = glossary.resolve_ref(text)
            if target is None or target.id == term.id:
                return None
            return _term_ref_span(target, target.id, text)

        return Markup(render_definition(term.definition or '', render_ref=_ref))

    return _render


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
