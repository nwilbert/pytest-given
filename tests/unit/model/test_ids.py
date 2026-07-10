from pytest_given.model import case_suffix, node_base


def test_node_base_drops_parametrize_tail() -> None:
    assert node_base('tests/t.py::test_x[1-2]') == 'tests/t.py::test_x'


def test_node_base_leaves_unparametrized_id_unchanged() -> None:
    assert node_base('tests/t.py::test_x') == 'tests/t.py::test_x'


def test_node_base_applies_to_a_bare_function_segment() -> None:
    assert node_base('test_x[1-2]') == 'test_x'


def test_case_suffix_returns_the_bracketed_tail() -> None:
    assert case_suffix('tests/t.py::test_x[1-2]') == '[1-2]'


def test_case_suffix_is_empty_without_a_tail() -> None:
    assert case_suffix('tests/t.py::test_x') == ''
