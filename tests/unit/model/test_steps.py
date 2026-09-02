from pytest_given.grouping.checks import structure_signature
from pytest_given.model import (
    Narration,
    Step,
    iter_steps,
    walk_steps,
)


def _step(phase: str, text: str, children: list[Step] | None = None) -> Step:
    return Step(
        phase=phase,  # type: ignore[arg-type]
        narration=Narration(text=text),
        children=children or [],
    )


def _tree() -> list[Step]:
    return [
        _step('given', 'a', [_step('given', 'a1'), _step('when', 'a2')]),
        _step('then', 'b'),
    ]


def test_walk_steps_yields_depth_first_index_paths() -> None:
    assert [(path, step.narration.text) for path, step in walk_steps(_tree())] == [
        ((0,), 'a'),
        ((0, 0), 'a1'),
        ((0, 1), 'a2'),
        ((1,), 'b'),
    ]


def test_iter_steps_is_walk_steps_with_the_paths_dropped() -> None:
    assert [s.narration.text for s in iter_steps(_tree())] == ['a', 'a1', 'a2', 'b']


def test_structure_signature_ignores_narration() -> None:
    other = [
        _step('given', 'different', [_step('given', 'x'), _step('when', 'y')]),
        _step('then', 'also different'),
    ]
    assert structure_signature(_tree()) == structure_signature(other)


def test_structure_signature_separates_different_shapes() -> None:
    assert structure_signature(_tree()) != structure_signature([_step('given', 'a')])


def test_structure_signature_of_an_empty_tree_is_empty() -> None:
    assert structure_signature([]) == ()
