from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Attachment:
    label: str
    content: str


@dataclass
class ErrorInfo:
    message: str
    diff: str | None = None


@dataclass
class Step:
    phase: str  # 'given', 'when', 'then'
    text: str
    status: str = 'passed'
    source: str | None = None  # 'fixture' if from a decorated fixture
    children: list[Step] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    error: ErrorInfo | None = None


@dataclass
class ParameterCase:
    values: list[Any]
    status: str = 'passed'
    error: ErrorInfo | None = None


@dataclass
class ParameterTable:
    names: list[str]
    cases: list[ParameterCase] = field(default_factory=list)


@dataclass
class Scenario:
    id: str
    name: str
    module: str
    tags: list[str] = field(default_factory=list)
    status: str = 'passed'
    duration_ms: int = 0
    steps: list[Step] = field(default_factory=list)
    parameters: ParameterTable | None = None
    error: ErrorInfo | None = None


@dataclass
class Metadata:
    project: str
    timestamp: str
    pytest_version: str
    plugin_version: str


@dataclass
class ReportData:
    metadata: Metadata
    scenarios: list[Scenario] = field(default_factory=list)
