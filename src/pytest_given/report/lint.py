"""Narration lint: rules that catch steps whose narration lies about their body.

Pure inspection of the built report model plus the AST of the step bodies the
run itself identified — no pytest imports — so every rule is unit-testable in
isolation. The plugin runs the rule passes at session finish, applies the
configured severities and ignore globs via `apply_config`, and surfaces the
findings per the design spec (docs/specs/2026-07-05-narration-lint-design.md).
"""

from __future__ import annotations

import ast
import dataclasses
import re
from collections.abc import Iterator
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
from typing import Literal, NewType

from ..model import (
    ActivityTermRef,
    Glossary,
    Narration,
    NarrationTermRef,
    NarrationValue,
    NodeId,
    Phase,
    Scenario,
    SourceLocation,
    Step,
    Story,
    TermId,
    id_derive,
)

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
    LintRule(id=RuleId('missing-phase'), surface='runtime', default='warn'),
    LintRule(id=RuleId('empty-step'), surface='ast', default='error'),
    LintRule(id=RuleId('then-without-check'), surface='ast', default='error'),
    LintRule(id=RuleId('check-outside-then'), surface='ast', default='warn'),
    LintRule(id=RuleId('action-in-then'), surface='ast', default='warn'),
    LintRule(id=RuleId('unused-interpolation'), surface='ast', default='warn'),
    LintRule(id=RuleId('divergent-case-structure'), surface='runtime', default='warn'),
    LintRule(id=RuleId('tag-shadows-term'), surface='runtime', default='warn'),
    LintRule(id=RuleId('dead-term'), surface='runtime', default='off'),
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


def run_runtime_rules(
    grouped: list[Scenario],
    per_case: list[Scenario],
    glossary: Glossary | None,
    stories: list[Story],
) -> list[Finding]:
    """Run the runtime-surface rules over the recorded report model.

    `missing-phase` and the glossary rules evaluate the grouped scenario list
    (one evaluation per logical scenario); `divergent-case-structure` needs
    the pre-grouping per-case list — the only place per-case step structure
    exists, since grouping collapses every case onto case 1's tree.
    """
    findings: list[Finding] = []
    findings.extend(_missing_phase_findings(grouped))
    findings.extend(_divergent_case_findings(per_case))
    if glossary is not None:
        findings.extend(_tag_shadows_term_findings(grouped, glossary))
        findings.extend(_dead_term_findings(grouped, glossary, stories))
    return findings


def run_ast_rules(scenarios: list[Scenario], rootdir: Path) -> list[Finding]:
    """Run the AST-surface rules over every step that carries a source anchor.

    Each file is parsed once (cached across scenarios) and every anchored step
    resolves to its `with` statement or helper `FunctionDef` by recorded line.
    Failure-tolerant by design: an unreadable or unparseable file, or a line
    with no matching node, silently skips that step's rules — lint must never
    crash the run.
    """
    indexes: dict[str, dict[int, _BodyNode] | None] = {}
    findings: list[Finding] = []
    for scenario in scenarios:
        resolved: list[tuple[_AnchoredStep, _BodyNode]] = []
        node_by_step: dict[int, _BodyNode] = {}
        for anchored in _anchored_steps(scenario):
            relpath = anchored.source.relpath
            if relpath not in indexes:
                indexes[relpath] = _index_body_nodes(rootdir / relpath)
            index = indexes[relpath]
            node = index.get(anchored.source.line) if index is not None else None
            if node is not None:
                resolved.append((anchored, node))
                node_by_step[id(anchored.step)] = node
        for anchored, node in resolved:
            for finding in (
                _empty_step_finding(anchored, node),
                _then_without_check_finding(anchored, node),
                _check_outside_then_finding(anchored, node, node_by_step),
            ):
                if finding is not None:
                    findings.append(finding)
            findings.extend(_unused_interpolation_findings(anchored, node))
        scenario_finding = _action_in_then_finding(scenario, resolved)
        if scenario_finding is not None:
            findings.append(scenario_finding)
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


# Canonical Given/When/Then order, used both to test completeness and to
# report missing phases in reading order rather than alphabetically.
_PHASE_ORDER: tuple[Phase, ...] = ('given', 'when', 'then')

# A step tree reduced to nested phase tuples — narration text and values
# ignored. Two cases with equal signatures render truthfully in the merged
# parameter-table view.
type _StepSignature = tuple[tuple[Phase, _StepSignature], ...]


def _missing_phase_findings(grouped: list[Scenario]) -> list[Finding]:
    """Rule `missing-phase`: a passed scenario lacks a Given, When, or Then.

    Non-passed scenarios are skipped — a skipped one records no steps and a
    failed one may be missing a phase only because it aborted mid-body.
    """
    findings: list[Finding] = []
    for scenario in grouped:
        if scenario.status != 'passed':
            continue
        present = {step.phase for step in _iter_steps(scenario.steps)}
        missing = [phase for phase in _PHASE_ORDER if phase not in present]
        if missing:
            findings.append(
                _scenario_finding(
                    RuleId('missing-phase'),
                    scenario,
                    f'missing: {", ".join(missing)}',
                )
            )
    return findings


def _divergent_case_findings(per_case: list[Scenario]) -> list[Finding]:
    """Rule `divergent-case-structure`: a parametrize case records a
    different step structure than case 1.

    Groups the pre-grouping cases by node-id base. Non-passed cases are
    exempt (skipped cases record no steps; failed cases abort mid-tree), so
    the baseline is the first passed case. One finding per scenario, naming
    the diverging case ids.
    """
    groups: dict[str, list[Scenario]] = {}
    for scenario in per_case:
        base, bracket, _ = scenario.id.partition('[')
        if bracket:
            groups.setdefault(base, []).append(scenario)
    findings: list[Finding] = []
    for base, cases in groups.items():
        passed = [case for case in cases if case.status == 'passed']
        if len(passed) < 2:
            continue
        baseline = _structure_signature(passed[0].steps)
        diverging = [
            _case_suffix(case)
            for case in passed[1:]
            if _structure_signature(case.steps) != baseline
        ]
        if diverging:
            findings.append(
                Finding(
                    rule=RuleId('divergent-case-structure'),
                    severity=_RULES_BY_ID[RuleId('divergent-case-structure')].default,
                    subject=base,
                    node_id=NodeId(base),
                    location=passed[0].source,
                    message=(
                        f'cases {", ".join(diverging)} record a different step '
                        f'structure than case {_case_suffix(passed[0])}'
                    ),
                )
            )
    return findings


def _case_suffix(scenario: Scenario) -> str:
    return '[' + scenario.id.partition('[')[2]


def _structure_signature(steps: list[Step]) -> _StepSignature:
    return tuple((step.phase, _structure_signature(step.children)) for step in steps)


def _tag_shadows_term_findings(
    grouped: list[Scenario], glossary: Glossary
) -> list[Finding]:
    """Rule `tag-shadows-term`: a scenario tag duplicates a glossary term.

    One finding per unique tag (subject = tag slug) — the fix is renaming the
    tag once, and per-scenario findings would be pure repetition.
    """
    counts: dict[TermId, tuple[str, NodeId, int]] = {}
    for scenario in grouped:
        for tag in scenario.tags:
            slug = id_derive(tag)
            if glossary.get(slug) is None:
                continue
            if slug in counts:
                first_tag, first_id, count = counts[slug]
                counts[slug] = (first_tag, first_id, count + 1)
            else:
                counts[slug] = (tag, scenario.id, 1)
    findings: list[Finding] = []
    for slug, (tag, node_id, count) in counts.items():
        term = glossary.get(slug)
        assert term is not None
        noun = 'scenario' if count == 1 else 'scenarios'
        findings.append(
            Finding(
                rule=RuleId('tag-shadows-term'),
                severity=_RULES_BY_ID[RuleId('tag-shadows-term')].default,
                subject=slug,
                node_id=node_id,
                location=None,
                message=(
                    f'tag {tag!r} duplicates glossary term {term.canonical!r} '
                    f'({count} {noun}, e.g. {node_id})'
                ),
            )
        )
    return findings


def _dead_term_findings(
    grouped: list[Scenario], glossary: Glossary, stories: list[Story]
) -> list[Finding]:
    """Rule `dead-term`: a glossary term is referenced by no step and no
    story. Default `off`: for a file-backed glossary, unreferenced terms are
    often intentionally present (documented behaviour)."""
    referenced: set[TermId] = set()
    for scenario in grouped:
        for narration in _iter_narrations(scenario):
            for part in narration.parts:
                if isinstance(part, NarrationTermRef):
                    referenced.add(part.term_id)
    for story in stories:
        for activity in story.activities:
            for path in activity.paths:
                for ref in path.parts:
                    if isinstance(ref, ActivityTermRef):
                        referenced.add(ref.term_id)
    return [
        Finding(
            rule=RuleId('dead-term'),
            severity=_RULES_BY_ID[RuleId('dead-term')].default,
            subject=term.id,
            node_id=None,
            location=term.source,
            message=f'term {term.canonical!r} is referenced by no step and no story',
        )
        for term in glossary.terms
        if term.id not in referenced
    ]


def _iter_narrations(scenario: Scenario) -> Iterator[Narration]:
    yield scenario.narration
    for step in _iter_steps(scenario.steps):
        yield step.narration


def _scenario_finding(rule: RuleId, scenario: Scenario, text: str) -> Finding:
    location = scenario.source
    if location is not None:
        filename = PurePosixPath(location.relpath).name
        text = f'{text} ({filename}:{location.line})'
    return Finding(
        rule=rule,
        severity=_RULES_BY_ID[rule].default,
        subject=scenario.id,
        node_id=scenario.id,
        location=location,
        message=text,
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


def _check_outside_then_finding(
    anchored: _AnchoredStep,
    node: _BodyNode,
    node_by_step: dict[int, _BodyNode],
) -> Finding | None:
    """Rule `check-outside-then`: an `assert` sits in a `given` or `when` body.

    `when_then` bodies are exempt — the shared body belongs to the pair's
    `then` half. Asserts inside a nested child step's block are that child's
    business (it is scanned as its own anchored step), so the parent's scan
    excludes resolved child subtrees.
    """
    if anchored.step.phase == 'then' or anchored.pair_when:
        return None
    child_nodes = {
        id(node_by_step[id(child)])
        for child in anchored.step.children
        if id(child) in node_by_step
    }
    if not _contains_assert_outside(node.body, child_nodes):
        return None
    return _anchored_finding(
        RuleId('check-outside-then'),
        anchored,
        f'assert inside {anchored.step.phase} {anchored.step.narration.text!r}',
    )


def _unused_interpolation_findings(
    anchored: _AnchoredStep, node: _BodyNode
) -> list[Finding]:
    """Rule `unused-interpolation`: a t-string step interpolates a bare
    identifier its body never uses.

    Only `with`-anchored steps are scanned — `Template` placeholders on
    decorated helpers are tied to parameters by decoration-time validation
    and are out of scope in v1. Term refs are exempt by type; complex
    expressions are skipped entirely. For a `given`, a store (the step
    binding the name) also counts as use.
    """
    if not isinstance(node, ast.With):
        return []
    values = [
        part
        for part in anchored.step.narration.parts
        if isinstance(part, NarrationValue)
    ]
    if not values:
        return []
    used = _names_used(node, include_stores=anchored.step.phase == 'given')
    findings: list[Finding] = []
    seen: set[str] = set()
    for part in values:
        name = _bare_identifier(part.expression)
        if name is None or name in seen:
            continue
        seen.add(name)
        if name not in used:
            findings.append(
                _step_finding(
                    RuleId('unused-interpolation'),
                    anchored,
                    f'interpolates {{{name}}} but never uses it',
                )
            )
    return findings


def _action_in_then_finding(
    scenario: Scenario, resolved: list[tuple[_AnchoredStep, _BodyNode]]
) -> Finding | None:
    """Rule `action-in-then` (per scenario): a `then` assertion contains a
    call, and no `when` step acts.

    A `when_then`'s `when` acts unconditionally (the construct wraps the act
    by definition — the acting expression need not be a call); a plain `when`
    acts iff its body contains a call or a subscript (an indexing action —
    the same reasoning, tuned on this repo's suite). Any `when` without a
    resolved anchor skips the whole scenario — unknowable beats wrong. A
    `when_then`'s `then` is excluded from the then-side scan: it anchors to
    the shared `with`, so any call there *is* the act.
    """
    node_of = {id(a.step): (a, node) for a, node in resolved}
    acts = False
    for step in _iter_steps(scenario.steps):
        if step.phase != 'when':
            continue
        entry = node_of.get(id(step))
        if entry is None:
            return None
        anchored, node = entry
        if anchored.pair_when or _body_performs_action(node):
            acts = True
    if acts:
        return None
    for anchored, node in resolved:
        if anchored.step.phase != 'then' or anchored.pair_then:
            continue
        if _assert_with_call(node):
            return _anchored_finding(
                RuleId('action-in-then'),
                anchored,
                f'then {anchored.step.narration.text!r} folds the action into '
                f'its assertion; no when acts',
            )
    return None


def _step_finding(rule: RuleId, anchored: _AnchoredStep, problem: str) -> Finding:
    return _anchored_finding(
        rule,
        anchored,
        f'{anchored.step.phase} {anchored.step.narration.text!r} {problem}',
    )


def _anchored_finding(rule: RuleId, anchored: _AnchoredStep, text: str) -> Finding:
    location = anchored.source
    filename = PurePosixPath(location.relpath).name
    return Finding(
        rule=rule,
        severity=_RULES_BY_ID[rule].default,
        subject=anchored.node_id,
        node_id=anchored.node_id,
        location=location,
        message=f'{text} ({filename}:{location.line})',
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


def _iter_steps(steps: list[Step]) -> Iterator[Step]:
    for step in steps:
        yield step
        yield from _iter_steps(step.children)


def _bare_identifier(expression: str) -> str | None:
    """The name if *expression* parses to a single `Name`, else None."""
    try:
        parsed = ast.parse(expression, mode='eval')
    except SyntaxError:
        return None
    return parsed.body.id if isinstance(parsed.body, ast.Name) else None


def _names_used(node: ast.With, *, include_stores: bool) -> set[str]:
    """Names used anywhere under the `with` — items and body, nested steps
    included — skipping t-string subtrees: an interpolation in a narration
    (this step's own, or a nested step's) is text, not a code use."""
    names: set[str] = set()
    stack: list[ast.AST] = list(ast.iter_child_nodes(node))
    while stack:
        sub = stack.pop()
        if isinstance(sub, ast.TemplateStr):
            continue
        if isinstance(sub, ast.Name) and (
            include_stores or isinstance(sub.ctx, ast.Load)
        ):
            names.add(sub.id)
        stack.extend(ast.iter_child_nodes(sub))
    return names


def _body_performs_action(node: _BodyNode) -> bool:
    """Whether the node's body (not its with-items) performs a call or an
    indexing action (subscript)."""
    return any(
        isinstance(sub, (ast.Call, ast.Subscript))
        for stmt in node.body
        for sub in ast.walk(stmt)
    )


def _assert_with_call(node: _BodyNode) -> bool:
    """Whether any `assert` in the node's subtree tests an expression
    containing a call."""
    return any(
        isinstance(sub, ast.Assert)
        and any(isinstance(part, ast.Call) for part in ast.walk(sub.test))
        for sub in ast.walk(node)
    )


def _contains_assert_outside(stmts: list[ast.stmt], excluded: set[int]) -> bool:
    """Whether an `assert` exists under *stmts*, skipping excluded subtrees
    (child-step blocks, identified by node id)."""
    stack: list[ast.AST] = list(stmts)
    while stack:
        node = stack.pop()
        if id(node) in excluded:
            continue
        if isinstance(node, ast.Assert):
            return True
        stack.extend(ast.iter_child_nodes(node))
    return False


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
