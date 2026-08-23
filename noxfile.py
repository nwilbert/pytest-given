import shutil
import tempfile
import webbrowser
import zipfile
from pathlib import Path

import nox

# On WSL under /mnt, put virtualenvs on the Linux filesystem
_proc_version = Path('/proc/version')
if (
    _proc_version.exists()
    and 'microsoft' in _proc_version.read_text(encoding='utf-8').lower()
    and Path.cwd().is_relative_to('/mnt')
):
    nox.options.envdir = str(
        Path.home() / '.local' / 'share' / 'nox-envs' / 'pytest-given'
    )

# Linted and formatted everywhere; only `src` and this file are type-checked.
# `tests` and `examples` are test code (heavy fixtures and loose dicts),
# `benchmarks` is throwaway scripting, and `conftest.py` is a one-liner.
code_paths = ['src', 'tests', 'examples', 'benchmarks', 'noxfile.py', 'conftest.py']
mypy_paths = ['src', 'noxfile.py']

nox.options.default_venv_backend = 'uv'
nox.options.reuse_existing_virtualenvs = True
nox.options.sessions = [
    'format',
    'lint',
    'mypy',
    'test',
    'coverage',
    'audit',
]


_SYNC_FLAGS = ('--locked', '--active')


def _sync(session: nox.Session, *groups: str, include_project: bool = False) -> None:
    if include_project:
        group_args = [arg for group in groups for arg in ('--group', group)]
        session.run(
            'uv',
            'sync',
            '--no-default-groups',
            *group_args,
            *_SYNC_FLAGS,
            external=True,
        )
    else:
        group_args = [arg for group in groups for arg in ('--only-group', group)]
        session.run(
            'uv',
            'sync',
            *group_args,
            *_SYNC_FLAGS,
            '--no-install-project',
            external=True,
        )


@nox.session(name='format')
def format_code(session: nox.Session) -> None:
    if session.posargs:
        session.error('format takes no arguments; `lint` is the read-only check')
    _sync(session, 'lint')
    session.run('ruff', 'check', '--select', 'I', '--fix', *code_paths)
    session.run('ruff', 'format', *code_paths)


@nox.session
def lint(session: nox.Session) -> None:
    """The read-only gate: lint rules, then formatting drift. `format` fixes both."""
    _sync(session, 'lint')
    session.run('ruff', 'check', *code_paths)
    session.run('ruff', 'format', '--check', *code_paths)


@nox.session
def mypy(session: nox.Session) -> None:
    _sync(session, 'typecheck', include_project=True)
    session.run('mypy', *mypy_paths)


@nox.session
def test(session: nox.Session) -> None:
    _sync(session, 'test', include_project=True)
    session.run('pytest')


@nox.session
def coverage(session: nox.Session) -> None:
    _sync(session, 'coverage', include_project=True)
    session.run(
        'coverage',
        'run',
        '--source',
        'pytest_given',
        '-m',
        'pytest',
        'tests/unit',
        'tests/integration',
    )
    try:
        session.run('coverage', 'report', '--fail-under', '100', '--show-missing')
    finally:
        if 'html' in session.posargs:
            session.run('coverage', 'html', '--skip-covered')
            webbrowser.open((Path.cwd() / 'htmlcov' / 'index.html').as_uri())


@nox.session
def audit(session: nox.Session) -> None:
    # Not _sync: pip-audit needs every declared group plus the project.
    session.run(
        'uv',
        'sync',
        '--all-groups',
        *_SYNC_FLAGS,
        external=True,
    )
    session.run('pip-audit', '--local')


# Run from a throwaway directory against an installed pytest-given, by `build`
# (the freshly built wheel) and `check_release` (whatever an index serves).
# Kept inline rather than as a file under the project so the run cannot pick up
# the repo's rootdir conftest and silently fall back to importing `src/`.
_SMOKE_TEST = """\
from pytest_given import given, scenario, then, when


@scenario('An installed pytest-given records narration')
def test_smoke():
    with given('a freshly installed pytest-given'):
        installed = True
    with when('the plugin renders a report'):
        rendered = installed
    with then('narration is captured'):
        assert rendered
"""

# Wheel paths that no in-repo test can vouch for: the suite imports from
# `src/`, so a package-data file missing from the wheel passes every test here
# and only fails on a user's first install. A trailing slash means "this
# directory must contain something"; anything else must match a member exactly,
# so a stray `py.typed.bak` cannot satisfy the `py.typed` requirement.
_REQUIRED_WHEEL_PATHS = (
    'pytest_given/py.typed',
    'pytest_given/report/templates/',
    'pytest_given/skills_data/',
)


def _wheel_is_missing(required: str, names: list[str]) -> bool:
    if required.endswith('/'):
        return not any(name.startswith(required) for name in names)
    return required not in names


@nox.session
def build(session: nox.Session) -> None:
    """Build the wheel + sdist, then verify them the way a consumer would.

    Run before dispatching the release workflow; the workflow runs this same
    session, so a green run here means the artifacts are release-shaped.
    """
    dist = Path('dist')
    if dist.exists():
        shutil.rmtree(dist)
    session.run('uv', 'build', external=True)

    wheels = sorted(dist.glob('*.whl'))
    assert len(wheels) == 1, f'expected exactly one wheel, got {wheels}'
    wheel = wheels[0].resolve()

    names = zipfile.ZipFile(wheel).namelist()
    missing = [
        required
        for required in _REQUIRED_WHEEL_PATHS
        if _wheel_is_missing(required, names)
    ]
    if missing:
        session.error(f'{wheel.name} is missing {", ".join(missing)}')

    _smoke_test_install(session, '--with', str(wheel), described_as=wheel.name)
    session.log(f'{wheel.name} passed packaging checks and a live smoke run')


def _smoke_test_install(
    session: nox.Session, *install_args: str, described_as: str
) -> None:
    """Run the smoke scenario against a pytest-given installed by `install_args`.

    Runs from a throwaway directory: `--isolated --no-project` keeps uv from
    resolving this repo, and being outside the project keeps pytest from finding
    the rootdir conftest — together they guarantee the import under test is the
    installed distribution rather than `src/`.
    """
    project_root = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        (workdir / 'test_smoke.py').write_text(_SMOKE_TEST, encoding='utf-8')
        session.chdir(workdir)
        try:
            session.run(
                'uv',
                'run',
                '--isolated',
                '--no-project',
                *install_args,
                'pytest',
                'test_smoke.py',
                '--given-md=smoke.md',
                '--given-html=smoke.html',
                '-q',
                external=True,
            )
            narration = (workdir / 'smoke.md').read_text(encoding='utf-8')
            if 'narration is captured' not in narration:
                session.error(f'{described_as} produced a report without narration')
            if (workdir / 'smoke.html').stat().st_size < 10_000:
                session.error(f'{described_as} produced a suspiciously small report')
        finally:
            # Windows cannot remove a directory that is still the cwd.
            session.chdir(project_root)


@nox.session
def check_release(session: nox.Session) -> None:
    """Install pytest-given from an index and smoke-test what it serves.

    `uv run nox -s check_release` checks PyPI; `-- testpypi` checks TestPyPI.
    Verifies a release after the fact, so it is not in the default session list.
    """
    target = session.posargs[0] if session.posargs else 'pypi'
    if target not in ('pypi', 'testpypi'):
        session.error(f"unknown index {target!r}; expected 'pypi' or 'testpypi'")

    # uv caches index responses, so a rehearsal published moments ago can be
    # invisible without forcing a re-read.
    install_args = ['--refresh-package', 'pytest-given']
    if target == 'testpypi':
        install_args += [
            '--index',
            'https://test.pypi.org/simple/',
            # pytest and jinja2 are not on TestPyPI and must still resolve
            # against real PyPI.
            '--index-strategy',
            'unsafe-best-match',
            # Rehearsals publish `.devN` versions, which are excluded by default.
            '--prerelease',
            'allow',
        ]
    install_args += ['--with', 'pytest-given']

    _smoke_test_install(
        session, *install_args, described_as=f'pytest-given from {target}'
    )
    session.log(f'the {target} release of pytest-given passed a live smoke run')


@nox.session
def examples(session: nox.Session) -> None:
    """Regenerate coffeeshop, hotel-booking, and file-glossary-booking reports."""
    _sync(session, 'test', include_project=True)
    # coffeeshop runs with --given-all-frames so it demonstrates the "show
    # internal frames" toggle on a real failure; the others use the default
    # filter so they show the clean user-only frames most users see.
    for test_file, slug, title, extra in [
        (
            'examples/coffeeshop/test_coffeeshop.py',
            'coffeeshop',
            'Coffee Shop Example',
            ['--given-all-frames'],
        ),
        (
            'examples/hotel-booking/test_hotel_booking.py',
            'hotel-booking',
            'Hotel Booking Example',
            [],
        ),
        (
            'examples/file-glossary-booking/test_file_glossary_booking.py',
            'file-glossary-booking',
            'File Glossary Example',
            [],
        ),
    ]:
        session.run(
            'pytest',
            test_file,
            f'--given-json=examples/{slug}/{slug}-data.json',
            f'--given-html=examples/{slug}/{slug}.html',
            f'--given-md=examples/{slug}/{slug}.md',
            f'--given-title={title}',
            '--given-source-link=github',
            # These suites have intentional failures, so the run already
            # returns a tolerated exit 1 (success_codes below), which masks
            # error-level lint findings. The printed summary is the signal
            # here.
            '--given-lint=true',
            # `given_lint_ignore` in pyproject.toml scopes an exemption to the
            # backend suite in `tests/`. An entry that suppresses nothing is
            # an error-level `stale-ignore` by design, so leaving the list in
            # place would print a spurious error on every examples run — the
            # entry's node is never collected here. Clear it for this suite.
            '-o',
            'given_lint_ignore=',
            '--tb=no',
            '--no-header',
            '-q',
            *extra,
            success_codes=[0, 1],
        )
    session.log(
        'Note: coffeeshop and hotel-booking have intentional failures for failure '
        'rendering (coffeeshop: test_failing; hotel-booking: gift-card decline case). '
        'coffeeshop uses --given-all-frames to demonstrate the internal-frames '
        'toggle; hotel-booking uses the default filter. '
        'file-glossary-booking has no intentional failures.'
    )


@nox.session
def self_report(session: nox.Session) -> None:
    """Regenerate the self-documentation report from pytest-given's own backend
    tests. The @scenario-decorated unit tests narrate the plugin's behavior in
    the vocabulary of GLOSSARY.md (loaded as a FileGlossary in tests/conftest.py).
    """
    _sync(session, 'test', include_project=True)
    # Only tests/unit: the integration tests carry no @scenario functions of
    # their own (their @scenario code lives in string literals fed to inner
    # pytester runs, which own their collectors), so including them would only
    # slow the regeneration down.
    session.run(
        'pytest',
        'tests/unit',
        '--given-json=examples/self-report/self-report-data.json',
        '--given-html=examples/self-report/self-report.html',
        '--given-md=examples/self-report/self-report.md',
        '--given-title=pytest-given Self-Report',
        '--given-source-link=github',
        # The backend suite has no intentional failures, so an error-level
        # lint finding turns this session red — a real gate.
        '--given-lint=true',
        '--tb=no',
        '--no-header',
        '-q',
    )


@nox.session
def benchmark(session: nox.Session) -> None:
    """Generate the large-scenarios suite and produce its JSON+HTML report.

    Outputs land in `benchmarks/` and are gitignored. For size sweeps or
    cProfile runs, invoke `benchmarks/bench.py` directly (see its docstring).
    """
    _sync(session, 'test', include_project=True)
    session.run('python', 'benchmarks/gen_large_scenarios.py')
    session.run(
        'pytest',
        'benchmarks/test_large_scenarios.py',
        '--given-json=benchmarks/large-scenarios-data.json',
        '--given-html=benchmarks/large-scenarios.html',
        '--given-source-link=github',
        '--tb=no',
        '--no-header',
        '-q',
        success_codes=[0, 1],
    )
