import pytest

from pytest_given.errors import PytestGivenError
from pytest_given.template import (
    Template,
    TextLiteral,
    TextPlaceholder,
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
