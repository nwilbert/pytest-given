"""`citations check` and `update`: the report links in Markdown documents,
held to a JSON report."""

import re
from collections.abc import Sequence
from pathlib import Path

import pytest

from pytest_given import attach, given, scenario, then, when
from pytest_given.citations import CitationsResult, check_citations, markdown_documents
from pytest_given.model import (
    Narration,
    NarrationLiteral,
    NarrationTermRef,
    PytestGivenError,
    ReportData,
    Scenario,
    Status,
    Step,
    TermId,
    narration_of,
)
from tests.ubiquitous_language import pg
from tests.unit.citation_reports import URL, report_, scenario_, story_


def _run(
    tmp_path: Path,
    document: str,
    report: ReportData,
    *,
    update: bool = False,
    name: str = 'doc.md',
    report_url: str | None = None,
    report_path: Path | None = None,
    covering: Sequence[str] = (),
) -> tuple[CitationsResult, str]:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(document.encode('utf-8'))
    result = check_citations(
        report,
        [path],
        report_url=report_url,
        report_path=report_path,
        update=update,
        covering=covering,
    )
    return result, path.read_bytes().decode('utf-8')


PAY = scenario_('t.py::test_pay', 'Pay by card')
# A link to the report, so that a document is checked rather than refused.
CURRENT = f'✅ [Pay by card]({URL}#scenario=t.py::test_pay)\n'


# --- The self-report's scenarios ---


@scenario(
    t"`citations update` rewrites a stale {pg['Citation'].l} to its target's "
    t'glyph, text and summary',
    tags=['spec/citations', 'versions/0.5.0'],
)
def test_update_rewrites_a_stale_citation(tmp_path: Path) -> None:
    with given(
        t'a {pg["Report"].l} where the tag `checkout` has a passed and an '
        t'xfailed {pg["Scenario"].l}'
    ):
        report = report_(
            scenario_('t.py::test_a', 'Pay', tags=('checkout',)),
            scenario_('t.py::test_b', 'Refund', status='xfailed', tags=('checkout',)),
        )
    with given('a document citing the tag under another name, as all passed'):
        document = f'✅ [Checkout]({URL}#tag=checkout) (1 ✅)\n'
        attach('document', document)
    with when('the document is updated'):
        result, written = _run(tmp_path, document, report, update=True)
    with then('its glyph, text and summary read what the report says'):
        attach('updated document', written)
        assert written == f'🔵 [checkout]({URL}#tag=checkout) (1 ✅ · 1 🔵)\n'
    with then('no finding remains'):
        assert result.remaining == []


@scenario(
    t'A plain {pg["Report link"].l} claims only that its target exists',
    tags=['spec/citations', 'versions/0.5.0'],
)
def test_a_plain_report_link_claims_only_that_its_target_exists(tmp_path: Path) -> None:
    with given(t'a {pg["Report"].l} whose one {pg["Scenario"].l} fails'):
        report = report_(scenario_('t.py::test_pay', 'Pay by card', status='failed'))
    with given('a document linking it, and a deleted test, in its own words'):
        document = (
            f'See [how paying works]({URL}#scenario=t.py::test_pay) and '
            f'[refunds]({URL}#scenario=t.py::test_refund).\n'
        )
        attach('document', document)
    with when('the document is updated'):
        result, written = _run(tmp_path, document, report, update=True)
    with then('only the link to the deleted test is a finding'):
        assert [(finding.kind, finding.line) for finding in result.findings] == [
            ('missing', 1)
        ]
    with then('the document is left as written'):
        assert written == document


@scenario(
    t'A {pg["Citation"].l} whose target left the {pg["Report"].l} is marked ❓ '
    t'and recovers once it is back',
    tags=['spec/citations', 'versions/0.5.0'],
)
def test_a_citation_to_a_gone_target_is_marked_and_recovers(tmp_path: Path) -> None:
    with given(t'a {pg["Citation"].l} of a passing {pg["Scenario"].l}'):
        document = f'✅ [Pay by card]({URL}#scenario=t.py::test_pay)\n'
        attach('document', document)
    with when(t'it is updated against a {pg["Report"].l} that lacks the scenario'):
        result, marked = _run(
            tmp_path, document, report_(scenario_('t.py::test_x', 'Other')), update=True
        )
    with then('it is marked ❓, keeping its target and text'):
        attach('marked document', marked)
        assert marked == f'❓ [Pay by card]({URL}#scenario=t.py::test_pay)\n'
    with then('it stays a finding'):
        assert [finding.kind for finding in result.remaining] == ['missing']
    with when(t'it is updated once the {pg["Report"].l} holds the scenario again'):
        _, recovered = _run(tmp_path, marked, report_(PAY), update=True)
    with then('it reads as current again'):
        assert recovered == document


@scenario(
    t'A {pg["Citation"].l} of any {pg["Case"].l} cites the grouped '
    t'{pg["Scenario"].l} holding it',
    tags=['spec/citations', 'versions/0.5.0'],
)
def test_a_citation_of_any_case_cites_its_grouped_scenario(tmp_path: Path) -> None:
    with given(
        t'a {pg["Report"].l} where the {pg["Case"].l.s} `[a]` and `[c]` of '
        t'`test_pour` group into one {pg["Scenario"].l}'
    ):
        report = report_(
            scenario_(
                't.py::test_pour[a]',
                'Pour',
                grouped=True,
                other_cases=('t.py::test_pour[c]',),
            )
        )
    with given(t'a document citing the {pg["Case"].l} `[c]`'):
        document = f'✅ [Pour]({URL}#scenario=t.py::test_pour%5Bc%5D)\n'
        attach('document', document)
    with when('the document is updated'):
        result, written = _run(tmp_path, document, report, update=True)
    with then(
        t'the {pg["Citation"].l} names its {pg["Scenario"].l} by the node ID of '
        t'`test_pour`'
    ):
        attach('updated document', written)
        assert written == f'✅ [Pour]({URL}#scenario=t.py::test_pour)\n'
    with then('no finding remains'):
        assert result.remaining == []


@scenario(
    t'A {pg["Citation"].l} keeps the emphasis its {pg["Scenario title"].l} '
    t'renders with',
    tags=['spec/citations', 'versions/0.5.0'],
)
def test_a_citation_keeps_the_emphasis_of_its_title(tmp_path: Path) -> None:
    with given(
        t'a {pg["Report"].l} whose {pg["Scenario title"].l} sets a word in bold'
    ):
        report = report_(scenario_('t.py::test_book', 'Books a **suite**'))
    with given(t'a document with a placeholder {pg["Citation"].l} of it'):
        document = f'? []({URL}#scenario=t.py::test_book)\n'
        attach('document', document)
    with when('the document is updated'):
        _, written = _run(tmp_path, document, report, update=True)
    with then('its link text sets the word in bold too'):
        attach('updated document', written)
        assert written == f'✅ [Books a **suite**]({URL}#scenario=t.py::test_book)\n'


# --- One test per row of the findings table ---


def test_a_renamed_test_is_repointed_by_its_unchanged_title(tmp_path: Path) -> None:
    report = report_(scenario_('t.py::test_pay_by_card', 'Pay by card'))
    document = f'✅ [Pay by card]({URL}#scenario=t.py::test_pay)\n'
    checked, _ = _run(tmp_path, document, report)
    assert [(f.kind, f.fixed_by_update) for f in checked.findings] == [
        ('repointed', True)
    ]
    result, written = _run(tmp_path, document, report, update=True)
    assert written == f'✅ [Pay by card]({URL}#scenario=t.py::test_pay_by_card)\n'
    assert result.remaining == []


def test_a_gone_tag_citation_is_marked_and_loses_its_summary(tmp_path: Path) -> None:
    result, written = _run(
        tmp_path, f'✅ [gone]({URL}#tag=gone) (2 ✅)\n', report_(PAY), update=True
    )
    assert written == f'❓ [gone]({URL}#tag=gone)\n'
    assert [f.kind for f in result.remaining] == ['missing']


def test_a_plain_link_to_a_gone_target_is_a_finding_left_alone(tmp_path: Path) -> None:
    document = f'[see]({URL}#view=stories&story=gone)\n'
    result, written = _run(tmp_path, document, report_(PAY), update=True)
    assert [f.kind for f in result.remaining] == ['missing']
    assert written == document


def test_stale_glyph_text_and_summary_and_a_missing_summary_are_rewritten(
    tmp_path: Path,
) -> None:
    report = report_(
        scenario_('t.py::test_pay', 'Pay by card', status='xfailed', tags=('x',))
    )
    document = (
        f'- ✅ [Pay with card]({URL}#scenario=t.py::test_pay)\n'
        f'- ✅ [x]({URL}#tag=x) (1 ✅)\n'
        f'- 🔵 [x]({URL}#tag=x)\n'
    )
    checked, _ = _run(tmp_path, document, report)
    assert {f.kind for f in checked.findings} == {'stale'}
    assert all(f.fixed_by_update for f in checked.findings)
    _, written = _run(tmp_path, document, report, update=True)
    assert written == (
        f'- 🔵 [Pay by card]({URL}#scenario=t.py::test_pay)\n'
        f'- 🔵 [x]({URL}#tag=x) (1 🔵)\n'
        f'- 🔵 [x]({URL}#tag=x) (1 🔵)\n'
    )


def _crossed_span() -> Scenario:
    scenario = scenario_('t.py::test_book')
    scenario.narration = narration_of(
        [
            NarrationLiteral(value='**'),
            NarrationTermRef(term_id=TermId('guest'), display='Guest'),
            NarrationLiteral(value=' books** a *suite*'),
        ]
    )
    return scenario


@pytest.mark.parametrize(
    ('report', 'fragment', 'text'),
    [
        (
            report_(scenario_('t.py::test_book', 'Books a **suite**')),
            'scenario=t.py::test_book',
            'Books a **suite**',
        ),
        (
            report_(_crossed_span()),
            'scenario=t.py::test_book',
            '\\*\\*Guest books\\*\\* a *suite*',
        ),
        (
            report_(scenario_('t.py::test_a', tags=('a*b*',))),
            'tag=a*b*',
            'a\\*b\\*',
        ),
        (
            report_(
                scenario_('t.py::test_a', stories=('s',)),
                stories=(story_('s', 'Book a *suite*'),),
            ),
            'view=stories&story=s',
            'Book a \\*suite\\*',
        ),
    ],
)
def test_written_link_text_reads_back_as_current(
    tmp_path: Path, report: ReportData, fragment: str, text: str
) -> None:
    _, written = _run(tmp_path, f'? []({URL}#{fragment})\n', report, update=True)
    assert f'[{text}]({URL}#{fragment})' in written
    rechecked, _ = _run(tmp_path, written, report)
    assert rechecked.findings == []


@pytest.mark.parametrize(
    'document',
    [
        f'Done: ✅ [x]({URL}#tag=x)\n(1 ✅) and more.\n',
        f'> Done: ✅ [x]({URL}#tag=x)\n> (1 ✅) and more.\n',
        f'- Done: ✅ [x]({URL}#tag=x)\r\n  (1 ✅)\r\n',
    ],
)
def test_a_summary_wrapped_onto_the_next_line_is_current(
    tmp_path: Path, document: str
) -> None:
    report = report_(scenario_('t.py::test_a', 'A', tags=('x',)))
    result, written = _run(tmp_path, document, report, update=True)
    assert (result.findings, written) == ([], document)


@pytest.mark.parametrize(
    ('document', 'expected'),
    [
        (
            f'Done: ✅ [x]({URL}#tag=x)\n(3 ❌) and more.\n',
            f'Done: 🔵 [x]({URL}#tag=x)\n(1 🔵) and more.\n',
        ),
        (
            f'> Done: ✅ [x]({URL}#tag=x)\r\n> (3 ❌)\r\n',
            f'> Done: 🔵 [x]({URL}#tag=x)\r\n> (1 🔵)\r\n',
        ),
    ],
)
def test_a_stale_wrapped_summary_is_rewritten_in_place(
    tmp_path: Path, document: str, expected: str
) -> None:
    report = report_(scenario_('t.py::test_a', 'A', status='xfailed', tags=('x',)))
    result, written = _run(tmp_path, document, report, update=True)
    assert written == expected
    assert [f.message for f in result.findings] == ['stale glyph', 'stale summary']


@pytest.mark.parametrize(
    ('document', 'expected'),
    [
        (
            f'Done: ✅ [x]({URL}#tag=x)\n(1 ✅) and more.\n',
            f'Done: ❓ [x]({URL}#tag=x) and more.\n',
        ),
        (
            f'> Done: ✅ [x]({URL}#tag=x)\r\n> (1 ✅)\r\n> Next.\r\n',
            f'> Done: ❓ [x]({URL}#tag=x)\r\n> Next.\r\n',
        ),
    ],
)
def test_a_gone_target_loses_its_wrapped_summary(
    tmp_path: Path, document: str, expected: str
) -> None:
    _, written = _run(tmp_path, document, report_(PAY), update=True)
    assert written == expected


def test_a_slug_or_case_suffix_in_any_report_link_becomes_the_node_id(
    tmp_path: Path,
) -> None:
    report = report_(
        scenario_('pkg/test_pour.py::test_pour[water]', 'Pour {liquid}', grouped=True),
        scenario_('pkg/test_shop.py::test_buy', 'Buy'),
    )
    document = (
        f'[buying]({URL}#scenario=shop/buy) and '
        f'✅ [Pour {{liquid}}]({URL}#scenario=pkg/test_pour.py::test_pour%5Bfire%5D)\n'
    )
    result, written = _run(tmp_path, document, report, update=True)
    assert written == (
        f'[buying]({URL}#scenario=pkg/test_shop.py::test_buy) and '
        f'✅ [Pour {{liquid}}]({URL}#scenario=pkg/test_pour.py::test_pour)\n'
    )
    assert result.remaining == []


def test_a_cited_failure_stays_a_finding_with_its_glyph_written(tmp_path: Path) -> None:
    report = report_(scenario_('t.py::test_pay', 'Pay by card', status='failed'))
    result, written = _run(
        tmp_path,
        f'✅ [Pay by card]({URL}#scenario=t.py::test_pay)\n',
        report,
        update=True,
    )
    assert written == f'❌ [Pay by card]({URL}#scenario=t.py::test_pay)\n'
    assert [f.kind for f in result.remaining] == ['failed']


def test_a_glyph_led_link_with_another_fragment_is_a_mistyped_citation(
    tmp_path: Path,
) -> None:
    result, _ = _run(
        tmp_path, f'✅ [search]({URL}#q=pay)\n[search]({URL}#q=pay)\n', report_(PAY)
    )
    assert [(f.kind, f.line) for f in result.findings] == [('mistyped', 1)]


def test_a_summary_after_several_spaces_is_rewritten_in_place(
    tmp_path: Path,
) -> None:
    report = report_(scenario_('t.py::test_a', 'A', tags=('checkout',)))
    document = f'✅ [checkout]({URL}#tag=checkout)  (3 ✅)\n'
    _, written = _run(tmp_path, document, report, update=True)
    assert written == f'✅ [checkout]({URL}#tag=checkout)  (1 ✅)\n'


@pytest.mark.parametrize('url', ['http://[oops/r.html#scenario=a', 'r%00.html#tag=a'])
def test_a_link_no_url_parser_reads_is_no_report_link(tmp_path: Path, url: str) -> None:
    result, _ = _run(
        tmp_path,
        f'✅ [x]({url})\n{CURRENT}',
        report_(PAY),
        report_path=tmp_path / 'r.html',
    )
    assert [link.line for link in result.links] == [2]
    assert result.findings == []


def test_a_link_is_read_as_rendered_escapes_and_entity_references_resolved(
    tmp_path: Path,
) -> None:
    report = report_(scenario_('t.py::test_a', 'A', tags=('spec_x',)))
    document = (
        f'✅ [spec_x]({URL}#tag=spec\\_x) (1 ✅)\n'
        f'[see]({URL}#view=stories&amp;story=gone)\n'
    )
    result, _ = _run(tmp_path, document, report)
    assert [(f.kind, f.line) for f in result.findings] == [('missing', 2)]


def test_a_fragment_after_an_entity_reference_hash_is_repointed(
    tmp_path: Path,
) -> None:
    document = f'✅ [Pay by card]({URL}&#35;scenario=t.py::test_pay[1])\n'
    _, written = _run(tmp_path, document, report_(PAY), update=True)
    assert written == f'✅ [Pay by card]({URL}&#35;scenario=t.py::test_pay)\n'


def test_a_summary_after_a_scenario_citation_is_left_to_the_author(
    tmp_path: Path,
) -> None:
    document = f'✅ [Pay by card]({URL}#scenario=t.py::test_pay) (2 ✅)\n'
    result, written = _run(tmp_path, document, report_(PAY), update=True)
    assert [f.kind for f in result.remaining] == ['stray-summary']
    assert written == document


# --- Repointing, placeholders, suggestions ---


def test_the_placeholder_is_filled(tmp_path: Path) -> None:
    _, written = _run(
        tmp_path, f'? [](<{URL}#scenario=t.py::test_pay>)\n', report_(PAY), update=True
    )
    assert written == f'✅ [Pay by card](<{URL}#scenario=t.py::test_pay>)\n'


@pytest.mark.parametrize('glyph', ['✓', '✗', '○', '⊗', '?', '❓'])
def test_a_text_glyph_or_placeholder_is_rewritten_as_emoji(
    tmp_path: Path, glyph: str
) -> None:
    _, written = _run(
        tmp_path,
        f'{glyph} [Pay by card]({URL}#scenario=t.py::test_pay)\n',
        report_(PAY),
        update=True,
    )
    assert written.startswith('✅ [Pay by card]')


def test_a_variation_selector_glyph_and_summary_are_current(tmp_path: Path) -> None:
    report = report_(scenario_('t.py::test_pay', 'Pay by card', tags=('x',)))
    document = (
        f'✅\ufe0f [Pay by card]({URL}#scenario=t.py::test_pay)\n'
        f'✅\ufe0f [x]({URL}#tag=x) (1 ✅\ufe0f)\n'
    )
    result, _ = _run(tmp_path, document, report)
    assert result.findings == []


@pytest.mark.parametrize(
    'scenarios',
    [
        (
            scenario_('t.py::test_a', 'Pay by card'),
            scenario_('t.py::test_b', 'Pay by card'),
        ),
        (scenario_('t.py::test_a', 'Pay by cards'),),
    ],
)
def test_repointing_needs_one_exact_title(
    tmp_path: Path, scenarios: tuple[Scenario, ...]
) -> None:
    result, written = _run(
        tmp_path,
        f'✅ [Pay by card]({URL}#scenario=t.py::test_gone)\n',
        report_(*scenarios),
        update=True,
    )
    assert written.startswith('❓ ')
    assert [f.kind for f in result.remaining] == ['missing']


def test_a_missing_target_lists_the_closest_candidates(tmp_path: Path) -> None:
    report = report_(scenario_('t.py::test_pay_by_card', 'Paying by card'))
    result, _ = _run(
        tmp_path, f'✅ [Pay by card]({URL}#scenario=t.py::test_pay_card)\n', report
    )
    (finding,) = result.findings
    assert finding.details[0].startswith('closest by node ID: t.py::test_pay_by_card')
    assert finding.lines()[0] == (
        f'{(tmp_path / "doc.md").as_posix()}:1: {finding.message}'
    )
    assert finding.lines()[1] == f'    {finding.details[0]}'


def test_an_empty_tag_reads_as_one_in_its_finding(tmp_path: Path) -> None:
    result, _ = _run(tmp_path, f'[all]({URL}#tag=)\n', report_(PAY))
    assert [f.message for f in result.findings] == [
        'a tag with an empty name is not in the report'
    ]


def test_an_empty_scenario_key_reads_as_one_when_repointed(tmp_path: Path) -> None:
    result, _ = _run(tmp_path, f'✅ [Pay by card]({URL}#scenario=)\n', report_(PAY))
    assert [f.message for f in result.findings] == [
        (
            'a scenario with an empty name is not in the report; its link text '
            'is the title of t.py::test_pay'
        )
    ]


# --- Reading ---


def test_relative_links_resolve_from_the_documents_directory(tmp_path: Path) -> None:
    report = report_(PAY, report_url=None)
    document = '✓ [Pay by card](../examples/r.html#scenario=t.py::test_pay)\n'
    _, written = _run(
        tmp_path,
        document,
        report,
        update=True,
        name='guide/doc.md',
        report_path=tmp_path / 'examples' / 'r.html',
    )
    assert written.startswith('✅ ')


def test_a_query_leaves_a_link_to_the_report(tmp_path: Path) -> None:
    document = (
        '✓ [Pay by card](../examples/r.html?v=2#scenario=t.py::test_pay)\n'
        f'✓ [Pay by card]({URL}?v=2#scenario=t.py::test_pay)\n'
    )
    _, written = _run(
        tmp_path,
        document,
        report_(PAY),
        update=True,
        name='guide/doc.md',
        report_path=tmp_path / 'examples' / 'r.html',
    )
    assert [line[0] for line in written.splitlines()] == ['✅', '✅']


def test_a_site_root_link_resolves_against_the_report_url(tmp_path: Path) -> None:
    document = '✓ [Pay by card](/report.html#scenario=t.py::test_pay)\n'
    result, _ = _run(tmp_path, document, report_(PAY))
    assert [f.kind for f in result.findings] == ['stale']
    result, _ = _run(
        tmp_path,
        f'{document}✅ [Pay by card](report.html#scenario=t.py::test_pay)\n',
        report_(PAY, report_url=None),
        report_path=tmp_path / 'report.html',
    )
    assert [link.line for link in result.links] == [2]
    assert result.findings == []


def test_without_a_report_path_relative_links_are_ordinary(tmp_path: Path) -> None:
    document = f'✓ [Pay by card](examples/r.html#scenario=t.py::test_pay)\n{CURRENT}'
    result, _ = _run(tmp_path, document, report_(PAY))
    assert [link.line for link in result.links] == [2]
    assert result.findings == []


def test_links_elsewhere_are_ordinary(tmp_path: Path) -> None:
    document = (
        '✓ [other](https://other.org/r.html#scenario=t.py::test_pay)\n'
        '✓ [same page](#scenario=t.py::test_pay)\n'
        '✓ [another file](other.html#scenario=t.py::test_pay)\n'
        f'{CURRENT}'
    )
    result, _ = _run(
        tmp_path, document, report_(PAY), report_path=tmp_path / 'examples' / 'r.html'
    )
    assert [link.line for link in result.links] == [4]
    assert result.findings == []


def test_the_report_url_flag_overrides_the_stored_one(tmp_path: Path) -> None:
    other = 'https://other.org/report.html'
    document = f'✓ [Pay by card]({other}#scenario=t.py::test_pay)\n'
    result, _ = _run(tmp_path, document, report_(PAY), report_url=other)
    assert [f.kind for f in result.findings] == ['stale']


def test_documents_that_never_link_the_report_are_an_error(tmp_path: Path) -> None:
    document = '✓ [Pay by card](https://other.org/r.html#scenario=t.py::test_pay)\n'
    report_path = tmp_path / 'examples' / 'r.html'
    with pytest.raises(
        PytestGivenError,
        match=re.escape(
            f'No document links to the report at {URL} or {report_path.as_posix()}'
        ),
    ):
        _run(tmp_path, document, report_(PAY), update=True, report_path=report_path)
    assert (tmp_path / 'doc.md').read_text(encoding='utf-8') == document


def test_neither_report_url_nor_report_path_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(PytestGivenError, match='report URL'):
        _run(tmp_path, 'text\n', report_(PAY, report_url=None))


def test_citations_in_a_table_cell_across_a_line_break_and_in_a_quote(
    tmp_path: Path,
) -> None:
    report = report_(scenario_('t.py::test_pay', 'Pay `a|b` by card'))
    document = (
        '| Kind | Citation |\n|---|---|\n'
        f'| scenario | ✓ [old]({URL}#scenario=t.py::test_pay) |\n'
        '\nDone ✓\n'
        f'[old]({URL}#scenario=t.py::test_pay)\n'
        f'\n> ✅ [Pay `a|b`\n> by card]({URL}#scenario=t.py::test_pay)\n'
    )
    result, written = _run(tmp_path, document, report, update=True)
    assert written == (
        '| Kind | Citation |\n|---|---|\n'
        f'| scenario | ✅ [Pay `a\\|b` by card]({URL}#scenario=t.py::test_pay) |\n'
        '\nDone ✅\n'
        f'[Pay `a|b` by card]({URL}#scenario=t.py::test_pay)\n'
        f'\n> ✅ [Pay `a|b`\n> by card]({URL}#scenario=t.py::test_pay)\n'
    )
    assert result.remaining == []


def test_a_formatted_glyph_or_sentence_question_mark_makes_a_plain_link(
    tmp_path: Path,
) -> None:
    document = (
        f'**✅** [old]({URL}#scenario=t.py::test_pay)\n'
        f'Is it done? [old]({URL}#scenario=t.py::test_pay)\n'
    )
    result, written = _run(tmp_path, document, report_(PAY), update=True)
    assert result.findings == []
    assert written == document


def test_an_authors_parenthetical_is_not_a_summary(tmp_path: Path) -> None:
    report = report_(scenario_('t.py::test_a', 'A', tags=('x',)))
    _, written = _run(
        tmp_path, f'✅ [x]({URL}#tag=x) (see below)\n', report, update=True
    )
    assert written == f'✅ [x]({URL}#tag=x) (1 ✅) (see below)\n'


def test_code_is_never_read(tmp_path: Path) -> None:
    document = (
        f'```\n✓ [old]({URL}#scenario=t.py::test_gone)\n```\n'
        f'`✓ [old]({URL}#tag=gone)`\n'
        f'{CURRENT}'
    )
    result, _ = _run(tmp_path, document, report_(PAY))
    assert [link.line for link in result.links] == [5]
    assert result.findings == []


# --- Writes ---


def test_update_is_idempotent_and_leaves_an_unchanged_file_alone(
    tmp_path: Path,
) -> None:
    document = f'✓ [old]({URL}#scenario=t.py::test_pay)\n'
    first, written = _run(tmp_path, document, report_(PAY), update=True)
    path = tmp_path / 'doc.md'
    assert first.updated == [path]
    stamp = path.stat().st_mtime_ns
    second = check_citations(
        report_(PAY), [path], report_url=None, report_path=None, update=True
    )
    assert (second.findings, second.updated) == ([], [])
    assert path.stat().st_mtime_ns == stamp
    assert path.read_bytes().decode('utf-8') == written


def test_check_writes_nothing(tmp_path: Path) -> None:
    document = f'✓ [old]({URL}#scenario=t.py::test_pay)\n'
    result, written = _run(tmp_path, document, report_(PAY))
    assert written == document
    assert result.updated == []


def test_crlf_line_endings_survive_an_update(tmp_path: Path) -> None:
    document = f'Intro\r\n\r\n✓ [old]({URL}#scenario=t.py::test_pay)\r\nOutro\r\n'
    _, written = _run(tmp_path, document, report_(PAY), update=True)
    assert written == (
        f'Intro\r\n\r\n✅ [Pay by card]({URL}#scenario=t.py::test_pay)\r\nOutro\r\n'
    )


def test_several_edits_on_one_line_apply_together(tmp_path: Path) -> None:
    report = report_(
        scenario_('t.py::test_pay', 'Pay by card', tags=('x',)),
        scenario_('pkg/test_shop.py::test_buy', 'Buy'),
    )
    document = (
        f'✓ [a]({URL}#scenario=shop/buy) · ? [b]({URL}#tag=x) (9 ❌) · '
        f'✗ [c]({URL}#scenario=t.py::test_pay)\n'
    )
    _, written = _run(tmp_path, document, report, update=True)
    assert written == (
        f'✅ [Buy]({URL}#scenario=pkg/test_shop.py::test_buy) · '
        f'✅ [x]({URL}#tag=x) (1 ✅) · '
        f'✅ [Pay by card]({URL}#scenario=t.py::test_pay)\n'
    )


def test_an_unusual_node_id_is_cited_end_to_end(tmp_path: Path) -> None:
    report = report_(scenario_('t.py::test_y[a b+c&d#e]', 'Odd'))
    _, written = _run(
        tmp_path,
        f'? []({URL}#scenario=t.py::test_y%5Ba%20b%2Bc%26d%23e%5D)\n',
        report,
        update=True,
    )
    assert written.startswith('✅ [Odd](')


def test_markdown_documents_searches_directories_for_md(tmp_path: Path) -> None:
    (tmp_path / 'a' / 'b').mkdir(parents=True)
    for name in ('a/one.md', 'a/b/two.md', 'a/notes.txt'):
        (tmp_path / name).write_text('x', encoding='utf-8')
    single = tmp_path / 'README.markdown'
    single.write_text('x', encoding='utf-8')
    assert markdown_documents([tmp_path / 'a', single]) == [
        tmp_path / 'a' / 'b' / 'two.md',
        tmp_path / 'a' / 'one.md',
        single,
    ]


def test_markdown_documents_names_each_file_once_and_no_directory(
    tmp_path: Path,
) -> None:
    (tmp_path / 'a' / 'notes.md').mkdir(parents=True)
    one = tmp_path / 'a' / 'one.md'
    one.write_text('x', encoding='utf-8')
    assert markdown_documents([tmp_path / 'a', one, tmp_path / 'a' / '..' / 'a']) == [
        one
    ]


def test_a_missing_document_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / 'nowhere.md'
    with pytest.raises(PytestGivenError, match=re.escape(f'{path.as_posix()} is')):
        markdown_documents([path])


def test_a_document_that_is_not_utf8_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / 'bad.md'
    path.write_bytes(b'\xff\xfe broken')
    with pytest.raises(PytestGivenError, match=re.escape(f'{path.as_posix()}:')):
        check_citations(
            report_(PAY), [path], report_url=None, report_path=None, update=False
        )


# --- Listing ---


_COVERING_REPORT = report_(
    scenario_('t.py::test_pay', 'Pay by card', tags=('checkout/card',), stories=('s',)),
    scenario_('t.py::test_refund', 'Refund', tags=('checkout/refund',)),
    stories=(story_('s'),),
)


@scenario(
    t'`--covering` keeps each {pg["Report link"].l} whose target counts the '
    t'{pg["Scenario"].l}, and each it cannot rule out',
    tags=['spec/citations-list', 'versions/0.5.0'],
)
@pytest.mark.parametrize(
    ('link', 'kept'),
    [
        (f'✅ [Pay by card]({URL}#scenario=t.py::test_pay)', True),
        (f'[paying]({URL}#scenario=t.py::test_pay)', True),
        (f'✅ [Refund]({URL}#scenario=t.py::test_refund)', False),
        (f'✅ [checkout/card]({URL}#tag=checkout/card) (1 ✅)', True),
        (f'✅ [checkout]({URL}#tag=checkout) (2 ✅)', True),
        (f'✅ [checkout/refund]({URL}#tag=checkout/refund) (1 ✅)', False),
        (f'✅ [s]({URL}#view=stories&story=s) (1 ✅)', True),
        (f'✅ [Gone]({URL}#scenario=t.py::test_gone)', True),
        (f'✅ [search]({URL}#q=pay)', True),
    ],
)
def test_covering_keeps_the_links_that_may_cite_the_scenario(
    tmp_path: Path, link: str, kept: bool
) -> None:
    with given(
        t'a {pg["Report"].l} where `test_pay` is tagged `checkout/card` and in a '
        t'{pg["Story"].l}, `test_refund` tagged `checkout/refund`'
    ):
        report = _COVERING_REPORT
    with given(t'a document holding the {pg["Report link"].l} {link}'):
        document = f'{link}\n'
    with when('its links are checked, covering `test_pay`'):
        result, _ = _run(tmp_path, document, report, covering=['t.py::test_pay'])
    with then(t'the {pg["Report link"].l} is kept: {kept}'):
        assert [checked in result.listed for checked in result.links] == [kept]


def test_every_report_link_is_listed_in_document_order(tmp_path: Path) -> None:
    document = (
        f'✅ [Pay by card]({URL}#scenario=t.py::test_pay)\n'
        f'[see]({URL}#view=stories&story=gone) and [elsewhere](https://other.org/r)\n'
        f'[the glossary]({URL}#view=glossary&term=guest)\n'
        f'? [x]({URL}#tag=x)\n'
        f'✅ [search]({URL}#q=pay)\n'
    )
    result, _ = _run(tmp_path, document, report_(PAY))
    assert [listed.lines()[0] for listed in result.listed] == [
        f'{(tmp_path / "doc.md").as_posix()}:{line}: {head}'
        for line, head in [
            (1, '✅ scenario t.py::test_pay'),
            (2, 'link story gone'),
            (4, '? tag x'),
            (5, '✅ #q=pay'),
        ]
    ]
    assert result.listed == result.links


def test_a_listed_link_names_its_target_as_the_document_writes_it(
    tmp_path: Path,
) -> None:
    report = report_(scenario_('pkg/test_shop.py::test_buy', 'Buy'))
    result, _ = _run(tmp_path, f'✅\ufe0f [Buy]({URL}#scenario=shop/buy)\n', report)
    (listed,) = result.links
    assert listed.lines() == [
        f'{(tmp_path / "doc.md").as_posix()}:1: ✅\ufe0f scenario shop/buy',
        (
            "    scenario fragment names 'shop/buy', which a report link names as "
            "'pkg/test_shop.py::test_buy'"
        ),
        '        #scenario=shop/buy → #scenario=pkg/test_shop.py::test_buy',
    ]


def test_each_finding_sits_on_its_own_link_two_on_one_row_included(
    tmp_path: Path,
) -> None:
    document = (
        '| a | b |\n|---|---|\n'
        f'| ✓ [Pay by card]({URL}#scenario=t.py::test_pay) '
        f'| ✅ [Gone]({URL}#scenario=t.py::test_gone) |\n'
    )
    result, _ = _run(tmp_path, document, report_(PAY))
    assert [
        [finding.message for finding in listed.findings] for listed in result.links
    ] == [['stale glyph'], ['scenario t.py::test_gone is not in the report']]
    assert result.findings == [
        finding for listed in result.links for finding in listed.findings
    ]


@pytest.mark.parametrize(
    'covering', ['t.py::test_pour[b]', 't.py::test_pour', 't/pour']
)
def test_a_case_node_id_or_a_slug_names_its_grouped_scenario(
    tmp_path: Path, covering: str
) -> None:
    report = report_(
        scenario_(
            't.py::test_pour[a]',
            'Pour',
            grouped=True,
            other_cases=('t.py::test_pour[b]',),
        ),
        PAY,
    )
    document = (
        f'✅ [Pour]({URL}#scenario=t.py::test_pour)\n'
        f'✅ [Pay by card]({URL}#scenario=t.py::test_pay)\n'
    )
    result, _ = _run(tmp_path, document, report, covering=[covering])
    assert [listed.named for listed in result.listed] == ['scenario t.py::test_pour']


def test_several_covered_scenarios_keep_the_union_and_count_what_they_leave_out(
    tmp_path: Path,
) -> None:
    report = report_(
        PAY, scenario_('t.py::test_refund', 'Refund'), scenario_('t.py::test_x', 'X')
    )
    document = (
        f'[a]({URL}#scenario=t.py::test_pay)\n'
        f'[b]({URL}#scenario=t.py::test_refund)\n'
        f'✓ [X]({URL}#scenario=t.py::test_x)\n'
    )
    result, _ = _run(
        tmp_path, document, report, covering=['t.py::test_pay', 't.py::test_refund']
    )
    assert [listed.line for listed in result.listed] == [1, 2]
    assert result.left_out == 1


def test_covering_a_scenario_the_report_lacks_is_an_error(tmp_path: Path) -> None:
    report = report_(scenario_('t.py::test_pay_by_card', 'Pay by card'))
    with pytest.raises(
        PytestGivenError,
        match=re.escape(
            'scenario t.py::test_pay_card is not in the report; '
            'closest by node ID: t.py::test_pay_by_card'
        ),
    ):
        _run(tmp_path, '', report, covering=['t.py::test_pay_card'])


def test_a_test_functions_node_id_covers_each_of_its_per_case_scenarios(
    tmp_path: Path,
) -> None:
    report = report_(
        scenario_('t.py::test_pour[a]', 'Pour [a]'),
        scenario_('t.py::test_pour[b]', 'Pour [b]'),
        PAY,
    )
    document = (
        f'[a]({URL}#scenario=t.py::test_pour%5Ba%5D)\n'
        f'[b]({URL}#scenario=t.py::test_pour%5Bb%5D)\n'
        f'[pay]({URL}#scenario=t.py::test_pay)\n'
    )
    result, _ = _run(tmp_path, document, report, covering=['t.py::test_pour'])
    assert [listed.line for listed in result.listed] == [1, 2]


# --- Narrated citations ---


NARRATION = '- **given** a card\n- **then** it is paid'


def _narrated_scenario(
    node_id: str = 't.py::test_pay',
    title: str = 'Pay by card',
    *,
    status: Status = 'passed',
    tags: tuple[str, ...] = (),
) -> Scenario:
    narrated = scenario_(node_id, title, status=status, tags=tags)
    narrated.steps = [
        Step(phase='given', narration=Narration(text='a card')),
        Step(phase='then', narration=Narration(text='it is paid')),
    ]
    return narrated


PAID = _narrated_scenario()


def _block(
    body: str = '\n',
    *,
    glyph: str = '✅',
    text: str = 'Pay by card',
    fragment: str = 'scenario=t.py::test_pay',
    url: str = URL,
    opening: str = '<details markdown="1">',
) -> str:
    """A narrated citation; `body` is the source between its summary line and
    its closing tag, a freshly copied block's blank line by default."""
    return (
        f'{opening}\n<summary>{glyph} <a href="{url}#{fragment}">{text}</a>'
        f'</summary>\n{body}</details>\n'
    )


FILLED = f'\n{NARRATION}\n\n'


@scenario(
    t"`citations update` writes a {pg['Narrated citation'].l}'s body from the "
    t'{pg["Report"].l}',
    tags=['spec/narrated-citations', 'versions/0.5.0'],
)
def test_update_writes_a_narrated_citations_body(tmp_path: Path) -> None:
    with given(t'a {pg["Report"].l} whose {pg["Scenario"].l} has two steps'):
        report = report_(PAID)
    with given(
        t'a document holding a {pg["Narrated citation"].l} of it, copied with an '
        t'empty body'
    ):
        document = f'Paying:\n\n{_block()}'
        attach('document', document)
    with when('the document is updated'):
        result, written = _run(tmp_path, document, report, update=True)
    with then("its body holds the scenario's narration between blank lines"):
        attach('updated document', written)
        assert written == f'Paying:\n\n{_block(FILLED)}'
    with then('no finding remains'):
        assert result.remaining == []


@scenario(
    t'`citations check` reports a {pg["Narrated citation"].l} whose body differs '
    t'from the {pg["Report"].l}',
    tags=['spec/narrated-citations', 'versions/0.5.0'],
)
def test_check_reports_a_stale_narrated_body(tmp_path: Path) -> None:
    with given(t'a {pg["Report"].l} whose {pg["Scenario"].l} ends in "it is paid"'):
        report = report_(PAID)
    with given(
        t'a document whose {pg["Narrated citation"].l} of it still ends in "it is '
        t'charged"'
    ):
        document = _block('\n- **given** a card\n- **then** it is charged\n\n')
        attach('document', document)
    with when('the document is checked'):
        result, _ = _run(tmp_path, document, report)
    with then(t'one stale narration is the only {pg["Citation finding"].l}'):
        assert [(f.kind, f.message) for f in result.findings] == [
            ('stale', 'stale narration')
        ]
    with then('it names the first line that differs, written and expected'):
        assert result.findings[0].details == (
            'written: - **then** it is charged',
            'expected: - **then** it is paid',
        )


@scenario(
    t'A {pg["Narrated citation"].l} of a tag or story is a {pg["Citation finding"].l} '
    t'`update` leaves',
    tags=['spec/narrated-citations', 'versions/0.5.0'],
)
def test_a_narrated_tag_citation_is_a_finding_update_leaves(tmp_path: Path) -> None:
    with given(t'a {pg["Report"].l} with the tag `checkout`'):
        report = report_(_narrated_scenario(tags=('checkout',)))
    with given(
        t'a document with a {pg["Narrated citation"].l} of the tag, its glyph and '
        t'body stale'
    ):
        document = _block(
            '\nThe checkout.\n\n', glyph='❌', text='checkout', fragment='tag=checkout'
        )
        attach('document', document)
    with when('the document is updated'):
        result, written = _run(tmp_path, document, report, update=True)
    with then(
        t'a stray narration is the only {pg["Citation finding"].l}, '
        t'one `update` cannot fix'
    ):
        assert [(f.kind, f.fixed_by_update) for f in result.findings] == [
            ('stray-narration', False)
        ]
    with then('the document is left as written'):
        assert written == document


def test_a_current_narrated_citation_is_silent(tmp_path: Path) -> None:
    document = f'Intro\n\n{_block(FILLED)}\nOutro\n'
    result, written = _run(tmp_path, document, report_(PAID), update=True)
    assert (result.findings, result.updated, written) == ([], [], document)


def test_a_narrated_citations_stale_glyph_and_link_text_are_rewritten(
    tmp_path: Path,
) -> None:
    document = _block(FILLED, glyph='❌', text='Pay with <em>card</em>')
    checked, _ = _run(tmp_path, document, report_(PAID))
    assert [(f.message, f.details) for f in checked.findings] == [
        ('stale glyph', ('❌ → ✅',)),
        ('stale link text', ('Pay with card → Pay by card',)),
    ]
    result, written = _run(tmp_path, document, report_(PAID), update=True)
    assert written == _block(FILLED)
    assert result.remaining == []


def test_a_narrated_citation_of_a_gone_scenario_keeps_its_body(tmp_path: Path) -> None:
    document = _block(FILLED)
    result, written = _run(
        tmp_path, document, report_(scenario_('t.py::test_x', 'Other')), update=True
    )
    assert written == _block(FILLED, glyph='❓')
    assert [f.kind for f in result.remaining] == ['missing']


def test_a_failed_narrated_citation_has_its_body_rewritten_and_stays_a_finding(
    tmp_path: Path,
) -> None:
    report = report_(_narrated_scenario(status='failed'))
    result, written = _run(tmp_path, _block(), report, update=True)
    assert written == _block(FILLED, glyph='❌')
    assert [f.kind for f in result.remaining] == ['failed']


def test_a_renamed_test_is_repointed_by_its_shown_title_with_a_code_span(
    tmp_path: Path,
) -> None:
    report = report_(_narrated_scenario('t.py::test_pay_by_card', 'Pay `by` card'))
    document = _block(text='Pay <code>by</code> card')
    checked, _ = _run(tmp_path, document, report)
    assert [f.kind for f in checked.findings] == ['repointed', 'stale']
    result, written = _run(tmp_path, document, report, update=True)
    assert written == _block(
        FILLED,
        text='Pay <code>by</code> card',
        fragment='scenario=t.py::test_pay_by_card',
    )
    assert result.remaining == []


@pytest.mark.parametrize(
    ('opening', 'expected'),
    [
        ('<details open>', '<details markdown="1" open>'),
        ('<details open markdown="0">', '<details open markdown="1">'),
        ("<details markdown='block'>", '<details markdown="1">'),
        ('<details markdown>', '<details markdown="1">'),
        (
            '<details title="see markdown here">',
            '<details markdown="1" title="see markdown here">',
        ),
    ],
)
def test_an_opening_tag_lacking_markdown_1_gains_it_keeping_other_attributes(
    tmp_path: Path, opening: str, expected: str
) -> None:
    document = _block(FILLED, opening=opening)
    checked, _ = _run(tmp_path, document, report_(PAID))
    assert [(f.message, f.details) for f in checked.findings] == [
        ('stale opening tag', (f'{opening} → {expected}',))
    ]
    _, written = _run(tmp_path, document, report_(PAID), update=True)
    assert written == _block(FILLED, opening=expected)


@pytest.mark.parametrize(
    'opening', ['<details markdown="1">', "<DETAILS open markdown='1'>"]
)
def test_an_opening_tag_with_markdown_1_is_current(
    tmp_path: Path, opening: str
) -> None:
    result, _ = _run(tmp_path, _block(FILLED, opening=opening), report_(PAID))
    assert result.findings == []


def test_a_title_with_a_code_span_and_an_ampersand_reads_back_as_current(
    tmp_path: Path,
) -> None:
    report = report_(_narrated_scenario(title='Pay `a&b` & more'))
    _, written = _run(tmp_path, _block(glyph='?', text=''), report, update=True)
    assert written == _block(FILLED, text='Pay <code>a&amp;b</code> &amp; more')
    rechecked, _ = _run(tmp_path, written, report)
    assert rechecked.findings == []
    hand_written, _ = _run(tmp_path, _block(FILLED, text='Pay a&b &amp; more'), report)
    assert hand_written.findings == []


def test_a_crlf_document_is_current_and_updated_with_crlf(tmp_path: Path) -> None:
    current = _block(FILLED).replace('\n', '\r\n')
    result, _ = _run(tmp_path, current, report_(PAID))
    assert result.findings == []
    _, written = _run(
        tmp_path, _block().replace('\n', '\r\n'), report_(PAID), update=True
    )
    assert written == current


_SUMMARY_LINE = (
    f'<summary>✅ <a href="{URL}#scenario=t.py::test_pay">Pay by card</a></summary>'
)


@pytest.mark.parametrize(
    ('copied', 'filled'),
    [
        (
            (
                f'- Paying:\n\n  <details markdown="1">\n  {_SUMMARY_LINE}\n\n'
                '  </details>\n'
            ),
            (
                f'- Paying:\n\n  <details markdown="1">\n  {_SUMMARY_LINE}\n\n'
                '  - **given** a card\n  - **then** it is paid\n\n  </details>\n'
            ),
        ),
        (
            f'> <details markdown="1">\n> {_SUMMARY_LINE}\n>\n> </details>\n',
            (
                f'> <details markdown="1">\n> {_SUMMARY_LINE}\n>\n'
                '> - **given** a card\n> - **then** it is paid\n>\n> </details>\n'
            ),
        ),
    ],
)
def test_a_body_under_a_list_item_or_blockquote_is_written_under_its_prefix(
    tmp_path: Path, copied: str, filled: str
) -> None:
    _, written = _run(tmp_path, copied, report_(PAID), update=True)
    assert written == filled
    rechecked, _ = _run(tmp_path, written, report_(PAID))
    assert rechecked.findings == []


def test_a_grouped_scenario_in_a_blockquote_is_clean_after_an_update(
    tmp_path: Path,
) -> None:
    pouring = scenario_(
        't.py::test_pour[a]', 'Pour', grouped=True, other_cases=('t.py::test_pour[b]',)
    )
    pouring.steps = [Step(phase='when', narration=Narration(text='pouring'))]
    report = report_(pouring)
    summary = f'<summary>? <a href="{URL}#scenario=t.py::test_pour">Pour</a></summary>'
    document = f'> <details markdown="1">\n> {summary}\n>\n> </details>\n'
    _, written = _run(tmp_path, document, report, update=True)
    assert written == (
        f'> <details markdown="1">\n> {summary.replace("?", "✅")}\n'
        '>\n> - **when** pouring\n>\n> | x |\n> |---|\n> | 1 |\n> | 1 |\n>\n'
        '> </details>\n'
    )
    rechecked, _ = _run(tmp_path, written, report)
    assert rechecked.findings == []


def test_a_report_link_in_a_stale_body_is_not_read(tmp_path: Path) -> None:
    document = _block(f'\n✓ [old]({URL}#scenario=t.py::test_gone)\n\n')
    checked, _ = _run(tmp_path, document, report_(PAID))
    assert [f.message for f in checked.findings] == ['stale narration']
    assert checked.findings[0].details == (
        f'written: ✓ [old]({URL}#scenario=t.py::test_gone)',
        'expected: - **given** a card',
    )
    _, written = _run(tmp_path, document, report_(PAID), update=True)
    assert written == _block(FILLED)


def test_a_narrated_citation_nested_in_a_rewritten_body_is_not_read(
    tmp_path: Path,
) -> None:
    report = report_(
        PAID, _narrated_scenario('t.py::test_refund', 'Refund', status='failed')
    )
    nested = _block(FILLED, text='Refund', fragment='scenario=t.py::test_refund')
    in_item = ''.join(
        f'  {line}' if line.strip() else line
        for line in nested.splitlines(keepends=True)
    )
    document = _block(f'\n- Refunding:\n\n{in_item}\n')
    result, written = _run(tmp_path, document, report, update=True)
    assert [f.message for f in result.findings] == ['stale narration']
    assert written == _block(FILLED)


def test_a_report_link_in_a_tag_citations_body_is_read(tmp_path: Path) -> None:
    report = report_(_narrated_scenario(tags=('checkout',)))
    document = _block(
        f'\n❌ [Pay]({URL}#scenario=t.py::test_pay)\n\n',
        text='checkout',
        fragment='tag=checkout',
    )
    result, _ = _run(tmp_path, document, report)
    assert [f.message for f in result.findings] == [
        'a tag citation takes no narration',
        'stale glyph',
        'stale link text',
    ]


@pytest.mark.parametrize(
    ('body', 'details'),
    [
        ('\n', ('written: (end of body)', 'expected: - **given** a card')),
        (
            f'\n{NARRATION}\n\nmore\n\n',
            ('written: more', 'expected: (end of body)'),
        ),
        (
            '\n- **given** a card\n\n- **then** it is paid\n\n',
            ('written: (blank line)', 'expected: - **then** it is paid'),
        ),
    ],
)
def test_a_stale_narration_names_a_blank_line_or_the_bodys_end(
    tmp_path: Path, body: str, details: tuple[str, ...]
) -> None:
    result, _ = _run(tmp_path, _block(body), report_(PAID))
    assert [f.details for f in result.findings] == [details]


def test_a_narrated_citation_holding_its_own_closing_tag_is_filled(
    tmp_path: Path,
) -> None:
    _, written = _run(tmp_path, _block(''), report_(PAID), update=True)
    assert written == _block(FILLED)


def test_an_href_with_a_character_reference_in_the_query_names_the_report(
    tmp_path: Path,
) -> None:
    report = report_(PAID, report_url=f'{URL}?v=1&w=2')
    document = _block(FILLED, glyph='❌', url=f'{URL}?v=1&amp;w=2')
    result, _ = _run(tmp_path, document, report)
    assert [f.message for f in result.findings] == ['stale glyph']


def test_a_details_block_citing_the_report_in_another_shape_is_mistyped(
    tmp_path: Path,
) -> None:
    document = (
        '<details markdown="1">\n'
        f'<summary>✅ <a class="x" href="{URL}#scenario=t.py::test_pay">Pay</a>'
        '</summary>\n\n</details>\n\n'
        '<details markdown="1">\n'
        '<summary>✅ <a class="x" href="https://other.org/r.html#scenario=a">A</a>'
        '</summary>\n\n</details>\n'
    )
    result, _ = _run(tmp_path, document, report_(PAID))
    (listed,) = result.links
    assert (listed.line, listed.named, listed.resolved) == (
        2,
        '#scenario=t.py::test_pay',
        None,
    )
    assert [f.kind for f in result.findings] == ['mistyped']
    assert result.findings[0].message == (
        'a <details> block cites the report, but its <a> takes attributes besides href'
    )


def test_a_narrated_citation_without_a_blank_line_above_it_is_mistyped(
    tmp_path: Path,
) -> None:
    document = _block(FILLED) + _block(FILLED)
    result, written = _run(tmp_path, document, report_(PAID), update=True)
    assert [(f.line, f.kind, f.message) for f in result.findings] == [
        (
            9,
            'mistyped',
            (
                'a <details> block cites the report, but a blank line must '
                'separate it from the HTML above it'
            ),
        )
    ]
    assert written == document


def test_a_narrated_citation_is_listed_and_covered_as_a_one_line_one(
    tmp_path: Path,
) -> None:
    report = report_(PAID, _narrated_scenario('t.py::test_refund', 'Refund'))
    document = (
        f'[refunds]({URL}#scenario=t.py::test_refund)\n\n{_block(FILLED)}'
        f'\n✅ [Refund]({URL}#scenario=t.py::test_refund)\n'
    )
    result, _ = _run(tmp_path, document, report)
    assert [listed.lines()[0] for listed in result.listed] == [
        f'{(tmp_path / "doc.md").as_posix()}:{line}: {head}'
        for line, head in [
            (1, 'link scenario t.py::test_refund'),
            (4, '✅ scenario t.py::test_pay'),
            (11, '✅ scenario t.py::test_refund'),
        ]
    ]
    covered, _ = _run(tmp_path, document, report, covering=['t.py::test_pay'])
    assert [listed.line for listed in covered.listed] == [4]
