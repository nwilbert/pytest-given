import json
from pathlib import Path

from pytest_given.cli import main


def test_cli_generates_html(tmp_path: Path) -> None:
    json_path = tmp_path / 'data.json'
    json_path.write_text(
        json.dumps(
            {
                'metadata': {
                    'project': 'cli-test',
                    'timestamp': '2026-04-09',
                    'pytest_version': '9',
                    'plugin_version': '0.1',
                },
                'scenarios': [],
            }
        )
    )
    html_path = tmp_path / 'out.html'
    rc = main(['report', str(json_path), '-o', str(html_path)])
    assert rc == 0
    assert html_path.exists()
    assert 'cli-test' in html_path.read_text()


def test_cli_missing_input_file(tmp_path: Path) -> None:
    rc = main(['report', str(tmp_path / 'nonexistent.json')])
    assert rc == 1


def test_cli_no_command() -> None:
    rc = main([])
    assert rc == 1
