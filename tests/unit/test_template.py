from string import templatelib

import pytest

from pytest_given.errors import PytestGivenError
from pytest_given.template import (
    Template,
    TextLiteral,
    TextPlaceholder,
    TextValue,
    parse_tstring,
)


def test_template_parses_literal_only() -> None:
    t = Template('hello world')
    assert t.template == 'hello world'
    assert t.parts == [TextLiteral(value='hello world')]


def test_template_parses_single_placeholder() -> None:
    t = Template('Brew {cup_size} ml')
    assert t.parts == [
        TextLiteral(value='Brew '),
        TextPlaceholder(name='cup_size', format_spec='', conversion=None),
        TextLiteral(value=' ml'),
    ]


def test_template_parses_format_spec_and_conversion() -> None:
    t = Template('n={n:03d} r={obj!r}')
    assert t.parts == [
        TextLiteral(value='n='),
        TextPlaceholder(name='n', format_spec='03d', conversion=None),
        TextLiteral(value=' r='),
        TextPlaceholder(name='obj', format_spec='', conversion='r'),
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


def test_template_attribute_access_raises_pytest_given_error() -> None:
    with pytest.raises(PytestGivenError, match='bare identifiers'):
        Template('count={obj.attr}')


def test_template_indexing_raises_pytest_given_error() -> None:
    with pytest.raises(PytestGivenError, match='bare identifiers'):
        Template('{d[key]}')


def test_template_expression_raises_pytest_given_error() -> None:
    with pytest.raises(PytestGivenError, match='bare identifiers'):
        Template('{x + 1}')


def test_parse_tstring_literal_only() -> None:
    cup_size = 200  # noqa: F841
    rendered, parts = parse_tstring(t'just a label')
    assert rendered == 'just a label'
    assert parts == [TextLiteral(value='just a label')]


def test_parse_tstring_single_interpolation() -> None:
    cup_size = 200
    rendered, parts = parse_tstring(t'a {cup_size} ml cup')
    assert rendered == 'a 200 ml cup'
    assert parts == [
        TextLiteral(value='a '),
        TextValue(
            rendered='200',
            expression='cup_size',
            format_spec='',
            conversion=None,
        ),
        TextLiteral(value=' ml cup'),
    ]


def test_parse_tstring_format_spec() -> None:
    n = 7
    rendered, parts = parse_tstring(t'n={n:03d}')
    assert rendered == 'n=007'
    assert parts == [
        TextLiteral(value='n='),
        TextValue(
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
        TextLiteral(value='r='),
        TextValue(
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
        TextValue(rendered='1', expression='a', format_spec='', conversion=None),
        TextValue(rendered='2', expression='b', format_spec='', conversion=None),
    ]


def test_parse_tstring_expression() -> None:
    price = 10
    rendered, parts = parse_tstring(t'cost: {price * 1.2}')
    assert rendered == 'cost: 12.0'
    assert parts[1] == TextValue(
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
