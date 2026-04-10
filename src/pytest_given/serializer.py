from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pytest_given.model import (
    Attachment,
    ErrorInfo,
    Metadata,
    ParameterCase,
    ParameterTable,
    ReportData,
    Scenario,
    Step,
)


def write_json(report: ReportData, path: Path) -> None:
    """Serialize report data and write to a JSON file."""
    data = serialize_report(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def serialize_report(report: ReportData) -> dict[str, Any]:
    """Convert a ReportData to a JSON-serializable dict."""
    return {
        'metadata': _serialize_metadata(report.metadata),
        'scenarios': [_serialize_scenario(s) for s in report.scenarios],
    }


def _serialize_metadata(meta: Metadata) -> dict[str, Any]:
    return {
        'project': meta.project,
        'timestamp': meta.timestamp,
        'pytest_version': meta.pytest_version,
        'plugin_version': meta.plugin_version,
    }


def _serialize_scenario(scenario: Scenario) -> dict[str, Any]:
    return {
        'id': scenario.id,
        'name': scenario.name,
        'module': scenario.module,
        'tags': scenario.tags,
        'status': scenario.status,
        'duration_ms': scenario.duration_ms,
        'steps': [_serialize_step(s) for s in scenario.steps],
        'parameters': (
            _serialize_parameter_table(scenario.parameters)
            if scenario.parameters
            else None
        ),
        'error': _serialize_error(scenario.error) if scenario.error else None,
    }


def _serialize_step(step: Step) -> dict[str, Any]:
    return {
        'phase': step.phase,
        'text': step.text,
        'status': step.status,
        'source': step.source,
        'children': [_serialize_step(c) for c in step.children],
        'attachments': [_serialize_attachment(a) for a in step.attachments],
        'error': _serialize_error(step.error) if step.error else None,
    }


def _serialize_parameter_table(table: ParameterTable) -> dict[str, Any]:
    return {
        'names': table.names,
        'cases': [_serialize_parameter_case(c) for c in table.cases],
    }


def _serialize_parameter_case(case: ParameterCase) -> dict[str, Any]:
    return {
        'values': case.values,
        'status': case.status,
        'error': _serialize_error(case.error) if case.error else None,
    }


def _serialize_attachment(att: Attachment) -> dict[str, Any]:
    return {'label': att.label, 'content': att.content}


def _serialize_error(err: ErrorInfo) -> dict[str, Any]:
    result: dict[str, Any] = {'message': err.message}
    result['diff'] = err.diff
    return result
