import json
from collections.abc import Callable
from pathlib import Path
from typing import assert_never

import jinja2
from markupsafe import Markup, escape

from ..model import (
    ActivityPart,
    ActivityTermRef,
    ActivityWord,
    Glossary,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    Scenario,
    SourceLocation,
    report_from_dict,
)
from .aggregations import (
    build_coverage_maps,
    build_glossary_aggregations,
    build_scenario_activity_index,
    build_scenario_slug_index,
    build_story_rollups,
    build_term_scenario_index,
    tab_visibility,
)
from .source_link import compile_source_link

_NUM_PARAM_COLORS = 6

# Maps parameter name to its color index (0-based, wraps at _NUM_PARAM_COLORS)
type ParamColorMap = dict[str, int]


def _neutralize_script_close(text: str) -> str:
    """Replace `</` with `<\\/` so text embedded in an inline `<script>` can't
    close the tag. `\\/` is a valid JS/JSON escape for `/`, so the parsed value
    is unchanged while the HTML parser no longer sees a closing tag."""
    return text.replace('</', '<\\/')


def _script_json(value: object) -> Markup:
    """Serialize `value` to JSON for embedding in an inline `<script>`, with
    `</` neutralized. `json.dumps` does not escape `</` inside string literals,
    and these blobs carry user-controlled node ids — so a parametrize id
    containing `</script>` would otherwise break out of the tag (stored XSS)."""
    return Markup(_neutralize_script_close(json.dumps(value)))


def render_html(
    json_path: Path,
    html_path: Path,
    source_link_template: str | None = None,
) -> None:
    """Render a JSON report to a self-contained HTML file.

    `source_link_template` is the already-resolved template string (preset
    expansion happens before this point). None disables source linking;
    each scenario then renders a plain `<span>` for its source location.
    """
    raw_json = json_path.read_text(encoding='utf-8')
    report = report_from_dict(json.loads(raw_json))
    # JSON doesn't escape `</` inside string literals, but we embed `raw_json`
    # inside an inline <script>; an attachment containing `</script>` would
    # close the tag and yield stored XSS. `\/` is a valid JSON/JS escape for
    # `/`, so this preserves the parsed value while neutering the HTML parser.
    safe_report_json = _neutralize_script_close(raw_json)

    templates_dir = Path(__file__).parent / 'templates'
    css = (templates_dir / 'styles.css').read_text(encoding='utf-8')
    app_js = (templates_dir / 'app.js').read_text(encoding='utf-8')
    alpine_js = (templates_dir / 'alpine.min.js').read_text(encoding='utf-8')

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        autoescape=True,
    )
    env.globals['zip'] = zip

    param_color_map = _build_param_color_map(report.scenarios)

    env.filters['source_url'] = _make_source_url_filter(
        template=source_link_template,
        project=report.metadata.project,
        commit_sha=report.metadata.commit_sha,
    )

    coverage_maps = build_coverage_maps(report)
    glossary_aggregations = build_glossary_aggregations(report)
    story_rollups = build_story_rollups(report, coverage_maps)
    scn_covers = build_scenario_activity_index(coverage_maps)
    visibility = tab_visibility(report)

    story_ids_json = _script_json([story.id for story in report.stories])
    term_ids_json = _script_json(
        [term.id for term in report.glossary.terms]
        if report.glossary is not None
        else []
    )
    term_scenario_index = build_term_scenario_index(report)
    term_scenarios_json = _script_json(term_scenario_index)
    scenario_slugs = build_scenario_slug_index(report)
    scenario_slugs_json = _script_json(
        {slug: node_id for node_id, slug in scenario_slugs.items()}
    )

    env.filters['narration'] = _make_narration_filter(
        param_color_map,
        glossary=report.glossary,
    )
    env.filters['activity_part'] = _make_activity_part_filter(report.glossary)
    template = env.get_template('report.html.j2')
    html = template.render(
        metadata=report.metadata,
        scenarios=report.scenarios,
        stories=report.stories,
        glossary=report.glossary,
        coverage_maps=coverage_maps,
        glossary_aggregations=glossary_aggregations,
        tab_visibility=visibility,
        story_rollups=story_rollups,
        scn_covers=scn_covers,
        report_json=Markup(safe_report_json),
        story_ids_json=story_ids_json,
        term_ids_json=term_ids_json,
        term_scenarios_json=term_scenarios_json,
        term_scenario_index=term_scenario_index,
        scenario_slugs=scenario_slugs,
        scenario_slugs_json=scenario_slugs_json,
        css=Markup(css),
        app_js=Markup(app_js),
        alpine_js=Markup(alpine_js),
        param_color_map=param_color_map,
        num_param_colors=_NUM_PARAM_COLORS,
    )
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding='utf-8')


def _build_param_color_map(scenarios: list[Scenario]) -> ParamColorMap:
    color_map: ParamColorMap = {}
    color_idx = 0
    for scenario in scenarios:
        if scenario.parameters is None:
            continue
        for name in scenario.parameters.names:
            if name not in color_map:
                color_map[name] = color_idx
                color_idx += 1
    return color_map


def _make_source_url_filter(
    *,
    template: str | None,
    project: str,
    commit_sha: str | None,
) -> Callable[[SourceLocation | None], str | None]:
    """Build a Jinja filter that resolves a SourceLocation to a URL string.

    Returns None when source linking is disabled or the source is absent —
    the template uses that as the signal to render a plain `<span>` via the
    `source_link` macro.

    The template is validated and parsed once here (not per location); the
    per-call closure only performs the substitution.
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
    glossary: Glossary | None = None,
) -> Callable[[Narration], Markup]:
    """Filter usage: `{{ step.narration | narration }}` or
    `{{ scenario.narration | narration }}`.

    The narration is a `Narration` dataclass with a flat `text` and a list
    of typed `NarrationPart` variants:
      - `NarrationLiteral` → escape `value`
      - `NarrationValue`   → `.param-value` highlight around `rendered`
      - `NarrationPlaceholder` → color-coded `{name!conv:spec}` token
      - `NarrationTermRef` → kind-coloured pill resolved via glossary
    Empty parts → escape `text` and emit verbatim.
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
    """Render one `NarrationPart` to an HTML fragment. The `case _` guard makes
    a future variant a type error here (via `assert_never`) rather than a part
    silently dropped from the rendered narration."""
    match part:
        case NarrationLiteral(value=value):
            return str(escape(value))
        case NarrationValue(rendered=rendered):
            return f'<span class="param-value">{escape(rendered)}</span>'
        case NarrationPlaceholder(name=name):
            color_idx = param_color_map.get(name, 0) % _NUM_PARAM_COLORS
            label = _placeholder_token(part)
            # Single-quote the JS arg because the HTML attribute is "..."
            # and parametrize names are Python identifiers (no `'`).
            safe_name = escape(name)
            enter = f"setHoverParam('{safe_name}', $event.currentTarget)"
            leave = 'setHoverParam(null, $event.currentTarget)'
            return (
                f'<span class="param-color-{color_idx}" '
                f'data-param="{safe_name}" '
                f'@mouseenter="{enter}" '
                f'@mouseleave="{leave}"'
                f'>{escape(label)}</span>'
            )
        case NarrationTermRef():
            return _render_term_ref(part, glossary, param_color_map)
        case _:
            assert_never(part)


_TERM_KIND_CLASSES = {
    'actor': 'term-ref-actor',
    'object': 'term-ref-object',
    'verb': 'term-ref-verb',
}


def _term_kind_class(kind: str | None) -> str:
    return (
        _TERM_KIND_CLASSES.get(kind, 'term-ref-unknown') if kind else 'term-ref-unknown'
    )


def _term_pill(
    *,
    classes: list[str],
    display: str,
    term_id: str | None = None,
    tooltip_name: str = '',
    tooltip_def: str = '',
) -> str:
    pill_classes = list(classes)
    if term_id is not None:
        pill_classes.append('term-ref--link')
    if tooltip_name:
        pill_classes.append('has-term-tip')
    attrs = [f'class="{" ".join(pill_classes)}"']
    if term_id is not None:
        attrs.append(f'data-term-id="{escape(term_id)}"')
    # The custom hover tooltip (see app.js) reads the canonical name and
    # definition off these attributes; it replaces the native `title` so the
    # term name can show as a styled heading above its definition.
    if tooltip_name:
        attrs.append(f'data-term-name="{escape(tooltip_name)}"')
        if tooltip_def:
            attrs.append(f'data-term-def="{escape(tooltip_def)}"')
    return f'<span {" ".join(attrs)}>{escape(display)}</span>'


def _render_term_ref(
    part: NarrationTermRef,
    glossary: Glossary | None,
    param_color_map: ParamColorMap,
) -> str:
    term = glossary.get(part.term_id) if glossary is not None else None
    if term is None:
        return str(escape(part.display))
    classes = [_term_kind_class(term.kind)]
    if part.param_column is not None:
        color_idx = param_color_map.get(part.param_column, 0) % _NUM_PARAM_COLORS
        classes.append(f'param-color-{color_idx}')
    return _term_pill(
        classes=classes,
        display=part.display,
        term_id=part.term_id,
        tooltip_name=term.canonical,
        tooltip_def=term.definition or '',
    )


def _placeholder_token(part: NarrationPlaceholder) -> str:
    """Reconstruct the source-side `{name!conv:spec}` token, so the merged
    template view preserves the author's format intent."""
    inner = part.name
    if part.conversion:
        inner += '!' + part.conversion
    if part.format_spec:
        inner += ':' + part.format_spec
    return '{' + inner + '}'


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
                return Markup(
                    _term_pill(
                        classes=[_term_kind_class(term.kind if term else None)],
                        display=display,
                        term_id=tid,
                        tooltip_name=term.canonical if term else '',
                        tooltip_def=term.definition or '' if term else '',
                    )
                )
            case ActivityWord(text=text):
                return Markup(f'<span class="activity-word">{escape(text)}</span>')

    return _render
