"""`pytest-given delta` end to end."""

import dataclasses
import json
from pathlib import Path

import pytest

from pytest_given import given, scenario, then, when
from pytest_given.cli import main
from pytest_given.model import (
    REPORT_SCHEMA_VERSION,
    Glossary,
    ReportData,
    delta_from_dict,
    report_to_dict,
)
from pytest_given.report import DEFAULT_DELTA_HTML_PATH, DEFAULT_DELTA_JSON_PATH
from pytest_given.report.delta.html_renderer import (
    RangeSide,
    delta_render_context,
    range_side,
)
from tests.git_repo import GitRepo
from tests.ubiquitous_language import pg
from tests.unit.delta.builders import meta, report, scn, step, term


def _write_report(path: Path, data: ReportData) -> Path:
    metadata = dataclasses.replace(data.metadata, schema_version=REPORT_SCHEMA_VERSION)
    path.write_text(
        json.dumps(report_to_dict(dataclasses.replace(data, metadata=metadata))),
        encoding='utf-8',
    )
    return path


def _write_pair(
    before: ReportData, after: ReportData, folder: Path = Path()
) -> list[str]:
    return [
        _write_report(folder / 'before.json', before).as_posix(),
        _write_report(folder / 'after.json', after).as_posix(),
    ]


def _read_delta() -> dict[str, object]:
    return json.loads(DEFAULT_DELTA_JSON_PATH.read_text(encoding='utf-8'))


@scenario(
    t'`pytest-given delta` writes a {pg["Delta report"].l} as JSON and HTML, '
    t'and exits 0 whether or not anything changed',
    tags=['delta'],
)
@pytest.mark.parametrize(
    ('after_title', 'listed'), [('Pay by card', 0), ('Pay by credit card', 1)]
)
def test_delta_writes_a_delta_json_and_html_and_exits_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, after_title: str, listed: int
) -> None:
    monkeypatch.chdir(tmp_path)
    with given(t'a before {pg["Report"].l} with a scenario titled "Pay by card"'):
        before = report(scn('t.py::test_pay', 'Pay by card'))
    with given(t'an after {pg["Report"].l} that titles it "{after_title}"'):
        after = report(scn('t.py::test_pay', after_title))
        inputs = _write_pair(before, after)
    with when('`pytest-given delta` compares the two'):
        rc = main(['delta', *inputs])
    with then('it exits 0'):
        assert rc == 0
    with then(t'the delta JSON lists {listed} changed scenarios'):
        assert len(_read_delta()['scenarios']) == listed
    with then('the delta HTML is written beside it'):
        assert DEFAULT_DELTA_HTML_PATH.is_file()


def test_the_summary_counts_the_changes_and_each_file_is_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    before = report(
        scn('t.py::test_a', 'A'), scn('t.py::test_b', 'B'), scn('t.py::test_c', 'C')
    )
    after = report(scn('t.py::test_a', 'A'), scn('t.py::test_b', 'B2'))
    assert main(['delta', *_write_pair(before, after)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == [
        f'Delta generated: {DEFAULT_DELTA_JSON_PATH}',
        f'Delta generated: {DEFAULT_DELTA_HTML_PATH}',
        'delta: 0 added, 1 changed, 1 removed scenarios; 1 unchanged',
    ]


def test_the_summary_counts_listed_terms_and_suggested_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    steps = (step('when', 'a guest pays by card'), step('then', 'the room is booked'))
    before = report(scn('t.py::test_old', 'Old', *steps))
    after = report(
        scn('t.py::test_new', 'New', *steps),
        glossary=Glossary(terms=[term('room', 'Room')]),
    )
    assert main(['delta', *_write_pair(before, after)]) == 0
    summary = capsys.readouterr().out.splitlines()[-1]
    assert summary == (
        'delta: 1 added, 0 changed, 1 removed scenarios; 0 unchanged; '
        '1 added, 0 changed, 0 removed terms; 1 suggested match'
    )


def test_one_output_flag_writes_only_that_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    inputs = _write_pair(report(), report())
    assert main(['delta', *inputs, '--html', 'out/d.html']) == 0
    assert Path('out/d.html').is_file()
    assert not DEFAULT_DELTA_JSON_PATH.exists()
    assert not DEFAULT_DELTA_HTML_PATH.exists()


def test_identical_reports_make_an_empty_delta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    same = report(scn('t.py::test_pay', 'Pay by card'))
    assert main(['delta', *_write_pair(same, same)]) == 0
    delta_dict = _read_delta()
    assert delta_dict['scenarios'] == []
    assert delta_render_context(delta_from_dict(delta_dict))['listed'] == []


def test_a_delta_json_alone_rerenders_the_html_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    inputs = _write_pair(report(scn('t.py::test_a', 'A')), report())
    assert main(['delta', *inputs]) == 0
    json_before = DEFAULT_DELTA_JSON_PATH.read_bytes()
    DEFAULT_DELTA_HTML_PATH.unlink()
    capsys.readouterr()
    assert main(['delta', DEFAULT_DELTA_JSON_PATH.as_posix()]) == 0
    assert DEFAULT_DELTA_HTML_PATH.is_file()
    assert DEFAULT_DELTA_JSON_PATH.read_bytes() == json_before
    assert capsys.readouterr().out.splitlines() == [
        f'Delta generated: {DEFAULT_DELTA_HTML_PATH}',
        'delta: 0 added, 0 changed, 1 removed scenarios; 0 unchanged',
    ]


def test_version_warnings_go_to_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    before = ReportData(metadata=meta(plugin_version='0.1.0'), scenarios=[])
    after = ReportData(metadata=meta(plugin_version='0.2.0'), scenarios=[])
    assert main(['delta', *_write_pair(before, after)]) == 0
    [warning] = capsys.readouterr().err.splitlines()
    assert warning.startswith('Warning: ')
    assert 'pytest-given 0.1.0' in warning


def _delta_file(tmp_path: Path) -> Path:
    inputs = _write_pair(report(), report(), tmp_path)
    path = tmp_path / 'delta.json'
    assert main(['delta', *inputs, '--json', str(path)]) == 0
    return path


@pytest.mark.parametrize(
    ('make_args', 'message'),
    [
        (lambda tmp: ['delta', 'missing.json', 'after.json'], 'missing.json not found'),
        (
            lambda tmp: ['delta', str(_delta_file(tmp)), str(_delta_file(tmp))],
            'pytest-given delta',
        ),
        (
            lambda tmp: ['delta', _write_pair(report(), report(), tmp)[0]],
            'is a report, not a delta',
        ),
        (
            lambda tmp: ['delta', str(_delta_file(tmp)), '--json', 'x.json'],
            '--json needs two reports to compare',
        ),
        (
            lambda tmp: ['delta', str(_delta_file(tmp)), '--renames', 'r.toml'],
            '--renames needs two reports to compare',
        ),
        (
            lambda tmp: ['delta', str(_delta_file(tmp)), '--before-label', 'v1'],
            '--before-label needs two reports to compare',
        ),
        (
            lambda tmp: ['delta', str(_delta_file(tmp)), '--after-label', 'v2'],
            '--after-label needs two reports to compare',
        ),
        (
            lambda tmp: ['delta', str(_delta_file(tmp)), '--title', 'Shop'],
            '--title needs two reports to compare',
        ),
        (
            lambda tmp: [
                'delta',
                *_write_pair(report(), report(), tmp),
                '--renames',
                'missing.toml',
            ],
            'rename log not found: missing.toml',
        ),
        (
            lambda tmp: [
                'delta',
                *_write_pair(report(), report(), tmp),
                '--theme',
                'x',
            ],
            '--theme',
        ),
        (
            lambda tmp: [
                'delta',
                *_write_pair(report(), report(), tmp),
                '--source-link',
                'bogus',
            ],
            '--source-link',
        ),
    ],
    ids=[
        'missing input',
        'a delta passed as a report',
        'a report as the single input',
        '--json with one input',
        '--renames with one input',
        '--before-label with one input',
        '--after-label with one input',
        '--title with one input',
        '--renames that does not exist',
        'an unknown theme',
        'an unknown source-link preset',
    ],
)
def test_what_the_delta_cannot_do_exits_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    make_args,
    message: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    args = make_args(tmp_path)
    capsys.readouterr()
    assert main(args) == 2
    err = capsys.readouterr().err
    assert err.startswith('Error: ')
    assert message in err


def test_a_schema_mismatch_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    inputs = _write_pair(report(), report())
    data = json.loads(Path(inputs[0]).read_text(encoding='utf-8'))
    del data['metadata']['schema_version']
    Path(inputs[0]).write_text(json.dumps(data), encoding='utf-8')
    assert main(['delta', *inputs]) == 2
    assert 'report schema version none' in capsys.readouterr().err


def test_a_delta_output_that_is_an_input_report_is_refused_and_the_input_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    inputs = _write_pair(report(scn('t.py::test_a', 'A')), report())
    before_bytes = Path(inputs[0]).read_bytes()
    output = tmp_path / 'before.json'
    assert main(['delta', *inputs, '--json', str(output)]) == 2
    assert Path(inputs[0]).read_bytes() == before_bytes
    assert capsys.readouterr().err == (
        f'Error: the delta JSON {output.as_posix()} is the input before.json; '
        'write it elsewhere\n'
    )


def test_an_html_output_that_is_an_input_report_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_report(Path('after.html'), report())
    _write_report(Path('before.json'), report())
    after_bytes = Path('after.html').read_bytes()
    assert main(['delta', 'before.json', 'after.html', '--html', 'after.html']) == 2
    assert Path('after.html').read_bytes() == after_bytes
    assert 'the delta HTML after.html is the input after.html' in (
        capsys.readouterr().err
    )


def test_a_rerender_onto_its_own_input_is_refused_and_the_input_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    delta_html = Path('delta.html')
    delta_html.write_bytes(_delta_file(tmp_path).read_bytes())
    capsys.readouterr()
    assert main(['delta', 'delta.html', '--html', str(tmp_path / 'delta.html')]) == 2
    assert delta_html.read_bytes() == (tmp_path / 'delta.json').read_bytes()
    assert 'is the input delta.html' in capsys.readouterr().err


def _drop_schema_version(path: str) -> None:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    del data['metadata']['schema_version']
    Path(path).write_text(json.dumps(data), encoding='utf-8')


def _malformed_rename_log(path: str) -> None:
    Path('given-renames.toml').write_text('[[term]]\n', encoding='utf-8')


@pytest.mark.parametrize(
    'spoil',
    [_drop_schema_version, _malformed_rename_log],
    ids=['a schema mismatch', 'a malformed rename log'],
)
def test_a_delta_that_cannot_be_built_takes_the_previous_one_with_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    spoil,
) -> None:
    monkeypatch.chdir(tmp_path)
    inputs = _write_pair(report(scn('t.py::test_a', 'A')), report())
    assert main(['delta', *inputs]) == 0
    spoil(inputs[0])
    capsys.readouterr()
    assert main(['delta', *inputs]) == 2
    assert not DEFAULT_DELTA_JSON_PATH.exists()
    assert not DEFAULT_DELTA_HTML_PATH.exists()
    assert Path(inputs[0]).is_file()
    assert 'Removed the previous' in capsys.readouterr().err


@pytest.mark.parametrize(
    ('make_args', 'removed'),
    [
        (
            lambda inputs: ['delta', inputs[0], 'after.jsn'],
            [DEFAULT_DELTA_JSON_PATH, DEFAULT_DELTA_HTML_PATH],
        ),
        (lambda inputs: ['delta', 'delta.jsn'], [DEFAULT_DELTA_HTML_PATH]),
        (lambda inputs: ['delta', 'broken.json'], [DEFAULT_DELTA_HTML_PATH]),
        (
            lambda inputs: ['delta', *inputs, '--renames', 'typo.toml'],
            [DEFAULT_DELTA_JSON_PATH, DEFAULT_DELTA_HTML_PATH],
        ),
    ],
    ids=[
        'a missing report',
        'a missing delta JSON',
        'a delta JSON that is no JSON',
        'a missing rename log',
    ],
)
def test_an_input_that_cannot_be_read_takes_the_previous_delta_with_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    make_args,
    removed: list[Path],
) -> None:
    monkeypatch.chdir(tmp_path)
    inputs = _write_pair(report(scn('t.py::test_a', 'A')), report())
    assert main(['delta', *inputs]) == 0
    Path('broken.json').write_text('{', encoding='utf-8')
    capsys.readouterr()
    assert main(make_args(inputs)) == 2
    assert not any(path.exists() for path in removed)
    assert 'Removed the previous' in capsys.readouterr().err


def test_a_report_of_an_older_schema_is_refused_by_its_version_not_its_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    inputs = _write_pair(report(), report())
    data = json.loads(Path(inputs[0]).read_text(encoding='utf-8'))
    data['metadata'] = {'schema_version': 0}
    Path(inputs[0]).write_text(json.dumps(data), encoding='utf-8')
    assert main(['delta', *inputs]) == 2
    err = capsys.readouterr().err
    assert 'report schema version 0' in err
    assert 'KeyError' not in err


def test_a_malformed_rename_log_exits_2_naming_the_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    Path('given-renames.toml').write_text(
        '[[scenario]]\nnew = "t.py::x"\n', encoding='utf-8'
    )
    assert main(['delta', *_write_pair(report(), report())]) == 2
    assert '[[scenario]] #1' in capsys.readouterr().err


@pytest.mark.parametrize(
    'command', [['report'], ['citations', 'check', 'doc.md', '--report']]
)
def test_a_delta_json_is_refused_where_a_report_is_expected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    command: list[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = _delta_file(tmp_path)
    Path('doc.md').write_text('# Doc\n', encoding='utf-8')
    capsys.readouterr()
    assert main([*command, str(path)]) == 2
    assert 'pytest-given delta' in capsys.readouterr().err


_RENAME = """\
[[scenario]]
old = "t.py::test_old"
new = "t.py::test_new"
rev = "{rev}"
"""


def _renamed_pair(before_sha: str | None, after_sha: str) -> list[str]:
    return _write_pair(
        report(scn('t.py::test_old', 'Pay'), sha=before_sha),
        report(scn('t.py::test_new', 'Pay by card'), sha=after_sha),
    )


@pytest.mark.parametrize(
    ('rev', 'range_', 'changes'),
    [
        ('v1', ('head', 'head'), ['added', 'removed']),
        ('v1.9', ('first', 'first'), ['added', 'removed']),
        ('v1.9', ('first', 'head'), ['changed']),
    ],
    ids=[
        'rev an ancestor of before: skipped',
        'rev past after: skipped',
        'rev in the range: applies',
    ],
)
def test_a_rename_entry_whose_rev_is_outside_the_range_is_skipped(
    git_repo: GitRepo,
    monkeypatch: pytest.MonkeyPatch,
    rev: str,
    range_: tuple[str, str],
    changes: list[str],
) -> None:
    monkeypatch.chdir(git_repo.path)
    Path('given-renames.toml').write_text(_RENAME.format(rev=rev), encoding='utf-8')
    before_sha, after_sha = (getattr(git_repo, end) for end in range_)
    assert main(['delta', *_renamed_pair(before_sha, after_sha)]) == 0
    listed = _read_delta()['scenarios']
    assert sorted(item['change'] for item in listed) == changes


def test_a_before_report_without_a_sha_applies_every_entry_with_one_warning(
    git_repo: GitRepo, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.chdir(git_repo.path)
    Path('given-renames.toml').write_text(_RENAME.format(rev='v1'), encoding='utf-8')
    assert main(['delta', *_renamed_pair(None, git_repo.head)]) == 0
    [warning] = capsys.readouterr().err.splitlines()
    assert warning == (
        'Warning: no ancestry answer (the before report has no commit SHA); '
        'rename-log entries with `rev` all apply'
    )
    delta = delta_from_dict(_read_delta())
    assert [item.change for item in delta.scenarios] == ['changed']
    assert range_side(delta.metadata.before) == RangeSide('2026-01-01 00:00')


def test_each_side_is_labelled_with_its_highest_tag_unless_a_label_is_passed(
    git_repo: GitRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(git_repo.path)
    inputs = _write_pair(report(sha=git_repo.first), report(sha=git_repo.head))
    assert main(['delta', *inputs]) == 0
    context = delta_render_context(delta_from_dict(_read_delta()))
    assert context['range'] == (
        RangeSide('v1', git_repo.first[:7]),
        RangeSide('v1.10', git_repo.head[:7]),
    )
    assert main(['delta', *inputs, '--after-label', 'next']) == 0
    delta = delta_from_dict(_read_delta())
    assert range_side(delta.metadata.after) == RangeSide('next', git_repo.head[:7])


@scenario(
    t'A {pg["Delta report"].l} is titled by `--title`, '
    t'or else by the title of the after {pg["Report"].l}',
    tags=['delta'],
)
@pytest.mark.parametrize(
    ('extra_args', 'shown'),
    [([], 'Shop'), (['--title', 'Shop changes for v2'], 'Shop changes for v2')],
)
def test_the_delta_is_titled_by_title_or_else_by_the_after_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra_args: list[str],
    shown: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    with given(t'an after {pg["Report"].l} titled "Shop"'):
        after = ReportData(metadata=meta(title='Shop'), scenarios=[])
        inputs = _write_pair(report(), after)
    with when(
        t'`pytest-given delta` compares it to a before one, '
        t'with the extra arguments {extra_args}'
    ):
        exit_code = main(['delta', *inputs, *extra_args])
    with then(t'the delta is titled "{shown}"'):
        assert exit_code == 0
        assert delta_render_context(delta_from_dict(_read_delta()))['title'] == shown


def test_an_empty_title_counts_as_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    after = ReportData(metadata=meta(title='Shop'), scenarios=[])
    assert main(['delta', *_write_pair(report(), after), '--title', '']) == 0
    assert delta_from_dict(_read_delta()).metadata.title is None
