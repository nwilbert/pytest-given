"""AST-surface rules: every recorded step that carries a source anchor is
resolved to its `with` statement or decorated helper `FunctionDef`, and the
body is inspected for structural lies."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ..model import NarrationValue, NodeId, Scenario, SourceLocation, Step
from .base import RULES_BY_ID, Finding, RuleId, iter_steps

# A step body's anchored AST node: the `with` statement of an inline step, or
# the decorated helper function whose body is the step body.
type _BodyNode = ast.With | ast.FunctionDef


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
    for step in iter_steps(scenario.steps):
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
        severity=RULES_BY_ID[rule].default,
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
