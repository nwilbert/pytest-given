"""The delta's sinks, JSON and HTML, written as a set like a report's."""

import json
from dataclasses import dataclass
from pathlib import Path

from ..model import DeltaData, JsonObject, delta_from_dict
from .delta_html import render_delta_html
from .sinks import RenderedFile, emit_files, failure_discarding, require_suffix
from .theme import DEFAULT_THEME, Theme

DEFAULT_DELTA_JSON_PATH = Path('given-report/delta-data.json')
DEFAULT_DELTA_HTML_PATH = Path('given-report/delta.html')


@dataclass(frozen=True)
class DeltaSinkConfig:
    json_path: Path | None = None
    html_path: Path | None = None
    source_link_template: str | None = None
    theme: Theme = DEFAULT_THEME

    def __post_init__(self) -> None:
        require_suffix('JSON', self.json_path, ('.json',))
        require_suffix('HTML', self.html_path, ('.html', '.htm'))

    def file_paths(self) -> list[Path]:
        return [path for path in (self.json_path, self.html_path) if path is not None]


@dataclass(frozen=True)
class RenderedDelta:
    """The delta as its sinks read it back, and the files they render."""

    delta: DeltaData
    files: list[RenderedFile]


def emit_delta_sinks(
    delta_dict: JsonObject, config: DeltaSinkConfig, source: str | None = None
) -> RenderedDelta:
    """Render and write both sinks, or leave neither behind — the previous
    delta included, as `emit_sinks` does for a report. A dict that is no delta
    fails here too."""
    return emit_files(
        lambda: _render_delta_sinks(delta_dict, config, source), config.file_paths()
    )


def delta_sink_failure(error: Exception, config: DeltaSinkConfig) -> str:
    """The failure, and what discarding the previous delta did — for a delta
    that fails before `emit_delta_sinks` too, like `sink_failure`."""
    return failure_discarding(error, config.file_paths())


def _render_delta_sinks(
    delta_dict: JsonObject, config: DeltaSinkConfig, source: str | None
) -> RenderedDelta:
    """The HTML renders from a copy read back through serde, so it shows only
    what the JSON can express."""
    delta = delta_from_dict(delta_dict, source)
    files: list[RenderedFile] = []
    if config.json_path is not None:
        files.append(RenderedFile(config.json_path, json.dumps(delta_dict, indent=2)))
    if config.html_path is not None:
        files.append(
            RenderedFile(
                config.html_path,
                render_delta_html(delta, config.source_link_template, config.theme),
            )
        )
    return RenderedDelta(delta, files)
