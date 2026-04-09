import json
import subprocess
import sys
from pathlib import Path


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
    result = subprocess.run(
        [sys.executable, '-m', 'pytest_given.cli', 'report', str(json_path), '-o', str(html_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert html_path.exists()
    assert 'cli-test' in html_path.read_text()


def test_cli_missing_input_file(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, '-m', 'pytest_given.cli', 'report', str(tmp_path / 'nonexistent.json')],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
