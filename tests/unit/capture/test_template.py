from string import templatelib

import pytest

from pytest_given.capture.template import Template, parse_tstring
from pytest_given.model import (
    NarrationLiteral,
    NarrationPlaceholder,
    NarrationValue,
    PytestGivenError,
)


def test_template_parses_literal_only() -> None:
    t = Template('hello world')
    assert t.template == 'hello world'
    assert t.parts == [NarrationLiteral(value='hello world')]


def test_template_parses_single_placeholder() -> None:
    t = Template('Brew {cup_size} ml')
    assert t.parts == [
        NarrationLiteral(value='Brew '),
        NarrationPlaceholder(name='cup_size', format_spec='', conversion=None),
        NarrationLiteral(value=' ml'),
    ]


def test_template_parses_format_spec_and_conversion() -> None:
    t = Template('n={n:03d} r={obj!r}')
    assert t.parts == [
        NarrationLiteral(value='n='),
        NarrationPlaceholder(name='n', format_spec='03d', conversion=None),
        NarrationLiteral(value=' r='),
        NarrationPlaceholder(name='obj', format_spec='', conversion='r'),
    ]


def test_template_get_identifiers() -> None:
    t = Template('a {x} b {y} c {x}')
    assert t.get_identifiers() == ['x', 'y', 'x']


def test_template_substitute_basic() -> None:
    t = Template('Brew {cup_size} ml')
    assert t.substitute({'cup_size': 200}) == 'Brew 200 ml'


def test_template_substitute_with_format_spec() -> None:
    t = Template('n={n:03d}')
    assert t.substitute({'n': 7}) == 'n=007'


def test_template_substitute_with_conversion() -> None:
    t = Template('r={obj!r}')
    assert t.substitute({'obj': 'hi'}) == "r='hi'"


def test_template_substitute_missing_key_raises() -> None:
    t = Template('Brew {cup_size} ml')
    with pytest.raises(KeyError, match='cup_size'):
        t.substitute({})


def test_template_escape_braces_round_trip() -> None:
    t = Template('escaped {{name}} literal')
    assert t.substitute({}) == 'escaped {name} literal'


def test_template_unclosed_brace_raises_value_error() -> None:
    with pytest.raises(ValueError, match="expected '}'"):
        Template('a {cup_size')


@pytest.mark.parametrize(
    'text',
    ['count={obj.attr}', '{d[key]}', '{x + 1}'],
    ids=['attribute', 'indexing', 'expression'],
)
def test_template_non_identifier_raises_pytest_given_error(text: str) -> None:
    with pytest.raises(PytestGivenError, match='bare identifiers'):
        Template(text)


def test_parse_tstring_literal_only() -> None:
    cup_size = 200  # noqa: F841
    rendered, parts = parse_tstring(t'just a label')
    assert rendered == 'just a label'
    assert parts == [NarrationLiteral(value='just a label')]


def test_parse_tstring_single_interpolation() -> None:
    cup_size = 200
    rendered, parts = parse_tstring(t'a {cup_size} ml cup')
    assert rendered == 'a 200 ml cup'
    assert parts == [
        NarrationLiteral(value='a '),
        NarrationValue(
            rendered='200',
            expression='cup_size',
            format_spec='',
            conversion=None,
        ),
        NarrationLiteral(value=' ml cup'),
    ]


def test_parse_tstring_format_spec() -> None:
    n = 7
    rendered, parts = parse_tstring(t'n={n:03d}')
    assert rendered == 'n=007'
    assert parts == [
        NarrationLiteral(value='n='),
        NarrationValue(
            rendered='007',
            expression='n',
            format_spec='03d',
            conversion=None,
        ),
    ]


def test_parse_tstring_conversion() -> None:
    obj = 'hi'
    rendered, parts = parse_tstring(t'r={obj!r}')
    assert rendered == "r='hi'"
    assert parts == [
        NarrationLiteral(value='r='),
        NarrationValue(
            rendered="'hi'",
            expression='obj',
            format_spec='',
            conversion='r',
        ),
    ]


def test_parse_tstring_consecutive_interpolations() -> None:
    a = 1
    b = 2
    rendered, parts = parse_tstring(t'{a}{b}')
    assert rendered == '12'
    assert parts == [
        NarrationValue(rendered='1', expression='a', format_spec='', conversion=None),
        NarrationValue(rendered='2', expression='b', format_spec='', conversion=None),
    ]


def test_parse_tstring_expression() -> None:
    price = 10
    rendered, parts = parse_tstring(t'cost: {price * 1.2}')
    assert rendered == 'cost: 12.0'
    assert parts[1] == NarrationValue(
        rendered='12.0',
        expression='price * 1.2',
        format_spec='',
        conversion=None,
    )


def test_parse_tstring_accepts_templatelib_template() -> None:
    """Sanity check: the input type is string.templatelib.Template."""
    cup_size = 200
    tpl = t'{cup_size}'
    assert isinstance(tpl, templatelib.Template)
    rendered, _ = parse_tstring(tpl)
    assert rendered == '200'
