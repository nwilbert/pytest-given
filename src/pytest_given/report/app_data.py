"""The JSON `app.js` seeds the report page's state from: the report's
projection, and what each citation copy button copies."""

from typing import TypedDict

from ..markdown import definition_html
from ..model import GlossaryTerm, ReportData, avoided_word
from .citation_index import (
    CitationIndex,
    CitationTemplate,
    Target,
    TargetKind,
    citation_templates,
)
from .glossary_view import section_keys
from .glyphs import STATUS_LABEL
from .html_narration import shown_text


def app_data(report: ReportData) -> dict[str, object]:
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


class CitationData(TypedDict):
    templates: dict[str, CitationTemplate]
    scenario: list[list[str]]
    tag: dict[str, list[str]]
    story: dict[str, list[str]]
    term: dict[str, list[str]]


def citation_data(report: ReportData, index: CitationIndex) -> CitationData | None:
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
