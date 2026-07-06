"""Narration lint: rules that catch steps whose narration lies about their body.

Pure inspection of the built report model plus the AST of the step bodies the
run itself identified — no pytest imports — so every rule is unit-testable in
isolation. The plugin runs the rule passes at session finish, applies the
configured severities and ignore globs via `apply_config`, and surfaces the
findings per the design spec (docs/specs/proposed/2026-07-05-narration-lint-design.md).
"""

from __future__ import annotations

import ast
import dataclasses
import re
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
from typing import Literal, NewType

from ..model import NodeId, Scenario, SourceLocation, Step

type Level = Literal['off', 'warn', 'error']
type Surface = Literal['runtime', 'ast']

RuleId = NewType('RuleId', str)

# Pseudo-rule for ignore-list entries that suppressed nothing; always an
# error, never configurable or ignorable — the list stays honest by
# construction.
STALE_IGNORE = RuleId('stale-ignore')

_LEVELS: tuple[Level, ...] = ('off', 'warn', 'error')


@dataclass(frozen=True, kw_only=True)
class Finding:
    """One lint finding, ready for the terminal summary."""

    rule: RuleId
    severity: Level
    subject: str
    node_id: NodeId | None
    location: SourceLocation | None
    message: str


@dataclass(frozen=True, kw_only=True)
class LintRule:
    id: RuleId
    surface: Surface
    default: Level


# The rule catalog as data: config validation and docs stay in sync with this
# one table.
RULES: tuple[LintRule, ...] = (
    LintRule(id=RuleId('empty-step'), surface='ast', default='error'),
    LintRule(id=RuleId('then-without-check'), surface='ast', default='error'),
)

_RULES_BY_ID: dict[RuleId, LintRule] = {rule.id: rule for rule in RULES}

# Shape of a rule-scoped prefix in an ignore entry. Anything before the first
# ':' that does not match this (a node-id glob's path or '*', say) makes the
# whole entry a bare pattern.
_RULE_PREFIX_RE = re.compile(r'[a-z][a-z0-9-]*')


@dataclass(frozen=True, kw_only=True)
class IgnoreEntry:
    """One `given_lint_ignore` entry: a subject glob, optionally rule-scoped."""

    raw: str
    rule: RuleId | None
    pattern: str


def parse_rule_levels(lines: list[str]) -> dict[RuleId, Level]:
    """Parse `given_lint_rules` entries of the form ``rule-id=level``.

    Raises ValueError on a malformed entry, unknown rule id, or unknown level
    (the plugin maps that to a UsageError at configure time).
    """
    levels: dict[RuleId, Level] = {}
    for line in lines:
        rule_part, sep, level_part = line.partition('=')
        if not sep:
            raise ValueError(
                f'invalid given_lint_rules entry {line!r}; expected rule-id=level.'
            )
        rule = RuleId(rule_part.strip())
        level = level_part.strip()
        if rule not in _RULES_BY_ID:
            raise ValueError(
                f'unknown rule {rule!r} in given_lint_rules '
                f'(known: {", ".join(sorted(_RULES_BY_ID))}).'
            )
        if level not in _LEVELS:
            raise ValueError(
                f'unknown level {level!r} for rule {rule!r} in given_lint_rules; '
                f'expected one of {", ".join(_LEVELS)}.'
            )
        levels[rule] = level
    return levels


def parse_ignore_entries(lines: list[str]) -> list[IgnoreEntry]:
    """Parse `given_lint_ignore` entries: subject globs with an optional
    ``rule-id:`` prefix.

    A prefix is only recognized when the text before the first ':' is shaped
    like a rule id — so node-id globs (``*::test_x``, ``tests/t.py::test_a``)
    parse as bare patterns. A rule-shaped prefix that names no known rule
    raises ValueError.
    """
    entries: list[IgnoreEntry] = []
    for line in lines:
        prefix, sep, rest = line.partition(':')
        if sep and _RULE_PREFIX_RE.fullmatch(prefix.strip()):
            rule = RuleId(prefix.strip())
            if rule not in _RULES_BY_ID:
                raise ValueError(
                    f'unknown rule prefix {rule!r} in given_lint_ignore entry '
                    f'{line!r} (known: {", ".join(sorted(_RULES_BY_ID))}).'
                )
            entries.append(IgnoreEntry(raw=line, rule=rule, pattern=rest.strip()))
        else:
            entries.append(IgnoreEntry(raw=line, rule=None, pattern=line.strip()))
    return entries


def run_ast_rules(scenarios: list[Scenario], rootdir: Path) -> list[Finding]:
    """Run the AST-surface rules over every step that carries a source anchor.

    Groups anchored steps by file, parses each file once, and resolves each
    step to its `with` statement or helper `FunctionDef` by recorded line.
    Failure-tolerant by design: an unreadable or unparseable file, or a line
    with no matching node, silently skips that step's rules — lint must never
    crash the run.
    """
    by_file: dict[str, list[_AnchoredStep]] = defaultdict(list)
    for scenario in scenarios:
        for anchored in _anchored_steps(scenario):
            by_file[anchored.source.relpath].append(anchored)
    findings: list[Finding] = []
    for relpath, anchored_steps in by_file.items():
        index = _index_body_nodes(rootdir / relpath)
        if index is None:
            continue
        for anchored in anchored_steps:
            node = index.get(anchored.source.line)
            if node is None:
                continue
            for rule in (_empty_step_finding, _then_without_check_finding):
                finding = rule(anchored, node)
                if finding is not None:
                    findings.append(finding)
    return findings


def apply_config(
    findings: list[Finding],
    levels: dict[RuleId, Level],
    ignores: list[IgnoreEntry],
) -> list[Finding]:
    """Resolve raw rule findings against the configuration, in report order.

    Drops findings of rules configured ``off`` (before ignore matching, so an
    entry scoped to a disabled rule counts as stale), suppresses findings
    matched by an ignore glob, maps the rest to their effective severity, and
    appends an error-level ``stale-ignore`` finding for every entry that
    suppressed nothing. Result is sorted errors-first, then by file/line, with
    the stale entries last.
    """
    effective = {rule.id: levels.get(rule.id, rule.default) for rule in RULES}
    used: set[int] = set()
    kept: list[Finding] = []
    for finding in findings:
        if effective[finding.rule] == 'off':
            continue
        suppressed = False
        for i, entry in enumerate(ignores):
            if entry.rule is not None and entry.rule != finding.rule:
                continue
            if fnmatch(finding.subject, entry.pattern):
                used.add(i)
                suppressed = True
        if not suppressed:
            kept.append(dataclasses.replace(finding, severity=effective[finding.rule]))
    kept.sort(key=_report_order)
    for i, entry in enumerate(ignores):
        if i not in used:
            kept.append(
                Finding(
                    rule=STALE_IGNORE,
                    severity='error',
                    subject=entry.raw,
                    node_id=None,
                    location=None,
                    message='suppressed no finding',
                )
            )
    return kept


def _report_order(finding: Finding) -> tuple[int, str, int, str, str]:
    relpath = finding.location.relpath if finding.location is not None else ''
    line = finding.location.line if finding.location is not None else 0
    return (
        0 if finding.severity == 'error' else 1,
        relpath,
        line,
        finding.rule,
        finding.subject,
    )


# A step body's anchored AST node: the `with` statement of an inline step, or
# the decorated helper function whose body is the step body.
type _BodyNode = ast.With | ast.FunctionDef


@dataclass(frozen=True, kw_only=True)
class _AnchoredStep:
    """A recorded step that carries a source anchor, with its pair role.

    A `when_then` pair is recognized as sibling `when`+`then` steps sharing
    one anchor — unambiguous, because cross-phase nesting is rejected at
    record time, so no other construct produces that shape.
    """

    node_id: NodeId
    step: Step
    source: SourceLocation
    pair_when: bool
    pair_then: bool


def _anchored_steps(scenario: Scenario) -> Iterator[_AnchoredStep]:
    def walk(steps: list[Step]) -> Iterator[_AnchoredStep]:
        for i, step in enumerate(steps):
            if step.source is not None:
                yield _AnchoredStep(
                    node_id=scenario.id,
                    step=step,
                    source=step.source,
                    pair_when=(
                        step.phase == 'when'
                        and i + 1 < len(steps)
                        and steps[i + 1].phase == 'then'
                        and steps[i + 1].source == step.source
                    ),
                    pair_then=(
                        step.phase == 'then'
                        and i > 0
                        and steps[i - 1].phase == 'when'
                        and steps[i - 1].source == step.source
                    ),
                )
            yield from walk(step.children)

    return walk(scenario.steps)


def _index_body_nodes(path: Path) -> dict[int, _BodyNode] | None:
    """Parse *path* and index its `With` and `FunctionDef` nodes by line.

    A `with` is reachable from any line of any of its with-items' context
    expressions (so multi-line parenthesized headers anchor correctly); a
    function from its `def` line and any decorator line (`co_firstlineno` of
    a decorated function is its first decorator line). Returns None when the
    file cannot be read or parsed.
    """
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except OSError, SyntaxError, ValueError:
        return None
    index: dict[int, _BodyNode] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            for item in node.items:
                expr = item.context_expr
                for line in range(expr.lineno, (expr.end_lineno or expr.lineno) + 1):
                    index.setdefault(line, node)
        elif isinstance(node, ast.FunctionDef):
            index.setdefault(node.lineno, node)
            for deco in node.decorator_list:
                for line in range(deco.lineno, (deco.end_lineno or deco.lineno) + 1):
                    index.setdefault(line, node)
    return index


def _empty_step_finding(anchored: _AnchoredStep, node: _BodyNode) -> Finding | None:
    """Rule `empty-step`: the step's body contains no executable code.

    Nested steps count as content for their parent (only leaves fire), and a
    `when_then` pair is analyzed once via its shared `with` — its
    `pytest.raises` with-item is not body content, so the acting expression
    must still be there.
    """
    if anchored.pair_then:
        return None
    body = [stmt for stmt in node.body if not _is_constant_stmt(stmt)]
    if not body:
        return _step_finding(RuleId('empty-step'), anchored, 'has no code')
    if anchored.step.phase != 'given' and all(_is_attach_stmt(s) for s in body):
        # Attaching is not acting or checking; a `given` that only attaches
        # its arranged artifact is legitimate.
        return _step_finding(
            RuleId('empty-step'), anchored, 'contains only attach() calls'
        )
    return None


def _then_without_check_finding(
    anchored: _AnchoredStep, node: _BodyNode
) -> Finding | None:
    """Rule `then-without-check`: a `then` body contains no assertion.

    A parent whose nested `then` child checks passes (the walk sees the whole
    subtree), and a `when_then`-produced `then` passes naturally: the
    `pytest.raises` with-item sits on its anchored `with`.
    """
    if anchored.step.phase != 'then':
        return None
    if _contains_check(node):
        return None
    return _step_finding(
        RuleId('then-without-check'), anchored, 'contains no assertion'
    )


def _step_finding(rule: RuleId, anchored: _AnchoredStep, problem: str) -> Finding:
    location = anchored.source
    filename = PurePosixPath(location.relpath).name
    return Finding(
        rule=rule,
        severity=_RULES_BY_ID[rule].default,
        subject=anchored.node_id,
        node_id=anchored.node_id,
        location=location,
        message=(
            f'{anchored.step.phase} {anchored.step.narration.text!r} {problem} '
            f'({filename}:{location.line})'
        ),
    )


def _is_constant_stmt(stmt: ast.stmt) -> bool:
    """`pass`, `...`, docstrings, and other constant-expression statements."""
    return isinstance(stmt, ast.Pass) or (
        isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
    )


def _is_attach_stmt(stmt: ast.stmt) -> bool:
    """An expression statement calling `attach` (bare name or attribute)."""
    if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)):
        return False
    func = stmt.value.func
    return (isinstance(func, ast.Name) and func.id == 'attach') or (
        isinstance(func, ast.Attribute) and func.attr == 'attach'
    )


def _contains_check(node: _BodyNode) -> bool:
    """Whether the node's subtree (body and with-items) checks anything."""
    return any(
        isinstance(sub, ast.Assert)
        or (isinstance(sub, ast.Call) and _is_check_call(sub))
        for sub in ast.walk(node)
    )


def _is_check_call(call: ast.Call) -> bool:
    """`assert*`-named calls (bare or attribute), pytest.raises/warns/fail."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id.startswith('assert')
    if isinstance(func, ast.Attribute):
        if func.attr.startswith('assert'):
            return True
        return (
            isinstance(func.value, ast.Name)
            and func.value.id == 'pytest'
            and func.attr in ('raises', 'warns', 'fail')
        )
    return False
