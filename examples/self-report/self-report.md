# pytest-given — pytest-given Self-Report

## ✓ A test without `@scenario` stays out of the «report»
`tests/integration/test_plugin.py:136::test_unannotated_test_not_in_report`

- **given** a suite whose only test is undecorated
- **when** the suite runs with --given-json
- **then** the test itself passes
- **then** the «report» holds no «scenario»

## ✓ A «step fixture» is «grafted» in as a given «step»
`tests/integration/test_plugin.py:205::test_step_fixture_appears_as_given_step`

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
`tests/integration/test_plugin.py:243::test_parametrized_test_as_table` · parametrization

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
`tests/integration/test_plugin.py:382::test_a_grouping_error_without_sinks_does_not_say_report_not_written` · validation

- **given** a suite whose narration varies across parametrize cases
- **when** the suite runs with no --given-* sink
- **then** the refusal is reported without claiming a report was skipped

## ✓ A refused run discards the previous run's «report»
`tests/integration/test_plugin.py:410::test_a_grouping_error_discards_the_previous_report` · validation

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
`tests/integration/test_plugin.py:478::test_an_unknown_source_link_preset_fails_before_the_suite_runs` · validation

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
- **then** no test ran: the run stopped at configure, before collection

## ✓ An unknown «source link» preset in an ini reports the ini name
`tests/integration/test_plugin.py:510::test_an_unknown_source_link_preset_in_an_ini_names_the_ini` · validation

- **given** a suite configured through the ini rather than the flag
- **when** the suite runs with an HTML sink
- **then** the error names the ini setting, not a flag the user never typed

## ✓ A bare run writes no «report» at all
`tests/integration/test_plugin.py:2319::test_no_output_flags_writes_nothing`

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
- **then** nothing is written to disk

## ✓ A bare `--given-md` prints the «narration» to stdout
`tests/integration/test_plugin.py:2332::test_given_md_prints_fenced_block`

- **given** a suite with one «scenario»
- **when** the suite runs with a bare --given-md
- **then** the narration is printed between the fence markers

## ✓ Each sink flag writes only its own «report» file
`tests/integration/test_plugin.py:2353::test_given_html_alone_writes_no_json`

- **given** a suite with one «scenario»
- **when** the suite runs with --given-html alone
- **then** the HTML rendering is written
- **then** no JSON lands beside it

## ✓ A sink flag pointed at a source file is refused before the suite runs
`tests/integration/test_plugin.py:2373::test_a_sink_path_that_is_not_a_report_file_is_refused` · validation

- **given** a suite with one «scenario»
- **when** a bare --given-html swallows the test path that follows it
- **then** the run is refused, naming the path and the flag-order fix
- **then** the source file is left exactly as it was, not overwritten

## ✓ A rejected authoring form fails the run and writes no «report»
`tests/integration/test_plugin.py:2406::test_a_rejected_form_fails_the_run_and_writes_no_sink` · validation

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
`tests/integration/test_plugin.py:2438::test_given_title_cli_flag_names_the_report`

- **given** a suite with one «scenario»
- **when** the suite runs with --given-title
- **then** the test passes
- **then** the title reaches the JSON metadata
- **then** the title also heads the Markdown rendering

## ✓ A run with no sink still enforces the «grouping» rules
`tests/integration/test_plugin.py:2624::test_bare_run_still_enforces_the_grouping_rules` · validation

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
`tests/integration/test_plugin_lint.py:227::test_the_flag_overrides_the_ini_in_both_directions`

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
`tests/integration/test_plugin_lint.py:433::test_lint_error_does_not_mask_a_more_specific_exit_code`

- **given** a suite whose lint would fail, deselected so nothing is collected
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
- **when** the run collects no test but still trips a stale ignore
- **then** the run keeps NO_TESTS_COLLECTED rather than reporting a test failure

## ✓ A failure inside the lint keeps the «report» it was handed
`tests/integration/test_plugin_lint.py:452::test_a_lint_failure_is_reported_and_keeps_the_written_report` · validation

- **given** a clean suite and a lint pass that raises
- **when** the suite runs with an HTML sink
- **then** the failure is summarized rather than raised as a traceback
- **then** the report that was already written is still there

## ✓ A «scenario» records under its «node ID»
`tests/unit/capture/test_collector.py:38::test_start_and_finish_scenario`

- **given** a fresh «Collector»
- **when** a «Scenario» starts under its «Node ID» and finishes
- **then** it carries its «Node ID», name, status and «Tag»

## ✓ A «scenario» is timed from past its «step fixture» setup
`tests/unit/capture/test_collector.py:54::test_duration_excludes_fixture_setup`

- **given** a «Collector» whose clock reads 100.3s once setup is done
- **when** the clock is started past setup and the body runs 0.2s
- **then** the recorded duration is the body alone, not the setup before it

## ✓ «Steps» record with their «phases»
`tests/unit/capture/test_collector.py:76::test_collect_steps`

- **given** an «Active scenario» in a fresh «Collector»
- **when** a given and a when «Step» are pushed
- **then** each «Step» carries its «Phase»

## ✓ «Steps» pushed during fixture setup record into the «fixture recording»
`tests/unit/capture/test_collector.py:217::test_push_step_during_fixture_setup_records_into_recording`

- **given** a «Fixture recording» under setup
- **when** a «Step» is pushed inside the fixture body
- **then** it is recorded as a child of the recording root

## ✓ An «attachment» lands on the «step» being recorded
`tests/unit/capture/test_collector.py:238::test_attach_during_fixture_setup_records_into_recording`

- **given** a «Fixture recording» under setup
- **when** an «Attachment» is attached inside the fixture body
- **then** the «Attachment» lands on the recording root

## ✓ Fixture-body «steps» do not leak into the «active scenario»
`tests/unit/capture/test_collector.py:257::test_push_step_routing_isolates_recording_from_scenario`

- **given** an «Active scenario» with a «Fixture recording»
- **when** a «Step» is pushed inside the fixture body
- **then** the step lives only in the recording, not the scenario

## ✓ An «attachment» outside every «step» is refused
`tests/unit/capture/test_collector.py:310::test_attach_outside_any_step_raises`

- **given** an «Active scenario» with no «Step» open
- **when** an «attachment» is made from the test body
- **then** it is refused rather than dropped

## ✓ A «fixture recording» is deep-copied when «grafted»
`tests/unit/capture/test_collector.py:327::test_graft_recording_deep_copies_into_scenario`

- **given** a «Fixture recording» with a nested child «Step»
- **when** a «Graft» copies it into the «Active scenario»
- **then** the scenario gains a deep copy of the recorded steps

## ✓ A «step fixture» failing in teardown fails its finished «scenario»
`tests/unit/capture/test_collector.py:468::test_fail_marks_a_finished_scenario_failed`

- **given** a «Scenario» that already finished as passed
- **when** a fixture raises past its yield, after the scenario finished
- **then** the recorded «scenario» carries the failure

## ✓ A teardown failure keeps the error the «scenario» already carries
`tests/unit/capture/test_collector.py:485::test_fail_keeps_an_existing_error`

- **given** a «Scenario» that already failed in its body
- **when** its fixture then also fails in teardown
- **then** the body failure is what the report shows

## ✓ A «Collector» reports which «node ids» it recorded
`tests/unit/capture/test_collector.py:501::test_records_reports_only_recorded_node_ids`

- **given** a «Collector» that recorded one «scenario»
- **when** the recorded and an unrecorded node id are both asked about
- **then** only the recorded node id is claimed

## ✓ A leaf given is «grafted» as a childless given «step»
`tests/unit/capture/test_collector.py:519::test_graft_leaf_given_appends_childless_given_step`

- **given** an «Active scenario» is being recorded
- **when** a leaf «Graft» appends a childless «Step»
- **then** the step is a given with no children

## ✓ «Grafting» with an override replaces the root label but keeps children
`tests/unit/capture/test_collector.py:537::test_graft_recording_override_replaces_root_narration_keeps_children`

- **given** a «Fixture recording» whose root has a label and a child
- **when** a «Graft» supplies an override «Narration»
- **then** the grafted root shows the override text and keeps its children

## ✓ «Grafting» with no «active scenario» is refused
`tests/unit/capture/test_collector.py:564::test_graft_leaf_given_without_scenario_is_refused`

- **given** a collector with no «Active scenario»
- **when** a leaf «Graft» runs
- **then** the invariant is asserted rather than silently dropping the step

## ✓ «FileGlossary» lookup is case-insensitive
`tests/unit/capture/test_file_glossary.py:27::test_lookup_is_case_insensitive`

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** the same «Term» is looked up in three different cases
- **then** every lookup resolves to one handle type and the same id

## ✓ Repeated lookups return the same handle
`tests/unit/capture/test_file_glossary.py:41::test_handles_are_memoized`

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** the same «Term» is looked up twice
- **then** both lookups return the one memoized handle

## ✓ File-loaded «terms» start «kindless»
`tests/unit/capture/test_file_glossary.py:54::test_terms_start_kindless`

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
- **when** a «File glossary» loads it
- **then** each «Term» is «Kindless» until «Kind inference» runs

## ✓ An unknown name raises with a suggestion
`tests/unit/capture/test_file_glossary.py:70::test_unknown_name_raises_with_suggestion` · diagnostics, validation

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** a misspelt «Term» is looked up
- **then** a PytestGivenError is raised with a spelling hint

## ✓ Handles are usable inline in an «activity»
`tests/unit/capture/test_file_glossary.py:88::test_usable_inline_in_activity`

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** its handles build an «Activity»
- **then** each slot becomes a «Term ref»

## ✓ Calling a handle overrides its display
`tests/unit/capture/test_file_glossary.py:104::test_call_overrides_display`

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** a handle is called to name an «Instance»
- **then** the «Term ref» carries the overridden display

## ✓ An explicit kind column sets «term» kinds
`tests/unit/capture/test_file_glossary.py:123::test_explicit_kind_column`

- **given** a Markdown glossary with an explicit Kind column
  - 📎 Glossary file:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Guest | x | Actor |
    | Room | y | Work Object |
    ```
- **when** the «File glossary» reads the Kind column
- **then** kinds come straight from the file, not «Kindless» inference

## ✓ A kind column can be selected by integer index
`tests/unit/capture/test_file_glossary.py:142::test_kind_column_by_integer_index`

- **given** a Markdown glossary with the kind in the third column
  - 📎 Glossary file:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Guest | x | Actor |
    | Room | y | Work Object |
    ```
- **when** the «File glossary» selects the kind column by index
- **then** the kinds are read from that column

## ✓ A «work_object» kind alias maps to the object kind
`tests/unit/capture/test_file_glossary.py:161::test_work_object_underscore_alias`

- **given** a glossary whose Kind cell says work_object
  - 📎 Glossary file:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Room | y | work_object |
    ```
- **when** the «File glossary» parses the kind
- **then** it normalizes to the «Work Object» kind

## ✓ An unrecognized kind value is rejected
`tests/unit/capture/test_file_glossary.py:176::test_unrecognized_kind_value_raises` · diagnostics, validation

- **given** a glossary whose Kind cell holds an unknown value
  - 📎 Glossary file:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Guest | x | Wizard |
    ```
- **when** the «File glossary» loads the file
- **then** a PytestGivenError names the unrecognized kind

## ✓ A missing «glossary» file is reported clearly
`tests/unit/capture/test_file_glossary.py:196::test_missing_file_raises` · validation

- **given** a path to a file that does not exist
- **when** a «File glossary» is opened on that path
- **then** a PytestGivenError reports the file is not found

## ✓ A «term» cell with no alphanumeric characters is rejected
`tests/unit/capture/test_file_glossary.py:221::test_empty_id_term_cell_raises` · diagnostics, validation

- **given** a row whose «Term» cell has no id-able characters
  - 📎 Glossary file:
    ```
    | Term | Meaning |
    |---|---|
    | @#$ | some definition |
    ```
- **when** the «File glossary» loads the file
- **then** a PytestGivenError is raised with file:line context

## ✓ Conflicting duplicate rows are rejected
`tests/unit/capture/test_file_glossary.py:241::test_conflicting_duplicate_rows_raise` · validation

- **given** two rows for one «Term» with different definitions
  - 📎 Glossary file:
    ```
    | Term | Meaning |
    |---|---|
    | Guest | First definition. |
    | Guest | Second definition. |
    ```
- **when** the «File glossary» loads the file
- **then** a PytestGivenError reports the conflicting rows

## ✓ A blank description normalizes to «undefined»
`tests/unit/capture/test_file_glossary.py:265::test_blank_description_cell_normalizes_to_none`

- **given** a row whose description cell is blank
  - 📎 Glossary file:
    ```
    | Term | Meaning |
    |---|---|
    | Guest |   |
    ```
- **when** the «File glossary» parses it
- **then** the «Term» definition is None, i.e. «Undefined»

## ✓ Identical duplicate rows collapse to one «term»
`tests/unit/capture/test_file_glossary.py:280::test_idempotent_duplicate_rows_ok`

- **given** two identical rows for the same «Term»
  - 📎 Glossary file:
    ```
    | Term | Meaning |
    |---|---|
    | Guest | A person booking. |
    | Guest | A person booking. |
    ```
- **when** the «File glossary» parses them
- **then** they collapse to a single «Term»

## ✓ Calling «FileGlossary» looks up a known «term»
`tests/unit/capture/test_file_glossary.py:303::test_file_glossary_call_known_name_returns_handle`

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** a known «Term» is looked up by call
- **then** a «Deferred term» is returned

## ✓ «FileGlossary» is a closed vocabulary
`tests/unit/capture/test_file_glossary.py:317::test_file_glossary_call_unknown_name_raises` · validation

- **given** a «File glossary» loaded from a Markdown file
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
- **then** no new «Term» was created

## ✓ «Term» ids are derived as URL-safe slugs · 8 cases
`tests/unit/capture/test_glossary.py:27::test_id_derive_produces_expected_slug`

- **given** the name {text}
- **when** it is slugified into a «Term» id
- **then** the id is the expected slug {expected}

| text | expected | |
|---|---|---|
| Guest | 'guest' | ✓ |
| Order received | 'order-received' | ✓ |
|   Work Object   | 'work-object' | ✓ |
| do_the_thing | 'do-the-thing' | ✓ |
| Buy / sell | 'buy-sell' | ✓ |
| Guest #1 | 'guest-1' | ✓ |
| café | 'caf' | ✓ |
| booking system | 'booking-system' | ✓ |

## ✓ A name with no id-able characters is rejected · 4 cases
`tests/unit/capture/test_glossary.py:53::test_id_derive_raises_on_empty_result` · validation

- **given** the name {text}
- **when** it is slugified into a «Term» id
- **then** a PytestGivenError reports the derived id is empty

| text | |
|---|---|
| --- | ✓ |
|     | ✓ |
|  | ✓ |
| ### | ✓ |

## ✓ Calling an «actor» names a distinct «instance»
`tests/unit/capture/test_glossary.py:101::test_actor_call_returns_instance_with_distinct_display`

- **given** an «Actor» handle for Guest
- **when** the «Actor» is called with a name
- **then** an «Instance» with a distinct display is returned

## ✓ Calling a «verb» records an «inflection» of the same «term»
`tests/unit/capture/test_glossary.py:127::test_verb_call_returns_inflection_sharing_term_identity`

- **given** a «Verb» handle for confirm
- **when** the «Verb» is called with a surface form
- **then** an «Inflection» sharing the verb identity is returned

## ✓ Registering an «actor» returns a typed handle
`tests/unit/capture/test_glossary.py:147::test_glossary_actor_registers_and_returns_handle`

- **given** an empty glossary
- **when** an «Actor» is registered with a definition
- **then** a handle carrying the «Actor» kind is returned

## ✓ Re-registering a «term» with matching fields is idempotent
`tests/unit/capture/test_glossary.py:179::test_glossary_re_registration_with_matching_fields_is_idempotent`

- **given** an «Actor» already registered with a definition
- **when** the same name and definition are registered again
- **then** both handles share the one «Term»

## ✓ Re-registering a «term» with a different definition is rejected
`tests/unit/capture/test_glossary.py:193::test_glossary_re_registration_with_mismatched_definition_raises` · validation

- **given** an «Actor» already registered with one definition
- **when** the name is registered again with a different definition
- **then** a PytestGivenError reports the conflict with the prior registration

## ✓ The same name cannot be two different kinds
`tests/unit/capture/test_glossary.py:211::test_glossary_cross_kind_collision_raises` · validation

- **given** a name already registered as an «Actor»
- **when** the same name is registered as a «Verb»
- **then** a PytestGivenError reports the conflict with the prior registration

## ✓ Registering an «actor» captures its definition site
`tests/unit/capture/test_glossary.py:235::test_glossary_actor_captures_source`

- **given** a rootdir-aware glossary
- **when** an «Actor» is registered
- **then** the «Term» records a «Source link» to this file

## ✓ Calling the «glossary» declares a «kindless» «term»
`tests/unit/capture/test_glossary.py:327::test_call_declares_kindless_term`

- **given** an empty glossary
- **when** a «Term» is declared by call, without a kind
- **then** the «Term» is registered as «Kindless»

## ✓ Subscript looks up an already-declared «term»
`tests/unit/capture/test_glossary.py:422::test_subscript_get_only_returns_handle`

- **given** a glossary with one declared «Term»
- **when** the name is looked up by subscript
- **then** the returned «Term» is the declared one

## ✓ Subscripting an unknown name raises with a hint
`tests/unit/capture/test_glossary.py:435::test_subscript_unknown_name_raises_with_hint` · diagnostics, validation

- **given** a glossary with one declared «Term»
- **when** a near-miss name is subscripted
- **then** a PytestGivenError is raised with a spelling hint

## ✓ «Term» kinds are inferred from activity-slot positions
`tests/unit/capture/test_kind_inference.py:46::test_infers_actor_verb_object_by_position`

- **given** a glossary of three «Kindless» «Term» entries
- **when** «Kind inference» runs over a «Story»
- **then** they are inferred as «Actor», «Verb», «Work Object» by slot

## ✓ An «actor» «slot» anywhere wins over a noun «slot» elsewhere
`tests/unit/capture/test_kind_inference.py:64::test_actor_anywhere_beats_object`

- **given** a «Term» that sits in a noun slot in one «Story»
- **when** the same «Term» also appears in an «Actor» slot
- **then** its inferred kind is «Actor»

## ✓ A «term» used in no «story» stays «kindless»
`tests/unit/capture/test_kind_inference.py:84::test_never_used_stays_kindless`

- **given** a «Term» referenced by no «Story»
- **when** «Kind inference» runs with no stories
- **then** the «Term» remains «Kindless»

## ✓ A «term» in both a «verb» and a noun «slot» is a conflict
`tests/unit/capture/test_kind_inference.py:96::test_verb_and_noun_conflict_raises` · diagnostics, validation

- **given** a «Kindless» «Term» used in a verb slot and a noun slot
- **when** kind resolution runs over both stories
- **then** a PytestGivenError names the conflicting term

## ✓ A declared kind consistent with its «slot» is kept
`tests/unit/capture/test_kind_inference.py:118::test_declared_kind_verified_and_kept`

- **given** a glossary with explicitly declared «Term» kinds
- **when** «Kind inference» runs over a matching «Story»
- **then** the declared kinds are verified and preserved

## ✓ A declared «verb» in an «actor» «slot» is rejected
`tests/unit/capture/test_kind_inference.py:140::test_declared_verb_in_actor_slot_raises` · diagnostics, validation

- **given** a «Term» declared as a «Verb»
- **when** kind resolution places it in the «Actor» slot
- **then** a PytestGivenError names the misplaced term

## ✓ A «term» used as both «verb» and «actor» is a conflict
`tests/unit/capture/test_kind_inference.py:157::test_verb_and_actor_conflict_raises` · diagnostics, validation

- **given** a «Kindless» «Term» used in a verb slot and an actor slot
- **when** kind resolution runs over both stories
- **then** a PytestGivenError names the conflicting term

## ✓ A declared «work object» in an «actor» «slot» is rejected
`tests/unit/capture/test_kind_inference.py:183::test_declared_object_in_actor_slot_raises` · diagnostics, validation

- **given** a «Term» declared as a «Work Object»
- **when** kind resolution places it in the «Actor» slot
- **then** a PytestGivenError names the misplaced term

## ✓ A declared «actor» in a «verb» «slot» is rejected
`tests/unit/capture/test_kind_inference.py:201::test_declared_actor_in_verb_slot_raises` · validation

- **given** a «Term» declared as an «Actor»
- **when** kind resolution places it at position 1 (the verb slot)
- **then** a PytestGivenError says an actor cannot fill the verb slot

## ✓ A conflict error names only the offending «stories»
`tests/unit/capture/test_kind_inference.py:220::test_conflict_where_names_only_offending_stories` · diagnostics, validation

- **given** an «Actor» «Term» that also appears in a verb slot
- **when** kind resolution raises
- **then** only the offending story is named in the message

## ✓ A conflict message excludes «stories» with an unrelated «slot»
`tests/unit/capture/test_kind_inference.py:240::test_inferred_conflict_where_excludes_unrelated_slot_stories` · diagnostics, validation

- **given** a «Kindless» «Term» used in verb, actor and noun slots
- **when** the verb-vs-actor conflict is raised
- **then** only the verb and actor stories are named, not the noun one

## ✓ A declared «verb» in a noun «slot» is rejected
`tests/unit/capture/test_kind_inference.py:263::test_declared_verb_in_noun_slot_raises` · validation

- **given** a «Term» declared as a «Verb»
- **when** kind resolution places it at position ≥2 (a noun slot)
- **then** a PytestGivenError says a verb cannot fill the noun slot

## ✓ «Slot» positions alternate verb/noun after the «actor»
`tests/unit/capture/test_kind_inference.py:282::test_slot_for_maps_odd_positions_to_verb`

- **given** the five positions of a short activity path
- **when** the «Slot» rule is applied to each position
- **then** position 0 is the actor «Slot», then verb and noun alternate

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
- **when** the parser reads it into rows for a «File glossary»
- **then** each row carries a «Term», definition and source line

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
- **then** every table contributes its «Term» rows

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
- **when** the parser reads it for a «File glossary»
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

- **given** a «Term» cell written with **bold** emphasis
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

- **given** «Term» cells using *italic* and `code` emphasis
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

- **given** a «Term» literally named work_object
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

- **given** a «Term» cell written as a code span around an asterisk pair
  - 📎 Markdown document:
    ```
    | Term | Meaning |
    |---|---|
    | `a*b*c` | a literal. |
    ```
- **when** the parser reads the term cell
- **then** the span unwraps once and its contents stay literal

## ✓ A «step» pairs its «narration» with a «phase»
`tests/unit/capture/test_step_descriptor.py:60::test_context_manager_basic`

- **when** a given «Step» descriptor is created
- **then** it carries the given «Phase» and its «Narration»

## ✓ A «step» opened outside a «scenario» warns rather than raising
`tests/unit/capture/test_step_descriptor.py:152::test_context_manager_unannotated_test_warns_instead_of_raises`

- **given** a «collector» recording inside an undecorated test
- **when** a given «step» is opened against it
- **then** a `PytestGivenWarning` is raised, not an error
- **then** it names the missing `@scenario`, so a suite can filter it

## ✓ «when_then» records the action and its outcome as siblings
`tests/unit/capture/test_step_descriptor.py:280::test_when_then_records_two_sibling_steps_on_clean_exit`

- **given** an «Active scenario» in a local «Collector»
- **when** a «when_then» block exits cleanly
- **then** a when and a sibling then «Step» are recorded

## ✓ «when_then» pairs with an inner pytest.raises
`tests/unit/capture/test_step_descriptor.py:305::test_when_then_pairs_with_inner_pytest_raises`

- **given** an «Active scenario» in a local «Collector»
- **when** the «when_then» body raises and an inner pytest.raises swallows it
- **then** both sibling steps are still recorded

## ✓ «when_then» omits the then when the body raises uncaught
`tests/unit/capture/test_step_descriptor.py:333::test_when_then_omits_then_when_body_raises_uncaught` · validation

- **given** an «Active scenario» in a local «Collector»
- **when** the «when_then» body raises with nothing catching inside
- **then** only the when step is recorded — the outcome never held

## ✓ A cross-phase «step» cannot open inside a «when_then» body · 2 cases
`tests/unit/capture/test_step_descriptor.py:375::test_when_then_rejects_cross_phase_nested_step` · validation

- **given** an «Active scenario» in a local «Collector»
- **when** a given or then opens inside the «when_then» body
- **then** a PytestGivenError reports the cross-phase nesting
- **then** the «Step stack» is left balanced

| phase_name | |
|---|---|
| given | ✓ |
| then | ✓ |

## ✓ A nested when becomes a child of the «when_then» action
`tests/unit/capture/test_step_descriptor.py:407::test_when_then_allows_nested_when_as_child_sub_step`

- **given** an «Active scenario» in a local «Collector»
- **when** a when opens inside the «when_then» body
- **then** the sub-action is a child of the action and the then still follows

## ✓ `@scenario` marks the test function without wrapping it
`tests/unit/capture/test_step_descriptor.py:451::test_scenario_marks_the_function_without_wrapping_it`

- **given** a test function taking one fixture
- **when** the function is decorated
- **then** the very same function comes back, keeping its signature
- **then** it carries the «scenario» marker, and a plain one does not

## ✓ An «attachment» label must be plain text · 3 cases
`tests/unit/capture/test_step_descriptor.py:521::test_attach_rejects_a_non_str_label` · validation

- **given** a non-str «Attachment» label of kind {label_kind}
- **when** it is attached
- **then** a PytestGivenError says «Attachment» labels are plain text

| label_kind | |
|---|---|
| deferred-template | ✓ |
| t-string | ✓ |
| not-a-string | ✓ |

## ✓ A string `activities=` argument is refused by `@scenario`
`tests/unit/capture/test_step_descriptor.py:940::test_scenario_rejects_a_string_activities_argument` · validation

- **given** a string where a sequence of «activity» ids goes
- **when** the «scenario» is declared
- **then** a `TypeError` naming the argument is raised

## ✓ An «actor» handle in a «path» becomes a «term ref»
`tests/unit/capture/test_story.py:63::test_path_dispatches_actor_to_activity_term_ref`

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **when** a «Path» is built from three glossary handles
- **then** the «Actor» slot becomes a «Term ref»

## ✓ An inflected «verb» keeps its «term» identity but shows the «inflection»
`tests/unit/capture/test_story.py:106::test_path_dispatches_inflected_verb_to_activity_term_ref_with_inflected_display`

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **given** a «Verb» handle called with an «Inflection»
- **when** it takes the verb slot of a «Path»
- **then** the «Term ref» shows the inflection over the same «Verb»

## ✓ A bare string in a «path» becomes a connective word
`tests/unit/capture/test_story.py:123::test_path_dispatches_bare_string_to_activity_word`

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **when** a «Path» is built with a bare word between term nodes
- **then** the bare word becomes an «Activity Part» word, not a «Term ref»

## ✓ A «path» needs at least an «actor», a «verb» and a node
`tests/unit/capture/test_story.py:138::test_path_rejects_path_with_fewer_than_three_parts` · validation

- **given** a Guest actor
- **given** a search verb
- **when** a «Path» of only two parts is built
- **then** a PytestGivenError rejects it as too short

## ✓ Position 0 of a «path» must be an «actor»
`tests/unit/capture/test_story.py:154::test_path_rejects_work_object_in_position_0` · validation

- **given** a search verb
- **given** a Room work object
- **when** a «Path» is built with a «Work Object» in position 0
- **then** a PytestGivenError says position 0 is the «Actor» slot

## ✓ A «verb» cannot open a «path»
`tests/unit/capture/test_story.py:169::test_path_rejects_verb_in_position_0` · validation

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **when** a «Verb» is placed in position 0 of a «Path»
- **then** a PytestGivenError says position 0 is the «Actor» slot

## ✓ A bare string may stand in for the «actor» «slot»
`tests/unit/capture/test_story.py:184::test_path_allows_bare_string_in_position_0`

- **given** a search verb
- **given** a Room work object
- **when** a bare string takes position 0 of a «Path»
- **then** it is accepted as an «Activity Part» word

## ✓ Position 1 of a «path» must be a «verb»
`tests/unit/capture/test_story.py:194::test_path_rejects_actor_in_position_1` · validation

- **given** a Guest actor
- **given** a Room work object
- **when** an «Actor» is placed in position 1 of a «Path»
- **then** a PytestGivenError says position 1 is the «Verb» slot

## ✓ A «work object» cannot fill the «verb» «slot»
`tests/unit/capture/test_story.py:209::test_path_rejects_work_object_in_position_1` · validation

- **given** a Guest actor
- **given** a Room work object
- **when** a «Work Object» is placed in position 1 of a «Path»
- **then** a PytestGivenError says position 1 is the «Verb» slot

## ✓ Position 2 of a «path» must be a noun
`tests/unit/capture/test_story.py:224::test_path_rejects_verb_in_position_2` · validation

- **given** a Guest actor
- **given** a search verb
- **when** a «Verb» is placed in position 2 of a «Path»
- **then** a PytestGivenError says position 2 is the noun slot

## ✓ A bare «verb» may sit between two real entity nodes
`tests/unit/capture/test_story.py:239::test_path_allows_bare_verb_between_term_nodes`

- **given** a Guest actor
- **given** a Room work object
- **when** a bare verb sits between an «Actor» and a «Work Object»
- **then** the entities are term refs and the verb stays a bare word

## ✓ A «path» may be fully bare words
`tests/unit/capture/test_story.py:254::test_path_allows_fully_bare_path`

- **given** three plain words with no glossary handles
- **when** a «Path» is built from them
- **then** every part is an «Activity Part» word

## ✓ Node/edge alternation allows a trailing connective node
`tests/unit/capture/test_story.py:273::test_path_allows_node_edge_alternation_with_connective`

- **given** an «Actor», a «Verb», a «Work Object» and a second actor
- **when** they form a five-part «Path» joined by a connective
- **then** even positions are term-ref nodes and the connective stays a word

## ✓ A «path» may not end on a dangling edge
`tests/unit/capture/test_story.py:298::test_path_rejects_dangling_edge` · validation

- **given** an «Actor», «Verb» and «Work Object» plus a connective
- **when** a path ending on a connective edge is built
- **then** a PytestGivenError rejects the dangling edge

## ✓ A single-path «activity» synthesizes one «path»
`tests/unit/capture/test_story.py:323::test_activity_single_path_synthesizes_one_path`

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **when** an «Activity» is built from handles directly
- **then** it wraps a single «Path»

## ✓ An «activity» may branch into multiple «paths»
`tests/unit/capture/test_story.py:336::test_activity_multi_path_accepts_multiple_paths`

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **given** two alternate «Path» branches
- **when** they are combined into one «Activity»
- **then** the activity carries both paths

## ✓ Mixing loose parts and prebuilt «paths» is rejected
`tests/unit/capture/test_story.py:350::test_activity_mixing_parts_and_paths_raises` · validation

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **given** a prebuilt «Path»
- **when** it is combined with loose handles in one «Activity»
- **then** a PytestGivenError rejects the mix

## ✓ «Activity» id 0 is reserved
`tests/unit/capture/test_story.py:367::test_activity_explicit_id_zero_raises` · validation

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **when** an «Activity» is built with explicit activity_id=0
- **then** a PytestGivenError says activity_id=0 is reserved

## ✓ A «story» auto-numbers its «activities» from one
`tests/unit/capture/test_story.py:385::test_story_auto_numbers_activities_from_one`

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **when** a «Story» is built from two «Activity» rows
- **then** the activities are numbered 1 and 2

## ✓ Auto-numbering skips ids already taken explicitly
`tests/unit/capture/test_story.py:400::test_story_auto_numbering_skips_taken_explicit_ids`

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **given** a mix of explicit and auto «Activity» ids
- **when** they are assembled into a «Story»
- **then** auto picks skip the ids already used explicitly

## ✓ Duplicate «activity» ids in a «story» are rejected
`tests/unit/capture/test_story.py:417::test_story_rejects_duplicate_activity_ids` · validation

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **given** two «Activity» rows sharing an explicit id
- **when** they are assembled into a «Story»
- **then** a PytestGivenError reports the duplicate activity id

## ✓ A «story» derives its id from its title
`tests/unit/capture/test_story.py:437::test_story_derives_id_from_title`

- **given** a human-readable story title
- **when** a «Story» is built from it
- **then** its id is the slugified title

## ✓ A «story» may span only one «glossary»
`tests/unit/capture/test_story.py:449::test_story_rejects_two_glossaries` · validation

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **given** two activities that reach two different glossaries
- **when** a «Story» is built spanning both glossaries
- **then** a PytestGivenError says a story spans multiple glossaries

## ✓ Two «stories» with the same id collide
`tests/unit/capture/test_story.py:495::test_story_id_collision_raises_with_both_sites` · validation

- **given** a «Story» already declared under an id
- **when** a second story is declared with the same slug
- **then** a PytestGivenError reports the id was already declared

## ✓ A «path» may chain a second verb-object pair
`tests/unit/capture/test_story.py:578::test_path_allows_second_verb_edge`

- **given** an «Actor», two «Verb» and two «Work Object» handles
- **when** they form a five-node «Path» (actor verb object verb object)
- **then** every slot is a «Term ref», with no bare words

## ✓ A declared «work object» in a «verb» «slot» is rejected at construction
`tests/unit/capture/test_story.py:670::test_file_glossary_declared_kind_in_wrong_slot_raises` · validation

- **given** a «File glossary» declaring Room a work object
- **when** Room is placed in the «verb» «slot»
- **then** a PytestGivenError names the term and its declared kind

## ✓ A «slot» error names the «term», not its repr
`tests/unit/capture/test_story.py:696::test_slot_error_message_stays_compact` · diagnostics

- **given** a Guest actor
- **given** a Room work object
- **given** a search verb
- **when** a «work object» is placed in the «verb» slot
- **then** the message names the term without dumping the glossary
- **then** the message is short and free of dataclass reprs

## ✓ A kindless «term» stays valid in any «slot»
`tests/unit/capture/test_story.py:717::test_kindless_term_is_accepted_in_either_slot` · validation

- **given** a «Kindless» «Term» declared with g(...)
- **when** it is placed in a node «slot» and a verb slot
- **then** both paths construct, leaving the kind to inference

## ✓ A non-handle «activity part» names its type
`tests/unit/capture/test_story.py:732::test_non_handle_part_names_its_type` · validation, diagnostics

- **given** a Guest actor
- **given** a Room work object
- **when** an int is passed where a «verb» handle belongs
- **then** a PytestGivenError names the offending type and the path

## ✓ A Template parses a bare placeholder
`tests/unit/capture/test_template.py:41::test_template_parses_single_placeholder` · parametrization

- **given** a deferred «Templatize» template with one placeholder
- **when** the template is parsed
- **then** it splits into literal and placeholder «Narration» parts

## ✓ A Template substitutes parametrize values
`tests/unit/capture/test_template.py:85::test_template_substitute_basic` · parametrization

- **given** a «Templatize» template referencing a «Case» column
- **when** a «Parameter table» value is substituted in
- **then** the placeholder is filled with that value

## ✓ A Template accepts bare identifiers only · 3 cases
`tests/unit/capture/test_template.py:122::test_template_non_identifier_raises_pytest_given_error` · validation

- **given** the placeholder {text}
- **when** a «Templatize» template is built from it
- **then** a PytestGivenError says bare identifiers only

| text | |
|---|---|
| count={obj.attr} | ✓ |
| {d[key]} | ✓ |
| {x + 1} | ✓ |

## ✓ A t-string interpolation becomes a value part
`tests/unit/capture/test_template.py:151::test_parse_tstring_single_interpolation`

- **given** a t-string step with one interpolated value
- **when** the t-string is parsed at runtime
- **then** the interpolation becomes a «Narration» value part

## ✓ A t-string can interpolate an arbitrary expression
`tests/unit/capture/test_template.py:214::test_parse_tstring_expression`

- **given** a t-string step interpolating a computed expression
- **when** the t-string is parsed
- **then** the «Value highlight» part records the full expression

## ✓ A «glossary» handle in a t-string emits a «term ref»
`tests/unit/capture/test_template.py:253::test_tstring_with_actor_emits_term_ref`

- **given** an «Actor» handle from the glossary
- **when** the handle is interpolated into a t-string step
- **then** the step carries a «Term ref» for that «Actor»

## ✓ A «work object» handle in a t-string emits a «term ref»
`tests/unit/capture/test_template.py:281::test_tstring_with_work_object_emits_term_ref`

- **given** a «Work Object» handle from the glossary
- **when** it is interpolated into a t-string step
- **then** the step carries a «Term ref» for that «Work Object»

## ✓ A bare «verb» handle keeps its canonical display
`tests/unit/capture/test_template.py:302::test_tstring_with_verb_emits_term_ref_with_canonical_display`

- **given** a «Verb» handle used without an «Inflection»
- **when** it is interpolated into a t-string step
- **then** the «Term ref» shows the canonical verb

## ✓ An inflected «verb» in a t-string shows the «inflection»
`tests/unit/capture/test_template.py:317::test_tstring_with_inflected_verb_emits_term_ref_with_inflected_display`

- **given** a «Verb» handle called with an «Inflection»
- **when** it is interpolated into a t-string step
- **then** the «Term ref» shows the inflection but keeps the verb id

## ✓ A «term ref» may not carry a format spec
`tests/unit/capture/test_template.py:357::test_tstring_term_ref_with_format_spec_raises` · validation

- **given** an «Actor» handle interpolated with a format spec
- **when** the t-string is parsed
- **then** a PytestGivenError says a «Term ref» takes no format spec

## ✓ A «FileGlossary» handle works in a t-string «step»
`tests/unit/capture/test_template.py:400::test_tstring_with_file_term_handle_emits_term_ref`

- **given** a «Deferred term» from a «File glossary»
- **when** it is interpolated into a t-string step
- **then** the step carries a single «Term ref»

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
`tests/unit/lint/test_ast_rules.py:262::test_then_without_check_fires`

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
`tests/unit/lint/test_ast_rules.py:426::test_check_outside_then_fires_on_assert_in_given_or_when`

- **given** a {phase} «step» whose body asserts
  - 📎 step body — *see parameter table*
- **when** the AST «rules» parse that source
- **then** a warn «finding» names the {phase} step holding the assert

| phase | step body | |
|---|---|---|
| given | step body | ✓ |
| when | step body | ✓ |

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
`tests/unit/lint/test_ast_rules.py:562::test_action_in_then_fires_when_no_when_exists`

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
`tests/unit/lint/test_ast_rules.py:738::test_unused_interpolation_fires_on_unused_bare_identifier`

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
`tests/unit/lint/test_runtime_rules.py:132::test_tag_shadows_term_fires_once_per_unique_tag`

- **given** a «glossary» defining one «term»
- **given** two scenarios carrying that word as a «tag»
- **when** the runtime «rules» run
- **then** a single warn «finding» names the «tag», the «term» it shadows, and both scenarios

## ✓ «Narration lint» flags a «term» that no «step» or «story» references
`tests/unit/lint/test_runtime_rules.py:220::test_dead_term_flags_unreferenced_term`

- **given** a «glossary» holding one unreferenced «term»
- **when** the runtime «rules» run over no scenarios and no stories
- **then** the «finding» names the unreferenced «term»
- **then** its «severity» is off — the rule is opt-in

## ✓ A «verb» «activity» ref has one identity regardless of «inflection»
`tests/unit/report/test_coverage.py:67::test_identity_of_activity_term_ref_verb_ignores_display`

- **given** a «Verb» written canonically and as an «Inflection»
- **when** «Coverage» derives each «Term ref» identity
- **then** both collapse to the one canonical verb identity

## ✓ A branching «activity» unions references across its «paths»
`tests/unit/report/test_coverage.py:150::test_a_refs_unions_across_multi_path_activity`

- **given** an «Activity» that branches into two «Path» alternatives
- **when** «Coverage» collects the «Activity» references
- **then** both «Instance» identities across the branches are present

## ✓ An «instance» «step» ref adds a canonical fallback
`tests/unit/report/test_coverage.py:204::test_s_for_step_instance_entity_ref_adds_canonical_fallback`

- **given** a «Step» referring to a named «Instance»
- **when** «Coverage» computes the identity set for the «Step»
- **then** it includes the canonical «Term ref» fallback

## ✓ A «verb» ref always resolves to its canonical identity
`tests/unit/report/test_coverage.py:219::test_s_for_step_verb_ref_always_canonical`

- **given** a «Step» using an «Inflection» of a «Verb»
- **when** «Coverage» computes its identity set
- **then** the identity ignores the surface form and stays canonical

## ✓ An unknown «term ref» is skipped
`tests/unit/report/test_coverage.py:231::test_s_for_step_unknown_term_ref_skipped` · validation

- **given** a «Step» referencing a «Term» not in the glossary
- **when** «Coverage» computes its identity set
- **then** the unknown ref contributes nothing to the identity set

## ✓ An «instance» «step» covers a canonical «activity»
`tests/unit/report/test_coverage.py:255::test_compute_coverage_covers_canonical_activity_via_instance_step`

- **given** a «Story» with a canonical «Activity»
- **when** a «Scenario» step names a specific «Instance»
- **then** «Coverage» reports the «Activity» as covered

## ✓ A canonical «step» does not cover an «instance» «activity»
`tests/unit/report/test_coverage.py:285::test_compute_coverage_does_not_cover_instance_activity_with_canonical_step`

- **given** an «Activity» anchored to a named «Instance»
- **when** a «Scenario» step only names the canonical «Actor»
- **then** «Coverage» leaves the more specific instance activity uncovered

## ✓ Promoting a bare word to a «verb» ref drops «coverage» from a «step» that matched
`tests/unit/report/test_coverage.py:316::test_compute_coverage_lost_when_activity_gains_a_term`

- **given** a «Step» naming two «term refs»
- **given** the same «Activity» with that middle slot a bare word, then a «Verb» ref
- **when** «Coverage» is computed against each «Story»
- **then** the two-ref «Activity» is covered
- **then** the widened «Activity» is no longer covered

## ✓ A «scenario» «activity» binding constrains «coverage»
`tests/unit/report/test_coverage.py:370::test_compute_coverage_scenario_constrained_to_activity_ids`

- **given** a «Story» with two matching activities
- **when** the «Scenario» «binds» only to activity 1
- **then** «Coverage» considers only the bound «Activity»

## ✓ An «activity» with two distinct «terms» is «coverage»-eligible
`tests/unit/report/test_coverage.py:416::test_is_coverage_eligible_true_for_two_distinct_terms`

- **given** an «Activity» anchored by two distinct «Term» refs
- **when** its «Coverage» eligibility is checked
- **then** it is eligible for «Coverage» tracking

## ✓ An under-anchored «activity» is not «coverage»-eligible
`tests/unit/report/test_coverage.py:438::test_is_coverage_eligible_false_for_one_distinct_term`

- **given** an «Activity» that mentions only one distinct «Term»
- **when** its «Coverage» eligibility is checked
- **then** it is ineligible — «Coverage» needs at least two anchors

## ✓ An under-anchored «activity» is never covered by narration matching
`tests/unit/report/test_coverage.py:468::test_compute_coverage_excludes_under_anchored_activity`

- **given** a «Story» whose «Activity» is all bare words
- **when** coverage is computed against a scenario
- **then** «Coverage» excludes the under-anchored «Activity»

## ✓ Nested «steps» are walked for «coverage»
`tests/unit/report/test_coverage.py:492::test_compute_coverage_nested_steps_are_walked`

- **given** a «Story» with one canonical «Activity»
- **when** the covering «Term ref»s live in a nested child «Step»
- **then** the nested «Step» still counts and the «Activity» is covered

## ✓ An explicit «step» binding covers an eligible «activity»
`tests/unit/report/test_coverage.py:526::test_compute_coverage_explicit_step_binding_covers_eligible_activity`

- **given** a «Story» with a coverage-eligible «Activity»
- **when** a «Step» «binds» to it explicitly by id
- **then** «Coverage» counts it directly, without identity matching

## ✓ An explicit binding covers an under-anchored «activity»
`tests/unit/report/test_coverage.py:554::test_compute_coverage_explicit_binding_covers_under_anchored_activity`

- **given** a «Story» whose «Activity» is under-anchored
- **when** a «Step» «binds» to it explicitly by id
- **then** «Coverage» counts it, despite the missing anchors

## ✓ The «glossary» view aggregates «instances» and «verb» forms
`tests/unit/report/test_glossary_view.py:53::test_build_glossary_aggregations_collects_instances_and_forms`

- **given** a «Report» whose «Story» and «Scenario» reference entity «Instance»s and an «Inflection»
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
              "activity_ids": [],
              "fixture_name": null
            }
          ],
          "parameters": null,
          "error": null,
          "skip_reason": null,
          "source": null,
          "story_id": "book",
          "activity_ids": []
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
            "kind": "verb",
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
          "activities": [
            {
              "id": 1,
              "paths": [
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
              ]
            }
          ],
          "source": null
        }
      ]
    }
    ```
- **when** the «Glossary» aggregations are built
- **then** the entity terms collect their «Instance»s
- **then** the verb collects its «Inflection» but not its canonical form

## ✓ «Terms» referenced by an «activity» record the «story»
`tests/unit/report/test_glossary_view.py:153::test_build_glossary_aggregations_records_story_refs_via_activities`

- **given** a «Story» whose «Activity» references an actor and a verb
- **when** the «Glossary» aggregations are built
- **then** the actor and the verb each list that «Story»

## ✓ A «story» referencing a «term» twice lists it once
`tests/unit/report/test_glossary_view.py:183::test_repeated_references_within_one_story_are_recorded_once`

- **given** a «Story» whose two «activities» repeat the same «Term» and the same «Inflection»
- **when** the «Glossary» aggregations are built
- **then** the «Story» and the «Inflection» appear once each

## ✓ A canonical entity reference is not an «instance»
`tests/unit/report/test_glossary_view.py:236::test_build_glossary_aggregations_canonical_entity_ref_is_not_an_instance`

- **given** a «Story» activity and a «Step» referencing entities by canonical name only
- **when** the «Glossary» aggregations are built
- **then** neither entity term records an «Instance»

## ✓ A «kindless» «term» records only its «story» ref
`tests/unit/report/test_glossary_view.py:322::test_build_glossary_aggregations_kindless_term_records_only_story_ref`

- **given** a «Kindless» «Term» referenced by a «Story» activity
- **when** the «Glossary» aggregations are built
- **then** the «Term» lists the «Story» but no «Instance» and no «Inflection»

## ✓ An «instance» seen in a fixture «step» records its fixture provenance
`tests/unit/report/test_glossary_view.py:355::test_glossary_aggregations_annotates_fixture_provenance`

- **given** a «Scenario» whose fixture-sourced «Step» names an «Instance»
- **when** the «Glossary» aggregations are built
- **then** the «Instance» carries the fixture name

## ✓ The «term» index maps each «term» to its «scenarios» once
`tests/unit/report/test_glossary_view.py:444::test_build_term_scenario_index_dedups_and_includes_scenario_narration`

- **given** a «Scenario» referencing one «Term» in two steps and another in its name
- **when** the term-scenario index is built
- **then** each «Term» maps to the scenario exactly once

## ✓ «Parameter coloring» marks placeholders and table headers
`tests/unit/report/test_html_renderer.py:223::test_render_parametrized_step_with_structured_narration` · parametrization

- **given** a «Report» holding a «Parametrized scenario» with a «Parameter table»
- **when** the «Renderer» renders the HTML page
- **then** «Parameter coloring» classes mark the grouped placeholder and the table headers
- **then** the page carries one generated color rule per column, after the stylesheet so a term ref bound to a column takes the column ink

## ✓ A passed «scenario» renders as a checked heading with «step» bullets
`tests/unit/report/test_md_renderer.py:46::test_passed_scenario_heading_and_steps`

- **given** a «Report» holding a passed «Scenario» with three steps
- **when** the Markdown «Report» is rendered
- **then** the heading is checked and each «Step» is a phase bullet
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
`tests/unit/report/test_md_renderer.py:145::test_nested_steps_indent`

- **given** a «Scenario» whose when «Step» has a nested child
- **when** the Markdown «Report» is rendered
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
`tests/unit/report/test_md_renderer.py:170::test_narration_parts_resolve_terms_and_values`

- **given** a «Step» whose «Narration» carries a «Term ref», a value and a placeholder
- **when** the Markdown «Report» is rendered
- **then** the «Term ref» renders in guillemets, the value verbatim and the placeholder in braces
  - 📎 Rendered Markdown:
    ```
    # pytest-given — proj
    
    ## ✓ ignored
    `tests/t.py::test_parts`
    
    - **when** a «Guest»42{amount}
    ```

## ✓ A «parametrized scenario» renders its «parameter table»
`tests/unit/report/test_md_renderer.py:241::test_parametrized_scenario_renders_table` · parametrization

- **given** a «Parametrized scenario» with a two-«Case» «Parameter table»
- **when** the Markdown «Report» is rendered
- **then** the heading counts the cases and the «Parameter table» lists each row
  - 📎 Rendered Markdown:
    ```
    # pytest-given — proj
    
    ## ✓ Pricing · 2 cases
    `tests/t.py::test_price`
    
    - **when** insert
    
    | euros | expect | |
    |---|---|---|
    | 1 | False | ✓ |
    | 2 | True | ✓ |
    ```

## ✓ A failing «step» is marked with a minimal error digest
`tests/unit/report/test_md_renderer.py:278::test_failing_scenario_renders_a_minimal_error`

- **given** a failed «Scenario» carrying a two-line error and an internal frame
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
- **when** the Markdown «Report» is rendered
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
`tests/unit/report/test_md_renderer.py:349::test_multiline_attachment_renders_fenced_block`

- **given** a «Step» carrying a multi-line «Attachment»
- **when** the Markdown «Report» is rendered
- **then** the «Attachment» content sits in an indented fence, not inline
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
`tests/unit/report/test_md_renderer.py:512::test_skipped_scenario_shows_reason`

- **given** a skipped «Scenario» with a reason
- **when** the Markdown «Report» is rendered
- **then** the heading is marked skipped and the reason follows the node id
  - 📎 Rendered Markdown:
    ```
    # pytest-given — proj
    
    ## ○ Later · skipped
    `tests/t.py::test_skip` — reason: needs fixture data
    
    - **when** act
    ```

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

| preset | url_scheme | |
|---|---|---|
| vscode | vscode://file/{path}:{line} | ✓ |
| cursor | cursor://file/{path}:{line} | ✓ |
| zed | zed://file/{path}:{line} | ✓ |
| pycharm | pycharm://open?file={path}&line={line} | ✓ |

## ✓ A raw URL template is used as the «source link» verbatim
`tests/unit/report/test_source_link.py:66::test_resolve_template_raw_template_passes_through`

- **given** a raw blob-URL template rather than a preset name
- **when** the config value is resolved
- **then** it comes back unchanged

## ✓ An unknown preset name is refused, with the valid ones listed
`tests/unit/report/test_source_link.py:76::test_resolve_template_unknown_preset_raises` · diagnostics

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

## ✓ An under-anchored «activity» is flagged ineligible in rollups
`tests/unit/report/test_story_view.py:167::test_build_story_rollups_flags_under_anchored_activity_ineligible`

- **given** a «Story» with an anchored and an under-anchored «Activity»
- **when** the story rollups are built
- **then** only the anchored «Activity» is «Coverage»-eligible

## ✓ A pinned under-anchored «activity» stops reading as untracked
`tests/unit/report/test_story_view.py:211::test_build_story_rollups_pinned_under_anchored_activity_is_tracked`

- **given** a «Story» whose only «Activity» is under-anchored
- **given** a «Scenario» whose «step» pins it by id
- **when** the story rollups are built
- **then** it stays narration-ineligible but is no longer untracked

## ✓ An «Activity» is labeled by the prose of its «paths»
`tests/unit/report/test_story_view.py:313::test_build_activity_labels_joins_parts_into_prose`

- **given** a «Story» with a two-«path» «activity»
- **when** the «activity» labels are built
- **then** the label reads as prose under a story-scoped key, with the «path» texts joined

## ✓ «Grouping» collapses parametrize «cases» into one «scenario»
`tests/unit/test_grouping.py:116::test_group_parametrized_any_failed_groups_as_failed` · parametrization

- **given** three «Case» records of one «Parametrized scenario»
- **when** the «grouping» pass collapses them
- **then** one scenario remains and any failed «Case» fails it

## ✓ A «parametrized scenario» keeps its place among the «scenarios» around it
`tests/unit/test_grouping.py:148::test_group_parametrized_keeps_source_order` · parametrization

- **given** a plain «scenario» between two parametrized ones
- **when** the «grouping» pass runs
- **then** the «report» lists them in the order the file declares

## ✓ The grouped tree comes from the first passed «case»
`tests/unit/test_grouping.py:247::test_baseline_is_the_first_passed_case_not_the_first_case` · parametrization

- **given** a skipped first «Case» and a second one that ran
- **when** the «cases» are «grouped»
- **then** the tree is the one the passed «Case» recorded

## ✓ A plain-str «narration» that varies across «cases» is refused
`tests/unit/test_grouping.py:474::test_a_varying_str_narration_raises_rule_one` · parametrization, validation

- **given** two «cases» whose text differs but records no parts
- **when** the «cases» are «grouped»
- **then** the grouping is refused
- **then** the error names the test, the missing parts and the t-string fix

## ✓ A narrated value that varies becomes a derived «parameter table» column
`tests/unit/test_grouping.py:591::test_a_varying_bare_name_interpolation_becomes_a_derived_column` · parametrization

- **given** two «cases» narrating a value that differs
- **when** «templatizing» walks the «cases»
- **then** the value becomes a derived column beside the parametrize one
- **then** the «Step» keeps a placeholder pointing at that column

## ✓ A varying interpolation that is not a bare name is refused
`tests/unit/test_grouping.py:703::test_a_varying_compound_interpolation_raises_rule_two` · diagnostics, parametrization, validation

- **given** two «cases» narrating a computed expression
- **when** the «cases» are «grouped»
- **then** the grouping is refused
- **then** the error quotes the expression and shows the bind-a-local fix

## ✓ A «parameter table» cell reads the way the scenario name formats it
`tests/unit/test_grouping.py:1069::test_a_scenario_name_format_spec_reaches_its_cell` · parametrization

- **given** a Template scenario name formatting its parameter
- **when** the «cases» are «grouped»
- **then** the cells carry the formatting the name declared

## ✓ A scenario name formatting a parameter a «step» reads plainly gets its own column
`tests/unit/test_grouping.py:1084::test_a_scenario_name_disagreeing_with_a_step_gets_its_own_column` · parametrization

- **given** a name formatting the parameter and a step reading it plainly
- **when** the «cases» are «grouped»
- **then** the name points at a column holding what it renders
- **then** the name renders the disambiguated token, text and parts agreeing

## ✓ A «step» formatting a parameter the scenario name reads plainly gets its own column
`tests/unit/test_grouping.py:1127::test_a_step_slot_disagreeing_with_the_name_gets_its_own_column` · parametrization

- **given** a step formatting the parameter and a name reading it plainly
- **when** the «cases» are «grouped»
- **then** the step points at a column holding what it renders
- **then** the step renders the disambiguated token, text and parts agreeing

## ✓ A «step» narrating a parameter its column no longer holds is refused
`tests/unit/test_grouping.py:1209::test_a_rebound_parametrize_name_raises_rule_three` · parametrization, validation

- **given** two «cases» narrating a value their column lacks
- **when** the «cases» are «grouped»
- **then** the grouping is refused
- **then** the error names the column and what the case actually narrated

## ✓ A «term ref» whose display differs between «cases» is refused
`tests/unit/test_grouping.py:1560::test_a_varying_term_ref_display_raises_rule_four` · parametrization, validation

- **given** two «cases» whose «Term ref» reads differently
- **when** the «cases» are «grouped»
- **then** the grouping is refused
- **then** the error names the «Term ref» and the split-it-out fix

## ✓ A «term ref» that *is* the parametrize value is refused too
`tests/unit/test_grouping.py:1617::test_a_param_bound_term_ref_that_varies_raises_rule_four` · parametrization, validation

- **given** two «cases» whose «Term ref» is the parameter itself
- **when** the «cases» are «grouped»
- **then** the grouping is refused
- **then** the error points at the per-case «scenario» opt-out

## ✓ An «attachment» whose payload varies becomes an «attachment» column
`tests/unit/test_grouping.py:1781::test_a_varying_attachment_becomes_a_column_and_leaves_a_content_less_badge` · parametrization

- **given** two «cases» attaching a label with differing payloads
- **when** «templatizing» walks the «cases»
- **then** the payload moves into an «attachment» column
- **then** the «Step» keeps a content-less badge pointing at it

## ✓ A «step» whose set of «attachment» labels differs between «cases» is refused
`tests/unit/test_grouping.py:1837::test_a_label_present_in_one_case_only_raises_rule_five` · parametrization, validation

- **given** an «Attachment» label only one «Case» attaches
- **when** the «cases» are «grouped»
- **then** the grouping is refused
- **then** the error names the label, the case, and asks for a constant one

## ✓ A «parameter table» cell reads the way the «step» that points at it read
`tests/unit/test_grouping.py:2383::test_a_formatted_param_cell_holds_the_text_the_step_narrated` · parametrization

- **given** two «cases» narrating a parameter with a format spec
- **when** «grouping» builds the «parameter table»
- **then** each cell carries the formatted text, under one column
- **then** the step keeps its placeholder, which that cell substitutes into

## ✓ «Cases» that narrate different «steps» are refused rather than «grouped»
`tests/unit/test_grouping.py:2540::test_divergent_step_structure_refuses_the_merge` · parametrization, validation

- **given** two «cases» whose «step» trees differ
- **when** the «cases» are «grouped»
- **then** the grouping is refused
- **then** the error names the divergence and the opt-out that answers it

## ✓ A «step» narrating a glossary term parameter keeps pointing at its «parameter table» column
`tests/unit/test_grouping.py:2691::test_a_step_slot_over_a_term_instance_keeps_pointing_at_its_cell` · parametrization

- **given** a step narrating a parameter bound to a glossary term instance
- **when** the «cases» are «grouped»
- **then** the «parameter table» holds the term displays alone
- **then** the step still points at that column

## ✓ A «parametrized scenario» can decline the «grouping» and keep one «scenario» per «case»
`tests/unit/test_percase.py:59::test_opted_out_group_emits_one_scenario_per_case` · parametrization

- **given** two «cases» of a scenario that opted out
- **when** the «grouping» pass runs
- **then** each «case» stands alone, with no «parameter table»
