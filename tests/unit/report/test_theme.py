import pytest

from pytest_given.model import PytestGivenError
from pytest_given.report.theme import DEFAULT_THEME, THEMES, resolve_theme


def test_default_theme_follows_the_system() -> None:
    assert DEFAULT_THEME == 'auto'
    assert THEMES == ('light', 'dark', 'auto')


@pytest.mark.parametrize('value', ['light', 'dark', 'auto'])
def test_resolve_theme_accepts_each_theme(value: str) -> None:
    assert resolve_theme(value, setting='--given-theme') == value


def test_resolve_theme_names_the_setting_and_the_choices_in_its_error() -> None:
    with pytest.raises(PytestGivenError) as excinfo:
        resolve_theme('Dark', setting='given_theme')
    message = str(excinfo.value)
    assert message.startswith("Unknown given_theme value 'Dark'")
    assert 'light, dark, auto' in message
