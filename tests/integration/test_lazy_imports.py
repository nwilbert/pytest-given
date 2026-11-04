import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 15), reason='lazy imports arrive in Python 3.15'
)


@pytest.mark.parametrize('entry_point', ['pytest_given.plugin', 'pytest_given.cli'])
def test_an_entry_point_loads_no_renderer_or_parser_until_used(
    entry_point: str,
) -> None:
    code = (
        f'import sys, {entry_point}; '
        "print(sorted({'jinja2', 'markdown_it', 'markupsafe'} & set(sys.modules)))"
    )
    loaded = subprocess.run(
        [sys.executable, '-c', code],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert loaded.strip() == '[]'


def test_the_plugin_loads_no_delta_renderer() -> None:
    code = (
        'import sys, pytest_given.plugin; '
        'print(sorted(name for name in sys.modules '
        "if name.startswith('pytest_given.report.delta')))"
    )
    loaded = subprocess.run(
        [sys.executable, '-c', code],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert loaded.strip() == '[]'
