import os
import sys
from pathlib import Path

import pytest

from pytest_given.capture import collector, source
from pytest_given.capture.source import (
    _co_filename_to_path,
    capture_caller_source,
    code_source,
    file_source,
    item_source,
    restore_rootdir,
    set_rootdir,
)
from pytest_given.model import SourceLocation


@pytest.fixture(autouse=True)
def _isolate_rootdir():
    restore_rootdir(None)
    yield
    restore_rootdir(None)


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


def test_package_root_prefixes_a_real_internal_frame_filename():
    """A hardcoded '/' here matches nothing on native Windows, and every story
    and term then silently records `source=None`."""
    assert source.PACKAGE_ROOT.endswith(os.sep)
    assert source.__file__.startswith(source.PACKAGE_ROOT)
    assert collector.__file__.startswith(source.PACKAGE_ROOT)


def test_the_walk_passes_over_frames_inside_the_package():
    """The anchor is the nearest frame *outside* `pytest_given/`, so a helper
    added anywhere in the chain cannot silently move it."""
    repo_root = Path(__file__).resolve().parents[3]
    set_rootdir(repo_root)

    def wrapper():
        return capture_caller_source()

    loc = wrapper()
    assert loc is not None
    assert loc.relpath.endswith('test_source.py')
    # `wrapper` is the nearest frame outside the package, so it is the anchor —
    # the walk stops at user code, wherever in user code that is.
    assert loc.line == wrapper.__code__.co_firstlineno + 1


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
    set_rootdir(tmp_path)
    target = tmp_path / 'glossary' / 'terms.md'
    loc = file_source(target, 42)
    assert loc is not None
    assert loc.relpath == 'glossary/terms.md'
    assert loc.line == 42


def test_resolution_is_cached_per_path(tmp_path: Path, monkeypatch):
    """`Path.resolve` walks every path component on disk (one lstat each),
    which dominates lint-enabled runs on slow mounts. The rootdir-relative
    result is memoized per path so repeated captures from the same file
    resolve only once."""
    set_rootdir(tmp_path)
    target = tmp_path / 'test_a.py'
    calls = 0
    real_resolve = Path.resolve

    def counting_resolve(self: Path, strict: bool = False) -> Path:
        nonlocal calls
        calls += 1
        return real_resolve(self, strict=strict)

    monkeypatch.setattr(Path, 'resolve', counting_resolve)
    assert file_source(target, 1) == SourceLocation(relpath='test_a.py', line=1)
    assert file_source(target, 2) == SourceLocation(relpath='test_a.py', line=2)
    assert calls == 1


def test_cached_resolution_is_dropped_when_rootdir_changes(tmp_path: Path):
    """A cached relpath is only valid for the rootdir it was computed against;
    `set_rootdir` must invalidate it or a pytester-style second session would
    see the first session's relpaths."""
    root_a = tmp_path / 'a'
    root_a.mkdir()
    set_rootdir(root_a)
    target = root_a / 'f.py'
    assert file_source(target, 1) is not None  # primes the cache
    set_rootdir(tmp_path / 'b')
    assert file_source(target, 1) is None


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


def test_a_stack_that_never_leaves_the_package_has_no_anchor(monkeypatch):
    """The walk stops at the first frame outside `pytest_given/`; with no such
    frame there is no user code to point at, and no link is the honest answer."""
    monkeypatch.setattr(source, 'PACKAGE_ROOT', '')
    assert capture_caller_source() is None
