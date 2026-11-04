import dataclasses
import hashlib
import re
import typing

from pytest_given.model import (
    DELTA_SCHEMA_VERSION,
    REPORT_SCHEMA_VERSION,
    DeltaData,
    ReportData,
)

PINNED_REPORT_SCHEMA = (
    1,
    '7f19299099e9d7509c95b386c28be7a7997fbd9f6349713a4e57357d9bd02713',
)

PINNED_DELTA_SCHEMA = (
    1,
    'c21c885c95b33522bc5f4f9186638b7ad4b22de7d4862cbaea4d43256800144b',
)


def schema_fingerprint(root: type) -> str:
    """sha256 over every dataclass reachable from `root`: class name, and per
    serialized field its name, unqualified type-hint repr, and whether it has
    a default. Skips `_`-prefixed and `serde_exclude` fields, as serde does.
    Each reachable `type` alias adds its expansion, as a hint names it only."""
    dataclasses_found, aliases_found = _reachable(root)
    lines = [
        f'type {alias.__name__} = {_hint_text(alias.__value__)}'
        for alias in sorted(aliases_found, key=lambda alias: alias.__name__)
    ]
    for dataclass in sorted(dataclasses_found, key=lambda cls: cls.__name__):
        hints = typing.get_type_hints(dataclass)
        lines.append(f'class {dataclass.__name__}')
        for field in _serialized_fields(dataclass):
            has_default = (
                field.default is not dataclasses.MISSING
                or field.default_factory is not dataclasses.MISSING
            )
            lines.append(
                f'  {field.name}: {_hint_text(hints[field.name])} default={has_default}'
            )
    return hashlib.sha256('\n'.join(lines).encode()).hexdigest()


def test_the_report_schema_version_moves_with_its_shape() -> None:
    assert (REPORT_SCHEMA_VERSION, schema_fingerprint(ReportData)) == (
        PINNED_REPORT_SCHEMA
    ), 'The report JSON changed shape: bump REPORT_SCHEMA_VERSION and re-pin.'


def test_the_delta_schema_version_moves_with_its_shape() -> None:
    assert (DELTA_SCHEMA_VERSION, schema_fingerprint(DeltaData)) == (
        PINNED_DELTA_SCHEMA
    ), 'The delta JSON changed shape: bump DELTA_SCHEMA_VERSION and re-pin.'


def _hint_text(hint: object) -> str:
    """A hint's repr with its dotted qualifiers dropped: Python 3.15 qualifies a
    `type` alias by its module, 3.14 does not."""
    return re.sub(r'\b(?:[A-Za-z_]\w*\.)+(?=[A-Za-z_])', '', repr(hint))


def _serialized_fields(dataclass: type) -> list[dataclasses.Field[object]]:
    return [
        field
        for field in dataclasses.fields(dataclass)
        if not field.name.startswith('_') and not field.metadata.get('serde_exclude')
    ]


def _reachable(root: type) -> tuple[set[type], set[typing.TypeAliasType]]:
    found_classes: set[type] = set()
    found_aliases: set[typing.TypeAliasType] = set()
    pending: list[object] = [root]
    while pending:
        current = pending.pop()
        if isinstance(current, typing.TypeAliasType):
            if current not in found_aliases:
                found_aliases.add(current)
                pending.append(current.__value__)
        elif isinstance(current, type) and dataclasses.is_dataclass(current):
            if current not in found_classes:
                found_classes.add(current)
                hints = typing.get_type_hints(current)
                pending.extend(
                    hints[field.name] for field in _serialized_fields(current)
                )
        else:
            pending.extend(typing.get_args(current))
    return found_classes, found_aliases
