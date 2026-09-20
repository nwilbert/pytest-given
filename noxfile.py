import base64
import json
import re
import shutil
import tempfile
import webbrowser
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
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
_WHEEL_SKILLS_DIR = 'pytest_given/.agents/skills/'
_REQUIRED_WHEEL_PATHS = (
    'pytest_given/py.typed',
    'pytest_given/report/templates/',
    'pytest_given/report/templates/fonts/',
    _WHEEL_SKILLS_DIR,
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
    _sync(session, 'build')
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
    _check_library_skills_discovery(session, wheel, names)
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
    with _throwaway_workdir(session) as workdir:
        (workdir / 'test_smoke.py').write_text(_SMOKE_TEST, encoding='utf-8')
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


@contextmanager
def _throwaway_workdir(session: nox.Session) -> Iterator[Path]:
    """Run the block from a fresh temporary directory, then restore the cwd."""
    project_root = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        session.chdir(workdir)
        try:
            yield workdir
        finally:
            # Windows cannot remove a directory that is still the cwd.
            session.chdir(project_root)


# `library-skills scan` lists skills of the project's direct dependencies only,
# so the throwaway consumer has to name pytest-given as one.
_CONSUMER_PYPROJECT = """[project]
name = "consumer"
version = "0.0.0"
dependencies = ["pytest-given"]
"""


def _check_library_skills_discovery(
    session: nox.Session, wheel: Path, names: list[str]
) -> None:
    """Verify that `library-skills` discovers every skill the wheel carries.

    `_REQUIRED_WHEEL_PATHS` only proves the skills directory is in the wheel;
    this proves the scanner's convention (`.agents/skills/<name>/SKILL.md`,
    name matching the directory) holds for each skill, which is what makes
    `uvx library-skills install` work for consumers.
    """
    expected = sorted(
        name.removeprefix(_WHEEL_SKILLS_DIR).removesuffix('/SKILL.md')
        for name in names
        if name.startswith(_WHEEL_SKILLS_DIR) and name.endswith('/SKILL.md')
    )
    assert expected, f'{wheel.name} carries no SKILL.md under {_WHEEL_SKILLS_DIR}'
    with _throwaway_workdir(session) as workdir:
        (workdir / 'pyproject.toml').write_text(_CONSUMER_PYPROJECT, encoding='utf-8')
        session.run('uv', 'venv', '--quiet', '.venv', external=True)
        session.run(
            'uv',
            'pip',
            'install',
            '--quiet',
            '--python',
            '.venv',
            str(wheel),
            external=True,
        )
        # nox exports UV_PROJECT_ENVIRONMENT=<session venv>, which
        # library-skills honors before the nearest `.venv` — so point it
        # at the consumer's environment explicitly.
        scan = session.run(
            'library-skills',
            'scan',
            '--json',
            env={'UV_PROJECT_ENVIRONMENT': '.venv'},
            silent=True,
        )
    assert isinstance(scan, str)
    discovered = sorted(skill['name'] for skill in json.loads(scan)['skills'])
    if discovered != expected:
        session.error(
            f'library-skills discovered {discovered} in {wheel.name}, '
            f'expected {expected}'
        )
    session.log(f'library-skills discovers {", ".join(discovered)}')


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
            '--given-lint',
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


_DOCS_SITE = Path('docs/site')


def _build_docs(session: nox.Session) -> None:
    """Stage the files the site embeds, then build it strictly.

    The staged files are single-sourced elsewhere in the repo: the full-size
    diagram the Home page links to (the README copy, see `diagram`), and every
    example's rendered report (one `<name>/<name>.html` per example directory).
    Each copy lands under docs_dir (Zensical builds everything there and has no
    exclude list), and every target is gitignored. CHANGELOG.md needs no copy:
    docs/site/changelog.md embeds it with a pymdownx.snippets include.
    """
    _sync(session, 'docs')
    staged = [
        (_DIAGRAM_README_COPY, _DOCS_SITE / 'assets' / 'pytest-given-diagram-full.svg'),
        *(
            (report, _DOCS_SITE / 'examples' / report.name)
            for report in sorted(Path('examples').glob('*/*.html'))
        ),
    ]
    for source, target in staged:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        session.log(f'staged {source} -> {target}')
    # --clean: the page cache is keyed on the Markdown source alone, so an edited
    # snippet include (the diagram SVG, CHANGELOG.md) would otherwise go stale.
    session.run('zensical', 'build', '--strict', '--clean')


@nox.session
def docs_build(session: nox.Session) -> None:
    """Stage the embedded reports and full-size diagram, then build the site."""
    _build_docs(session)


_DIAGRAM_SOURCE = _DOCS_SITE / 'assets' / 'pytest-given-diagram.svg'
_DIAGRAM_FONT = (
    _DOCS_SITE / 'assets' / 'fonts' / 'source-sans-3-latin-wght-normal.woff2'
)
_DIAGRAM_README_COPY = Path('docs/pytest-given-diagram.svg')

# The site defines these tokens from the theme's variables (stylesheets/extra.css);
# the README copy has no theme, so it carries the resolved values, light first and
# dark under a prefers-color-scheme query. Keep in step with extra.css.
_DIAGRAM_TOKENS_LIGHT = {
    'bg': '#fff',
    'line': 'rgba(0, 0, 0, 0.55)',
    'panel': '#f5f5f5',
    'panel-edge': 'rgba(0, 0, 0, 0.32)',
    'people-fill': '#ead9f2',
    'people-ink': '#3f1d4e',
    'artifact-fill': '#5b2c6f',
    'artifact-ink': '#fff',
}
_DIAGRAM_TOKENS_DARK = {
    'bg': '#0b0c0f',
    'line': 'hsla(225, 15%, 90%, 0.56)',
    'panel': 'hsla(225, 20%, 10%, 1)',
    'panel-edge': 'hsla(225, 15%, 90%, 0.32)',
    'people-fill': '#352e3c',
    'people-ink': '#e4d3ec',
    'artifact-fill': '#c9a6dc',
    'artifact-ink': '#0b0c0f',
}


def _token_block(tokens: dict[str, str], indent: str) -> str:
    return ''.join(
        f'{indent}  --pg-diagram-{name}: {value};\n' for name, value in tokens.items()
    )


@nox.session(venv_backend='none')
def diagram(session: nox.Session) -> None:
    """Derive the README's standalone diagram from the site's inline SVG.

    On the site the SVG is inlined, so page CSS supplies the font and the colour
    tokens; GitHub and PyPI render the README copy as an image, so it embeds the
    Source Sans 3 subset the site already ships and resolves the tokens itself. A pure
    text transform: same inputs, same bytes. Rerun after editing the source SVG
    or the token lists above, and commit the result.
    """
    source = _DIAGRAM_SOURCE.read_text(encoding='utf-8')
    font = base64.b64encode(_DIAGRAM_FONT.read_bytes()).decode('ascii')
    standalone_style = (
        '  <style>\n'
        '    @font-face {\n'
        '      font-family: "Source Sans 3";\n'
        '      font-weight: 200 900;\n'
        f'      src: url("data:font/woff2;base64,{font}") format("woff2");\n'
        '    }\n'
        '    svg {\n'
        '      font-family: "Source Sans 3", system-ui, sans-serif;\n'
        + _token_block(_DIAGRAM_TOKENS_LIGHT, '    ')
        + '    }\n'
        '    @media (prefers-color-scheme: dark) {\n'
        '      svg {\n' + _token_block(_DIAGRAM_TOKENS_DARK, '      ') + '      }\n'
        '    }\n'
        '  </style>\n'
    )
    header = (
        '<!-- Generated by `nox -s diagram` from '
        'docs/site/assets/pytest-given-diagram.svg; edit that file, not this one. -->\n'
    )
    open_tag_end = source.index('>\n') + 2
    artwork_style_end = '  </style>\n'
    assert source.count(artwork_style_end) == 1
    standalone = (
        header
        + source[:open_tag_end].replace(
            '<svg ', '<svg xmlns="http://www.w3.org/2000/svg" ', 1
        )
        + standalone_style
        + source[open_tag_end:].replace(
            artwork_style_end,
            # Own background, so the label halos always match what they sit on.
            artwork_style_end
            + '  <rect width="1000" height="1000" fill="var(--pg-diagram-bg)"/>\n',
        )
    )
    _DIAGRAM_README_COPY.write_text(standalone, encoding='utf-8', newline='\n')
    session.log(f'wrote {_DIAGRAM_README_COPY}')


@nox.session
def docs_deploy(session: nox.Session) -> None:
    """Build the site strictly, then publish it to gh-pages with mike.

    `-- <version> [alias]`: `dev` for main, `<major.minor>` for a release,
    `latest` as the alias that the site root should follow.
    """
    if not 1 <= len(session.posargs) <= 2:
        session.error('usage: nox -s docs_deploy -- <version> [alias]')
    version, *aliases = session.posargs
    # mike runs its own (non-strict) build; this one is the gate.
    _build_docs(session)
    session.run('mike', 'deploy', '--push', '--update-aliases', version, *aliases)
    # The site root follows `latest` once a release exists; before that, `dev`.
    if 'latest' in aliases:
        session.run('mike', 'set-default', '--push', 'latest')
    elif version == 'dev':
        listing = session.run('mike', 'list', silent=True)
        assert isinstance(listing, str)
        if not re.search(r'\blatest\b', listing):
            session.run('mike', 'set-default', '--push', 'dev')


@nox.session
def self_report(session: nox.Session) -> None:
    """Regenerate the self-documentation report from pytest-given's own backend
    tests. The @scenario-decorated unit tests narrate the plugin's behavior in
    the vocabulary of GLOSSARY.md (loaded as a FileGlossary in tests/conftest.py).
    """
    _sync(session, 'test', include_project=True)
    # The whole backend suite: tests/unit narrates the internals, and
    # tests/integration narrates the plugin's outermost behavior through inner
    # pytester runs. Most of the @scenario text under tests/integration lives
    # in string literals fed to those inner runs, which own their own
    # collectors — only the outer, decorated tests reach this report.
    session.run(
        'pytest',
        'tests',
        '--given-json=examples/self-report/self-report-data.json',
        '--given-html=examples/self-report/self-report.html',
        '--given-md=examples/self-report/self-report.md',
        '--given-title=pytest-given Self-Report',
        '--given-source-link=github',
        # The backend suite has no intentional failures, so an error-level
        # lint finding turns this session red — a real gate.
        '--given-lint',
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
