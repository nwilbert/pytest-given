import pytest

from pytest_given import Template
from pytest_given.collector import Collector, set_active_collector
from pytest_given.decorators import StepDescriptor, attach, given, scenario, then, when
from pytest_given.errors import PytestGivenError
from pytest_given.model import FixtureRecording, Step
from pytest_given.template import Narration, NarrationLiteral, NarrationValue


def test_context_manager_basic() -> None:
    """StepDescriptor exposes phase and narration attributes."""
    desc = StepDescriptor('given', 'a coffee machine')
    assert desc.phase == 'given'
    assert desc.narration.text == 'a coffee machine'


def test_decorator_basic() -> None:
    """StepDescriptor works as a function decorator."""
    desc = StepDescriptor('when', 'inserting money')

    @desc
    def insert_money() -> str:
        return 'done'

    assert insert_money() == 'done'
    assert hasattr(insert_money, '_step_descriptor')
    assert insert_money._step_descriptor.narration.text == 'inserting money'


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
        assert scenario.steps[0].narration.text == 'a coffee machine'
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
    collector.push_step('given', Narration(text='a step'))
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


def test_step_descriptor_with_plain_str_has_empty_narration_parts() -> None:
    desc = StepDescriptor('given', 'a thing')
    assert desc.narration.text == 'a thing'
    assert desc.narration.parts == []


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
    collector.push_step('given', Narration(text='a step'))
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


def test_step_descriptor_with_tstring_no_interpolations_still_has_parts() -> None:
    """A t-string with only literal text produces structured parts — parts is
    non-empty iff the author used a t-string, not iff the text was dynamic."""
    desc = given(t'just a label')
    assert desc.narration.text == 'just a label'
    assert desc.narration.parts == [NarrationLiteral(value='just a label')]


def test_step_descriptor_with_tstring_records_rendered_text_and_parts() -> None:
    cup_size = 200
    desc = given(t'a {cup_size} ml cup')
    assert desc.narration.text == 'a 200 ml cup'
    assert desc.narration.parts == [
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


def test_decorator_records_step_when_called_inside_scenario() -> None:
    """A @when-decorated plain helper pushes a step on call and pops on return."""
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    set_active_collector(collector)
    try:

        @when('inserting money')
        def insert(amount: int) -> int:
            return amount * 2

        assert insert(5) == 10
        scenario = collector.finish_scenario(status='passed', duration_ms=0)
    finally:
        set_active_collector(None)
    assert len(scenario.steps) == 1
    step = scenario.steps[0]
    assert step.phase == 'when'
    assert step.narration.text == 'inserting money'
    assert step.children == []


def test_decorator_outside_scenario_is_silent() -> None:
    """A decorated helper called when the collector is idle / absent just runs."""
    set_active_collector(None)

    @when('helper')
    def helper() -> int:
        return 42

    assert helper() == 42  # no exception, no warning

    collector = Collector()
    set_active_collector(collector)
    try:
        assert helper() == 42  # collector idle: still silent
    finally:
        set_active_collector(None)


def test_decorator_pops_step_on_exception() -> None:
    """If the helper raises, the step is popped so the stack stays balanced."""
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    set_active_collector(collector)
    try:

        @when('boom')
        def boom() -> None:
            raise RuntimeError('nope')

        with pytest.raises(RuntimeError, match='nope'):
            boom()
        with given('after'):
            pass
        scenario = collector.finish_scenario(status='passed', duration_ms=0)
    finally:
        set_active_collector(None)
    assert [s.narration.text for s in scenario.steps] == ['boom', 'after']


def test_decorator_nested_inside_active_step_becomes_child() -> None:
    """A @when helper called inside `with when(...):` becomes a child step."""
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    set_active_collector(collector)
    try:

        @when('inner')
        def inner() -> None:
            return None

        with when('outer'):
            inner()
        scenario = collector.finish_scenario(status='passed', duration_ms=0)
    finally:
        set_active_collector(None)
    assert len(scenario.steps) == 1
    outer = scenario.steps[0]
    assert outer.narration.text == 'outer'
    assert [c.narration.text for c in outer.children] == ['inner']


def test_decorator_skips_push_when_active_fixture_descriptor_matches() -> None:
    """When the wrapper is called as the fixture body, push/pop are skipped —
    pytest_fixture_setup has already pre-created the recording's root step."""
    desc = StepDescriptor('given', 'a coffee machine')

    @desc
    def fixture_body() -> str:
        return 'value'

    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    root = Step(phase='given', narration=Narration(text='a coffee machine'))
    recording = FixtureRecording(root=root)
    token = collector.enter_fixture_setup(recording, descriptor=desc)
    set_active_collector(collector)
    try:
        assert fixture_body() == 'value'
        assert recording.stack == [root]
        assert root.children == []
    finally:
        collector.exit_fixture_setup(token)
        set_active_collector(None)


def test_decorator_records_when_called_from_inside_fixture_body() -> None:
    """A *different* @given helper called from inside a fixture body records
    into that fixture's recording (active descriptor doesn't match)."""
    outer_desc = StepDescriptor('given', 'a coffee machine')
    inner_desc = StepDescriptor('given', 'inserting money')

    @inner_desc
    def insert() -> None:
        return None

    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    root = Step(phase='given', narration=Narration(text='a coffee machine'))
    recording = FixtureRecording(root=root)
    token = collector.enter_fixture_setup(recording, descriptor=outer_desc)
    set_active_collector(collector)
    try:
        insert()
    finally:
        collector.exit_fixture_setup(token)
        set_active_collector(None)
    assert [c.narration.text for c in root.children] == ['inserting money']
