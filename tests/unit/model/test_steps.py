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
