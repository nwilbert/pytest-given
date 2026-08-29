"""The sinks a run writes, rendered as a set and written as a set.

A run may be told to write any combination of JSON, HTML and Markdown, and
they have to agree with each other: a render that raises must not leave this
run's JSON beside the previous run's HTML, with nothing on either saying so.
So rendering and writing are separate steps — `render_sinks` does everything
that can fail and touches no file, `write_sinks` touches files and cannot fail
on content.

Pytest-free like the rest of `report/`: the caller resolves its options into a
`SinkConfig`, which is also what lets `pytest-given report` reach the same code.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..model import ReportData
from .html_renderer import render_html_string
from .md_renderer import render_md


@dataclass(frozen=True)
class SinkConfig:
    """Which sinks a run was told to write, and how to render them.

    `md_to_stdout` is its own flag rather than a sentinel path, so nothing
    downstream has to know that a bare `--given-md` means `-`.
    """

    json_path: Path | None = None
    html_path: Path | None = None
    md_path: Path | None = None
    md_to_stdout: bool = False
    source_link_template: str | None = None

    def file_paths(self) -> list[Path]:
        """The paths this run would write, in sink order. Only real files —
        Markdown bound for stdout has no path to overwrite or discard."""
        return [
            path
            for path in (self.json_path, self.html_path, self.md_path)
            if path is not None
        ]

    def writes_anything(self) -> bool:
        """Whether any sink is configured — `file_paths()` plus stdout Markdown,
        which writes no file but still has to be rendered."""
        return bool(self.file_paths()) or self.md_to_stdout


@dataclass(frozen=True)
class RenderedSinks:
    """Every configured sink rendered to text, before any of them is written."""

    files: list[tuple[Path, str]] = field(default_factory=list)
    md_stdout: str | None = None


def render_sinks(
    report: ReportData, report_dict: dict[str, Any], config: SinkConfig
) -> RenderedSinks:
    """Render the configured sinks to text. Nothing here touches the filesystem.

    `report_dict` is the already-serialized report — the JSON sink writes it
    verbatim, so the two sinks cannot disagree about what was serialized.
    """
    files: list[tuple[Path, str]] = []
    if config.json_path is not None:
        files.append((config.json_path, json.dumps(report_dict, indent=2)))
    if config.html_path is not None:
        files.append(
            (
                config.html_path,
                render_html_string(
                    report, source_link_template=config.source_link_template
                ),
            )
        )
    md_stdout: str | None = None
    if config.md_path is not None or config.md_to_stdout:
        md = render_md(report)
        if config.md_to_stdout:
            md_stdout = md
        if config.md_path is not None:
            files.append((config.md_path, md))
    return RenderedSinks(files=files, md_stdout=md_stdout)


def write_sinks(rendered: RenderedSinks) -> None:
    for path, text in rendered.files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')


def discard_stale_sinks(config: SinkConfig) -> list[str]:
    """Delete the sinks this run would have written, and say which.

    Writing no report leaves the *previous* run's in place, where it reads as
    current — the one outcome worse than no report at all. Only the paths this
    run was told to write are touched.
    """
    removed = []
    for path in config.file_paths():
        if not path.is_file():
            continue
        path.unlink()
        removed.append(f'Removed the previous {path} — it would read as current.')
    return removed
