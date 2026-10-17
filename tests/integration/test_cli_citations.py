"""`pytest-given citations check` / `update` end to end."""

import json
from pathlib import Path

import pytest

from pytest_given import attach, given, scenario, then, when
from pytest_given.cli import main
from tests.ubiquitous_language import pg

URL = 'https://example.org/report.html'


def _write_report(tmp_path: Path, *, report_url: str | None = URL) -> Path:
    path = tmp_path / 'report.json'
    path.write_text(
        json.dumps(
            {
                'metadata': {
                    'project': 'p',
                    'timestamp': 't',
                    'pytest_version': '9',
                    'plugin_version': '0',
                    'report_url': report_url,
                },
                'scenarios': [
                    {
                        'id': 't.py::test_pay',
                        'narration': {'text': 'Pay by card'},
                        'module': 'm',
                        'steps': [
                            {'phase': 'then', 'narration': {'text': 'it is paid'}}
                        ],
                    },
                    {
                        'id': 't.py::test_refund',
                        'narration': {'text': 'Refund'},
                        'module': 'm',
                    },
                ],
            }
        ),
        encoding='utf-8',
    )
    return path


def _doc(tmp_path: Path, text: str) -> Path:
    docs = tmp_path / 'docs'
    docs.mkdir(exist_ok=True)
    path = docs / 'spec.md'
    path.write_text(text, encoding='utf-8')
    return path


_CITATIONS = {
    'current': f'✅ [Pay by card]({URL}#scenario=t.py::test_pay)\n',
    'stale': f'✓ [old]({URL}#scenario=t.py::test_pay)\n',
    'of a gone scenario': f'✅ [Gone]({URL}#scenario=t.py::test_gone)\n',
}


@scenario(
    t'The `citations` exit code says whether a {pg["Citation finding"].l} '
    t'remains, so CI can gate on it',
    tags=['spec/citations'],
)
@pytest.mark.parametrize(
    ('command', 'citation', 'report_state', 'exit_code', 'rewritten'),
    [
        ('check', 'current', 'readable', 0, False),
        ('check', 'stale', 'readable', 1, False),
        ('update', 'stale', 'readable', 0, True),
        ('update', 'of a gone scenario', 'readable', 1, True),
        ('update', 'stale', 'unreadable', 2, False),
    ],
)
def test_the_citations_exit_code_says_whether_a_finding_remains(
    tmp_path: Path, command, citation, report_state, exit_code, rewritten
) -> None:
    with given(t'a document with a {pg["Citation"].l} that is {citation}'):
        doc = _doc(tmp_path, _CITATIONS[citation])
        attach('document', _CITATIONS[citation])
    with given(t'a JSON {pg["Report"].l} that is {report_state}'):
        report = _write_report(tmp_path)
        if report_state == 'unreadable':
            report.write_text('{not json', encoding='utf-8')
    with when(t'`pytest-given citations` {command} runs on the document'):
        rc = main(['citations', command, str(doc), '--report', str(report)])
    with then(t'it exits {exit_code}'):
        assert rc == exit_code
    with then(t'the document was rewritten: {rewritten}'):
        assert (doc.read_text(encoding='utf-8') != _CITATIONS[citation]) == rewritten


def test_check_exits_0_when_every_citation_is_current(tmp_path: Path, capsys) -> None:
    report = _write_report(tmp_path)
    _doc(tmp_path, f'✅ [Pay by card]({URL}#scenario=t.py::test_pay)\n')
    rc = main(['citations', 'check', str(tmp_path / 'docs'), '--report', str(report)])
    assert rc == 0
    assert 'every report link is current' in capsys.readouterr().out


def test_check_exits_1_and_prints_each_finding(tmp_path: Path, capsys) -> None:
    report = _write_report(tmp_path)
    doc = _doc(tmp_path, f'✓ [old]({URL}#scenario=t.py::test_pay)\n')
    assert main(['citations', 'check', str(doc), '--report', str(report)]) == 1
    out = capsys.readouterr().out
    assert f'{doc.as_posix()}:1: stale glyph' in out
    assert '✓ → ✅' in out
    assert '`citations update` fixes 2' in out
    assert (
        doc.read_text(encoding='utf-8') == f'✓ [old]({URL}#scenario=t.py::test_pay)\n'
    )


def test_update_rewrites_and_exits_0(tmp_path: Path, capsys) -> None:
    report = _write_report(tmp_path)
    doc = _doc(tmp_path, f'✓ [old]({URL}#scenario=t.py::test_pay)\n')
    assert main(['citations', 'update', str(doc), '--report', str(report)]) == 0
    assert doc.read_text(encoding='utf-8') == (
        f'✅ [Pay by card]({URL}#scenario=t.py::test_pay)\n'
    )
    assert 'updated 1 document' in capsys.readouterr().out


def test_update_exits_1_when_findings_remain(tmp_path: Path, capsys) -> None:
    report = _write_report(tmp_path)
    doc = _doc(tmp_path, f'✅ [Gone]({URL}#scenario=t.py::test_gone)\n')
    assert main(['citations', 'update', str(doc), '--report', str(report)]) == 1
    assert doc.read_text(encoding='utf-8').startswith('❓ ')
    assert '1 finding remain' in capsys.readouterr().out


@pytest.mark.parametrize('report_text', ['{not json', '{"metadata": {}}'])
def test_an_unreadable_report_exits_2_and_writes_nothing(
    tmp_path: Path, capsys, report_text: str
) -> None:
    report = tmp_path / 'report.json'
    report.write_text(report_text, encoding='utf-8')
    doc = _doc(tmp_path, f'✓ [old]({URL}#scenario=t.py::test_pay)\n')
    assert main(['citations', 'update', str(doc), '--report', str(report)]) == 2
    assert doc.read_text(encoding='utf-8').startswith('✓ ')
    assert 'Error:' in capsys.readouterr().err


def test_an_unreadable_report_is_named_by_its_posix_path(
    tmp_path: Path, capsys
) -> None:
    report = tmp_path / 'report.json'
    report.write_text('{not json', encoding='utf-8')
    doc = _doc(tmp_path, 'text\n')
    assert main(['citations', 'check', str(doc), '--report', str(report)]) == 2
    assert f'Error: {report.as_posix()} is not valid JSON' in capsys.readouterr().err


def test_a_missing_report_is_named_by_its_posix_path(tmp_path: Path, capsys) -> None:
    report = tmp_path / 'reports' / 'missing.json'
    doc = _doc(tmp_path, 'text\n')
    assert main(['citations', 'check', str(doc), '--report', str(report)]) == 2
    assert f'Error: {report.as_posix()} not found' in capsys.readouterr().err


def test_a_report_that_is_not_utf8_exits_2(tmp_path: Path) -> None:
    report = tmp_path / 'report.json'
    report.write_bytes(b'\xff\xfe')
    doc = _doc(tmp_path, 'text\n')
    assert main(['citations', 'check', str(doc), '--report', str(report)]) == 2


def test_an_unreadable_document_exits_2_and_writes_no_other(tmp_path: Path) -> None:
    report = _write_report(tmp_path)
    good = _doc(tmp_path, f'✓ [old]({URL}#scenario=t.py::test_pay)\n')
    (tmp_path / 'docs' / 'bad.md').write_bytes(b'\xff\xfe')
    rc = main(['citations', 'update', str(tmp_path / 'docs'), '--report', str(report)])
    assert rc == 2
    assert good.read_text(encoding='utf-8').startswith('✓ ')


def test_a_missing_document_path_exits_2(tmp_path: Path) -> None:
    report = _write_report(tmp_path)
    rc = main(['citations', 'check', str(tmp_path / 'nope'), '--report', str(report)])
    assert rc == 2


def test_neither_report_url_nor_report_path_exits_2(tmp_path: Path, capsys) -> None:
    report = _write_report(tmp_path, report_url=None)
    doc = _doc(tmp_path, 'text\n')
    assert main(['citations', 'check', str(doc), '--report', str(report)]) == 2
    assert 'report URL' in capsys.readouterr().err


def test_report_path_reads_relative_links(tmp_path: Path) -> None:
    report = _write_report(tmp_path, report_url=None)
    doc = _doc(tmp_path, '✓ [old](../site/r.html#scenario=t.py::test_pay)\n')
    rc = main(
        [
            'citations',
            'update',
            str(doc),
            '--report',
            str(report),
            '--report-path',
            str(tmp_path / 'site' / 'r.html'),
        ]
    )
    assert rc == 0
    assert doc.read_text(encoding='utf-8').startswith('✅ [Pay by card]')


def test_a_bad_report_url_flag_exits_2(tmp_path: Path) -> None:
    report = _write_report(tmp_path)
    doc = _doc(tmp_path, 'text\n')
    rc = main(
        [
            'citations',
            'check',
            str(doc),
            '--report',
            str(report),
            '--report-url',
            'r.html',
        ]
    )
    assert rc == 2


def test_a_verb_is_required() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(['citations'])
    assert excinfo.value.code == 2


def _narrated(body: str) -> str:
    return (
        '<details markdown="1">\n'
        f'<summary>✅ <a href="{URL}#scenario=t.py::test_pay">Pay by card</a>'
        f'</summary>\n{body}</details>\n'
    )


def test_update_fills_a_narrated_citations_empty_body(tmp_path: Path) -> None:
    report = _write_report(tmp_path)
    doc = _doc(tmp_path, _narrated('\n'))
    assert main(['citations', 'update', str(doc), '--report', str(report)]) == 0
    assert doc.read_text(encoding='utf-8') == _narrated('\n- **then** it is paid\n\n')


def test_check_exits_1_on_a_stale_narrated_body(tmp_path: Path, capsys) -> None:
    report = _write_report(tmp_path)
    doc = _doc(tmp_path, _narrated('\n- **then** it is charged\n\n'))
    assert main(['citations', 'check', str(doc), '--report', str(report)]) == 1
    out = capsys.readouterr().out
    assert f'{doc.as_posix()}:2: stale narration' in out
    assert 'written: - **then** it is charged' in out


# --- Listing ---

_LISTED = (
    '# Paying\n'
    f'✅ [Pay by card]({URL}#scenario=t.py::test_pay) and '
    f'✓ [Refund]({URL}#scenario=t.py::test_refund)\n'
    f'See [refunds]({URL}#scenario=t.py::test_refund) and '
    f'[elsewhere](https://other.org/)\n'
)


@scenario(
    t'`citations check --list` prints every {pg["Report link"].l}, its findings '
    t'under it',
    tags=['spec/citations-list'],
)
def test_check_list_prints_every_report_link_with_its_findings(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with given(
        t'a document with two {pg["Citation"].l.s}, one of them stale, and a plain '
        t'{pg["Report link"].l}'
    ):
        doc = _doc(tmp_path, _LISTED).relative_to(tmp_path)
        attach('document', _LISTED)
    with given(t'a JSON {pg["Report"].l} of its scenarios'):
        report = _write_report(tmp_path)
    with when('`pytest-given citations check --list` runs on the document'):
        rc = main(['citations', 'check', '--list', str(doc), '--report', str(report)])
        out = capsys.readouterr().out
        attach('output', out)
    with then(
        t'each {pg["Report link"].l} is a line, with each finding indented under '
        t'its own'
    ):
        assert out.splitlines() == [
            f'{doc.as_posix()}:2: ✅ scenario t.py::test_pay',
            f'{doc.as_posix()}:2: ✓ scenario t.py::test_refund',
            '    stale glyph',
            '        ✓ → ✅',
            f'{doc.as_posix()}:3: link scenario t.py::test_refund',
            'citations: 1 finding; `citations update` fixes 1',
        ]
    with then('it exits 1 for the finding'):
        assert rc == 1


@scenario(
    t'`--covering` leaves {pg["Report link"].l.s} out of the list but still counts '
    t'their findings',
    tags=['spec/citations-list'],
)
def test_covering_still_counts_the_findings_it_leaves_out(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with given(
        t'a document whose stale {pg["Citation"].l} cites `test_refund`, not `test_pay`'
    ):
        doc = _doc(tmp_path, _LISTED).relative_to(tmp_path)
        attach('document', _LISTED)
    with given(t'a JSON {pg["Report"].l} of its scenarios'):
        report = _write_report(tmp_path)
    with when('`pytest-given citations check --covering` names `test_pay`'):
        rc = main(
            [
                'citations',
                'check',
                '--covering',
                't.py::test_pay',
                str(doc),
                '--report',
                str(report),
            ]
        )
        out = capsys.readouterr().out
        attach('output', out)
    with then(t'only the {pg["Citation"].l} of `test_pay` is listed'):
        assert out.splitlines()[:-1] == [
            f'{doc.as_posix()}:2: ✅ scenario t.py::test_pay'
        ]
    with then('the summary counts the finding it left out'):
        assert out.splitlines()[-1] == (
            'citations: 1 finding, 1 of them left out by --covering; '
            '`citations update` fixes 1'
        )
    with then('it exits 1 for that finding'):
        assert rc == 1


def test_list_of_current_links_exits_0(tmp_path: Path, capsys) -> None:
    doc = _doc(tmp_path, f'✅ [Pay by card]({URL}#scenario=t.py::test_pay)\n')
    report = _write_report(tmp_path)
    rc = main(['citations', 'check', '--list', str(doc), '--report', str(report)])
    assert rc == 0
    assert capsys.readouterr().out.splitlines() == [
        f'{doc.as_posix()}:1: ✅ scenario t.py::test_pay',
        'citations: every report link is current',
    ]


def test_a_repeated_covering_lists_the_links_of_each(tmp_path: Path, capsys) -> None:
    doc = _doc(tmp_path, _LISTED)
    report = _write_report(tmp_path)
    rc = main(
        [
            'citations',
            'check',
            str(doc),
            '--report',
            str(report),
            '--covering',
            't.py::test_pay',
            '--covering',
            't.py::test_refund',
        ]
    )
    assert rc == 1
    out = capsys.readouterr().out
    assert out.count(f'{doc.as_posix()}:') == 3
    assert out.splitlines()[-1] == 'citations: 1 finding; `citations update` fixes 1'


def test_covering_an_unknown_scenario_exits_2(tmp_path: Path, capsys) -> None:
    doc = _doc(tmp_path, _LISTED)
    report = _write_report(tmp_path)
    rc = main(
        [
            'citations',
            'check',
            str(doc),
            '--report',
            str(report),
            '--covering',
            't.py::test_pai',
        ]
    )
    assert rc == 2
    assert capsys.readouterr().err == (
        'Error: scenario t.py::test_pai is not in the report; '
        'closest by node ID: t.py::test_pay, t.py::test_refund\n'
    )


@pytest.mark.parametrize('option', [['--list'], ['--covering', 't.py::test_pay']])
def test_update_takes_neither_listing_option(tmp_path: Path, option) -> None:
    doc = _doc(tmp_path, _LISTED)
    report = _write_report(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        main(['citations', 'update', *option, str(doc), '--report', str(report)])
    assert excinfo.value.code == 2
