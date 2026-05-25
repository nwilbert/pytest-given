import pytest

from pytest_given import Template
from pytest_given.collector import Collector, set_active_collector
from pytest_given.decorators import StepDescriptor, attach, given, scenario, then, when
from pytest_given.errors import PytestGivenError
from pytest_given.template import NarrationLiteral, NarrationValue


def test_context_manager_basic() -> None:
    """StepDescriptor exposes phase and text attributes."""
    desc = StepDescriptor('given', 'a coffee machine')
    assert desc.phase == 'given'
    assert desc.text == 'a coffee machine'


def test_decorator_basic() -> None:
    """StepDescriptor works as a function decorator."""
    desc = StepDescriptor('when', 'inserting money')

    @desc
    def insert_money() -> str:
        return 'done'

    assert insert_money() == 'done'
    assert hasattr(insert_money, '_step_descriptor')
    assert insert_money._step_descriptor.text == 'inserting money'


def test_decorator_preserves_function_metadata() -> None:
    """Decorated function keeps its original name and docstring."""
    desc = StepDescriptor('given', 'a machine')

    @desc
    def my_func() -> None:
        """My docstring."""

    assert my_func.__name__ == 'my_func'
    assert my_func.__doc__ == 'My docstring.'


def test_context_manager_records_step_in_collector() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    set_active_collector(collector)
    try:
        desc = StepDescriptor('given', 'a coffee machine')
        with desc:
            pass
        scenario = collector.finish_scenario(status='passed', duration_ms=0)
        assert len(scenario.steps) == 1
        assert scenario.steps[0].text == 'a coffee machine'
    finally:
        set_active_collector(None)


def test_context_manager_without_collector_raises() -> None:
    """Calling with given(...) when no collector is set is a programming error."""
    set_active_collector(None)
    desc = StepDescriptor('given', 'orphan')
    with pytest.raises(PytestGivenError, match='no active scenario or fixture'), desc:
        pass


def test_context_manager_in_idle_collector_raises() -> None:
    """Collector in idle state still raises."""
    collector = Collector()
    set_active_collector(collector)
    try:
        with (
            pytest.raises(PytestGivenError, match='no active scenario'),
            StepDescriptor('given', 'orphan'),
        ):
            pass
    finally:
        set_active_collector(None)


def test_context_manager_unannotated_test_warns_instead_of_raises() -> None:
    """When inside an unannotated test, soft-warn instead of raising."""
    collector = Collector()
    collector.inside_unannotated_test = True
    set_active_collector(collector)
    try:
        with (
            pytest.warns(pytest.PytestWarning, match='without @scenario'),
            StepDescriptor('given', 'noisy'),
        ):
            pass
    finally:
        set_active_collector(None)


def test_attach_without_collector_raises() -> None:
    set_active_collector(None)
    with pytest.raises(PytestGivenError, match='no active scenario or fixture'):
        attach('label', 'content')


def test_attach_unannotated_test_warns_instead_of_raises() -> None:
    collector = Collector()
    collector.inside_unannotated_test = True
    set_active_collector(collector)
    try:
        with pytest.warns(pytest.PytestWarning, match='without @scenario'):
            attach('label', 'content')
    finally:
        set_active_collector(None)


def test_attach_non_string_content_serializes_as_json() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('given', 'a step')
    set_active_collector(collector)
    try:
        attach('payload', {'a': 1, 'b': [2, 3]})
    finally:
        set_active_collector(None)
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    att = scenario.steps[-1].attachments[0]
    assert att.label == 'payload'
    assert att.content_type == 'json'
    assert '"a": 1' in att.content
    assert '2' in att.content
    assert '3' in att.content


def test_step_descriptor_with_plain_str_has_no_text_parts() -> None:
    desc = StepDescriptor('given', 'a thing')
    assert desc.text == 'a thing'
    assert desc.text_parts is None


def test_step_descriptor_decorator_on_fixture_rejects_structured_text() -> None:
    """@given(t'...') on a fixture raises — fixture args aren't in scope."""
    cup_size = 200
    desc = StepDescriptor('given', t'a {cup_size} ml cup')

    def fixture_body() -> int:
        return cup_size

    with pytest.raises(PytestGivenError, match='not allowed on a fixture'):
        desc(fixture_body)


def test_scenario_with_plain_str_keeps_name() -> None:
    deco = scenario('Brew coffee')
    assert deco.name == 'Brew coffee'
    assert isinstance(deco.name, str)


def test_scenario_with_template_keeps_template() -> None:
    tmpl = Template('Brew {cup_size} ml')
    deco = scenario(tmpl)
    assert deco.name is tmpl


def test_scenario_with_tstring_raises() -> None:
    cup_size = 200
    with pytest.raises(PytestGivenError, match=r't-string.*@scenario'):
        scenario(t'Brew {cup_size} ml')


def test_attach_with_tstring_label_renders_eagerly() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('given', 'a step')
    set_active_collector(collector)
    try:
        size = 200
        attach(t'cup {size}', 'content')
    finally:
        set_active_collector(None)
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    att = scenario.steps[-1].attachments[0]
    assert att.label == 'cup 200'


def test_attach_with_pytest_given_template_raises() -> None:
    with pytest.raises(PytestGivenError, match=r'attach.*not supported'):
        attach(Template('cup {size}'), 'content')


def test_step_descriptor_with_tstring_no_interpolations_still_has_text_parts() -> None:
    """A t-string with only literal text produces structured parts — text_parts
    is present iff the author used a t-string, not iff the text was dynamic."""
    desc = given(t'just a label')
    assert desc.text == 'just a label'
    assert desc.text_parts == [NarrationLiteral(value='just a label')]


def test_step_descriptor_with_tstring_records_rendered_text_and_parts() -> None:
    cup_size = 200
    desc = given(t'a {cup_size} ml cup')
    assert desc.text == 'a 200 ml cup'
    assert desc.text_parts == [
        NarrationLiteral(value='a '),
        NarrationValue(
            rendered='200',
            expression='cup_size',
            format_spec='',
            conversion=None,
        ),
        NarrationLiteral(value=' ml cup'),
    ]


def test_given_with_pytest_given_template_raises() -> None:
    with pytest.raises(PytestGivenError, match='not supported in a test body'):
        given(Template('a {cup_size} ml cup'))


def test_when_with_pytest_given_template_raises() -> None:
    with pytest.raises(PytestGivenError, match='not supported in a test body'):
        when(Template('x {y}'))


def test_then_with_pytest_given_template_raises() -> None:
    with pytest.raises(PytestGivenError, match='not supported in a test body'):
        then(Template('x {y}'))
