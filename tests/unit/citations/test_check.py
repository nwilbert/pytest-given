"""`citations check` and `update`: the report links in Markdown documents,
held to a JSON report."""

import re
from pathlib import Path

import pytest

from pytest_given import attach, given, scenario, then, when
from pytest_given.citations import CitationsResult, check_citations, markdown_documents
from pytest_given.model import (
    PytestGivenError,
    ReportData,
    Scenario,
)
from tests.ubiquitous_language import pg
from tests.unit.citation_reports import URL, report_, scenario_


def _run(
    tmp_path: Path,
    document: str,
    report: ReportData,
    *,
    update: bool = False,
    name: str = 'doc.md',
    report_url: str | None = None,
    report_path: Path | None = None,
) -> tuple[CitationsResult, str]:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(document.encode('utf-8'))
    result = check_citations(
        report, [path], report_url=report_url, report_path=report_path, update=update
    )
    return result, path.read_bytes().decode('utf-8')


PAY = scenario_('t.py::test_pay', 'Pay by card')


# --- The self-report's scenarios ---


@scenario(
    t"`citations update` rewrites a stale {pg['Citation'].l} to its target's "
    t'glyph, text and summary',
    tags=['spec/citations'],
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
    tags=['spec/citations'],
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
    tags=['spec/citations'],
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
        tmp_path, f'✅ [x]({url})\n', report_(PAY), report_path=tmp_path / 'r.html'
    )
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
    assert finding.details[0].startswith('closest by node id: t.py::test_pay_by_card')
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
        document,
        report_(PAY, report_url=None),
        report_path=tmp_path / 'report.html',
    )
    assert result.findings == []


def test_without_a_report_path_relative_links_are_ordinary(tmp_path: Path) -> None:
    document = '✓ [Pay by card](examples/r.html#scenario=t.py::test_pay)\n'
    result, _ = _run(tmp_path, document, report_(PAY))
    assert result.findings == []


def test_links_elsewhere_are_ordinary(tmp_path: Path) -> None:
    document = (
        '✓ [other](https://other.org/r.html#scenario=t.py::test_pay)\n'
        '✓ [same page](#scenario=t.py::test_pay)\n'
        '✓ [another file](other.html#scenario=t.py::test_pay)\n'
    )
    result, _ = _run(
        tmp_path, document, report_(PAY), report_path=tmp_path / 'examples' / 'r.html'
    )
    assert result.findings == []


def test_the_report_url_flag_overrides_the_stored_one(tmp_path: Path) -> None:
    other = 'https://other.org/report.html'
    document = f'✓ [Pay by card]({other}#scenario=t.py::test_pay)\n'
    result, _ = _run(tmp_path, document, report_(PAY), report_url=other)
    assert [f.kind for f in result.findings] == ['stale']


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
    )
    result, _ = _run(tmp_path, document, report_(PAY))
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
