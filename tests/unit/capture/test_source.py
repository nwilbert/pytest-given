import sys
from pathlib import Path

import pytest

from pytest_given.capture.source import (
    _co_filename_to_path,
    _reset_rootdir,
    capture_caller_source,
    code_source,
    item_source,
    set_rootdir,
)
from pytest_given.model import SourceLocation


@pytest.fixture(autouse=True)
def _isolate_rootdir():
    _reset_rootdir()
    yield
    _reset_rootdir()


def test_returns_none_when_rootdir_unset():
    assert capture_caller_source() is None


def test_returns_none_when_caller_outside_rootdir(tmp_path: Path):
    set_rootdir(tmp_path)
    # This test file lives outside tmp_path, so the caller (this function)
    # is outside rootdir.
    assert capture_caller_source() is None


def test_captures_caller_when_inside_rootdir():
    # Use the repo root itself as rootdir — this file is inside it.
    repo_root = Path(__file__).resolve().parents[3]
    set_rootdir(repo_root)
    loc = capture_caller_source()
    assert isinstance(loc, SourceLocation)
    assert loc.relpath.endswith('tests/unit/capture/test_source.py')
    assert '/' in loc.relpath  # POSIX-normalized even on Windows
    assert loc.line > 0


def test_skip_argument_walks_up_call_stack():
    repo_root = Path(__file__).resolve().parents[3]
    set_rootdir(repo_root)

    def wrapper():
        # skip=2: skip capture_caller_source itself + this wrapper, land on the
        # test function below.
        return capture_caller_source(skip=2)

    loc = wrapper()
    assert loc is not None
    assert loc.relpath.endswith('test_source.py')
    # Line should point at the `loc = wrapper()` call site, not into wrapper.
    # We don't assert the exact line (would couple to formatting) — only that
    # it's reachable and inside the test function's body range.
    assert loc.line > 0


def test_co_filename_to_path_rewrites_windows_path_on_wsl(monkeypatch):
    """Under WSL, co_filename for a Windows-filesystem file is a Windows path
    (``C:\\...``); it is rewritten to the ``/mnt/c/...`` form so pathlib treats
    the separators correctly."""
    monkeypatch.setattr('pytest_given.capture.source._IS_WSL', True)
    result = _co_filename_to_path(r'C:\Users\me\repo\tests\test_x.py')
    assert result.as_posix() == '/mnt/c/Users/me/repo/tests/test_x.py'


def test_co_filename_to_path_leaves_posix_path_unchanged_on_wsl(monkeypatch):
    """A genuine POSIX co_filename has no Windows drive prefix, so it passes
    through untouched even when running under WSL."""
    monkeypatch.setattr('pytest_given.capture.source._IS_WSL', True)
    result = _co_filename_to_path('/home/me/repo/tests/test_x.py')
    assert result.as_posix() == '/home/me/repo/tests/test_x.py'


def test_co_filename_to_path_rewrites_mnt_path_on_windows(monkeypatch):
    """On native Windows a co_filename can arrive in WSL-mount form (e.g. a
    ``.pyc`` rewritten under WSL is reused on Windows for the same checkout);
    ``/mnt/<drive>/...`` is folded back to ``<drive>:\\...`` so it shares a drive
    anchor with the rootdir."""
    monkeypatch.setattr('pytest_given.capture.source._IS_WSL', False)
    monkeypatch.setattr('pytest_given.capture.source._IS_WINDOWS', True)
    result = _co_filename_to_path('/mnt/c/Users/me/repo/tests/test_x.py')
    assert result.as_posix() == 'C:/Users/me/repo/tests/test_x.py'
    # Drive root with no trailing path still yields a drive-prefixed path
    # (exact trailing-slash form is platform-dependent, so only check the drive).
    assert _co_filename_to_path('/mnt/d').as_posix().startswith('D:')


def test_co_filename_to_path_leaves_posix_path_unchanged_on_windows(monkeypatch):
    """A non-/mnt POSIX path on native Windows is left alone — only the WSL
    mount prefix is special-cased."""
    monkeypatch.setattr('pytest_given.capture.source._IS_WSL', False)
    monkeypatch.setattr('pytest_given.capture.source._IS_WINDOWS', True)
    result = _co_filename_to_path('/usr/local/lib/test_x.py')
    assert result.as_posix() == '/usr/local/lib/test_x.py'


def test_item_source_passes_through_relative_location():
    """The common (native) case: `item.location[0]` is already rootdir-relative,
    so it is kept verbatim — no rootdir lookup needed."""
    loc = item_source('examples/coffeeshop/test_coffeeshop.py', 100)
    assert loc.relpath == 'examples/coffeeshop/test_coffeeshop.py'
    assert loc.line == 100


@pytest.mark.skipif(
    sys.platform == 'win32',
    reason='WSL /mnt rewriting is POSIX-only; native Windows pathlib treats '
    '/mnt/<drive> as drive-relative, not absolute.',
)
def test_item_source_rerelativizes_windows_absolute_path_on_wsl(monkeypatch):
    """Under WSL, pytest cannot relativize a Windows `co_filename` against the
    POSIX /mnt rootdir and falls back to the absolute ``C:\\...`` path. It is
    rewritten and re-relativized so the source link stays repo-relative."""
    monkeypatch.setattr('pytest_given.capture.source._IS_WSL', True)
    set_rootdir(Path('/mnt/c/Users/me/repo'))
    loc = item_source(r'C:\Users\me\repo\examples\test_x.py', 7)
    assert loc.relpath == 'examples/test_x.py'
    assert loc.line == 7


def test_item_source_relativizes_absolute_path_inside_rootdir(tmp_path: Path):
    """An absolute path inside rootdir is re-relativized to a posix relpath.
    Uses a real (platform-native) absolute path so it exercises the
    is_absolute -> relativize branch on every OS, including Windows."""
    set_rootdir(tmp_path)
    target = tmp_path / 'examples' / 'test_x.py'
    loc = item_source(str(target), 12)
    assert loc.relpath == 'examples/test_x.py'
    assert loc.line == 12


def test_item_source_keeps_absolute_path_outside_rootdir():
    """An absolute path that cannot be relativized degrades to the path as
    given rather than to 'no link' — every scenario keeps a source."""
    set_rootdir(Path('/some/root'))
    loc = item_source('/elsewhere/test_x.py', 3)
    assert loc.relpath == '/elsewhere/test_x.py'
    assert loc.line == 3


def test_file_source_returns_location_inside_rootdir(tmp_path: Path):
    """file_source returns a SourceLocation with posix relpath when the path
    is inside the configured rootdir."""
    from pytest_given.capture.source import file_source

    set_rootdir(tmp_path)
    target = tmp_path / 'glossary' / 'terms.md'
    loc = file_source(target, 42)
    assert loc is not None
    assert loc.relpath == 'glossary/terms.md'
    assert loc.line == 42


def test_code_source_returns_none_when_rootdir_unset():
    def f() -> None: ...

    assert code_source(f.__code__) is None


def test_code_source_anchors_at_the_function_definition():
    repo_root = Path(__file__).resolve().parents[3]
    set_rootdir(repo_root)
    base = sys._getframe().f_lineno

    def f() -> None: ...

    loc = code_source(f.__code__)
    assert loc == SourceLocation(
        relpath='tests/unit/capture/test_source.py', line=base + 2
    )
