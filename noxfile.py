import webbrowser
from pathlib import Path

import nox

src_path = 'src'
code_paths = [src_path, 'tests', 'noxfile.py']

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
    session.run('mypy', src_path)


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
    """Regenerate examples/report-data.json and examples/report.html."""
    _sync(session, 'test', include_project=True)
    session.run(
        'pytest',
        'examples/test_examples.py',
        '--given-json=examples/report-data.json',
        '--given-html',
        '--given-html-output=examples/report.html',
        '--given-source-link=github',
        '--tb=no',
        '--no-header',
        '-q',
        success_codes=[0, 1],
    )
    session.log(
        'Note: 1 intentional failure is expected (demonstrates failure rendering).'
    )
