import pytest

from pytest_given import Template
from pytest_given.capture.collector import Collector, set_active_collector
from pytest_given.capture.decorators import (
    StepDescriptor,
    _normalize_activity,
    attach,
    given,
    scenario,
    then,
    when,
)
from pytest_given.capture.story import (
    activity as activity_fn,
)
from pytest_given.capture.story import (
    clear_story_registry,
)
from pytest_given.capture.story import (
    story as story_fn,
)
from pytest_given.model import (
    ActivityId,
    FixtureRecording,
    Glossary,
    Narration,
    NarrationLiteral,
    NarrationValue,
    PytestGivenError,
    Step,
)


@pytest.fixture(autouse=True)
def _reset_story_registry():
    from pytest_given.capture.glossary import clear_glossary_registry

    clear_story_registry()
    clear_glossary_registry()
    yield
    clear_story_registry()
    clear_glossary_registry()


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


def test_step_descriptor_decorator_accepts_tstring() -> None:
    """T-strings on decorators evaluate eagerly at module load; module-level
    values (e.g. Glossary handles) interpolate, and the wrapped function
    records the step on each call. For helpers needing bound-arg interpolation,
    pytest_given.Template is the canonical form."""
    g = Glossary()
    guest = g.actor('Guest')
    desc = StepDescriptor('given', t'our guest {guest("Alice")}')

    def fixture_body() -> str:
        return 'Alice'

    wrapped = desc(fixture_body)
    assert wrapped is not None  # didn't raise
    assert desc.narration.text == 'our guest Alice'


def test_step_descriptor_decorator_rejects_tstring_with_non_glossary_value() -> None:
    """A t-string on a decorator with a plain (non-glossary) interpolation
    would silently bake the module-level value; raise with a guiding message."""
    cup_size = 200
    desc = StepDescriptor('given', t'a {cup_size} ml cup')

    def helper() -> int:
        return cup_size

    with pytest.raises(PytestGivenError, match='cup_size'):
        desc(helper)


def test_step_descriptor_decorator_rejects_tstring_mixed_glossary_and_value() -> None:
    """Even when the t-string also contains a valid glossary handle, any plain
    value interpolation is rejected — partial safety isn't safety."""
    g = Glossary()
    guest = g.actor('Guest')
    age = 30
    desc = StepDescriptor('given', t'{guest("Alice")}, aged {age}')

    def helper() -> None: ...

    with pytest.raises(PytestGivenError, match='age'):
        desc(helper)


def test_when_then_records_two_sibling_steps_on_clean_exit() -> None:
    """when_then('W', 'T') wraps the body as a `when` and emits a sibling
    `then` once the body exits cleanly."""
    from pytest_given.capture.decorators import when_then

    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    set_active_collector(collector)
    try:
        with when_then('the action runs', 'the outcome holds'):
            pass
        scenario = collector.finish_scenario(status='passed', duration_ms=0)
    finally:
        set_active_collector(None)
    assert [(s.phase, s.narration.text) for s in scenario.steps] == [
        ('when', 'the action runs'),
        ('then', 'the outcome holds'),
    ]
    assert all(s.status == 'passed' for s in scenario.steps)
    assert all(s.children == [] for s in scenario.steps)


def test_when_then_pairs_with_inner_pytest_raises() -> None:
    """The canonical raise pattern: an inner pytest.raises swallows the error
    the body throws, so when_then still emits both sibling steps."""
    from pytest_given.capture.decorators import when_then

    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    set_active_collector(collector)
    try:
        with (
            when_then('the parser reads a bad document', 'it is rejected'),
            pytest.raises(ValueError, match='boom'),
        ):
            raise ValueError('boom')
        scenario = collector.finish_scenario(status='passed', duration_ms=0)
    finally:
        set_active_collector(None)
    assert [(s.phase, s.narration.text) for s in scenario.steps] == [
        ('when', 'the parser reads a bad document'),
        ('then', 'it is rejected'),
    ]


def test_when_then_omits_then_when_body_raises_uncaught() -> None:
    """If the body raises and nothing catches it, the outcome never held —
    the `when` is recorded but no `then` sibling is emitted, and the
    exception propagates."""
    from pytest_given.capture.decorators import when_then

    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    set_active_collector(collector)
    try:
        with pytest.raises(RuntimeError, match='nope'), when_then('act', 'result'):
            raise RuntimeError('nope')
        scenario = collector.finish_scenario(status='passed', duration_ms=0)
    finally:
        set_active_collector(None)
    assert [(s.phase, s.narration.text) for s in scenario.steps] == [
        ('when', 'act'),
    ]


def test_when_then_accepts_tstrings_for_glossary_refs() -> None:
    """Both narrations accept t-strings so glossary handles can render."""
    from pytest_given.capture.decorators import when_then

    g = Glossary()
    room = g.work_object('Room')
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    set_active_collector(collector)
    try:
        with when_then(t'booking a {room}', t'the {room} is held'):
            pass
        scenario = collector.finish_scenario(status='passed', duration_ms=0)
    finally:
        set_active_collector(None)
    assert [s.narration.text for s in scenario.steps] == [
        'booking a Room',
        'the Room is held',
    ]


def test_when_then_exported_from_package() -> None:
    """when_then is part of the public API."""
    import pytest_given

    assert pytest_given.when_then is not None


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


@pytest.mark.parametrize('phase_factory', [given, when, then])
def test_phase_with_pytest_given_template_as_context_manager_raises(
    phase_factory,
) -> None:
    """`with given/when/then(Template(...))` is rejected — t-strings handle
    the body case."""
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    set_active_collector(collector)
    try:
        with (
            pytest.raises(PytestGivenError, match='not supported in a test body'),
            phase_factory(Template('a {cup_size} ml cup')),
        ):
            pass
    finally:
        set_active_collector(None)


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


def test_decorator_with_template_validates_placeholder_in_signature() -> None:
    """@when(Template('{amount}')) accepts a function with `amount` in its signature."""

    @when(Template('I insert ${amount}'))
    def insert(machine: dict[str, int], amount: int) -> None:
        machine['balance'] += amount

    assert hasattr(insert, '_step_descriptor')
    assert insert._step_descriptor.narration.text == 'I insert ${amount}'


def test_decorator_with_template_placeholder_not_in_signature_raises() -> None:
    """Placeholder name absent from the signature → PytestGivenError at decoration."""
    with pytest.raises(PytestGivenError, match='amount'):

        @when(Template('I insert ${amount}'))
        def insert(machine: dict[str, int]) -> None: ...


def test_decorator_template_error_lists_available_parameters() -> None:
    with pytest.raises(PytestGivenError, match='machine'):

        @when(Template('I insert ${amount}'))
        def insert(machine: dict[str, int]) -> None: ...


def test_decorator_template_placeholder_matching_var_positional_raises() -> None:
    """Placeholder referencing *args is rejected at decoration time."""
    with pytest.raises(PytestGivenError, match='positional-or-keyword'):

        @when(Template('values: ${args}'))
        def helper(*args: int) -> None: ...


def test_decorator_template_placeholder_matching_var_keyword_raises() -> None:
    """Placeholder referencing **kwargs is rejected at decoration time."""
    with pytest.raises(PytestGivenError, match='positional-or-keyword'):

        @when(Template('values: ${kwargs}'))
        def helper(**kwargs: int) -> None: ...


def test_decorator_template_records_substituted_narration_per_call() -> None:
    """Each call substitutes its bound arg values into the recorded step."""
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    set_active_collector(collector)
    try:

        @when(Template('I insert ${amount}'))
        def insert(amount: int) -> int:
            return amount * 2

        assert insert(2) == 4
        assert insert(5) == 10
        scenario = collector.finish_scenario(status='passed', duration_ms=0)
    finally:
        set_active_collector(None)
    texts = [s.narration.text for s in scenario.steps]
    assert texts == ['I insert $2', 'I insert $5']


def test_decorator_template_records_structured_value_parts() -> None:
    """Substituted placeholders surface in `parts` as NarrationValue."""
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    set_active_collector(collector)
    try:

        @when(Template('I insert ${amount}'))
        def insert(amount: int) -> None: ...

        insert(7)
        scenario = collector.finish_scenario(status='passed', duration_ms=0)
    finally:
        set_active_collector(None)
    [step] = scenario.steps
    assert step.narration.text == 'I insert $7'
    assert step.narration.parts == [
        NarrationLiteral(value='I insert $'),
        NarrationValue(
            rendered='7',
            expression='amount',
            format_spec='',
            conversion=None,
        ),
    ]


def test_decorator_template_uses_default_when_caller_omits_arg() -> None:
    """Defaulted parameter not passed at the call → default substituted."""
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    set_active_collector(collector)
    try:

        @when(Template('I insert ${amount}'))
        def insert(amount: int = 1) -> None: ...

        insert()
        scenario = collector.finish_scenario(status='passed', duration_ms=0)
    finally:
        set_active_collector(None)
    assert scenario.steps[0].narration.text == 'I insert $1'


def test_decorator_template_preserves_format_spec_and_conversion() -> None:
    """Format spec and `!r` conversion flow through to the rendered step."""
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    set_active_collector(collector)
    try:

        @given(Template('a balance of {initial:.2f}'))
        def setup(initial: float) -> None: ...

        @then(Template('the receipt says {message!r}'))
        def assert_receipt(message: str) -> None: ...

        setup(3.5)
        assert_receipt('paid')
        scenario = collector.finish_scenario(status='passed', duration_ms=0)
    finally:
        set_active_collector(None)
    texts = [s.narration.text for s in scenario.steps]
    assert texts == ['a balance of 3.50', "the receipt says 'paid'"]


def test_decorator_template_on_fixture_raises() -> None:
    """pytest_given.Template on a fixture is rejected with the documented message."""

    @pytest.fixture
    def fixture_body() -> int:
        return 1

    desc = StepDescriptor('given', Template('value ${x}'))
    with pytest.raises(PytestGivenError, match='not yet supported'):
        desc(fixture_body)


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


def test_step_descriptor_accepts_activity_int():
    step = given('a thing', activity=3)
    assert step.activity_ids == (ActivityId(3),)


def test_step_descriptor_accepts_activity_sequence():
    step = when('an event', activity=[1, 2])
    assert step.activity_ids == (ActivityId(1), ActivityId(2))


def test_step_descriptor_activity_defaults_empty():
    step = then('a result')
    assert step.activity_ids == ()


def test_step_descriptor_rejects_non_int_activity_id():
    with pytest.raises(TypeError, match='activity'):
        given('x', activity='one')  # type: ignore[arg-type]


def test_step_descriptor_rejects_non_sequence_activity():
    with pytest.raises(TypeError, match='activity'):
        given('x', activity=1.5)  # type: ignore[arg-type]


# --- Task 7.1: ScenarioDecorator story= / activities= ---


def test_scenario_decorator_accepts_story_kwarg():
    g = Glossary()
    guest = g.actor('Guest')
    search = g.verb('search')
    room = g.work_object('Room')
    s = story_fn('Book Scenario Decorator', [activity_fn(guest, search, room)])
    deco = scenario('test', story=s)
    assert deco.story is s


def test_scenario_decorator_accepts_activities_kwarg():
    deco = scenario('test activities', activities=[1, 2, 3])
    assert deco.activity_ids == (ActivityId(1), ActivityId(2), ActivityId(3))


def test_scenario_decorator_defaults_story_none_and_activities_empty():
    deco = scenario('test defaults')
    assert deco.story is None
    assert deco.activity_ids == ()


def test_scenario_decorator_rejects_non_story_object():
    with pytest.raises(PytestGivenError, match='Story instance'):
        scenario('test', story='not-a-story')  # type: ignore[arg-type]


def test_normalize_activity_rejects_str():
    with pytest.raises(TypeError, match='int or a Sequence'):
        _normalize_activity('3')  # type: ignore[arg-type]


def test_normalize_activity_rejects_bool():
    with pytest.raises(TypeError, match='int or a Sequence'):
        _normalize_activity(True)  # type: ignore[arg-type]


def test_normalize_activity_rejects_non_int_in_sequence():
    with pytest.raises(TypeError, match='must contain int values'):
        _normalize_activity((1, 'x'))  # type: ignore[list-item]


def test_push_step_rejects_activity_id_not_in_story_no_scope() -> None:
    """Collector.push_step rejects activity_ids that aren't in the story at
    all when the scenario has no narrower scope. Validation lives on the
    collector so every push_step entry point gets it."""
    collector = Collector()
    g = Glossary()
    guest = g.actor('Guest')
    search = g.verb('search')
    room = g.work_object('Room')
    s = story_fn('Step Scope No Restriction', [activity_fn(guest, search, room)])
    collector.start_scenario('id', 'a', 'mod', [], story=s, activity_ids=())
    with pytest.raises(PytestGivenError, match='not in story'):
        collector.push_step(
            'given', Narration(text='a thing'), activity_ids=(ActivityId(99),)
        )


def test_push_step_rejects_activity_id_outside_scenario_scope() -> None:
    """When the scenario narrows scope, ids outside that scope are rejected
    by the collector regardless of story membership."""
    collector = Collector()
    g = Glossary()
    guest = g.actor('Guest')
    search = g.verb('search')
    room = g.work_object('Room')
    s = story_fn(
        'Scoped',
        [
            activity_fn(guest, search, room, id=1),
            activity_fn(guest('Alice'), search, room, id=2),
        ],
    )
    collector.start_scenario(
        'id', 'a', 'mod', [], story=s, activity_ids=(ActivityId(1),)
    )
    with pytest.raises(PytestGivenError, match='outside scenario scope'):
        collector.push_step(
            'given', Narration(text='a thing'), activity_ids=(ActivityId(2),)
        )


def test_push_step_requires_story_when_activity_ids_given() -> None:
    """Step activity_ids without a story on the scenario is a user error."""
    collector = Collector()
    collector.start_scenario('id', 'a', 'mod', [])
    with pytest.raises(PytestGivenError, match='requires a story'):
        collector.push_step(
            'given', Narration(text='a thing'), activity_ids=(ActivityId(1),)
        )
