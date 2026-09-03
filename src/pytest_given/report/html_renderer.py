"""Rendering the HTML report: the Jinja environment, the context its
templates read, and the filters that turn model parts into markup.

Everything the page displays is rendered into the markup here; the one
JSON blob beside it is what `app.js` seeds its state from.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import jinja2
from markupsafe import Markup, escape

from ..model import (
    ActivityPart,
    ActivityTermRef,
    ActivityWord,
    AttachmentRef,
    Glossary,
    GlossaryTerm,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    ReportData,
    Scenario,
    SourceLocation,
    TermId,
    placeholder_token,
)
from .glossary_view import build_glossary_view, build_glossary_views
from .inline_markdown import render_inline_markdown
from .palette import param_column_colors
from .slugs import build_scenario_slug_index
from .source_link import compile_source_link
from .story_view import (
    build_activity_labels,
    build_coverage_maps,
    build_scenario_activity_index,
    build_story_rollups,
)

_TEMPLATES_DIR = Path(__file__).parent / 'templates'

# Maps parameter name to its color index. The index resolves to a color via
# `palette.param_column_colors`, which never runs out.
type ParamColorMap = dict[str, int]


@dataclass(frozen=True)
class TabVisibility:
    """Which browse tabs a report has anything to show in."""

    scenarios: bool
    stories: bool
    glossary: bool

    @property
    def visible_count(self) -> int:
        return sum((self.scenarios, self.stories, self.glossary))


def tab_visibility(report: ReportData) -> TabVisibility:
    return TabVisibility(
        scenarios=True,
        stories=bool(report.stories),
        glossary=bool(report.glossary is not None and report.glossary.terms),
    )


def _inline_md(text: str | None) -> Markup:
    """Jinja filter: render a term description's inline Markdown to safe HTML.

    The `not text` guard matters: `markupsafe.escape(None)` renders the literal
    string 'None', and `term.definition` is None for undefined terms."""
    if not text:
        return Markup('')
    return Markup(render_inline_markdown(text))


def render_html_string(
    report: ReportData,
    source_link_template: str | None,
) -> str:
    """Render a report model to a self-contained HTML document.

    `source_link_template` is the already-resolved template string (preset
    expansion happens before this point). None disables source linking.

    Returns the document rather than writing it — `sinks` owns the writing.
    """
    # Built once and handed to both: the narration filter colors placeholders
    # with it, and the template emits the matching `.param-color-N` rules.
    param_color_map = _build_param_color_map(report.scenarios)
    env = _build_env(report, source_link_template, param_color_map)
    return env.get_template('report.html.j2').render(
        **_render_context(report, param_color_map)
    )


def _build_env(
    report: ReportData,
    source_link_template: str | None,
    param_color_map: ParamColorMap,
) -> jinja2.Environment:
    """The Jinja environment: the template loader plus every filter and test
    the report templates call."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
    )
    env.globals['zip'] = zip
    # The step-tree macro branches on this: an AttachmentRef has no content to
    # expand, only a column to point at.
    env.tests['attachment_ref'] = lambda value: isinstance(value, AttachmentRef)
    env.filters['source_url'] = _make_source_url_filter(
        template=source_link_template,
        project=report.metadata.project,
        commit_sha=report.metadata.commit_sha,
    )
    env.filters['narration'] = _make_narration_filter(
        param_color_map,
        glossary=report.glossary,
    )
    env.filters['activity_part'] = _make_activity_part_filter(report.glossary)
    env.filters['inline_md'] = _inline_md
    return env


def _render_context(
    report: ReportData, param_color_map: ParamColorMap
) -> dict[str, object]:
    """Everything `report.html.j2` reads, in three groups: the report model
    itself, the precomputed aggregations, and the JSON blobs the page's Alpine
    state is seeded from."""
    coverage_maps = build_coverage_maps(report)
    scn_covers = build_scenario_activity_index(coverage_maps)
    activity_labels = build_activity_labels(report)
    glossary_views = build_glossary_views(report)
    scenario_slugs = build_scenario_slug_index(report)
    term_ids = [term.id for term in report.glossary.terms] if report.glossary else []
    return {
        'metadata': report.metadata,
        'scenarios': report.scenarios,
        'stories': report.stories,
        'glossary': report.glossary,
        'glossary_view': build_glossary_view(report, glossary_views),
        'tab_visibility': tab_visibility(report),
        'story_rollups': build_story_rollups(report, coverage_maps),
        'scn_covers': scn_covers,
        'scenario_slugs': scenario_slugs,
        'param_color_map': param_color_map,
        # The colors themselves, emitted as `.param-color-N` rules beside the
        # stylesheet. They are generated per report rather than sitting in
        # styles.css, because how many a report needs is a property of the
        # report.
        'param_colors': param_column_colors(len(param_color_map)),
        'app_data_js': _script_json_parse(
            _app_data(report)
            | {
                'story_ids': [story.id for story in report.stories],
                'term_ids': term_ids,
                'term_scenarios': glossary_views.term_scenarios,
                'scenario_activities': scn_covers,
                'activity_labels': activity_labels,
                'scenario_slugs': {
                    slug: node_id for node_id, slug in scenario_slugs.items()
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
    user-controlled node ids and activity prose.
    """
    payload = json.dumps(json.dumps(value, separators=(',', ':')))
    return Markup('JSON.parse(' + _neutralize_script_data(payload) + ')')


def _app_data(report: ReportData) -> dict[str, object]:
    """The projection of the report that `app.js` seeds its state from.

    Not the whole report: everything the page displays is already rendered into
    the markup, and a second copy of every step, traceback and attachment
    payload was the biggest single thing in a large report's HTML. Adding a
    field to `reportApp` means adding it here."""
    return {
        'metadata': {'timestamp': report.metadata.timestamp},
        'glossary': (
            {
                'terms': [
                    {
                        'id': term.id,
                        'canonical': term.canonical,
                        'kind': term.kind,
                        'definition': term.definition,
                        # Pre-rendered once per term, for the hover tooltip.
                        # `render_inline_markdown` escapes the text and
                        # re-admits only <br>/<code>/<strong>/<em>, which is
                        # what lets app.js assign it as innerHTML.
                        'definition_html': render_inline_markdown(
                            term.definition or ''
                        ),
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
                'story_id': scenario.story_id,
                'narration': {'text': scenario.narration.text},
            }
            for scenario in report.scenarios
        ],
    }


def _bundled_assets() -> dict[str, Markup]:
    """The stylesheet and scripts inlined into the page — the whole reason the
    report needs no server and no external asset."""
    return {
        name: Markup((_TEMPLATES_DIR / filename).read_text(encoding='utf-8'))
        for name, filename in (
            ('css', 'styles.css'),
            ('app_js', 'app.js'),
            ('alpine_js', 'alpine.min.js'),
        )
    }


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
) -> Callable[[SourceLocation | None], str | None]:
    """Build a Jinja filter that resolves a SourceLocation to a URL string.

    Returns None when source linking is disabled or the source is absent — the
    template reads that as "render a plain `<span>`". The template itself is
    validated and parsed once here, not per location.
    """
    substitute = (
        None
        if template is None
        else compile_source_link(template, project=project, commit_sha=commit_sha)
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
    """Jinja filter: renders a `Narration` to HTML, part by part.

    Usage: `{{ step.narration | narration }}`. A parts-less narration (a plain
    string label) is escaped and emitted verbatim.
    """

    def _render(narration: Narration) -> Markup:
        if not narration.parts:
            return Markup(str(escape(narration.text)))
        out = [
            _render_narration_part(part, param_color_map, glossary)
            for part in narration.parts
        ]
        return Markup(''.join(out))

    return _render


def _render_narration_part(
    part: NarrationPart,
    param_color_map: ParamColorMap,
    glossary: Glossary | None,
) -> str:
    """Render one `NarrationPart` to an HTML fragment."""
    match part:
        case NarrationLiteral(value=value):
            return str(escape(value))
        case NarrationValue(rendered=rendered):
            return f'<span class="value-highlight">{escape(rendered)}</span>'
        case NarrationPlaceholder(name=name, column_id=column_id):
            color_idx = param_color_map.get(name, 0)
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
            return (
                f'<span class="param-color-{color_idx}" '
                f'data-param="{safe_id}" '
                f'data-subst="{safe_id}"'
                f'>{escape(label)}</span>'
            )
        case NarrationTermRef():
            return _render_term_ref(part, glossary)


_TERM_KIND_CLASSES: dict[str | None, str] = {
    'actor': 'term-ref-actor',
    'object': 'term-ref-object',
    'verb': 'term-ref-verb',
}


def _term_kind_class(kind: str | None) -> str:
    """The CSS class for a term's kind. A kind still deferred to inference —
    or one this renderer does not know — falls back, and `dict.get` already
    reads `None` as a miss."""
    return _TERM_KIND_CLASSES.get(kind, 'term-ref-unknown')


def _term_ref_span(term: GlossaryTerm | None, term_id: TermId, display: str) -> str:
    """One term reference, as an activity part.

    A term the glossary does not hold gets a plain span: no `data-term-id`, so
    the deep-link handler cannot navigate to a `#term=` that does not exist,
    and no tooltip marker. That arm is reached only from the activity filter —
    `_render_term_ref` handles the same case for a *narration* by returning
    bare text, because narration prose wraps nothing, while every part of an
    activity timeline is a span and a bare text node would break its layout.

    The tooltip's name and definition are *not* written here — `app.js` looks
    them up by id in the glossary `_app_data` already ships, which is what
    keeps a term used 900 times from carrying 900 copies of its definition.
    """
    if term is None:
        return f'<span class="term-ref-unknown">{escape(display)}</span>'
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


def _make_activity_part_filter(
    glossary: Glossary | None,
) -> Callable[[ActivityPart], Markup]:
    """Jinja filter: renders a single `ActivityPart` to HTML.

    Usage: `{{ part | activity_part }}`
    """

    def _render(part: ActivityPart) -> Markup:
        match part:
            case ActivityTermRef(term_id=tid, display=display):
                term = glossary.get(tid) if glossary else None
                return Markup(_term_ref_span(term, tid, display))
            case ActivityWord(text=text):
                return Markup(f'<span class="activity-word">{escape(text)}</span>')

    return _render
