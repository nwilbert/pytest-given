# pytest-given — pytest-given Self-Report

## ✓ A «scenario» failing on a pytest-given refusal points at the test, not at pytest-given
`tests/integration/test_plugin.py:157::test_refusal_frame_points_at_the_test`

- **given** a suite that nests across phases and mistypes a term
  - 📎 suite:
    ```
    
        from pytest_given import Glossary, given, scenario, when
    
        g = Glossary()
        g.actor('Guest')
    
        @scenario('nested across phases')
        def test_nest():
            with given('a machine'):
                with when('it brews'):
                    pass
    
        @scenario('a mistyped term')
        def test_lookup():
            with given('a guest'):
                g['Gust']
    ```
- **when** the suite runs with --given-json
- **then** both scenarios fail
- **then** each failure ends on its own test function

## ✓ A test without `@scenario` stays out of the «report»
`tests/integration/test_plugin.py:178::test_unannotated_test_not_in_report`

- **given** a suite whose only test is undecorated
- **when** the suite runs with --given-json
- **then** the test itself passes
- **then** the «report» holds no «scenario»

## ✓ A «step fixture» is «grafted» in as a given «step»
`tests/integration/test_plugin.py:247::test_step_fixture_appears_as_given_step`

- **given** a «scenario» consuming a «step fixture»
  - 📎 suite:
    ```
    import pytest
    from pytest_given import scenario, given, then
    
    @pytest.fixture
    @given("a prepared value")
    def value():
        return 42
    
    @scenario("Fixture test")
    def test_fixture(value):
        with then(f"value is {value}"):
            assert value == 42
    ```
- **when** the suite runs with --given-json
- **then** the test passes
- **then** the «step» from the fixture leads the recorded steps

## ✓ The «cases» of a «parametrized scenario» become one «scenario» with a «parameter table»
`tests/integration/test_plugin.py:285::test_parametrized_test_as_table` · parametrization

- **given** a «parametrized scenario» over two «cases»
  - 📎 suite:
    ```
    import pytest
    from pytest_given import scenario, given, when, then
    
    @scenario("Param test", tags=["math"])
    @pytest.mark.parametrize("a,b,expected", [(1, 2, 3), (2, 3, 5)])
    def test_add(a, b, expected):
        with given(t"a={a} and b={b}"):
            pass
        with then(t"sum is {expected}"):
            assert a + b == expected
    ```
- **when** the suite runs with --given-json
- **then** both cases pass
- **then** the two runs collapse into one «scenario»
- **then** the «parameter table» holds a param column per argument
- **then** it holds one row per «case», with that row's values
- **then** the grouped steps carry a placeholder per matching name

## ✓ A refusal on a run with no sink does not claim a «report» was skipped
`tests/integration/test_plugin.py:424::test_a_grouping_error_without_sinks_does_not_say_report_not_written` · validation

- **given** a suite whose narration varies across parametrize cases
- **when** the suite runs with no --given-* sink
- **then** the refusal is reported without claiming a report was skipped

## ✓ A refused run discards the previous run's «report»
`tests/integration/test_plugin.py:452::test_a_grouping_error_discards_the_previous_report` · validation

- **given** a suite whose narration varies across parametrize cases
  - 📎 suite:
    ```
    import pytest
    from pytest_given import scenario, when
    
    @scenario("Brew")
    @pytest.mark.parametrize("cup_size", [200, 350])
    def test_brew(cup_size):
        with when(f"it brews {cup_size} ml"):
            assert cup_size > 0
    ```
- **given** a «report» on disk from a previous run
- **when** the suite runs with those sinks configured
- **then** the run says no report was written, naming the sink
- **then** the stale files are gone rather than left reading as current

## ✓ An unknown «source link» preset stops the run before it collects
`tests/integration/test_plugin.py:520::test_an_unknown_source_link_preset_fails_before_the_suite_runs` · validation

- **given** a suite that would otherwise pass
  - 📎 suite:
    ```
    from pytest_given import scenario, then
    
    @scenario("Brew")
    def test_brew():
        with then("it brews"):
            assert True
    ```
- **when** the suite runs with a misspelled «source link» preset
- **then** the run ends as a usage error, naming the flag the user typed
- **then** no test ran

## ✓ An unknown «source link» preset in an ini reports the ini name
`tests/integration/test_plugin.py:552::test_an_unknown_source_link_preset_in_an_ini_names_the_ini` · validation

- **given** a suite configured through the ini rather than the flag
- **when** the suite runs with an HTML sink
- **then** the error names the ini setting, not a flag the user never typed

## ✓ A «report» that fails to render discards the previous one too
`tests/integration/test_plugin.py:578::test_a_render_failure_leaves_no_half_replaced_report` · validation

- **given** a suite with one «scenario»
- **given** a «report» pair on disk from a previous run
- **when** the run trips a «renderer» failure
- **then** the run fails, saying no report was written
- **then** neither the stale pair nor a half-written new one survives

## ✓ A fixture failing in teardown fails its finished «scenario»
`tests/integration/test_plugin.py:797::test_fixture_teardown_failure_fails_the_scenario`

- **given** a «scenario» whose fixture raises after its yield
  - 📎 suite:
    ```
    import pytest
    from pytest_given import scenario, given, then
    
    @pytest.fixture
    def resource():
        yield 1
        raise RuntimeError("teardown boom")
    
    @scenario("Teardown-failed")
    def test_a(resource):
        with given("a resource"):
            value = resource
        with then("it is one"):
            assert value == 1
    ```
- **when** the suite runs with --given-json
- **then** pytest counts the test passed and its teardown an error
- **then** the «report» marks the «scenario» failed with the teardown error

## ✓ A «step fixture» refuses «steps» and «attachments» in its teardown · 2 cases
`tests/integration/test_plugin.py:934::test_step_fixture_teardown_refuses_steps_and_attachments` · validation

- **given** a «step fixture» that adds a {late} after its yield
  - 📎 suite — *see parameter table*
- **when** the suite runs
- **then** the test passes but its teardown errors with a PytestGivenError

| late | suite |
|---|---|
| step | suite |
| attachment | suite |

- **step** — suite:
  ```
  import pytest
  from pytest_given import scenario, given, then, attach
  
  @pytest.fixture
  @given("a thing")
  def thing():
      yield 1
      with given("a late step"): pass
  
  @scenario("Teardown raises")
  def test_use(thing):
      with then("it is one"):
          assert thing == 1
  ```

- **attachment** — suite:
  ```
  import pytest
  from pytest_given import scenario, given, then, attach
  
  @pytest.fixture
  @given("a thing")
  def thing():
      yield 1
      attach("late", "data")
  
  @scenario("Teardown raises")
  def test_use(thing):
      with then("it is one"):
          assert thing == 1
  ```

## ✓ A fixture decorated with @when or @then is refused · 2 cases
`tests/integration/test_plugin.py:966::test_when_or_then_on_a_fixture_is_refused` · validation

- **given** a fixture decorated with @{decorator}
  - 📎 suite — *see parameter table*
- **when** the suite runs
- **then** the run fails with a PytestGivenError that points at @given

| decorator | suite |
|---|---|
| when | suite |
| then | suite |

- **when** — suite:
  ```
  import pytest
  from pytest_given import scenario, then, when
  
  @pytest.fixture
  @when("a coin is inserted")
  def coin():
      return 2
  
  @scenario("uses the fixture")
  def test_use(coin):
      with then("the coin is 2"):
          assert coin == 2
  ```

- **then** — suite:
  ```
  import pytest
  from pytest_given import scenario, then, then
  
  @pytest.fixture
  @then("a coin is inserted")
  def coin():
      return 2
  
  @scenario("uses the fixture")
  def test_use(coin):
      with then("the coin is 2"):
          assert coin == 2
  ```

## ✓ A «scenario» is matched against each of its «stories»
`tests/integration/test_plugin.py:1860::test_scenario_matched_against_two_stories`

- **given** a «scenario» binding two «stories» whose «sentence» its «narration» fits
  - 📎 suite:
    ```
    from pytest_given import Glossary, scenario, sentence, story, when
    
    g = Glossary()
    guest = g.actor('Guest')
    search = g.activity('search')
    room = g.work_object('Room')
    a = story('Book', [sentence(guest, search, room)])
    b = story('Stay', [sentence(guest, search, room)])
    
    @scenario('both', stories=[a, b])
    def test_both():
        with when(t'the {guest} does a {search} for a {room}'):
            pass
    ```
- **when** the suite runs with --given-json
- **then** the test passes
- **then** the «scenario» «binds» both «stories» and covers the «sentence» of each

## ✓ A declared «story» no «scenario» covers appears in the report
`tests/integration/test_plugin.py:1932::test_a_declared_story_no_scenario_covers_appears`

- **given** a suite declaring a «story» that no «scenario» names or «pins»
  - 📎 suite:
    ```
    from pytest_given import Glossary, given, scenario, sentence, story
    
    g = Glossary()
    guest = g.actor('Guest')
    search = g.activity('search')
    room = g.work_object('Room')
    story('Unread', [sentence(guest, search, room)])
    
    @scenario('x')
    def test_x():
        with given('something'):
            pass
    ```
- **when** the suite runs with --given-json
- **then** the report lists the «story», its «sentence» covered by nothing

## ✓ A pinned «scenario» still counts its «step» «pins»
`tests/integration/test_plugin.py:1970::test_a_pinned_scenario_still_counts_its_step_pins`

- **given** a «scenario» pinning one «sentence», whose «steps» pin a second and narrate a third
  - 📎 suite:
    ```
    from pytest_given import Glossary, given, scenario, sentence, story
    
    g = Glossary()
    guest = g.actor('Guest')
    search = g.activity('search')
    room = g.work_object('Room')
    s = story('Book', [
        sentence(guest('Alice'), search, room),
        sentence(guest('Bob'), search, room),
        sentence(guest, search, room)])
    
    @scenario('x', stories=s, pins=s[1])
    def test_x():
        with given('a pinned step', pins=s[2]):
            pass
        with given(t'the {guest} does a {search} for a {room}'):
            pass
    ```
- **when** the suite runs with --given-json
- **then** the «scenario» covers both pinned «sentences» and not the one its narration would match

## ✓ A «step» «pin» into a «story» outside stories= covers it
`tests/integration/test_plugin.py:2017::test_a_step_pin_into_a_story_outside_stories_covers_it`

- **given** a «step» pinning a «story» its «scenario» does not name
  - 📎 suite:
    ```
    from pytest_given import Glossary, given, scenario, sentence, story
    
    g = Glossary()
    guest = g.actor('Guest')
    search = g.activity('search')
    room = g.work_object('Room')
    a = story('Book', [sentence(guest, search, room)])
    b = story('Stay', [sentence(guest, search, room)])
    
    @scenario('x', stories=a)
    def test_x():
        with given('thing', pins=b[1]):
            pass
    ```
- **when** the suite runs with --given-json
- **then** the «scenario» passes and covers the pinned «sentence», in the «story» it did not name

## ✓ A wide «fixture recording» keeps its «pins» in every «scenario» it is grafted into
`tests/integration/test_plugin.py:2059::test_a_wide_fixture_pin_counts_in_every_scenario_it_reaches`

- **given** a module-scoped «step fixture» pinning a «sentence», set up first by an unannotated test
  - 📎 suite:
    ```
    import pytest
    from pytest_given import Glossary, given, scenario, sentence, story
    
    g = Glossary()
    guest = g.actor('Guest')
    search = g.activity('search')
    room = g.work_object('Room')
    a = story('Book', [sentence(guest, search, room)])
    b = story('Stay', [sentence(guest, search, room)])
    
    @pytest.fixture(scope='module')
    @given('a module-scoped arrangement')
    def wide():
        with given('an inner step', pins=a[1]):
            pass
        yield 1
    
    def test_unannotated(wide):
        assert wide == 1
    
    @scenario('first', stories=a)
    def test_first(wide):
        pass
    
    @scenario('second', stories=b)
    def test_second(wide):
        pass
    ```
- **when** the suite runs with --given-json
- **then** every test passes, and both «scenarios» cover the pinned «sentence», whichever «story» they name

## ✓ An Annotated label carrying a «pin» pins its «step»
`tests/integration/test_plugin.py:2121::test_annotated_label_carrying_a_pin_pins_its_step`

- **given** a «scenario» whose Annotated given(...) label on a «plain fixture» carries a «pin»
  - 📎 suite:
    ```
    from typing import Annotated
    import pytest
    from pytest_given import Glossary, given, scenario, sentence, story
    
    g = Glossary()
    guest = g.actor('Guest')
    search = g.activity('search')
    room = g.work_object('Room')
    s = story('Book', [sentence(guest, search, room)])
    
    @pytest.fixture
    def room_number():
        return 7
    
    @scenario('x', stories=s)
    def test_x(room_number: Annotated[int, given('a room', pins=s[1])]):
        pass
    ```
- **when** the suite runs
- **then** the label's «step» carries the «pin»

## ✓ An Annotated label retells the «pins» of the fixture label it replaces · 3 cases
`tests/integration/test_plugin.py:2161::test_annotated_label_pins_retell_the_fixture_root`

- **given** a label with pins={label_pins} over a fixture pinning a[1]
- **when** the suite runs
- **then** the grafted root carries the expected «pins», and the inner «step» keeps its own

| label_pins | root_pins |
|---|---|
| None | [{'story_id': 'book', 'sentence_id': 1}] |
| [] | [] |
| [a[2]] | [{'story_id': 'book', 'sentence_id': 2}] |

## ✓ An Annotated Template label on an unparametrized «scenario» fails that «scenario»
`tests/integration/test_plugin.py:2651::test_annotated_template_label_without_parametrize_fails_scenario`

- **given** a Template label on a plain fixture parameter
  - 📎 suite:
    ```
    from typing import Annotated
    import pytest
    from pytest_given import scenario, given, when, Template
    
    @pytest.fixture
    def room():
        return 101
    
    @scenario('a room is booked')
    def test_it(room: Annotated[int, given(Template('room {room} is free'))]):
        with when('it is booked'):
            pass
    ```
- **when** the suite runs with an HTML «report»
- **then** the scenario errors, naming the parameter and the fix
- **then** the HTML «report» is still written

## ✓ An Annotated Template label whose placeholder names no parametrize column fails its «scenario»
`tests/integration/test_plugin.py:2689::test_annotated_template_label_naming_no_column_fails_scenario`

- **given** a «parametrized scenario» whose Template label names a plain fixture, not a column
  - 📎 suite:
    ```
    from typing import Annotated
    import pytest
    from pytest_given import scenario, given, when, Template
    
    @pytest.fixture
    def room():
        return 101
    
    @scenario('bad')
    @pytest.mark.parametrize('x', [1])
    def test_it(x, room: Annotated[int, given(Template('room {room}'))]):
        with when('it is booked'):
            pass
    ```
- **when** the suite runs
- **then** the scenario errors, naming the placeholder and its parameter

## ✓ A bare run writes no «report» at all
`tests/integration/test_plugin.py:2781::test_no_output_flags_writes_nothing`

- **given** a suite with one «scenario»
  - 📎 suite:
    ```
    
        import pytest
        from pytest_given import scenario, given, when, then
    
        @scenario('Buy coffee')
        def test_buy():
            with given('a machine'):
                pass
            with when('I insert money'):
                pass
            with then('I get coffee'):
                assert True
    ```
- **when** the suite runs with no output flag
- **then** the run passes
- **then** no report directory appears in the default location

## ✓ A bare `--given-md` prints the «narration» to stdout
`tests/integration/test_plugin.py:2794::test_given_md_prints_fenced_block`

- **given** a suite with one «scenario»
- **when** the suite runs with a bare --given-md
- **then** the narration is printed between the fence markers

## ✓ `--given-html` alone writes no JSON «report»
`tests/integration/test_plugin.py:2815::test_given_html_alone_writes_no_json`

- **given** a suite with one «scenario»
- **when** the suite runs with --given-html alone
- **then** the HTML rendering is written
- **then** no JSON lands in the default location

## ✓ A sink flag pointed at a source file is refused before the suite runs
`tests/integration/test_plugin.py:2835::test_a_sink_path_that_is_not_a_report_file_is_refused` · validation

- **given** a suite with one «scenario»
- **when** a bare --given-html swallows the test path that follows it
- **then** the run is refused, naming the path and the flag-order fix
- **then** the source file is left exactly as it was, not overwritten

## ✓ A rejected authoring form fails the run and writes no «report»
`tests/integration/test_plugin.py:2868::test_a_rejected_form_fails_the_run_and_writes_no_sink` · validation

- **given** a suite whose narration varies across parametrize cases
  - 📎 suite:
    ```
    
    import pytest
    from pytest_given import scenario, when
    
    @pytest.mark.parametrize('cup_size', [200, 350])
    @scenario('Brew')
    def test_brew(cup_size):
        with when(f'the machine brews {cup_size} ml'):
            pass
    ```
- **when** the suite runs with all three sinks configured
- **then** the run fails, naming the offending form
- **then** not one sink is written, and no traceback escapes

## ✓ `--given-title` names the «report» instead of the rootdir
`tests/integration/test_plugin.py:2900::test_given_title_cli_flag_names_the_report`

- **given** a suite with one «scenario»
- **when** the suite runs with --given-title
- **then** the test passes
- **then** the title reaches the JSON metadata
- **then** the title also heads the Markdown rendering

## ✓ `--given-theme` sets the «theme» the HTML «report» opens in
`tests/integration/test_plugin.py:3003::test_given_theme_cli_flag_sets_the_report_default`

- **given** a suite with one «scenario»
- **when** the suite runs with --given-theme=dark
- **then** the test passes
- **then** the page declares dark as its default «theme»

## ✓ An unknown «theme» stops the run before it collects
`tests/integration/test_plugin.py:3051::test_an_unknown_theme_fails_before_the_suite_runs` · validation

- **given** a suite that would otherwise pass
- **when** the suite runs with a misspelled «theme», and no HTML sink
- **then** the run ends as a usage error, naming the flag the user typed
- **then** no test ran

## ✓ A run with no sink still enforces the «grouping» rules
`tests/integration/test_plugin.py:3168::test_bare_run_still_enforces_the_grouping_rules` · validation

- **given** a suite whose f-string narration records no parts
  - 📎 suite:
    ```
    import pytest
    from pytest_given import scenario, then
    
    @scenario("Brew")
    @pytest.mark.parametrize('cup_size', [200, 300])
    def test_brew(cup_size):
        with then(f'it brews {cup_size} ml'):
            assert cup_size
    ```
- **when** the suite runs with no sink configured
- **then** the run still fails, naming the offending form

## ✓ «Narration lint» is off unless it is asked for
`tests/integration/test_plugin_lint.py:89::test_disabled_by_default_records_no_sources_and_reports_nothing`

- **given** a suite with one flawed «step»
  - 📎 suite:
    ```
    
    from pytest_given import scenario, given, when, then
    
    @scenario("Empty given")
    def test_empty_given():
        with given("a value"):
            pass
        with when("computing"):
            x = 2
        with then("it is two"):
            assert x == 2
    ```
- **when** the suite runs without the lint flag
- **then** the run passes and says nothing about the lint
- **then** no step source is recorded, so the AST surface costs nothing

## ✓ An error-«severity» «finding» fails the run
`tests/integration/test_plugin_lint.py:118::test_enabled_error_finding_fails_the_run`

- **given** a suite whose given «step» has an empty body
  - 📎 suite:
    ```
    
    from pytest_given import scenario, given, when, then
    
    @scenario("Empty given")
    def test_empty_given():
        with given("a value"):
            pass
        with when("computing"):
            x = 2
        with then("it is two"):
            assert x == 2
    ```
- **when** the suite runs with the lint enabled
- **then** the run exits failed, naming the «lint rule» and the step

## ✓ A «lint rule» downgraded to warn reports without failing the run
`tests/integration/test_plugin_lint.py:150::test_warn_override_prints_but_does_not_fail`

- **given** a suite whose given «step» has an empty body
  - 📎 suite:
    ```
    
    from pytest_given import scenario, given, when, then
    
    @scenario("Empty given")
    def test_empty_given():
        with given("a value"):
            pass
        with when("computing"):
            x = 2
        with then("it is two"):
            assert x == 2
    ```
- **when** the suite runs with that «lint rule» set to warn
- **then** the run still passes
- **then** the «finding» is printed anyway

## ✓ Either «narration lint» flag overrides the ini for one run
`tests/integration/test_plugin_lint.py:228::test_the_flag_overrides_the_ini_in_both_directions`

- **given** a suite with one flawed «step»
  - 📎 suite:
    ```
    
    from pytest_given import scenario, given, when, then
    
    @scenario("Empty given")
    def test_empty_given():
        with given("a value"):
            pass
        with when("computing"):
            x = 2
        with then("it is two"):
            assert x == 2
    ```
- **when** the suite runs with the lint enabled by ini but off by flag
- **then** the lint does not run
- **when** the suite runs with the lint disabled by ini but on by flag
- **then** the lint runs and its error finding fails the run

## ✓ An error «finding» leaves a more specific exit code alone
`tests/integration/test_plugin_lint.py:440::test_lint_error_does_not_mask_a_more_specific_exit_code`

- **given** a suite whose lint would fail, under a stale ignore entry
  - 📎 suite:
    ```
    
    from pytest_given import scenario, given, when, then
    
    @scenario("Empty given")
    def test_empty_given():
        with given("a value"):
            pass
        with when("computing"):
            x = 2
        with then("it is two"):
            assert x == 2
    ```
- **when** the suite runs deselected, so nothing is collected
- **then** the run keeps NO_TESTS_COLLECTED rather than reporting a test failure

## ✓ A failure inside the lint keeps the «report» it was handed
`tests/integration/test_plugin_lint.py:456::test_a_lint_failure_is_reported_and_keeps_the_written_report` · validation

- **given** a clean suite and a lint pass that raises
- **when** the suite runs with an HTML sink
- **then** the failure is summarized rather than raised as a traceback
- **then** the report that was already written is still there

## ✓ A «scenario» records under its «node ID»
`tests/unit/capture/test_collector.py:41::test_start_and_finish_scenario`

- **given** a fresh «collector»
- **when** a «scenario» starts under its «Node ID» and finishes
- **then** it carries its «Node ID», name, status and «tag»

## ✓ A «scenario» is timed from past its «step fixture» setup
`tests/unit/capture/test_collector.py:57::test_duration_excludes_fixture_setup`

- **given** a «collector» whose clock reads 100.3s once setup is done
- **when** the clock is started past setup and the body runs 0.2s
- **then** the recorded duration is the body alone, not the setup before it

## ✓ «Steps» record with their «phases»
`tests/unit/capture/test_collector.py:79::test_collect_steps`

- **given** an «active scenario» in a fresh «collector»
- **when** a given and a when «step» are pushed
- **then** each «step» carries its «phase»

## ✓ «Steps» pushed during fixture setup record into the «fixture recording»
`tests/unit/capture/test_collector.py:223::test_push_step_during_fixture_setup_records_into_recording`

- **given** a «fixture recording» under setup
- **when** a «step» is pushed inside the fixture body
- **then** it is recorded as a child of the recording root

## ✓ An «attachment» lands on the «step» being recorded
`tests/unit/capture/test_collector.py:247::test_attach_during_fixture_setup_records_into_recording`

- **given** a «fixture recording» under setup
- **when** an «attachment» is attached inside the fixture body
- **then** the «attachment» lands on the recording root

## ✓ Fixture-body «steps» do not leak into the «active scenario»
`tests/unit/capture/test_collector.py:269::test_push_step_routing_isolates_recording_from_scenario`

- **given** an «active scenario» with a «fixture recording»
- **when** a «step» is pushed inside the fixture body
- **then** the step lives only in the recording, not the scenario

## ✓ An «attachment» outside every «step» is refused
`tests/unit/capture/test_collector.py:325::test_attach_outside_any_step_raises` · validation

- **given** an «active scenario» with no «step» open
- **when** an «attachment» is made from the test body
- **then** it is refused rather than dropped

## ✓ A «fixture recording» is deep-copied when «grafted»
`tests/unit/capture/test_collector.py:343::test_graft_recording_deep_copies_into_scenario`

- **given** a «fixture recording» with a nested child «step»
- **when** a «graft» copies it into the «active scenario»
- **then** the scenario gains a deep copy of the recorded steps

## ✓ The «collector» fails a «scenario» that already finished
`tests/unit/capture/test_collector.py:485::test_fail_marks_a_finished_scenario_failed`

- **given** a «scenario» that already finished as passed
- **when** the «collector» is told of a failure after that
- **then** the recorded «scenario» carries the failure

## ✓ A teardown failure keeps the error the «scenario» already carries
`tests/unit/capture/test_collector.py:501::test_fail_keeps_an_existing_error`

- **given** a «scenario» that already failed in its body
- **when** its fixture then also fails in teardown
- **then** the body failure is what the report shows

## ✓ A «collector» reports which «node ids» it recorded
`tests/unit/capture/test_collector.py:517::test_records_reports_only_recorded_node_ids`

- **given** a «collector» that recorded one «scenario»
- **when** the recorded and an unrecorded node id are both asked about
- **then** only the recorded node id is claimed

## ✓ A leaf given is «grafted» as a childless given «step»
`tests/unit/capture/test_collector.py:535::test_graft_leaf_given_appends_childless_given_step`

- **given** an «active scenario» is being recorded
- **when** a leaf «graft» appends a childless «step»
- **then** the step is a given with no children

## ✓ «Grafting» with an override replaces the root label but keeps children
`tests/unit/capture/test_collector.py:556::test_graft_recording_override_replaces_root_narration_keeps_children`

- **given** a «fixture recording» whose root has a label and a child
- **when** a «graft» supplies an override «narration»
- **then** the grafted root shows the override text and keeps its children

## ✓ «Grafting» with no «active scenario» is refused
`tests/unit/capture/test_collector.py:586::test_graft_leaf_given_without_scenario_is_refused`

- **given** a collector with no «active scenario»
- **when** a leaf «graft» runs
- **then** the invariant is asserted rather than silently dropping the step

## ✓ «FileGlossary» lookup is case-insensitive
`tests/unit/capture/test_file_glossary.py:29::test_lookup_is_case_insensitive`

- **given** a «file glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** the same «term» is looked up in three different cases
- **then** every lookup resolves to one handle type and the same id

## ✓ Repeated lookups return the same handle
`tests/unit/capture/test_file_glossary.py:43::test_handles_are_memoized`

- **given** a «file glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** the same «term» is looked up twice
- **then** both lookups return the one memoized handle

## ✓ File-loaded «terms» start «kindless»
`tests/unit/capture/test_file_glossary.py:56::test_terms_start_kindless`

- **given** a Markdown glossary file with no kind column
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** a «file glossary» loads it
- **then** each «term» is «kindless» until «kind inference» runs

## ✓ An unknown name raises with a suggestion
`tests/unit/capture/test_file_glossary.py:73::test_unknown_name_raises_with_suggestion` · diagnostics, validation

- **given** a «file glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** a misspelt «term» is looked up
- **then** a PytestGivenError is raised with a spelling hint

## ✓ Handles are usable inline in a «sentence»
`tests/unit/capture/test_file_glossary.py:91::test_usable_inline_in_sentence`

- **given** a «file glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** its handles build a «sentence»
- **then** each slot becomes a «term ref»

## ✓ Calling a handle overrides its display
`tests/unit/capture/test_file_glossary.py:107::test_call_overrides_display`

- **given** a «file glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** a handle is called to name an «instance»
- **then** the «term ref» carries the overridden display

## ✓ An explicit kind column sets «term» kinds
`tests/unit/capture/test_file_glossary.py:126::test_explicit_kind_column`

- **given** a Markdown glossary with an explicit Kind column
  - 📎 Glossary file:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Guest | x | Actor |
    | Room | y | Work Object |
    | book | z | Activity |
    ```
- **when** the «file glossary» reads the Kind column
- **then** kinds come straight from the file, not «kind inference»

## ✓ A kind column can be selected by integer index
`tests/unit/capture/test_file_glossary.py:147::test_kind_column_by_integer_index`

- **given** a Markdown glossary with the kind in the third column
  - 📎 Glossary file:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Guest | x | Actor |
    | Room | y | Work Object |
    ```
- **when** the «file glossary» selects the kind column by index
- **then** the kinds are read from that column

## ✓ A «work_object» kind alias maps to the object kind
`tests/unit/capture/test_file_glossary.py:166::test_work_object_underscore_alias`

- **given** a glossary whose Kind cell says work_object
  - 📎 Glossary file:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Room | y | work_object |
    ```
- **when** the «file glossary» parses the kind
- **then** it normalizes to the «work object» kind

## ✓ An unrecognized kind value is rejected
`tests/unit/capture/test_file_glossary.py:181::test_unrecognized_kind_value_raises` · diagnostics, validation

- **given** a glossary whose Kind cell holds an unknown value
  - 📎 Glossary file:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Guest | x | Wizard |
    ```
- **when** the «file glossary» loads the file
- **then** a PytestGivenError names the unrecognized kind

## ✓ A missing «glossary» file is reported clearly
`tests/unit/capture/test_file_glossary.py:201::test_missing_file_raises` · validation

- **given** a path to a file that does not exist
- **when** a «file glossary» is opened on that path
- **then** a PytestGivenError reports the file is not found

## ✓ A «term» cell with no alphanumeric characters is rejected
`tests/unit/capture/test_file_glossary.py:226::test_empty_id_term_cell_raises` · diagnostics, validation

- **given** a row whose «term» cell has no id-able characters
  - 📎 Glossary file:
    ```
    | Term | Meaning |
    |---|---|
    | @#$ | some definition |
    ```
- **when** the «file glossary» loads the file
- **then** a PytestGivenError is raised with file:line context

## ✓ A «file glossary» error about its tables names the file · 3 cases
`tests/unit/capture/test_file_glossary.py:246::test_table_errors_name_the_file` · diagnostics, validation

- **given** a glossary file with {problem}
- **given** that file on disk as bad.md
  - 📎 Glossary file — *see parameter table*
- **when** a «file glossary» loads it
- **then** a PytestGivenError names the file before the problem

| problem | doc | expected | Glossary file |
|---|---|---|---|
| no table | # no table here<br> | bad\.md: found no Markdown pipe table | Glossary file |
| a short row | \| Term \| Meaning \|<br>\|---\|---\|<br>\| Guest \|<br> | bad\.md: data row at line 3 | Glossary file |
| no Term column | \| Word \| Meaning \|<br>\|---\|---\|<br>\| Guest \| x \|<br> | bad\.md: column 'Term' | Glossary file |

- **no table, # no table here<br>, bad\.md: found no Markdown pipe table** — Glossary file:
  ```
  # no table here
  ```

- **a short row, \| Term \| Meaning \|<br>\|---\|---\|<br>\| Guest \|<br>, bad\.md: data row at line 3** — Glossary file:
  ```
  | Term | Meaning |
  |---|---|
  | Guest |
  ```

- **no Term column, \| Word \| Meaning \|<br>\|---\|---\|<br>\| Guest \| x \|<br>, bad\.md: column 'Term'** — Glossary file:
  ```
  | Word | Meaning |
  |---|---|
  | Guest | x |
  ```

## ✓ Conflicting duplicate rows are rejected
`tests/unit/capture/test_file_glossary.py:286::test_conflicting_duplicate_rows_raise` · validation

- **given** two rows for one «term» with different definitions
  - 📎 Glossary file:
    ```
    | Term | Meaning |
    |---|---|
    | Guest | First definition. |
    | Guest | Second definition. |
    ```
- **when** the «file glossary» loads the file
- **then** a PytestGivenError points at the second row as the conflict

## ✓ A blank description normalizes to «undefined»
`tests/unit/capture/test_file_glossary.py:312::test_blank_description_cell_normalizes_to_none`

- **given** a row whose description cell is blank
  - 📎 Glossary file:
    ```
    | Term | Meaning |
    |---|---|
    | Guest |   |
    ```
- **when** the «file glossary» parses it
- **then** the «term» definition is None, i.e. «undefined»

## ✓ Identical duplicate rows collapse to one «term»
`tests/unit/capture/test_file_glossary.py:327::test_idempotent_duplicate_rows_ok`

- **given** two identical rows for the same «term»
  - 📎 Glossary file:
    ```
    | Term | Meaning |
    |---|---|
    | Guest | A person booking. |
    | Guest | A person booking. |
    ```
- **when** the «file glossary» parses them
- **then** they collapse to a single «term»

## ✓ Calling «FileGlossary» looks up a known «term»
`tests/unit/capture/test_file_glossary.py:350::test_file_glossary_call_known_name_returns_handle`

- **given** a «file glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** a known «term» is looked up by call
- **then** a «deferred term» is returned

## ✓ «FileGlossary» is a closed vocabulary
`tests/unit/capture/test_file_glossary.py:364::test_file_glossary_call_unknown_name_raises` · validation

- **given** a «file glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** an unknown name is called
- **then** a PytestGivenError is raised
- **then** no new «term» was created

## ✓ «Term» ids are derived as URL-safe slugs · 8 cases
`tests/unit/capture/test_glossary.py:27::test_id_derive_produces_expected_slug`

- **given** the name {text}
- **when** it is slugified into a «term» id
- **then** the id is the expected slug {expected}

| text | expected |
|---|---|
| Guest | 'guest' |
| Order received | 'order-received' |
|   Work Object   | 'work-object' |
| do_the_thing | 'do-the-thing' |
| Buy / sell | 'buy-sell' |
| Guest #1 | 'guest-1' |
| café | 'caf' |
| booking system | 'booking-system' |

## ✓ A name with no id-able characters is rejected · 4 cases
`tests/unit/capture/test_glossary.py:53::test_id_derive_raises_on_empty_result` · validation

- **given** the name {text}
- **when** it is slugified into a «term» id
- **then** a PytestGivenError reports the derived id is empty

| text |
|---|
| --- |
|     |
|  |
| ### |

## ✓ Calling an «actor» names a distinct «instance»
`tests/unit/capture/test_glossary.py:101::test_actor_call_returns_instance_with_distinct_display`

- **given** an «actor» handle for Guest
- **when** the «actor» is called with a name
- **then** an «instance» with a distinct display is returned

## ✓ Calling an «activity» records an «inflection» of the same «term»
`tests/unit/capture/test_glossary.py:127::test_activity_call_returns_inflection_sharing_term_identity`

- **given** an «activity» handle for confirm
- **when** the «activity» is called with a surface form
- **then** an «inflection» sharing the activity identity is returned

## ✓ Registering an «actor» returns a typed handle
`tests/unit/capture/test_glossary.py:147::test_glossary_actor_registers_and_returns_handle`

- **given** an empty glossary
- **when** an «actor» is registered with a definition
- **then** a handle carrying the «actor» kind is returned

## ✓ Re-registering a «term» with matching fields is idempotent
`tests/unit/capture/test_glossary.py:182::test_glossary_re_registration_with_matching_fields_is_idempotent`

- **given** an «actor» already registered with a definition
- **when** the same name and definition are registered again
- **then** both handles share the one «term»

## ✓ Re-registering a «term» with a different definition is rejected
`tests/unit/capture/test_glossary.py:199::test_glossary_re_registration_with_mismatched_definition_raises` · validation

- **given** an «actor» already registered with one definition
- **when** the name is registered again with a different definition
- **then** a PytestGivenError reports the conflict with the prior registration

## ✓ The same name cannot be two different kinds
`tests/unit/capture/test_glossary.py:217::test_glossary_cross_kind_collision_raises` · validation

- **given** a name already registered as an «actor»
- **when** the same name is registered as an «activity»
- **then** a PytestGivenError reports the conflict with the prior registration

## ✓ Registering an «actor» captures its definition site
`tests/unit/capture/test_glossary.py:241::test_glossary_actor_captures_source`

- **given** a rootdir-aware glossary
- **when** an «actor» is registered
- **then** the «term» records a «source link» to this file

## ✓ Calling the «glossary» declares a «kindless» «term»
`tests/unit/capture/test_glossary.py:335::test_call_declares_kindless_term`

- **given** an empty glossary
- **when** a «term» is declared by call, without a kind
- **then** the «term» is registered as «kindless»

## ✓ Subscript looks up an already-declared «term»
`tests/unit/capture/test_glossary.py:433::test_subscript_get_only_returns_handle`

- **given** a glossary with one declared «term»
- **when** the name is looked up by subscript
- **then** the returned «term» is the declared one

## ✓ Subscripting an unknown name raises with a hint
`tests/unit/capture/test_glossary.py:446::test_subscript_unknown_name_raises_with_hint` · diagnostics, validation

- **given** a glossary with one declared «term»
- **when** a near-miss name is subscripted
- **then** a PytestGivenError is raised with a spelling hint

## ✓ «Term» kinds are inferred from clause-slot positions
`tests/unit/capture/test_kind_inference.py:46::test_infers_actor_activity_object_by_position`

- **given** a glossary of three «kindless» «term» entries
- **when** «kind inference» runs over a «story»
- **then** they are inferred as «actor», «activity», «work object» by slot

## ✓ A «term» named only in the second «clause» of a «sentence» gets its kind inferred
`tests/unit/capture/test_kind_inference.py:65::test_infers_kinds_from_a_second_clause`

- **given** a glossary of «kindless» «term» entries
- **given** a «sentence» whose second «clause» starts at another «actor»
- **when** «kind inference» runs over its «story»
- **then** the first «term» of the second clause is an «actor»

## ✓ An «actor» «slot» anywhere wins over a noun «slot» elsewhere
`tests/unit/capture/test_kind_inference.py:103::test_actor_anywhere_beats_object`

- **given** a «glossary» of «kindless» «term» entries
- **given** one «story» putting a «term» in a noun slot and another putting it in an «actor» slot
- **when** «kind inference» runs over both «stories»
- **then** its inferred kind is «actor»

## ✓ A «term» used in no «story» stays «kindless»
`tests/unit/capture/test_kind_inference.py:128::test_never_used_stays_kindless`

- **given** a «term» referenced by no «story»
- **when** «kind inference» runs with no stories
- **then** the «term» remains «kindless»

## ✓ A «term» in both a verb and a noun «slot» is a conflict
`tests/unit/capture/test_kind_inference.py:140::test_activity_and_noun_conflict_raises` · diagnostics, validation

- **given** a «kindless» «term» used in a verb slot and a noun slot
- **when** «kind inference» runs over both «stories»
- **then** a PytestGivenError names the conflicting term

## ✓ A declared kind consistent with its «slot» is kept
`tests/unit/capture/test_kind_inference.py:163::test_declared_kind_verified_and_kept`

- **given** a glossary with explicitly declared «term» kinds
- **when** «kind inference» runs over a matching «story»
- **then** the declared kinds are verified and preserved

## ✓ A declared «activity» in an «actor» «slot» is rejected
`tests/unit/capture/test_kind_inference.py:185::test_declared_activity_in_actor_slot_raises` · diagnostics, validation

- **given** a «term» declared as an «activity»
- **when** «kind inference» finds it in the «actor» slot
- **then** a PytestGivenError names the misplaced term

## ✓ A «term» used as both «activity» and «actor» is a conflict
`tests/unit/capture/test_kind_inference.py:203::test_activity_and_actor_conflict_raises` · diagnostics, validation

- **given** a «kindless» «term» used in a verb slot and an actor slot
- **when** «kind inference» runs over both «stories»
- **then** a PytestGivenError names the conflicting term

## ✓ A declared «work object» in an «actor» «slot» is rejected
`tests/unit/capture/test_kind_inference.py:229::test_declared_object_in_actor_slot_raises` · diagnostics, validation

- **given** a «term» declared as a «work object»
- **when** «kind inference» finds it in the «actor» slot
- **then** a PytestGivenError names the misplaced term

## ✓ A declared «actor» in a verb «slot» is rejected
`tests/unit/capture/test_kind_inference.py:247::test_declared_actor_in_verb_slot_raises` · validation

- **given** a «term» declared as an «actor»
- **when** «kind inference» finds it at position 1 (the verb slot)
- **then** a PytestGivenError says an actor cannot fill the verb slot

## ✓ A conflict error names only the offending «stories»
`tests/unit/capture/test_kind_inference.py:266::test_conflict_where_names_only_offending_stories` · diagnostics, validation

- **given** an «actor» «term» that also appears in a verb slot
- **when** «kind inference» runs over both «stories»
- **then** a PytestGivenError reports the conflict
- **then** only the offending story is named in the message

## ✓ A conflict message excludes «stories» with an unrelated «slot»
`tests/unit/capture/test_kind_inference.py:293::test_inferred_conflict_where_excludes_unrelated_slot_stories` · diagnostics, validation

- **given** a «kindless» «term» used in verb, actor and noun slots
- **when** «kind inference» runs over all three «stories»
- **then** a PytestGivenError reports the verb-vs-actor conflict
- **then** only the verb and actor stories are named, not the noun one

## ✓ A declared «activity» in a noun «slot» is rejected
`tests/unit/capture/test_kind_inference.py:323::test_declared_activity_in_noun_slot_raises` · validation

- **given** a «term» declared as an «activity»
- **when** «kind inference» finds it at position ≥2 (a noun slot)
- **then** a PytestGivenError says a verb cannot fill the noun slot

## ✓ «Slot» positions alternate verb/noun after the «actor»
`tests/unit/capture/test_kind_inference.py:342::test_slot_for_maps_odd_positions_to_verb`

- **given** the five positions of a short clause
- **when** the «slot» rule is applied to each position
- **then** position 0 is the actor «slot», then verb and noun alternate

## ✓ A pipe table parses into «term» and definition rows
`tests/unit/capture/test_markdown_glossary.py:24::test_parses_default_columns`

- **given** a Markdown document with one pipe table
  - 📎 Markdown document:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest | A person booking. |
    | Room  | A bookable room. |
    ```
- **when** the parser reads it into rows for a «file glossary»
- **then** each row carries a «term», definition and source line

## ✓ Multiple tables in one file are merged
`tests/unit/capture/test_markdown_glossary.py:41::test_merges_multiple_tables`

- **given** a document containing two separate pipe tables
  - 📎 Markdown document:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest | A person booking. |
    | Room  | A bookable room. |
    
    ## More
    
    | Term | Meaning |
    |---|---|
    | Search | Look up. |
    ```
- **when** the parser reads the whole document
- **then** every table contributes its «term» rows

## ✓ Columns can be selected by header name
`tests/unit/capture/test_markdown_glossary.py:59::test_column_by_header_name_case_insensitive`

- **given** a table with custom, differently-cased header names
  - 📎 Markdown document:
    ```
    | Word | Note | Role |
    |---|---|---|
    | Guest | x | Actor |
    ```
- **when** the parser selects columns by header name
- **then** the named columns are matched case-insensitively

## ✓ Escaped pipes are preserved in cells
`tests/unit/capture/test_markdown_glossary.py:74::test_escaped_pipe_in_cell`

- **given** cells containing escaped pipe characters (\|)
  - 📎 Markdown document:
    ```
    | Term | Meaning |
    |---|---|
    | A\|B | pipe\|here |
    ```
- **when** the parser splits the row
- **then** the escaped pipe survives as a literal pipe

## ✓ Tables inside fenced code blocks are skipped
`tests/unit/capture/test_markdown_glossary.py:91::test_skips_tables_in_fenced_code_blocks`

- **given** a fenced code block that contains a look-alike table
  - 📎 Markdown document:
    ````
    ```
    | Term | Meaning |
    |---|---|
    | Fake | nope |
    ```
    
    | Term | Meaning |
    |---|---|
    | Real | yes |
    ````
- **when** the parser reads the document
- **then** only the real table outside the fence contributes rows

## ✓ A file with no pipe table is rejected
`tests/unit/capture/test_markdown_glossary.py:109::test_no_table_raises` · validation

- **given** a document with no pipe table
  - 📎 Markdown document:
    ```
    # Just a heading
    
    No tables here.
    ```
- **when** the parser reads it for a «file glossary»
- **then** a PytestGivenError reports that the file has no pipe table

## ✓ A missing named column is rejected
`tests/unit/capture/test_markdown_glossary.py:129::test_missing_named_column_raises` · diagnostics, validation

- **given** a Markdown document with one pipe table
  - 📎 Markdown document:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest | A person booking. |
    | Room  | A bookable room. |
    ```
- **when** the parser selects a header name that is absent
- **then** a PytestGivenError names the missing column

## ✓ A column index out of range is rejected
`tests/unit/capture/test_markdown_glossary.py:146::test_index_out_of_range_raises` · diagnostics, validation

- **given** a Markdown document with one pipe table
  - 📎 Markdown document:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest | A person booking. |
    | Room  | A bookable room. |
    ```
- **when** the parser selects a column index past the table width
- **then** a PytestGivenError names the out-of-range column

## ✓ A data row with too few columns is rejected
`tests/unit/capture/test_markdown_glossary.py:170::test_data_row_with_fewer_columns_raises` · diagnostics, validation

- **given** a table with a data row narrower than its header
  - 📎 Markdown document:
    ```
    | Term | Meaning | Type |
    |---|---|---|
    | Guest | A person |
    | Room | A bookable room | place |
    ```
- **when** the parser reads the short row
- **then** a PytestGivenError points at the short row

## ✓ Bold «term» cells render as clean «terms»
`tests/unit/capture/test_markdown_glossary.py:188::test_strips_bold_from_term_cell`

- **given** a «term» cell written with **bold** emphasis
  - 📎 Markdown document:
    ```
    | Term | Meaning |
    |---|---|
    | **Scenario** | A decorated test. |
    ```
- **when** the parser reads the term cell
- **then** the emphasis is unwrapped to the plain canonical

## ✓ Italic and inline-code «term» cells are unwrapped
`tests/unit/capture/test_markdown_glossary.py:207::test_strips_italic_and_inline_code_from_term_cell`

- **given** «term» cells using *italic* and `code` emphasis
  - 📎 Markdown document:
    ```
    | Term | Meaning |
    |---|---|
    | *Step* | one. |
    | `given` | two. |
    ```
- **when** the parser reads the term cells
- **then** each unwraps to its plain text

## ✓ Underscores inside an identifier survive
`tests/unit/capture/test_markdown_glossary.py:222::test_preserves_underscores_inside_term_identifier`

- **given** a «term» literally named work_object
  - 📎 Markdown document:
    ```
    | Term | Meaning |
    |---|---|
    | work_object | a thing. |
    ```
- **when** the parser reads the term cell
- **then** the single underscores are not treated as emphasis

## ✓ Emphasis is stripped from kind cells too
`tests/unit/capture/test_markdown_glossary.py:237::test_strips_emphasis_from_kind_cell`

- **given** a Kind cell written with bold emphasis
  - 📎 Markdown document:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Guest | x | **Actor** |
    ```
- **when** the parser reads the kind cell
- **then** the kind is unwrapped to plain text

## ✓ Definition markdown is left intact
`tests/unit/capture/test_markdown_glossary.py:252::test_leaves_description_markdown_intact`

- **given** a definition cell rich with inline code
  - 📎 Markdown document:
    ```
    | Term | Meaning |
    |---|---|
    | Scenario | A test decorated with `@scenario(...)`. |
    ```
- **when** the parser reads the row
- **then** the definition keeps its markup for the tooltip

## ✓ A pipe line without a separator is not a table
`tests/unit/capture/test_markdown_glossary.py:270::test_pipe_line_without_separator_is_skipped`

- **given** prose containing a stray pipe, then a real table
  - 📎 Markdown document:
    ```
    This line has a | in it but no separator follows.
    Next line is not a separator.
    
    | Term | Meaning |
    |---|---|
    | Real | yes |
    ```
- **when** the parser reads the document
- **then** only the real pipe table produces rows

## ✓ A code-span «term» cell keeps the markup inside it
`tests/unit/capture/test_markdown_glossary.py:292::test_code_span_term_cell_keeps_inner_markup`

- **given** a «term» cell written as a code span around an asterisk pair
  - 📎 Markdown document:
    ```
    | Term | Meaning |
    |---|---|
    | `a*b*c` | a literal. |
    ```
- **when** the parser reads the term cell
- **then** the span unwraps once and its contents stay literal

## ✓ A «step» pairs its «narration» with a «phase»
`tests/unit/capture/test_step_descriptor.py:54::test_context_manager_basic`

- **when** a given «step» descriptor is created
- **then** it carries the given «phase» and its «narration»

## ✓ A «step» opened outside a «scenario» warns rather than raising
`tests/unit/capture/test_step_descriptor.py:154::test_context_manager_unannotated_test_warns_instead_of_raises`

- **given** a «collector» recording inside an undecorated test
- **when** a given «step» is opened against it
- **then** a `PytestGivenWarning` is raised, not an error
- **then** it names the missing `@scenario`, so a suite can filter it

## ✓ «when_then» records the action and its outcome as siblings
`tests/unit/capture/test_step_descriptor.py:287::test_when_then_records_two_sibling_steps_on_clean_exit`

- **given** an «active scenario» in a local «collector»
- **when** a «when_then» block exits cleanly
- **then** a when and a sibling then «step» are recorded

## ✓ «when_then» pairs with an inner pytest.raises
`tests/unit/capture/test_step_descriptor.py:314::test_when_then_pairs_with_inner_pytest_raises`

- **given** an «active scenario» in a local «collector»
- **when** the «when_then» body raises and an inner pytest.raises swallows it
- **then** both sibling steps are still recorded

## ✓ «when_then» omits the then when the body raises uncaught
`tests/unit/capture/test_step_descriptor.py:342::test_when_then_omits_then_when_body_raises_uncaught` · validation

- **given** an «active scenario» in a local «collector»
- **when** the «when_then» body raises with nothing catching inside
- **then** only the when step is recorded — the outcome never held

## ✓ A cross-phase «step» cannot open inside a «when_then» body · 2 cases
`tests/unit/capture/test_step_descriptor.py:384::test_when_then_rejects_cross_phase_nested_step` · validation

- **given** an «active scenario» in a local «collector»
- **when** a given or then opens inside the «when_then» body
- **then** a PytestGivenError reports the cross-phase nesting
- **then** the «step stack» is left balanced

| phase_name |
|---|
| given |
| then |

## ✓ A nested when becomes a child of the «when_then» action
`tests/unit/capture/test_step_descriptor.py:416::test_when_then_allows_nested_when_as_child_sub_step`

- **given** an «active scenario» in a local «collector»
- **when** a when opens inside the «when_then» body
- **then** the sub-action is a child of the action and the then still follows

## ✓ `@scenario` marks the test function without wrapping it
`tests/unit/capture/test_step_descriptor.py:463::test_scenario_marks_the_function_without_wrapping_it`

- **given** a test function taking one fixture
- **when** the function is decorated
- **then** the very same function comes back, keeping its signature
- **then** it carries the «scenario» marker, and a plain one does not

## ✓ An «attachment» label must be plain text · 3 cases
`tests/unit/capture/test_step_descriptor.py:533::test_attach_rejects_a_non_str_label` · validation

- **given** a non-str «attachment» label of kind {label_kind}
- **when** it is attached
- **then** a PytestGivenError says «attachment» labels are plain text

| label_kind |
|---|
| deferred-template |
| t-string |
| not-a-string |

## ✓ A `Template` «narration» is refused in a test body · 3 cases
`tests/unit/capture/test_step_descriptor.py:575::test_phase_with_pytest_given_template_as_context_manager_raises` · validation

- **given** an «active scenario» in a local «collector»
- **when** a {phase_name} «step» opens on a `Template`
- **then** a PytestGivenError says a template is not supported in a test body

| phase_name |
|---|
| given |
| when |
| then |

## ✓ A bare number or name is refused where a «pin» goes · 3 cases
`tests/unit/capture/test_step_descriptor.py:967::test_pins_refuse_a_bare_number_or_name` · validation

- **given** a sentence number or name written without its «story»
- **when** a «step» is declared with it
- **then** a PytestGivenError shows the handle form

| bare |
|---|
| 3 |
| cancel |
| [1, 2] |

## ✓ An «actor» handle in a «clause» becomes a «term ref»
`tests/unit/capture/test_story.py:61::test_clause_dispatches_actor_to_clause_term_ref`

- **given** a Guest actor
- **given** a search activity
- **given** a Room work object
- **when** a «clause» is built from three glossary handles
- **then** the «actor» slot becomes a «term ref»

## ✓ An inflected «activity» keeps its «term» identity but shows the «inflection»
`tests/unit/capture/test_story.py:105::test_clause_dispatches_inflected_activity_to_clause_term_ref_with_inflected_display`

- **given** a Guest actor
- **given** a search activity
- **given** a Room work object
- **given** an «activity» handle called with an «inflection»
- **when** it takes the verb slot of a «clause»
- **then** the «term ref» shows the inflection over the same «activity»

## ✓ A bare string in a «clause» becomes a connective word
`tests/unit/capture/test_story.py:127::test_clause_dispatches_bare_string_to_clause_word`

- **given** a Guest actor
- **given** a search activity
- **given** a Room work object
- **when** a «clause» is built with a bare word between term nodes
- **then** the bare word becomes a «clause part» word, not a «term ref»

## ✓ A «clause» needs at least an «actor», an «activity» and a node
`tests/unit/capture/test_story.py:143::test_clause_rejects_fewer_than_three_parts` · validation

- **given** a Guest actor
- **given** a search activity
- **when** a «clause» of only two parts is built
- **then** a PytestGivenError rejects it as too short, counting the parts

## ✓ Position 0 of a «clause» must be an «actor»
`tests/unit/capture/test_story.py:161::test_clause_rejects_work_object_in_position_0` · validation

- **given** a search activity
- **given** a Room work object
- **when** a «clause» is built with a «work object» in position 0
- **then** a PytestGivenError says position 0 is the «actor» slot

## ✓ An «activity» cannot open a «clause»
`tests/unit/capture/test_story.py:177::test_clause_rejects_activity_in_position_0` · validation

- **given** a Guest actor
- **given** a search activity
- **given** a Room work object
- **when** an «activity» is placed in position 0 of a «clause»
- **then** a PytestGivenError says position 0 is the «actor» slot

## ✓ A bare string may stand in for the «actor» «slot»
`tests/unit/capture/test_story.py:192::test_clause_allows_bare_string_in_position_0`

- **given** a search activity
- **given** a Room work object
- **when** a bare string takes position 0 of a «clause»
- **then** it is accepted as a «clause part» word

## ✓ Position 1 of a «clause» must be an «activity»
`tests/unit/capture/test_story.py:202::test_clause_rejects_actor_in_position_1` · validation

- **given** a Guest actor
- **given** a Room work object
- **when** an «actor» is placed in position 1 of a «clause»
- **then** a PytestGivenError says position 1 is the verb «slot»

## ✓ A «work object» cannot fill the verb «slot»
`tests/unit/capture/test_story.py:217::test_clause_rejects_work_object_in_position_1` · validation

- **given** a Guest actor
- **given** a Room work object
- **when** a «work object» is placed in position 1 of a «clause»
- **then** a PytestGivenError says position 1 is the verb «slot»

## ✓ Position 2 of a «clause» must be a noun
`tests/unit/capture/test_story.py:233::test_clause_rejects_activity_in_position_2` · validation

- **given** a Guest actor
- **given** a search activity
- **when** an «activity» is placed in position 2 of a «clause»
- **then** a PytestGivenError says position 2 is the noun slot

## ✓ A bare verb may sit between two real entity nodes
`tests/unit/capture/test_story.py:248::test_clause_allows_bare_verb_between_term_nodes`

- **given** a Guest actor
- **given** a Room work object
- **when** a bare verb sits between an «actor» and a «work object»
- **then** the entities are term refs and the verb stays a bare word

## ✓ A «clause» may be fully bare words
`tests/unit/capture/test_story.py:265::test_clause_allows_fully_bare_words`

- **given** three plain words with no glossary handles
- **when** a «clause» is built from them
- **then** every part is a «clause part» word

## ✓ Node/edge alternation allows a trailing connective node
`tests/unit/capture/test_story.py:284::test_clause_allows_node_edge_alternation_with_connective`

- **given** an «actor», an «activity», a «work object» and a second actor
- **when** they form a five-part «clause» joined by a connective
- **then** even positions are term-ref nodes and the connective stays a word

## ✓ A «clause» may not end on a dangling edge
`tests/unit/capture/test_story.py:310::test_clause_rejects_dangling_edge` · validation

- **given** an «actor», «activity» and «work object» plus a connective
- **when** a clause ending on a connective edge is built
- **then** a PytestGivenError names the trailing arrow with no target

## ✓ A single-clause «sentence» synthesizes one «clause»
`tests/unit/capture/test_story.py:340::test_sentence_single_clause_synthesizes_one_clause`

- **given** a Guest actor
- **given** a search activity
- **given** a Room work object
- **when** a «sentence» is built from handles directly
- **then** it wraps a single «clause»

## ✓ A «sentence» may hold several «clauses»
`tests/unit/capture/test_story.py:356::test_sentence_accepts_multiple_clauses`

- **given** a Guest actor
- **given** a search activity
- **given** a Room work object
- **given** two «clauses»
- **when** they are combined into one «sentence»
- **then** the sentence carries both clauses

## ✓ Mixing loose parts and prebuilt «clauses» is rejected
`tests/unit/capture/test_story.py:373::test_sentence_mixing_parts_and_clauses_raises` · validation

- **given** a Guest actor
- **given** a search activity
- **given** a Room work object
- **given** a prebuilt «clause»
- **when** it is combined with loose handles in one «sentence»
- **then** a PytestGivenError rejects the mix

## ✓ A «story» auto-numbers its «sentences» from one
`tests/unit/capture/test_story.py:393::test_story_auto_numbers_sentences_from_one`

- **given** a Guest actor
- **given** a search activity
- **given** a Room work object
- **when** a «story» is built from two «sentence» rows
- **then** the sentences are numbered 1 and 2

## ✓ A «story» derives its id from its title
`tests/unit/capture/test_story.py:411::test_story_derives_id_from_title`

- **given** a human-readable story title
- **when** a «story» is built from it
- **then** its id is the slugified title

## ✓ A «story» may span only one «glossary»
`tests/unit/capture/test_story.py:423::test_story_rejects_two_glossaries` · validation

- **given** a Guest actor
- **given** a search activity
- **given** a Room work object
- **given** two sentences that reach two different glossaries
- **when** a «story» is built spanning both glossaries
- **then** a PytestGivenError says a story spans multiple glossaries

## ✓ A «sentence» «handle» is looked up by name or by number
`tests/unit/capture/test_story.py:469::test_story_hands_out_a_sentence_by_name_and_by_number`

- **given** a Guest actor
- **given** a search activity
- **given** a Room work object
- **given** a «story» whose second «sentence» is named
- **when** the «sentence» is looked up by its name and by its number
- **then** both «handles» name sentence 2 of that «story»

## ✓ Iterating a «story» yields its «sentence» handles
`tests/unit/capture/test_story.py:491::test_iterating_a_story_yields_its_sentence_handles`

- **given** a Guest actor
- **given** a search activity
- **given** a Room work object
- **given** a «story» of two «sentences»
- **when** the «story» is iterated
- **then** it yields each «sentence» handle in order

## ✓ Looking up a «sentence» the «story» lacks lists the ones it has
`tests/unit/capture/test_story.py:528::test_story_lookup_miss_lists_the_sentences`

- **given** a Guest actor
- **given** a search activity
- **given** a Room work object
- **given** a «story» with an unnamed and a named «sentence»
- **when** an unknown name is looked up
- **then** a PytestGivenError lists the story's sentences

## ✓ Two «sentences» of one «story» cannot share a name
`tests/unit/capture/test_story.py:596::test_story_rejects_duplicate_sentence_names` · validation

- **given** a Guest actor
- **given** a search activity
- **given** a Room work object
- **given** two «sentences» both named "cancel"
- **when** a «story» is built from them
- **then** a PytestGivenError names the duplicate and both numbers

## ✓ An empty or padded «sentence» name is refused · 3 cases
`tests/unit/capture/test_story.py:614::test_sentence_rejects_an_empty_or_padded_name` · validation

- **given** a Guest actor
- **given** a search activity
- **given** a Room work object
- **given** the «sentence» name {bad_name}
- **when** a «sentence» is built with that name
- **then** a PytestGivenError says what a name must be

| bad_name |
|---|
| '' |
| ' cancel' |
| 'cancel ' |

## ✓ Two «stories» with the same id collide
`tests/unit/capture/test_story.py:634::test_story_id_collision_raises_with_both_sites` · validation

- **given** a «story» already declared under an id
- **when** a second story is declared with the same slug
- **then** a PytestGivenError reports the id was already declared

## ✓ A «clause» may chain a second verb-object pair
`tests/unit/capture/test_story.py:717::test_clause_allows_second_verb_edge`

- **given** an «actor», two «activity» and two «work object» handles
- **when** they form a five-node «clause» (actor verb object verb object)
- **then** every slot is a «term ref», with no bare words

## ✓ A declared «work object» in a verb «slot» is rejected at construction
`tests/unit/capture/test_story.py:769::test_file_glossary_declared_kind_in_wrong_slot_raises` · validation

- **given** a «file glossary» declaring Room a work object
- **when** Room is placed in the verb «slot»
- **then** a PytestGivenError names the term and its declared kind

## ✓ A «slot» error names the «term», not its repr
`tests/unit/capture/test_story.py:795::test_slot_error_message_stays_compact` · diagnostics

- **given** a Guest actor
- **given** a Room work object
- **given** a search activity
- **when** a «work object» is placed in the verb slot
- **then** the message names the term without dumping the glossary
- **then** the message is short and free of dataclass reprs

## ✓ A kindless «term» stays valid in any «slot»
`tests/unit/capture/test_story.py:816::test_kindless_term_is_accepted_in_either_slot` · validation

- **given** a «kindless» «term» declared with g(...)
- **when** it is placed in a node «slot» and a verb slot
- **then** both clauses construct, leaving the kind to inference

## ✓ A non-handle «clause part» names its type
`tests/unit/capture/test_story.py:831::test_non_handle_part_names_its_type` · validation, diagnostics

- **given** a Guest actor
- **given** a Room work object
- **when** an int is passed where an «activity» handle belongs
- **then** a PytestGivenError names the offending type and the clause

## ✓ A Template parses a bare placeholder
`tests/unit/capture/test_template.py:41::test_template_parses_single_placeholder` · parametrization

- **given** a deferred `Template` with one placeholder
- **when** the template is parsed
- **then** it splits into literal and placeholder «narration» parts

## ✓ A Template substitutes parametrize values
`tests/unit/capture/test_template.py:85::test_template_substitute_basic` · parametrization

- **given** a `Template` referencing a parametrize column
- **when** a parametrize value is substituted in
- **then** the placeholder is filled with that value

## ✓ A Template accepts bare identifiers only · 3 cases
`tests/unit/capture/test_template.py:122::test_template_non_identifier_raises_pytest_given_error` · validation

- **given** the placeholder {text}
- **when** a `Template` is built from it
- **then** a PytestGivenError says bare identifiers only

| text |
|---|
| count={obj.attr} |
| {d[key]} |
| {x + 1} |

## ✓ A t-string interpolation becomes a value part
`tests/unit/capture/test_template.py:152::test_parse_tstring_single_interpolation`

- **given** a t-string step with one interpolated value
- **when** the t-string is parsed at runtime
- **then** the interpolation becomes a «narration» value part

## ✓ A t-string can interpolate an arbitrary expression
`tests/unit/capture/test_template.py:219::test_parse_tstring_expression`

- **given** a t-string step interpolating a computed expression
- **when** the t-string is parsed
- **then** the «value highlight» part records the full expression

## ✓ A «glossary» handle in a t-string emits a «term ref»
`tests/unit/capture/test_template.py:259::test_tstring_with_actor_emits_term_ref`

- **given** an «actor» handle from the glossary
- **when** the handle is interpolated into a t-string step
- **then** the step carries a «term ref» for that «actor»

## ✓ A «work object» handle in a t-string emits a «term ref»
`tests/unit/capture/test_template.py:287::test_tstring_with_work_object_emits_term_ref`

- **given** a «work object» handle from the glossary
- **when** it is interpolated into a t-string step
- **then** the step carries a «term ref» for that «work object»

## ✓ A bare «activity» handle keeps its canonical display
`tests/unit/capture/test_template.py:310::test_tstring_with_activity_emits_term_ref_with_canonical_display`

- **given** an «activity» handle used without an «inflection»
- **when** it is interpolated into a t-string step
- **then** the «term ref» shows the canonical activity

## ✓ An inflected «activity» in a t-string shows the «inflection»
`tests/unit/capture/test_template.py:327::test_tstring_with_inflected_activity_emits_term_ref_with_inflected_display`

- **given** an «activity» handle called with an «inflection»
- **when** it is interpolated into a t-string step
- **then** the «term ref» shows the inflection but keeps the activity id

## ✓ A «term ref» may not carry a format spec
`tests/unit/capture/test_template.py:369::test_tstring_term_ref_with_format_spec_raises` · validation

- **given** an «actor» handle interpolated with a format spec
- **when** the t-string is parsed
- **then** a PytestGivenError says a «term ref» takes no format spec

## ✓ A «FileGlossary» handle works in a t-string «step»
`tests/unit/capture/test_template.py:412::test_tstring_with_file_term_handle_emits_term_ref`

- **given** a «deferred term» from a «file glossary»
- **when** it is interpolated into a t-string step
- **then** the step carries a single «term ref»

## ✓ «Narration lint» flags a «step» whose body does nothing
`tests/unit/lint/test_ast_rules.py:101::test_empty_step_fires_on_pass_only_body`

- **given** a given «step» whose body is only `pass`
  - 📎 step body:
    ```
    def test_a():
        with given('a value'):
            pass
    ```
- **when** the AST «rules» parse that source
- **then** an empty-step «finding» points at the «step» line
- **then** its «severity» is error

## ✓ «Narration lint» flags a then «step» that checks nothing
`tests/unit/lint/test_ast_rules.py:265::test_then_without_check_fires`

- **given** a then «step» whose body only calls
  - 📎 step body:
    ```
    def test_a():
        with then('it is one'):
            x = compute()
            handlers[0](x)
    ```
- **when** the AST «rules» parse that source
- **then** a then-without-check «finding» reports the unchecked then

## ✓ «Narration lint» flags an assert outside a then «step» · 2 cases
`tests/unit/lint/test_ast_rules.py:432::test_check_outside_then_fires_on_assert_in_given_or_when`

- **given** a {phase} «step» whose body asserts
  - 📎 step body — *see parameter table*
- **when** the AST «rules» parse that source
- **then** a warn «finding» names the {phase} step holding the assert

| phase | step body |
|---|---|
| given | step body |
| when | step body |

- **given** — step body:
  ```
  def test_a():
      with given('a stocked machine'):
          machine = stock()
          assert machine['coffees'] > 0
  ```

- **when** — step body:
  ```
  def test_a():
      with when('a stocked machine'):
          machine = stock()
          assert machine['coffees'] > 0
  ```

## ✓ «Narration lint» flags a then «step» that folds in the action
`tests/unit/lint/test_ast_rules.py:572::test_action_in_then_fires_when_no_when_exists`

- **given** a «scenario» with no when, acting inside its then
  - 📎 step body:
    ```
    def test_a():
        with given('a machine'):
            machine = stock()
        with then('it brews'):
            assert brew(machine) == 'coffee'
    ```
- **when** the AST «rules» parse that source
- **then** a warn «finding» points at the then and says no when acts

## ✓ «Narration lint» flags a «narration» interpolating a name the body never uses
`tests/unit/lint/test_ast_rules.py:752::test_unused_interpolation_fires_on_unused_bare_identifier`

- **given** a given «step» whose body never loads the name
  - 📎 step body:
    ```
    def test_a():
        with given(t'a {size} ml cup'):
            cup = make_cup()
    ```
- **when** the AST «rules» parse that source
- **then** a warn «finding» names the interpolation the body ignores

## ✓ «Narration lint» flags a passed «scenario» that skips a «phase»
`tests/unit/lint/test_runtime_rules.py:63::test_missing_phase_fires_on_passed_two_phase_scenario`

- **given** a passed «scenario» narrating only given and then
- **when** the runtime «rules» run
- **then** one missing-phase «finding» names the absent when and the «scenario» source
- **then** its «severity» is the catalog default, warn

## ✓ «Narration lint» flags a «tag» that duplicates a «term»
`tests/unit/lint/test_runtime_rules.py:134::test_tag_shadows_term_fires_once_per_unique_tag`

- **given** a «glossary» defining one «term»
- **given** two scenarios carrying that word as a «tag»
- **when** the runtime «rules» run
- **then** a single warn «finding» names the «tag» and the «term» it shadows, counting the scenarios and naming one

## ✓ «Narration lint» flags a «term» referenced by no «scenario» name, «step» or «story»
`tests/unit/lint/test_runtime_rules.py:225::test_dead_term_flags_unreferenced_term`

- **given** a «glossary» holding one unreferenced «term»
- **when** the runtime «rules» run over no scenarios and no stories
- **then** the «finding» names the unreferenced «term»
- **then** its «severity» is off — the rule is opt-in

## ✓ «Narration lint» counts a «term» named only in the second «clause» of a «sentence» as referenced
`tests/unit/lint/test_runtime_rules.py:296::test_dead_term_passes_term_referenced_only_by_a_second_clause`

- **given** a «story» whose one «sentence» names the «term» only in its second «clause»
- **when** the runtime «rules» run over that story
- **then** dead-term flags none of its terms

## ✓ A «sentence» is referenced by its «terms», whatever their surface form
`tests/unit/report/test_coverage.py:54::test_a_refs_collects_term_ids_whatever_the_display`

- **given** a «sentence» written with an «instance» and an «inflection»
- **when** «coverage» collects the «sentence» references
- **then** they are the «term» ids alone; words contribute nothing

## ✓ A multi-clause «sentence» unions references across its «clauses»
`tests/unit/report/test_coverage.py:80::test_a_refs_unions_across_multi_clause_sentence`

- **given** a «sentence» with two «clauses»
- **when** «coverage» collects the «sentence» references
- **then** the «terms» of both clauses are present

## ✓ A «sentence» whose «clauses» start at different «actors» builds and is covered
`tests/unit/report/test_coverage.py:108::test_sentence_with_clauses_from_different_actors_is_covered`

- **given** a «sentence» of two «clauses»: a guest signs the register, and a clerk signs the register
- **given** a «step» naming both actors, the activity and the register
- **when** «coverage» is computed against the «story»
- **then** the «sentence» is covered

## ✓ A «step» is referenced by its «terms», whatever their surface form
`tests/unit/report/test_coverage.py:164::test_s_for_step_collects_term_ids_whatever_the_display`

- **given** a «step» naming an «instance» and an «inflection»
- **when** «coverage» collects the «step» references
- **then** they are the «term» ids alone

## ✓ An «instance» and its bare «term» cover each other
`tests/unit/report/test_coverage.py:193::test_compute_coverage_matches_instance_and_bare_term_both_ways`

- **given** a «sentence» naming a bare «actor»
- **given** the same «sentence» naming an «instance» of that actor
- **given** a «step» naming the «instance», and one naming the bare actor
- **when** «coverage» is computed for each pairing
- **then** the «instance» «step» covers the bare «sentence»
- **then** the bare «step» covers the «instance» «sentence»

## ✓ Promoting a bare word to an «activity» ref drops «coverage» from a «step» that matched
`tests/unit/report/test_coverage.py:262::test_compute_coverage_lost_when_sentence_gains_a_term`

- **given** a «step» naming two «term refs»
- **given** the same «sentence» with that middle slot a bare word, then an «activity» ref
- **when** «coverage» is computed against each «story»
- **then** the two-ref «sentence» is covered
- **then** the widened «sentence» is no longer covered

## ✓ A «scenario» «pin» covers exactly its «sentences»
`tests/unit/report/test_coverage.py:312::test_compute_coverage_scenario_pin_replaces_matching`

- **given** a «story» with a matching and an under-anchored «sentence»
- **given** a «scenario» whose «step» matches sentence 1 but which pins sentence 2
- **when** «coverage» is computed against the «story»
- **then** only the pinned «sentence» is covered, matching never ran

## ✓ A «step» is narration-matched only where neither it nor its «scenario» «pins» · 5 cases
`tests/unit/report/test_coverage.py:398::test_narration_matching_runs_only_where_nothing_pins`

- **given** a scenario with pins={scenario_pins}
- **given** a step matching sentence 1, with pins={step_pins}
- **when** «coverage» is computed against the «story»
- **then** the «scenario» covers what the «step» contributes

| scenario_pins | step_pins | covered |
|---|---|---|
| None | None | {1} |
| None | [2] | {2} |
| [] | None | set() |
| [] | [2] | {2} |
| [1] | [2] | {1, 2} |

## ✓ A «sentence» with two distinct «terms» is «coverage»-eligible
`tests/unit/report/test_coverage.py:471::test_is_coverage_eligible_true_for_two_distinct_terms`

- **given** a «sentence» anchored by two distinct «term» refs
- **when** its «coverage» eligibility is checked
- **then** it is eligible for «coverage» tracking

## ✓ An under-anchored «sentence» is not «coverage»-eligible
`tests/unit/report/test_coverage.py:495::test_is_coverage_eligible_false_for_one_distinct_term`

- **given** a «sentence» that mentions only one distinct «term»
- **when** its «coverage» eligibility is checked
- **then** it is ineligible — «coverage» needs at least two anchors

## ✓ An under-anchored «sentence» is never covered by narration matching
`tests/unit/report/test_coverage.py:527::test_compute_coverage_excludes_under_anchored_sentence`

- **given** a «story» whose «sentence» is all bare words
- **given** a «scenario» narrating one «term ref»
- **when** «coverage» is computed against the «story»
- **then** «coverage» excludes the under-anchored «sentence»

## ✓ Nested «steps» are walked for «coverage»
`tests/unit/report/test_coverage.py:551::test_compute_coverage_nested_steps_are_walked`

- **given** a «story» with one canonical «sentence»
- **given** the covering «term refs» in a nested child «step»
- **when** «coverage» is computed against the «story»
- **then** the nested «step» still counts and the «sentence» is covered

## ✓ A «step» «pin» covers an eligible «sentence»
`tests/unit/report/test_coverage.py:589::test_compute_coverage_explicit_step_binding_covers_eligible_sentence`

- **given** a «story» with a coverage-eligible «sentence»
- **given** a «step» «pinning» it by number
- **when** «coverage» is computed against the «story»
- **then** «coverage» counts it directly, without narration matching

## ✓ A «pin» covers an under-anchored «sentence»
`tests/unit/report/test_coverage.py:615::test_compute_coverage_explicit_binding_covers_under_anchored_sentence`

- **given** a «story» whose «sentence» is under-anchored
- **given** a «step» «pinning» it by number
- **when** «coverage» is computed against the «story»
- **then** «coverage» counts it, despite the missing anchors

## ✓ The «glossary» view aggregates «instances» and «activity» forms
`tests/unit/report/test_glossary_view.py:66::test_build_glossary_aggregations_collects_instances_and_forms`

- **given** a «report» whose «story» and «scenario» reference entity «instance»s and an «inflection»
  - 📎 Report data:
    ```
    {
      "metadata": {
        "project": "p",
        "timestamp": "t",
        "pytest_version": "8",
        "plugin_version": "0",
        "commit_sha": null,
        "title": null
      },
      "scenarios": [
        {
          "id": "t",
          "narration": {
            "text": "s",
            "parts": []
          },
          "module": "m",
          "tags": [],
          "status": "passed",
          "duration_ms": 0,
          "steps": [
            {
              "phase": "when",
              "narration": {
                "text": "x",
                "parts": [
                  {
                    "term_id": "guest",
                    "display": "Alice",
                    "expression": ""
                  },
                  {
                    "term_id": "search",
                    "display": "searches",
                    "expression": ""
                  },
                  {
                    "term_id": "room",
                    "display": "Deluxe Suite",
                    "expression": ""
                  }
                ]
              },
              "children": [],
              "attachments": [],
              "pins": null,
              "fixture_name": null
            }
          ],
          "parameters": null,
          "error": null,
          "skip_reason": null,
          "source": null,
          "story_ids": [
            "book"
          ],
          "pins": null
        }
      ],
      "glossary": {
        "terms": [
          {
            "id": "guest",
            "kind": "actor",
            "canonical": "Guest",
            "definition": null,
            "source": null
          },
          {
            "id": "room",
            "kind": "object",
            "canonical": "Room",
            "definition": null,
            "source": null
          },
          {
            "id": "search",
            "kind": "activity",
            "canonical": "search",
            "definition": null,
            "source": null
          }
        ]
      },
      "stories": [
        {
          "id": "book",
          "title": "Book",
          "sentences": [
            {
              "id": 1,
              "clauses": [
                {
                  "parts": [
                    {
                      "term_id": "guest",
                      "display": "Alice"
                    },
                    {
                      "term_id": "search",
                      "display": "searches for"
                    },
                    {
                      "term_id": "room",
                      "display": "Deluxe Suite"
                    }
                  ]
                }
              ],
              "name": null
            }
          ],
          "source": null
        }
      ]
    }
    ```
- **when** the «glossary» aggregations are built
- **then** the entity terms collect their «instance»s
- **then** the activity collects its «inflection» but not its canonical form

## ✓ «Terms» referenced by a «sentence» record the «story»
`tests/unit/report/test_glossary_view.py:167::test_build_glossary_aggregations_records_story_refs_via_sentences`

- **given** a «story» whose «sentence» references an actor and an activity
- **when** the «glossary» aggregations are built
- **then** the actor and the activity each list that «story»

## ✓ A «story» referencing a «term» twice lists it once
`tests/unit/report/test_glossary_view.py:198::test_repeated_references_within_one_story_are_recorded_once`

- **given** a «story» whose two «sentences» repeat the same «term» and the same «inflection»
- **when** the «glossary» aggregations are built
- **then** the «story» and the «inflection» appear once each

## ✓ A canonical entity reference is not an «instance», whatever its case
`tests/unit/report/test_glossary_view.py:253::test_build_glossary_aggregations_canonical_entity_ref_is_not_an_instance`

- **given** a «story» sentence referencing entities by canonical name, and a «step» referencing one in lowercase
- **when** the «glossary» aggregations are built
- **then** neither entity term records an «instance»

## ✓ A «kindless» «term» records only its «story» ref
`tests/unit/report/test_glossary_view.py:337::test_build_glossary_aggregations_kindless_term_records_only_story_ref`

- **given** a «kindless» «term» referenced by a «story» sentence
- **when** the «glossary» aggregations are built
- **then** the «term» lists the «story» but no «instance» and no «inflection»

## ✓ An «instance» seen in a fixture «step» records its fixture provenance
`tests/unit/report/test_glossary_view.py:371::test_glossary_aggregations_annotates_fixture_provenance`

- **given** a «scenario» whose fixture-sourced «step» names an «instance»
- **when** the «glossary» aggregations are built
- **then** the «instance» carries the fixture name

## ✓ The «term» index maps each «term» to its «scenarios» once
`tests/unit/report/test_glossary_view.py:460::test_build_term_scenario_index_dedups_and_includes_scenario_narration`

- **given** a «scenario» referencing one «term» in two steps and another in its name
- **when** the term-scenario index is built
- **then** each «term» maps to the scenario exactly once

## ✓ «Parameter coloring» marks placeholders and table headers
`tests/unit/report/test_html_renderer.py:227::test_render_parametrized_step_with_structured_narration` · parametrization

- **given** a «report» holding a «parametrized scenario» with a «parameter table»
- **when** the «renderer» renders the HTML page
- **then** «parameter coloring» classes mark the grouped placeholder and the table headers
- **then** the page carries one generated color rule per column, after the stylesheet so a term ref bound to a column takes the column ink
- **then** each column ink is a token set once per theme, so the dark theme only redefines the token

## ✓ A passed «scenario» renders as a checked heading with «step» bullets
`tests/unit/report/test_md_renderer.py:49::test_passed_scenario_heading_and_steps`

- **given** a «report» holding a passed «scenario» with three steps
- **when** the Markdown «report» is rendered
- **then** the heading is checked and each «step» is a phase bullet
  - 📎 Rendered Markdown:
    ```
    # pytest-given — proj
    
    ## ✓ Buy coffee
    `tests/t.py::test_buy` · billing, happy-path
    
    - **given** a machine
    - **when** I insert $2
    - **then** I get a coffee
    ```

## ✓ Nested «steps» indent under their parent
`tests/unit/report/test_md_renderer.py:150::test_nested_steps_indent`

- **given** a «scenario» whose when «step» has a nested child
- **when** the Markdown «report» is rendered
- **then** the child bullet indents under its parent
  - 📎 Rendered Markdown:
    ```
    # pytest-given — proj
    
    ## ✓ Nest
    `tests/t.py::test_nest`
    
    - **when** outer
      - **when** inner
    ```

## ✓ Structured «narration» renders «terms», values and placeholders
`tests/unit/report/test_md_renderer.py:177::test_narration_parts_resolve_terms_and_values`

- **given** a «step» whose «narration» carries a «term ref», a value and a placeholder
- **when** the Markdown «report» is rendered
- **then** the «term ref» renders in guillemets, the value verbatim and the placeholder in braces
  - 📎 Rendered Markdown:
    ```
    # pytest-given — proj
    
    ## ✓ ignored
    `tests/t.py::test_parts`
    
    - **when** a «Guest»42{amount}
    ```

## ✓ A «parametrized scenario» renders its «parameter table»
`tests/unit/report/test_md_renderer.py:249::test_parametrized_scenario_renders_table` · parametrization

- **given** a «parametrized scenario» with a two-«case» «parameter table»
- **when** the Markdown «report» is rendered
- **then** the heading counts the cases and the «parameter table» lists each row
  - 📎 Rendered Markdown:
    ```
    # pytest-given — proj
    
    ## ✓ Pricing · 2 cases
    `tests/t.py::test_price`
    
    - **when** insert
    
    | euros | expect |
    |---|---|
    | 1 | False |
    | 2 | True |
    ```

## ✓ The «parameter table» shows a status column only when its cases differ in status · 5 cases
`tests/unit/report/test_md_renderer.py:287::test_param_table_shows_status_column_only_when_case_statuses_differ` · parametrization

- **given** a «parameter table» whose first «case» is {first_status} and whose second is {second_status}
- **when** the Markdown «report» is rendered
- **then** the status column is {status_column}
  - 📎 Rendered Markdown — *see parameter table*

| first_status | second_status | status_column | Rendered Markdown |
|---|---|---|---|
| passed | passed | omitted | Rendered Markdown |
| skipped | skipped | omitted | Rendered Markdown |
| failed | failed | omitted | Rendered Markdown |
| passed | skipped | shown | Rendered Markdown |
| passed | failed | shown | Rendered Markdown |

- **passed, passed, omitted** — Rendered Markdown:
  ```
  # pytest-given — proj
  
  ## ✓ Att · 2 cases
  `tests/t.py::test_att`
  
  - **when** act
  
  | coin |
  |---|
  | euro |
  | token |
  ```

- **skipped, skipped, omitted** — Rendered Markdown:
  ```
  # pytest-given — proj
  
  ## ✓ Att · 2 cases
  `tests/t.py::test_att`
  
  - **when** act
  
  | coin |
  |---|
  | euro |
  | token |
  ```

- **failed, failed, omitted** — Rendered Markdown:
  ```
  # pytest-given — proj
  
  ## ✓ Att · 2 cases
  `tests/t.py::test_att`
  
  - **when** act
  
  | coin |
  |---|
  | euro |
  | token |
  ```

- **passed, skipped, shown** — Rendered Markdown:
  ```
  # pytest-given — proj
  
  ## ✓ Att · 2 cases
  `tests/t.py::test_att`
  
  - **when** act
  
  | coin | |
  |---|---|
  | euro | ✓ |
  | token | ○ |
  ```

- **passed, failed, shown** — Rendered Markdown:
  ```
  # pytest-given — proj
  
  ## ✓ Att · 2 cases
  `tests/t.py::test_att`
  
  - **when** act
  
  | coin | |
  |---|---|
  | euro | ✓ |
  | token | ✗ |
  ```

## ✓ A failed «scenario» ends with a minimal error digest
`tests/unit/report/test_md_renderer.py:324::test_failing_scenario_renders_a_minimal_error`

- **given** a failed «scenario» carrying a two-line error and an internal frame
  - 📎 Error record:
    ```
    {
      "message": "ValueError: not sold out\nassert 1 == 0",
      "frames": [
        {
          "path": "/x/_pytest/runner.py",
          "lineno": 1,
          "func": "run",
          "code": "",
          "is_internal": true
        },
        {
          "path": "/x/tests/test_shop.py",
          "lineno": 88,
          "func": "test_sold_out",
          "code": "buy(m)",
          "is_internal": false
        }
      ],
      "error_tail": null
    }
    ```
- **when** the Markdown «report» is rendered
- **then** the heading is crossed and the error follows the steps
  - 📎 Rendered Markdown:
    ```
    # pytest-given — proj
    
    ## ✗ Sold out
    `tests/t.py::test_sold_out`
    
    - **then** reports sold out
    
    > ValueError: not sold out
    > test_shop.py:88 in test_sold_out
    ```
- **then** only the first message line and the non-internal frame are quoted

## ✓ A multi-line «attachment» renders as a fenced block
`tests/unit/report/test_md_renderer.py:395::test_multiline_attachment_renders_fenced_block`

- **given** a «step» carrying a multi-line «attachment»
- **when** the Markdown «report» is rendered
- **then** the «attachment» content sits in an indented fence, not inline
  - 📎 Rendered Markdown:
    ````
    # pytest-given — proj
    
    ## ✓ Multi
    `tests/t.py::test_multiline`
    
    - **then** result
      - 📎 Doc:
        ```
        line1
        line2
        ```
    ````

## ✓ A skipped scenario shows its skip reason
`tests/unit/report/test_md_renderer.py:559::test_skipped_scenario_shows_reason`

- **given** a skipped «scenario» with a reason
- **when** the Markdown «report» is rendered
- **then** the heading is marked skipped and the reason follows the node id
  - 📎 Rendered Markdown:
    ```
    # pytest-given — proj
    
    ## ○ Later · skipped
    `tests/t.py::test_skip` — reason: needs fixture data
    
    - **when** act
    ```

## ✓ The JSON report carries each «sentence»'s «coverage»
`tests/unit/report/test_sinks.py:174::test_json_sink_carries_per_sentence_coverage`

- **given** a «story» with a covered, an uncovered, an untracked «sentence»
- **when** the JSON sink is rendered
- **then** a top-level `coverage` lists every «sentence» once
- **then** the rest of the report is the input dict, unchanged

## ✓ A re-rendered report recomputes «coverage» rather than carrying it
`tests/unit/report/test_sinks.py:209::test_json_sink_replaces_incoming_coverage`

- **given** a saved report dict whose `coverage` no longer matches its steps
- **when** `pytest-given report` re-renders it to JSON
- **then** the «coverage» is the one the «step»s actually earn

## ✓ The literal `none` disables the «source link»
`tests/unit/report/test_source_link.py:29::test_resolve_template_none_returns_none`

- **given** the «source link» config set to `none`
- **when** the config value is resolved
- **then** no template comes back, so no link is rendered

## ✓ A named editor preset becomes that editor's «source link» template · 4 cases
`tests/unit/report/test_source_link.py:44::test_resolve_template_editor_preset`

- **given** the config set to the {preset} preset
- **when** the config value is resolved
- **then** the template is that editor's URL scheme

| preset | url_scheme |
|---|---|
| vscode | vscode://file/{path}:{line} |
| cursor | cursor://file/{path}:{line} |
| zed | zed://file/{path}:{line} |
| pycharm | pycharm://open?file={path}&line={line} |

## ✓ A raw URL template is used as the «source link» verbatim
`tests/unit/report/test_source_link.py:66::test_resolve_template_raw_template_passes_through`

- **given** a raw blob-URL template rather than a preset name
- **when** the config value is resolved
- **then** it comes back unchanged

## ✓ An unknown preset name is refused, with the valid ones listed
`tests/unit/report/test_source_link.py:76::test_resolve_template_unknown_preset_raises` · diagnostics, validation

- **given** a bareword that is neither a known preset nor a template
- **when** the config value is resolved
- **then** the value is refused
- **then** the error names the offender and lists every valid preset

## ✓ The github preset prefers GITHUB_REPOSITORY over the git remote
`tests/unit/report/test_source_link.py:113::test_resolve_github_preset_env_beats_remote`

- **given** GITHUB_REPOSITORY naming one repository
- **given** an origin remote naming a different one
- **when** the github preset is resolved
- **then** the template points at the environment's repository

## ✓ The github preset derives org and repo from the git origin remote
`tests/unit/report/test_source_link.py:136::test_resolve_github_preset_from_https_remote`

- **given** no GITHUB_REPOSITORY, and an https origin remote
- **when** the github preset is resolved
- **then** the blob-URL template names the remote's org and repo

## ✓ The github preset refuses a remote that is not on GitHub
`tests/unit/report/test_source_link.py:189::test_resolve_github_preset_non_github_remote_raises` · diagnostics

- **given** no GITHUB_REPOSITORY, and an origin remote on another host
- **when** the github preset is resolved
- **then** the preset is refused
- **then** the error points at the env var and the raw-template escape hatch

## ✓ An under-anchored «sentence» is flagged ineligible in rollups
`tests/unit/report/test_story_view.py:208::test_build_story_rollups_flags_under_anchored_sentence_ineligible`

- **given** a «story» with an anchored and an under-anchored «sentence»
- **when** the story rollups are built
- **then** only the anchored «sentence» is «coverage»-eligible

## ✓ A pinned under-anchored «sentence» stops reading as untracked
`tests/unit/report/test_story_view.py:255::test_build_story_rollups_pinned_under_anchored_sentence_is_tracked`

- **given** a «story» whose only «sentence» is under-anchored
- **given** a «scenario» whose «step» pins it by id
- **when** the story rollups are built
- **then** it stays narration-ineligible but is no longer untracked

## ✓ A «scenario» bound to two «stories» is matched against each
`tests/unit/report/test_story_view.py:359::test_build_story_rollups_lists_a_scenario_under_each_bound_story`

- **given** two «stories» each with a guest-search-room «sentence»
- **given** a «scenario» bound to both whose «step» names those terms
- **when** the story rollups are built
- **then** the «scenario» is listed under, and covers, both «stories»

## ✓ A «sentence» is labeled by the prose of its «clauses»
`tests/unit/report/test_story_view.py:411::test_build_sentence_labels_joins_parts_into_prose`

- **given** a «story» with a two-«clause» «sentence»
- **when** the «sentence» labels are built
- **then** the label gives the number, then reads as prose under a story-scoped key, with the «clause» texts joined

## ✓ «Grouping» collapses parametrize «cases» into one «scenario»
`tests/unit/test_grouping.py:117::test_group_parametrized_any_failed_groups_as_failed` · parametrization

- **given** three «case» records of one «parametrized scenario»
- **when** the «grouping» pass collapses them
- **then** one scenario remains and any failed «case» fails it

## ✓ A «parametrized scenario» keeps its place among the «scenarios» around it
`tests/unit/test_grouping.py:154::test_group_parametrized_keeps_source_order` · parametrization

- **given** a plain «scenario» between two parametrized ones
- **when** the «grouping» pass runs
- **then** the «report» lists them in the order the file declares

## ✓ Same-named «parametrized scenarios» on different test functions stay apart
`tests/unit/test_grouping.py:180::test_group_parametrized_distinct_functions_same_name_do_not_group` · parametrization

- **given** two test functions whose «cases» share one name
- **when** the «grouping» pass runs
- **then** each function keeps its own «scenario» and «parameter table»

## ✓ The grouped tree comes from the first passed «case»
`tests/unit/test_grouping.py:265::test_baseline_is_the_first_passed_case_not_the_first_case` · parametrization

- **given** a skipped first «case» and a second one that ran
- **when** the «cases» are «grouped»
- **then** the tree is the one the passed «case» recorded

## ✓ A plain-str «narration» that varies across «cases» is refused
`tests/unit/test_grouping.py:492::test_a_varying_str_narration_raises_rule_one` · parametrization, validation

- **given** two «cases» whose text differs but records no parts
- **when** the «cases» are «grouped»
- **then** the grouping is refused
- **then** the error names the test, the missing parts and the t-string fix
- **then** it names the «case» whose values were baked in, and the per-case opt-out

## ✓ A narrated value that varies becomes a derived «parameter table» column
`tests/unit/test_grouping.py:615::test_a_varying_bare_name_interpolation_becomes_a_derived_column` · parametrization

- **given** two «cases» narrating a value that differs
- **when** «templatizing» walks the «cases»
- **then** the value becomes a derived column beside the parametrize one
- **then** the «step» keeps a placeholder pointing at that column
- **then** the placeholder keeps the format spec and conversion it narrated

## ✓ A varying interpolation that is not a bare name is refused
`tests/unit/test_grouping.py:728::test_a_varying_compound_interpolation_raises_rule_two` · diagnostics, parametrization, validation

- **given** two «cases» narrating a computed expression
- **when** the «cases» are «grouped»
- **then** the grouping is refused
- **then** the error quotes the expression and shows the bind-a-local fix

## ✓ A «parameter table» cell reads the way the scenario name formats it
`tests/unit/test_grouping.py:1094::test_a_scenario_name_format_spec_reaches_its_cell` · parametrization

- **given** a Template scenario name formatting its parameter
- **when** the «cases» are «grouped»
- **then** the cells carry the formatting the name declared

## ✓ A scenario name formatting a parameter a «step» reads plainly gets its own column
`tests/unit/test_grouping.py:1109::test_a_scenario_name_disagreeing_with_a_step_gets_its_own_column` · parametrization

- **given** a name formatting the parameter and a step reading it plainly
- **when** the «cases» are «grouped»
- **then** the name points at a column holding what it renders
- **then** the name renders the disambiguated token, text and parts agreeing

## ✓ A «step» formatting a parameter the scenario name reads plainly gets its own column
`tests/unit/test_grouping.py:1152::test_a_step_slot_disagreeing_with_the_name_gets_its_own_column` · parametrization

- **given** a step formatting the parameter and a name reading it plainly
- **when** the «cases» are «grouped»
- **then** the step points at a column holding what it renders
- **then** the step renders the disambiguated token, text and parts agreeing

## ✓ A «step» narrating a parameter its column no longer holds is refused
`tests/unit/test_grouping.py:1234::test_a_rebound_parametrize_name_raises_rule_three` · parametrization, validation

- **given** two «cases» narrating a value their column lacks
- **when** the «cases» are «grouped»
- **then** the grouping is refused
- **then** the error names the column and what the case actually narrated

## ✓ A «term ref» whose display differs between «cases» is refused
`tests/unit/test_grouping.py:1585::test_a_varying_term_ref_display_raises_rule_four` · parametrization, validation

- **given** two «cases» whose «term ref» reads differently
- **when** the «cases» are «grouped»
- **then** the grouping is refused
- **then** the error names the «term ref» and the split-it-out fix

## ✓ A «term ref» that *is* the parametrize value is refused too
`tests/unit/test_grouping.py:1644::test_a_param_bound_term_ref_that_varies_raises_rule_four` · parametrization, validation

- **given** two «cases» whose «term ref» is the parameter itself
- **when** the «cases» are «grouped»
- **then** the grouping is refused
- **then** the error points at the per-case «scenario» opt-out

## ✓ An «attachment» whose payload varies becomes an «attachment» column
`tests/unit/test_grouping.py:1808::test_a_varying_attachment_becomes_a_column_and_leaves_a_content_less_badge` · parametrization

- **given** two «cases» attaching a label with differing payloads
- **when** «templatizing» walks the «cases»
- **then** the payload moves into an «attachment» column
- **then** the «step» keeps a content-less badge pointing at it

## ✓ A «step» whose set of «attachment» labels differs between «cases» is refused
`tests/unit/test_grouping.py:1864::test_a_label_present_in_one_case_only_raises_rule_five` · parametrization, validation

- **given** an «attachment» label only one «case» attaches
- **when** the «cases» are «grouped»
- **then** the grouping is refused
- **then** the error names the label, the case, and asks for a constant one

## ✓ A «parameter table» cell reads the way the «step» that points at it read
`tests/unit/test_grouping.py:2410::test_a_formatted_param_cell_holds_the_text_the_step_narrated` · parametrization

- **given** two «cases» narrating a parameter with a format spec
- **when** «grouping» builds the «parameter table»
- **then** each cell carries the formatted text, under one column
- **then** the step keeps its placeholder, which that cell substitutes into

## ✓ «Cases» that narrate different «steps» are refused rather than «grouped»
`tests/unit/test_grouping.py:2570::test_divergent_step_structure_refuses_the_merge` · parametrization, validation

- **given** two «cases» whose «step» trees differ
- **when** the «cases» are «grouped»
- **then** the grouping is refused
- **then** the error names the divergence and the opt-out that answers it

## ✓ A «step» narrating a glossary term parameter keeps pointing at its «parameter table» column
`tests/unit/test_grouping.py:2720::test_a_step_slot_over_a_term_instance_keeps_pointing_at_its_cell` · parametrization

- **given** a step narrating a parameter bound to a glossary term instance
- **when** the «cases» are «grouped»
- **then** the «parameter table» holds the term displays alone
- **then** the step still points at that column

## ✓ A «parametrized scenario» can decline the «grouping» and keep one «scenario» per «case»
`tests/unit/test_percase.py:59::test_opted_out_group_emits_one_scenario_per_case` · parametrization

- **given** two «cases» of a scenario that opted out
- **when** the «grouping» pass runs
- **then** each «case» stands alone, with no «parameter table»
