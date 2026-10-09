import pytest

from pytest_given.model import PytestGivenError, derived_id, id_derive, plural, s_form


def test_derived_id_returns_none_where_id_derive_raises() -> None:
    assert derived_id('---') is None
    with pytest.raises(PytestGivenError, match='derived id is empty'):
        id_derive('---')


def test_derived_id_agrees_with_id_derive_on_a_derivable_name() -> None:
    assert derived_id('Flat White') == id_derive('Flat White') == 'flat-white'


@pytest.mark.parametrize('name', ['\u212a', '\u0130'])
def test_a_character_that_lowercases_into_ascii_still_derives(name: str) -> None:
    """The fold happens after `str.lower`, so a non-ASCII character whose
    lowercase form is ASCII does have a slug. A predicate that tested the
    original characters for ASCII-ness would wrongly call these underivable."""
    assert derived_id(name) is not None
    assert derived_id(name) == id_derive(name)


@pytest.mark.parametrize(
    ('word', 's_form_of_word'),
    [
        ('room', 'rooms'),
        ('book', 'books'),
        ('bus', 'buses'),
        ('box', 'boxes'),
        ('watch', 'watches'),
        ('wish', 'wishes'),
        ('category', 'categories'),
        ('key', 'keys'),
        ('buy', 'buys'),
        ('booking request', 'booking requests'),
        ('API', 'APIs'),
        ('SMS', 'SMSs'),
        ('Y', 'Ys'),
    ],
)
def test_s_form_follows_the_regular_english_spelling_rules(
    word: str, s_form_of_word: str
) -> None:
    assert s_form(word) == s_form_of_word


def test_plural_agrees_the_noun_with_its_count() -> None:
    assert [plural(count, 'story') for count in (0, 1, 2)] == [
        '0 stories',
        '1 story',
        '2 stories',
    ]
