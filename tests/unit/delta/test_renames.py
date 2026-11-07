"""Reading `given-renames.toml`: what it accepts, and the entry named on refusal."""

import re
from pathlib import Path

import pytest

from pytest_given import given, scenario, then, when
from pytest_given.delta import (
    DEFAULT_RENAMES_PATH,
    RenameEntry,
    RenameLog,
    parse_rename_log,
    read_rename_log,
)
from pytest_given.model import PytestGivenError
from tests.ubiquitous_language import pg

SOURCE = 'given-renames.toml'

# The spec's example, verbatim.
SPEC_EXAMPLE = """\
# Identity changes pytest-given can't detect by itself.
# Read by `pytest-given delta`. Entries apply in file order, so chains work.

[[scenario]]
old = "examples/hotel-booking/test_hotel_booking.py::test_declined_payment"
new = "examples/hotel-booking/test_payments.py::test_declined_payment_holds_booking"
rev = "v0.6.0"

[[scenario]]  # renamed, and one case's generated ID changed with its value
old = "examples/coffeeshop/test_coffeeshop.py::test_pricing"
new = "examples/coffeeshop/test_coffeeshop.py::test_price_list"
cases = { "1.5-True" = "2.0-True" }
rev = "v0.6.0"

[[scenario]]  # only cases changed: `new` left out means the identity stayed
old = "examples/coffeeshop/test_coffeeshop.py::test_price_list"
cases = { "happy-hour" = "happy-hour-weekdays" }
rev = "v0.7.0"

[[term]]
old = "room"
new = "suite"
rev = "v0.6.0"
"""


def _refused(text: str, label: str) -> None:
    with pytest.raises(PytestGivenError, match=re.escape(label)):
        parse_rename_log(text, SOURCE)


@scenario(
    t'A {pg["Rename log"].l} entry with neither `new` nor `cases` is refused, '
    t'naming the entry',
    tags=['delta'],
)
def test_an_entry_without_new_or_cases_is_malformed() -> None:
    with given(t'a {pg["Rename log"].l} whose second scenario entry only names `old`'):
        text = (
            '[[scenario]]\nold = "a.py::t"\nnew = "b.py::t"\n\n'
            '[[scenario]]\nold = "c.py::t"\n'
        )
    with when('it is parsed'):
        with pytest.raises(PytestGivenError) as refusal:
            parse_rename_log(text, SOURCE)
    with then('the error names `[[scenario]] #2`'):
        assert '[[scenario]] #2 (old = "c.py::t")' in str(refusal.value)
        assert SOURCE in str(refusal.value)


def test_the_spec_example_parses_verbatim() -> None:
    log = parse_rename_log(SPEC_EXAMPLE, SOURCE)

    assert [(entry.table, entry.position) for entry in log.entries] == [
        ('scenario', 1),
        ('scenario', 2),
        ('scenario', 3),
        ('term', 1),
    ]
    first, second, third = log.of('scenario')
    assert first == RenameEntry(
        table='scenario',
        position=1,
        old='examples/hotel-booking/test_hotel_booking.py::test_declined_payment',
        new='examples/hotel-booking/test_payments.py::test_declined_payment_holds_booking',
        rev='v0.6.0',
    )
    assert second.cases == {'1.5-True': '2.0-True'}
    assert third.new is None
    assert third.cases == {'happy-hour': 'happy-hour-weekdays'}
    assert log.of('term') == (
        RenameEntry(table='term', position=1, old='room', new='suite', rev='v0.6.0'),
    )
    assert log.revs() == {'v0.6.0', 'v0.7.0'}


def test_a_case_key_may_hold_brackets_separators_and_non_ascii() -> None:
    text = (
        '[[scenario]]\nold = "a.py::t"\ncases = { "a]b" = "x::y", "größe-☕" = "ü" }\n'
    )

    (entry,) = parse_rename_log(text, SOURCE).entries

    assert entry.cases == {'a]b': 'x::y', 'größe-☕': 'ü'}


def test_an_empty_log_has_no_entries_and_no_revs() -> None:
    log = parse_rename_log('', SOURCE)

    assert log == RenameLog()
    assert log.revs() == frozenset()


def test_an_entry_labels_itself_by_table_position_and_old() -> None:
    entry = RenameEntry(table='term', position=3, old='room')

    assert entry.label == '[[term]] #3 (old = "room")'


@pytest.mark.parametrize(
    ('text', 'label'),
    [
        pytest.param('[[scenario]\n', SOURCE, id='bad-toml'),
        pytest.param('[[scenario]]\nnew = "b.py::t"\n', '[[scenario]] #1', id='no-old'),
        pytest.param(
            '[[scenario]]\nold = "a.py::t[1]"\nnew = "b.py::t"\n',
            '[[scenario]] #1 (old = "a.py::t[1]")',
            id='old-with-parametrize-tail',
        ),
        pytest.param(
            '[[scenario]]\nold = "a.py::t"\nnew = "b.py::t[1]"\n',
            '[[scenario]] #1 (old = "a.py::t")',
            id='new-with-parametrize-tail',
        ),
        pytest.param(
            '[[scenario]]\nold = "a.py::t"\nnew = "b.py::t"\nrev = "--all"\n',
            '[[scenario]] #1 (old = "a.py::t")',
            id='option-like-rev',
        ),
        pytest.param(
            '[[scenario]]\nold = "a.py::t"\nnews = "b.py::t"\n',
            '[[scenario]] #1 (old = "a.py::t")',
            id='unknown-key',
        ),
        pytest.param(
            '[[test]]\nold = "a"\nnew = "b"\n', '[[test]]', id='unknown-table'
        ),
        pytest.param(
            '[[term]]\nold = "room"\ncases = { "a" = "b" }\n',
            '[[term]] #1 (old = "room")',
            id='term-with-cases',
        ),
        pytest.param(
            '[[term]]\nold = "room"\n',
            '[[term]] #1 (old = "room")',
            id='term-without-new',
        ),
        pytest.param(
            '[[scenario]]\nold = "a.py::t"\nnew = 3\n',
            '[[scenario]] #1 (old = "a.py::t")',
            id='non-string-new',
        ),
        pytest.param(
            '[[scenario]]\nold = 3\nnew = "b"\n', '[[scenario]] #1', id='non-string-old'
        ),
        pytest.param(
            '[[scenario]]\nold = "a.py::t"\nnew = "b.py::t"\nrev = 3\n',
            '[[scenario]] #1 (old = "a.py::t")',
            id='non-string-rev',
        ),
        pytest.param(
            '[[scenario]]\nold = "a.py::t"\ncases = ["a"]\n',
            '[[scenario]] #1 (old = "a.py::t")',
            id='cases-not-a-table',
        ),
        pytest.param(
            '[[scenario]]\nold = "a.py::t"\ncases = { "a" = 2 }\n',
            '[[scenario]] #1 (old = "a.py::t")',
            id='non-string-case-value',
        ),
        pytest.param('scenario = "a.py::t"\n', 'scenario', id='table-not-an-array'),
        pytest.param('scenario = ["a.py::t"]\n', 'scenario', id='array-of-strings'),
    ],
)
def test_a_malformed_log_is_refused_naming_the_entry(text: str, label: str) -> None:
    _refused(text, label)


def test_the_default_log_is_read_from_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / DEFAULT_RENAMES_PATH).write_text(SPEC_EXAMPLE, encoding='utf-8')

    log = read_rename_log(None)

    assert len(log.entries) == 4


def test_no_default_log_reads_as_an_empty_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    assert read_rename_log(None) == RenameLog()


def test_an_explicit_log_is_read_and_its_errors_name_the_path(tmp_path: Path) -> None:
    path = tmp_path / 'renames.toml'
    path.write_text('[[term]]\nold = "room"\n', encoding='utf-8')

    with pytest.raises(PytestGivenError, match=re.escape(str(path))):
        read_rename_log(path)


def test_an_explicit_log_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    missing = tmp_path / 'missing.toml'

    with pytest.raises(PytestGivenError, match=re.escape(str(missing))):
        read_rename_log(missing)


def test_a_log_that_is_not_utf_8_is_refused_naming_the_path(tmp_path: Path) -> None:
    path = tmp_path / 'renames.toml'
    path.write_bytes(b'[[term]]\nold = "caf\xe9"\n')

    with pytest.raises(PytestGivenError, match=re.escape(f'{path}: not valid UTF-8')):
        read_rename_log(path)
