"""The delta's sinks, JSON and HTML, written as a set like a report's."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..model import DeltaData, JsonObject, delta_from_dict
from .delta_html import render_delta_html
from .sinks import RenderedFile, emit_files, require_suffix
from .theme import DEFAULT_THEME, Theme


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
    load: Callable[[], tuple[JsonObject, str | None]], config: DeltaSinkConfig
) -> RenderedDelta:
    """Load the delta dict and where it came from, render and write both sinks,
    or leave neither behind — the previous delta included, as `emit_sinks` does
    for a report: a delta that can't be built or isn't one fails the same way."""
    return emit_files(lambda: _render_delta_sinks(load, config), config.file_paths())


def _render_delta_sinks(
    load: Callable[[], tuple[JsonObject, str | None]], config: DeltaSinkConfig
) -> RenderedDelta:
    """The HTML renders from a copy read back through serde, so it shows only
    what the JSON can express."""
    delta_dict, source = load()
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
