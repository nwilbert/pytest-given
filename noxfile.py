import webbrowser
from pathlib import Path

import nox

# Linted and formatted everywhere; `tests` and `examples` are test code and are
# deliberately not type-checked (heavy fixtures and loose dicts).
code_paths = ['src', 'tests', 'examples', 'noxfile.py']
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


def _sync(session: nox.Session, *groups: str, include_project: bool = False) -> None:
    if include_project:
        group_args = [arg for group in groups for arg in ('--group', group)]
        session.run(
            'uv',
            'sync',
            '--no-default-groups',
            *group_args,
            '--exact',
            '--active',
            external=True,
        )
    else:
        group_args = [arg for group in groups for arg in ('--only-group', group)]
        session.run(
            'uv',
            'sync',
            *group_args,
            '--exact',
            '--active',
            '--no-install-project',
            external=True,
        )


@nox.session
def format(session: nox.Session) -> None:
    _sync(session, 'lint')
    session.run('ruff', 'check', '--select', 'I', '--fix', *code_paths)
    session.run('ruff', 'format', *session.posargs, *code_paths)


@nox.session
def lint(session: nox.Session) -> None:
    _sync(session, 'lint')
    session.run('ruff', 'check', *session.posargs, *code_paths)


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
    session.run(
        'uv',
        'sync',
        '--all-groups',
        '--exact',
        '--active',
        external=True,
    )
    session.run('pip-audit', '--local')


@nox.session
def examples(session: nox.Session) -> None:
    """Regenerate coffeeshop, hotel-booking, and file-glossary-booking reports."""
    _sync(session, 'test', include_project=True)
    for test_file, slug in [
        ('examples/coffeeshop/test_coffeeshop.py', 'coffeeshop'),
        ('examples/hotel-booking/test_hotel_booking.py', 'hotel-booking'),
        (
            'examples/file-glossary-booking/test_file_glossary_booking.py',
            'file-glossary-booking',
        ),
    ]:
        session.run(
            'pytest',
            test_file,
            f'--given-json=examples/{slug}/{slug}-data.json',
            '--given-html',
            f'--given-html-output=examples/{slug}/{slug}.html',
            '--given-source-link=github',
            '--tb=no',
            '--no-header',
            '-q',
            success_codes=[0, 1],
        )
    session.log(
        'Note: coffeeshop and hotel-booking have intentional failures for failure '
        'rendering (coffeeshop: test_failing; hotel-booking: gift-card decline case). '
        'file-glossary-booking has no intentional failures.'
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
        '--given-html',
        '--given-html-output=benchmarks/large-scenarios.html',
        '--given-source-link=github',
        '--tb=no',
        '--no-header',
        '-q',
        success_codes=[0, 1],
    )
