"""AST-surface rules: every recorded step that carries a source anchor is
resolved to its `with` statement or decorated helper `FunctionDef`, and the
body is inspected for structural lies."""

import ast
import keyword
from collections.abc import Callable, Container, Iterable
from dataclasses import dataclass
from pathlib import Path

from ..model import (
    NarrationPlaceholder,
    NarrationValue,
    Phase,
    Scenario,
    SourceLocation,
    Step,
    StepPath,
    walk_steps,
)
from .base import (
    ACTION_IN_THEN,
    CHECK_OUTSIDE_THEN,
    EMPTY_STEP,
    THEN_WITHOUT_CHECK,
    UNUSED_INTERPOLATION,
    RawFinding,
    RuleId,
)

# A step body's anchored AST node: the `with` statement of an inline step, or
# the decorated helper function whose body is the step body. `AsyncFunctionDef`
# is not a `FunctionDef` subclass and needs naming separately — the step
# decorators wrap coroutines and async generators too, so a helper narrating
# async code anchors exactly like a sync one.
type _BodyNode = ast.With | ast.FunctionDef | ast.AsyncFunctionDef


def run_ast_rules(
    scenarios: list[Scenario], rootdir: Path, enabled: Container[RuleId]
) -> list[RawFinding]:
    """Run the `enabled` AST-surface rules over every step with a source anchor.

    Each file is parsed once (cached across scenarios) and every anchored step
    resolves to its `with` statement or helper `FunctionDef` by recorded line.
    Failure-tolerant by design: an unreadable or unparseable file, or a line
    with no matching node, silently skips that step's rules — lint must never
    crash the run.

    Nothing is parsed when every rule here is off: the whole point of `off` is
    that the rule does not run, and reading and parsing every test file to
    build findings that would then be discarded is the expensive half.
    """
    step_rules = [fn for rule, fn in _STEP_RULES.items() if rule in enabled]
    scenario_rules = [fn for rule, fn in _SCENARIO_RULES.items() if rule in enabled]
    if not step_rules and not scenario_rules:
        return []
    indexes: dict[str, dict[int, _BodyNode] | None] = {}
    findings: list[RawFinding] = []
    for scenario in scenarios:
        scan = _scan_scenario(scenario, rootdir, indexes)
        for resolved in scan.steps:
            for step_rule in step_rules:
                findings.extend(step_rule(resolved, scan))
        for scenario_rule in scenario_rules:
            findings.extend(scenario_rule(scan))
    return findings


@dataclass(frozen=True, kw_only=True)
class _Resolved:
    """A step carrying a source anchor, the AST node its body resolved to, and
    its `when_then` role.

    A `when_then` pair is recognized as sibling `when`+`then` steps sharing
    one anchor — unambiguous, because cross-phase nesting is rejected at
    record time, so no other construct produces that shape. `pair_role` is
    which half of such a pair this step is, or None when it is not in one; a
    step has one phase, so the two halves were never independent.
    """

    path: StepPath
    step: Step
    source: SourceLocation
    pair_role: Phase | None
    node: _BodyNode


@dataclass(frozen=True, kw_only=True)
class _Scan:
    """One scenario's resolved steps, plus the path index the rules look
    siblings and children up in."""

    scenario: Scenario
    steps: list[_Resolved]
    by_path: dict[StepPath, _Resolved]


def _scan_scenario(
    scenario: Scenario,
    rootdir: Path,
    indexes: dict[str, dict[int, _BodyNode] | None],
) -> _Scan:
    """Every step of `scenario` that carries a source anchor *and* resolves to
    an AST node, tagged with its `when_then` role.

    Siblings are reached through the path index rather than by walking a level
    at a time: a step's neighbours are the paths differing only in the last
    component.
    """
    by_path = dict(walk_steps(scenario.steps))
    steps: list[_Resolved] = []
    for path, step in by_path.items():
        source = step.source
        if source is None:
            continue
        if source.relpath not in indexes:
            indexes[source.relpath] = _index_body_nodes(rootdir / source.relpath)
        index = indexes[source.relpath]
        node = index.get(source.line) if index is not None else None
        if node is None:
            continue
        before = by_path.get((*path[:-1], path[-1] - 1)) if path[-1] else None
        after = by_path.get((*path[:-1], path[-1] + 1))
        steps.append(
            _Resolved(
                path=path,
                step=step,
                source=source,
                pair_role=_pair_role(step, before, after, source),
                node=node,
            )
        )
    return _Scan(
        scenario=scenario,
        steps=steps,
        by_path={resolved.path: resolved for resolved in steps},
    )


def _pair_role(
    step: Step, before: Step | None, after: Step | None, source: SourceLocation
) -> Phase | None:
    """Which half of a `when_then` pair `step` is, or None when it is in none.

    The two halves were never independent — a step has one phase — so this is
    one answer rather than a flag per half.
    """
    if (
        step.phase == 'when'
        and after is not None
        and after.phase == 'then'
        and after.source == source
    ):
        return 'when'
    if (
        step.phase == 'then'
        and before is not None
        and before.phase == 'when'
        and before.source == source
    ):
        return 'then'
    return None


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
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            index.setdefault(node.lineno, node)
            for deco in node.decorator_list:
                for line in range(deco.lineno, (deco.end_lineno or deco.lineno) + 1):
                    index.setdefault(line, node)
    return index


def _empty_step(resolved: _Resolved, scan: _Scan) -> Iterable[RawFinding]:
    """Rule `empty-step`: the step's body contains no executable code.

    Nested steps count as content for their parent (only leaves fire), and a
    `when_then` pair is analyzed once via its shared `with` — its
    `pytest.raises` with-item is not body content, so the acting expression
    must still be there.
    """
    if resolved.pair_role == 'then':
        return
    body = [stmt for stmt in resolved.node.body if not _is_constant_stmt(stmt)]
    if not body:
        yield _step_finding(EMPTY_STEP, scan, resolved, 'has no code')
    elif resolved.step.phase != 'given' and all(_is_attach_stmt(s) for s in body):
        # Attaching is not acting or checking; a `given` that only attaches
        # its arranged artifact is legitimate.
        yield _step_finding(EMPTY_STEP, scan, resolved, 'contains only attach() calls')


def _then_without_check(resolved: _Resolved, scan: _Scan) -> Iterable[RawFinding]:
    """Rule `then-without-check`: a `then` body contains no assertion.

    A parent whose nested `then` child checks passes (the walk sees the whole
    subtree), and a `when_then`-produced `then` passes naturally: the
    `pytest.raises` with-item sits on its anchored `with`.
    """
    if resolved.step.phase == 'then' and not _contains_check(resolved.node):
        yield _step_finding(THEN_WITHOUT_CHECK, scan, resolved, 'contains no assertion')


def _check_outside_then(resolved: _Resolved, scan: _Scan) -> Iterable[RawFinding]:
    """Rule `check-outside-then`: an `assert` sits in a `given` or `when` body.

    `when_then` bodies are exempt — the shared body belongs to the pair's
    `then` half. Asserts inside a nested child step's block are that child's
    business (it is scanned as its own anchored step), so the parent's scan
    excludes resolved child subtrees.
    """
    if resolved.step.phase == 'then' or (resolved.pair_role == 'when'):
        return
    child_nodes = {
        id(child.node)
        for index in range(len(resolved.step.children))
        if (child := scan.by_path.get((*resolved.path, index))) is not None
    }
    if _contains_assert_outside(resolved.node.body, child_nodes):
        yield _anchored_finding(
            CHECK_OUTSIDE_THEN,
            scan,
            resolved,
            f'assert inside {resolved.step.phase} {resolved.step.narration.text!r}',
        )


def _unused_interpolation(resolved: _Resolved, scan: _Scan) -> Iterable[RawFinding]:
    """Rule `unused-interpolation`: a t-string step interpolates a bare
    identifier its body never uses.

    Only `with`-anchored steps are scanned — `Template` placeholders on
    decorated helpers are tied to parameters by decoration-time validation
    and are out of scope in v1. Term refs are exempt by type; complex
    expressions are skipped entirely. For a `given`, a store (the step
    binding the name) also counts as use.

    Placeholders count as interpolations too: the lint runs on *grouped*
    scenarios, where grouping has already turned every varying interpolation
    into one, so scanning values alone would be blind to parametrized
    scenarios. A placeholder names its column, so a disambiguated name
    (`price #2`) drops out with the complex expressions.
    """
    node = resolved.node
    if not isinstance(node, ast.With):
        return
    expressions = [
        part.expression if isinstance(part, NarrationValue) else part.name
        for part in resolved.step.narration.parts
        if isinstance(part, (NarrationValue, NarrationPlaceholder))
    ]
    if not expressions:
        return
    used = _names_used(node, include_stores=resolved.step.phase == 'given')
    seen: set[str] = set()
    for expression in expressions:
        name = _bare_identifier(expression)
        if name is None or name in seen:
            continue
        seen.add(name)
        if name not in used:
            yield _step_finding(
                UNUSED_INTERPOLATION,
                scan,
                resolved,
                f'interpolates {{{name}}} but never uses it',
            )


def _action_in_then(scan: _Scan) -> Iterable[RawFinding]:
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
    acts = False
    for path, step in walk_steps(scan.scenario.steps):
        if step.phase != 'when':
            continue
        resolved = scan.by_path.get(path)
        if resolved is None:
            return
        if (resolved.pair_role == 'when') or _body_performs_action(resolved.node):
            acts = True
    if acts:
        return
    for resolved in scan.steps:
        if resolved.step.phase != 'then' or (resolved.pair_role == 'then'):
            continue
        if _assert_with_call(resolved.node):
            yield _anchored_finding(
                ACTION_IN_THEN,
                scan,
                resolved,
                f'then {resolved.step.narration.text!r} folds the action into '
                f'its assertion; no when acts',
            )
            return


type _StepRule = Callable[[_Resolved, _Scan], Iterable[RawFinding]]
type _ScenarioRule = Callable[[_Scan], Iterable[RawFinding]]

# Keyed by rule id, so `run_ast_rules` can drop the ones that are off before
# it parses anything.
_STEP_RULES: dict[RuleId, _StepRule] = {
    EMPTY_STEP: _empty_step,
    THEN_WITHOUT_CHECK: _then_without_check,
    CHECK_OUTSIDE_THEN: _check_outside_then,
    UNUSED_INTERPOLATION: _unused_interpolation,
}

_SCENARIO_RULES: dict[RuleId, _ScenarioRule] = {
    ACTION_IN_THEN: _action_in_then,
}


def _step_finding(
    rule: RuleId, scan: _Scan, resolved: _Resolved, problem: str
) -> RawFinding:
    return _anchored_finding(
        rule,
        scan,
        resolved,
        f'{resolved.step.phase} {resolved.step.narration.text!r} {problem}',
    )


def _anchored_finding(
    rule: RuleId, scan: _Scan, resolved: _Resolved, text: str
) -> RawFinding:
    return RawFinding(
        rule=rule,
        subject=scan.scenario.id,
        location=resolved.source,
        message=text,
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
    """The name if *expression* is a single identifier, else None.

    Asked of the string rather than of `ast.parse`, which reads `#` as a
    comment: a disambiguated column name (`price #2`) parses to `Name('price')`
    and would be reported under a token the report never shows. The keyword
    test stands in for the rest of what the parse ruled out — `class` is an
    identifier by `str`'s reckoning but not a name. Soft keywords (`match`,
    `type`) are ordinary names and stay.
    """
    if not expression.isidentifier() or keyword.iskeyword(expression):
        return None
    return expression


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
