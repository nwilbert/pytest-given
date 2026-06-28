from pathlib import Path

from pytest_given.capture.source import _reset_rootdir, set_rootdir
from pytest_given.capture.traceback import parse_short_repr


def test_parses_multi_frame_short_repr() -> None:
    text = (
        '.venv/lib/site-packages/_pytest/runner.py:353: in from_call\n'
        '    result: TResult | None = func()\n'
        '                             ^^^^^^\n'
        'tests/test_billing.py:10: in test_buy_coffee\n'
        '    assert machine["coffees"] == 20\n'
        'E   assert 10 == 20'
    )
    frames, tail = parse_short_repr(text)
    assert len(frames) == 2
    # site-packages frames are collapsed to a venv-independent tail.
    assert frames[0].path == 'site-packages/_pytest/runner.py'
    assert frames[0].lineno == 353
    assert frames[0].func == 'from_call'
    assert frames[0].is_internal is True
    assert frames[1].path == 'tests/test_billing.py'
    assert frames[1].lineno == 10
    assert frames[1].func == 'test_buy_coffee'
    assert frames[1].is_internal is False
    assert frames[1].code == '    assert machine["coffees"] == 20'
    assert tail == 'E   assert 10 == 20'


def test_caret_rows_preserved_in_code() -> None:
    text = (
        'tests/t.py:1: in f\n'
        '    return foo(bar)\n'
        '           ^^^^^^^^\n'
        'E   NameError: foo'
    )
    frames, tail = parse_short_repr(text)
    assert len(frames) == 1
    assert frames[0].code == '    return foo(bar)\n           ^^^^^^^^'
    assert tail == 'E   NameError: foo'


def test_multi_line_error_tail() -> None:
    text = (
        'tests/t.py:1: in f\n'
        '    assert x == y\n'
        'E   AssertionError: assert {1, 2} == {1, 3}\n'
        'E     Extra items in the left set:\n'
        'E     2'
    )
    frames, tail = parse_short_repr(text)
    assert len(frames) == 1
    assert tail is not None
    assert tail.count('\n') == 2
    assert tail.startswith('E   AssertionError')


def test_no_frame_headers_returns_text_as_tail() -> None:
    text = 'some unexpected pytest output'
    frames, tail = parse_short_repr(text)
    assert frames == []
    assert tail == 'some unexpected pytest output'


def test_empty_input() -> None:
    frames, tail = parse_short_repr('')
    assert frames == []
    assert tail is None


def test_windows_path_normalized_to_forward_slashes() -> None:
    text = (
        'tests\\unit\\capture\\test_x.py:12: in test_thing\n'
        '    assert False\n'
        'E   AssertionError'
    )
    frames, _ = parse_short_repr(text)
    assert frames[0].path == 'tests/unit/capture/test_x.py'
    assert frames[0].is_internal is False


def test_site_packages_frame_collapsed_to_venv_independent_tail() -> None:
    """The same dependency frame renders with a machine-specific venv prefix on
    different setups (`.nox/.../Lib/site-packages` on Windows, `$HOME/.../
    site-packages` on WSL); both collapse to the stable `site-packages/...` tail
    so reports don't churn between environments."""
    windows, _ = parse_short_repr(
        '.nox/examples/Lib/site-packages/_pytest/runner.py:1: in from_call\n'
        '    func()\nE   AssertionError'
    )
    wsl, _ = parse_short_repr(
        '/home/me/.local/share/nox-envs/proj/examples/lib/python3.14/'
        'site-packages/_pytest/runner.py:1: in from_call\n'
        '    func()\nE   AssertionError'
    )
    assert windows[0].path == 'site-packages/_pytest/runner.py'
    assert wsl[0].path == 'site-packages/_pytest/runner.py'
    assert windows[0].is_internal is True
    assert wsl[0].is_internal is True


def test_pluggy_frame_classified_internal() -> None:
    text = (
        '.venv/lib/site-packages/pluggy/_hooks.py:512: in __call__\n'
        '    return self._hookexec(...)\n'
        'E   AssertionError'
    )
    frames, _ = parse_short_repr(text)
    assert frames[0].is_internal is True


def test_pytest_given_wrapper_frame_classified_internal() -> None:
    text = (
        'src/pytest_given/capture/decorators.py:191: in wrapper\n'
        '    return func(*args, **kwargs)\n'
        'E   AssertionError'
    )
    frames, _ = parse_short_repr(text)
    assert frames[0].is_internal is True


def test_third_party_library_not_internal() -> None:
    text = (
        '.venv/lib/site-packages/hypothesis/strategies.py:42: in draw\n'
        '    raise BadStrategy()\n'
        'E   BadStrategy'
    )
    frames, _ = parse_short_repr(text)
    assert frames[0].is_internal is False


def test_frame_without_tail_is_flushed() -> None:
    text = 'tests/t.py:5: in g\n    do_thing()'
    frames, tail = parse_short_repr(text)
    assert len(frames) == 1
    assert frames[0].func == 'g'
    assert frames[0].code == '    do_thing()'
    assert tail is None


def test_user_test_file_not_internal() -> None:
    text = 'tests/test_billing.py:10: in test_buy\n    assert False\nE   assert False'
    frames, _ = parse_short_repr(text)
    assert frames[0].is_internal is False


def test_absolute_user_frame_relativized_to_rootdir(tmp_path: Path) -> None:
    """A project/user frame that arrives absolute (e.g. a stale cross-environment
    `.pyc` makes pytest emit the file's absolute path) is folded back to a
    rootdir-relative path so reports don't leak a machine-specific location."""
    _reset_rootdir()
    set_rootdir(tmp_path)
    try:
        target = tmp_path / 'tests' / 'test_x.py'
        text = f'{target.as_posix()}:5: in test_x\n    assert False\nE   AssertionError'
        frames, _ = parse_short_repr(text)
        assert frames[0].path == 'tests/test_x.py'
        assert frames[0].lineno == 5
    finally:
        _reset_rootdir()
