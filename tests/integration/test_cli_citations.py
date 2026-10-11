"""`pytest-given citations check` / `update` end to end."""

import json
from pathlib import Path

import pytest

from pytest_given.cli import main

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
                    }
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
