from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pytest_given.model import ReportData


def write_json(report: ReportData, path: Path) -> None:
    """Serialize report data and write to a JSON file."""
    data = serialize_report(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def serialize_report(report: ReportData) -> dict[str, Any]:
    """Convert a ReportData to a JSON-serializable dict."""
    return asdict(report)
