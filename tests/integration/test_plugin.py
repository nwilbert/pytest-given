import json


def test_basic_scenario_generates_json(pytester, tmp_path):
    """A simple @scenario test produces JSON output."""
    pytester.makepyfile(
        """
        from pytest_given import scenario, given, when, then

        @scenario("My scenario", tags=["smoke"])
        def test_example():
            with given("a value"):
                x = 1
            with when("I double it"):
                result = x * 2
            with then("it is 2"):
                assert result == 2
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert len(data['scenarios']) == 1
    s = data['scenarios'][0]
    assert s['narration']['text'] == 'My scenario'
    assert s['tags'] == ['smoke']
    assert s['status'] == 'passed'
    assert len(s['steps']) == 3
    assert s['steps'][0]['phase'] == 'given'
    assert s['steps'][0]['narration']['text'] == 'a value'


def test_nested_steps(pytester, tmp_path):
    """Nested context managers produce nested steps."""
    pytester.makepyfile(
        """
        from pytest_given import scenario, when

        @scenario("Nested test")
        def test_nested():
            with when("outer"):
                with when("inner"):
                    pass
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    steps = data['scenarios'][0]['steps']
    assert len(steps) == 1
    assert steps[0]['narration']['text'] == 'outer'
    assert len(steps[0]['children']) == 1
    assert steps[0]['children'][0]['narration']['text'] == 'inner'


def test_failed_scenario(pytester, tmp_path):
    """A failing assertion is captured in the step error."""
    pytester.makepyfile(
        """
        from pytest_given import scenario, then

        @scenario("Failing test")
        def test_fail():
            with then("this fails"):
                assert 1 == 2
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(failed=1)
    data = json.loads(json_path.read_text())
    s = data['scenarios'][0]
    assert s['status'] == 'failed'
    error = s['error']
    assert error is not None
    assert isinstance(error['frames'], list)
    assert error['frames'], 'expected at least one frame'
    user_frames = [f for f in error['frames'] if not f['is_internal']]
    assert any(f['func'] == 'test_fail' for f in user_frames), (
        f'expected a user frame for test_fail, got {error["frames"]!r}'
    )
    assert error['error_tail'] is not None
    assert 'assert 1 == 2' in error['error_tail']


def test_unannotated_test_not_in_report(pytester, tmp_path):
    """Tests without @scenario don't appear in the report."""
    pytester.makepyfile(
        """
        def test_plain():
            assert True
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    assert len(data['scenarios']) == 0


def test_attachment_in_report(pytester, tmp_path):
    """Attachments on steps appear in the JSON."""
    pytester.makepyfile(
        """
        from pytest_given import scenario, then, attach

        @scenario("Attach test")
        def test_attach():
            with then("check"):
                attach("my log", "log content")
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    att = data['scenarios'][0]['steps'][0]['attachments']
    assert len(att) == 1
    assert att[0]['label'] == 'my log'


def test_step_fixture_appears_as_given_step(pytester, tmp_path):
    """A step fixture appears as a given step."""
    pytester.makepyfile(
        """
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
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    steps = data['scenarios'][0]['steps']
    assert steps[0]['phase'] == 'given'
    assert steps[0]['narration']['text'] == 'a prepared value'


def test_parameterized_test_as_table(pytester, tmp_path):
    """Parameterized tests produce a parameter table in the report."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, given, when, then

        @scenario("Param test", tags=["math"])
        @pytest.mark.parametrize("a,b,expected", [(1, 2, 3), (2, 3, 5)])
        def test_add(a, b, expected):
            with given(t"a={a} and b={b}"):
                pass
            with then(t"sum is {expected}"):
                assert a + b == expected
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=2)
    data = json.loads(json_path.read_text())
    # Parameterized tests are grouped into one scenario with a parameter table
    assert len(data['scenarios']) == 1
    s = data['scenarios'][0]
    assert s['narration']['text'] == 'Param test'
    assert s['parameters'] is not None
    assert s['parameters']['names'] == ['a', 'b', 'expected']
    assert len(s['parameters']['cases']) == 2
    assert s['parameters']['cases'][0]['values'] == [1, 2, 3]
    assert s['parameters']['cases'][0]['status'] == 'passed'
    assert s['parameters']['cases'][1]['values'] == [2, 3, 5]
    # The merged step's narration parts carry placeholders for matching param names.
    given_parts = s['steps'][0]['narration']['parts']
    placeholder_names = [p['name'] for p in given_parts if 'name' in p]
    assert placeholder_names == ['a', 'b']
    then_parts = s['steps'][1]['narration']['parts']
    then_placeholders = [p['name'] for p in then_parts if 'name' in p]
    assert then_placeholders == ['expected']


def test_parameterized_with_failure(pytester, tmp_path):
    """A parameterized test with a failing case marks the scenario as failed."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, then

        @scenario("Fail param")
        @pytest.mark.parametrize("n", [1, 2])
        def test_check(n):
            with then(t"n={n} is 1"):
                assert n == 1
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1, failed=1)
    data = json.loads(json_path.read_text())
    assert len(data['scenarios']) == 1
    s = data['scenarios'][0]
    assert s['status'] == 'failed'
    assert s['parameters']['cases'][0]['status'] == 'passed'
    assert s['parameters']['cases'][1]['status'] == 'failed'
    assert s['parameters']['cases'][1]['values'] == [2]


def test_full_html_report_generation(pytester, tmp_path):
    """Full pipeline: tests -> JSON -> HTML."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, given, when, then, attach

        @pytest.fixture
        @given("a calculator")
        def calc():
            return {"value": 0}

        @scenario("Basic addition", tags=["math"])
        def test_add(calc):
            with when("I add 2 and 3"):
                calc["value"] = 2 + 3
            with then("the result is 5"):
                assert calc["value"] == 5
                attach("debug", f"result was {calc['value']}")

        @scenario("Failing test", tags=["math"])
        def test_fail(calc):
            with then("this will fail"):
                assert 1 == 2
        """
    )
    json_path = tmp_path / 'report.json'
    html_path = tmp_path / 'report.html'
    result = pytester.runpytest(
        f'--given-json={json_path}',
        '--given-html',
        f'--given-html-output={html_path}',
    )
    result.assert_outcomes(passed=1, failed=1)
    assert json_path.exists()
    assert html_path.exists()

    # Verify JSON structure
    data = json.loads(json_path.read_text())
    assert len(data['scenarios']) == 2
    names = {s['narration']['text'] for s in data['scenarios']}
    assert names == {'Basic addition', 'Failing test'}

    # Verify HTML content
    html = html_path.read_text(encoding='utf-8')
    assert 'Basic addition' in html
    assert 'Failing test' in html
    assert 'a calculator' in html
    assert 'x-data' in html  # Alpine.js reactive


def test_fixture_setup_failure_appears_in_report(pytester, tmp_path):
    """A scenario whose fixture errors during setup still appears as failed,
    not silently dropped — pytest_runtest_logreport must finish the scenario
    at the setup phase when no call phase will run."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, then

        @pytest.fixture
        def broken():
            raise RuntimeError("fixture boom")

        @scenario("Setup-failed")
        def test_a(broken):
            with then("never runs"):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    pytester.runpytest(f'--given-json={json_path}')
    data = json.loads(json_path.read_text())
    assert len(data['scenarios']) == 1
    s = data['scenarios'][0]
    assert s['narration']['text'] == 'Setup-failed'
    assert s['status'] == 'failed'
    assert s['error'] is not None
    assert 'fixture boom' in s['error']['message']


def test_unannotated_after_setup_failure_is_not_contaminated(pytester, tmp_path):
    """When a @scenario test's fixture fails and is followed by an unannotated
    test, the next test's `with given(...)` must warn (not push into the
    orphaned scenario)."""
    pytester.makepyfile(
        """
        import warnings
        import pytest
        from pytest_given import scenario, given, then

        @pytest.fixture
        def broken():
            raise RuntimeError("boom")

        @scenario("Failing scenario")
        def test_a(broken):
            with then("never runs"):
                pass

        def test_b():
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                with given('a thing'):
                    pass
                assert any('without @scenario' in str(w.message) for w in caught)
        """
    )
    json_path = tmp_path / 'report.json'
    pytester.runpytest(f'--given-json={json_path}')
    data = json.loads(json_path.read_text())
    failing = [
        s for s in data['scenarios'] if s['narration']['text'] == 'Failing scenario'
    ]
    assert len(failing) == 1
    assert failing[0]['steps'] == []


def test_given_inside_unannotated_test_warns(pytester, tmp_path):
    """A `with given(...)` inside a non-@scenario test warns, doesn't crash."""
    pytester.makepyfile(
        """
        import warnings
        from pytest_given import given

        def test_plain():
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                with given('a thing'):
                    pass
                assert any('without @scenario' in str(w.message) for w in caught)
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)


def test_with_given_inside_fixture_body_is_captured(pytester, tmp_path):
    """Nested `with given(...)` in a step fixture body lands under its step."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, given, then

        @pytest.fixture
        @given("a shop")
        def shop():
            with given("with 3 items"):
                pass
            return {"items": 3}

        @scenario("Fixture body recording")
        def test_shop(shop):
            with then("items == 3"):
                assert shop["items"] == 3
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    steps = data['scenarios'][0]['steps']
    assert steps[0]['narration']['text'] == 'a shop'
    assert len(steps[0]['children']) == 1
    assert steps[0]['children'][0]['narration']['text'] == 'with 3 items'
    assert steps[1]['narration']['text'] == 'items == 3'


def test_given_in_fixture_teardown_raises(pytester, tmp_path):
    """Calling `with given(...)` after the fixture's yield is a hard error."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, given, then

        @pytest.fixture
        @given("a thing")
        def thing():
            yield 1
            with given("teardown step"):  # illegal
                pass

        @scenario("Teardown raises")
        def test_use(thing):
            with then("v == 1"):
                assert thing == 1
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}', '-v')
    # The test body passes; the teardown failure should surface as an error.
    # pytester reports teardown errors as ERROR, not as a failed test.
    assert result.ret != 0
    result.stdout.fnmatch_lines(['*PytestGivenError*'])


def test_attach_in_fixture_teardown_raises(pytester, tmp_path):
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, given, then, attach

        @pytest.fixture
        @given("a thing")
        def thing():
            yield 1
            attach("late", "data")

        @scenario("Attach teardown raises")
        def test_use(thing):
            with then("v == 1"):
                assert thing == 1
        """
    )
    result = pytester.runpytest('-v')
    assert result.ret != 0
    result.stdout.fnmatch_lines(['*PytestGivenError*'])


def test_when_on_fixture_raises(pytester):
    """@when on a fixture is rejected: fixtures are setup, only @given fits."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, when, then

        @pytest.fixture
        @when("inserting money")
        def coin():
            return 2

        @scenario("uses bad fixture")
        def test_use(coin):
            with then("coin is 2"):
                assert coin == 2
        """
    )
    result = pytester.runpytest('-v')
    assert result.ret != 0
    result.stdout.fnmatch_lines(['*PytestGivenError*', '*@given*'])


def test_then_on_fixture_raises(pytester):
    """@then on a fixture is rejected for the same reason as @when."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, then

        @pytest.fixture
        @then("a coffee is dispensed")
        def coffee():
            return 'espresso'

        @scenario("uses bad fixture")
        def test_use(coffee):
            with then("coffee is espresso"):
                assert coffee == 'espresso'
        """
    )
    result = pytester.runpytest('-v')
    assert result.ret != 0
    result.stdout.fnmatch_lines(['*PytestGivenError*', '*@given*'])


def test_session_scoped_fixture_records_for_each_consumer(pytester, tmp_path):
    """A session-scoped step fixture body runs once but each consumer's
    scenario shows the recorded subtree."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, given, then

        @pytest.fixture(scope='session')
        @given("a database")
        def db():
            with given("seeded with 2 users"):
                pass
            return {"users": 2}

        @scenario("First consumer")
        def test_a(db):
            with then("ok"):
                assert db["users"] == 2

        @scenario("Second consumer")
        def test_b(db):
            with then("ok"):
                assert db["users"] == 2
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=2)
    data = json.loads(json_path.read_text())
    scenarios = {s['narration']['text']: s for s in data['scenarios']}
    for name in ('First consumer', 'Second consumer'):
        steps = scenarios[name]['steps']
        assert steps[0]['narration']['text'] == 'a database'
        assert steps[0]['children'][0]['narration']['text'] == 'seeded with 2 users'


def test_class_scoped_fixture_records_for_each_consumer(pytester, tmp_path):
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, given, then

        @pytest.fixture(scope='class')
        @given("a browser")
        def browser():
            with given("navigated to /"):
                pass
            return "browser"

        class TestUI:
            @scenario("Click A")
            def test_a(self, browser):
                with then("ok"):
                    assert browser == "browser"

            @scenario("Click B")
            def test_b(self, browser):
                with then("ok"):
                    assert browser == "browser"
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=2)
    data = json.loads(json_path.read_text())
    for s in data['scenarios']:
        assert s['steps'][0]['children'][0]['narration']['text'] == 'navigated to /'


def test_nested_step_fixtures_appear_as_siblings(pytester, tmp_path):
    """Fixture B depending on fixture A: both recordings graft as top-level."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, given, then

        @pytest.fixture
        @given("a database")
        def db():
            with given("seeded"):
                pass
            return "db"

        @pytest.fixture
        @given("an authenticated user")
        def user(db):
            with given("with admin role"):
                pass
            return f"user@{db}"

        @scenario("Nested")
        def test_uses_both(user):
            with then("ok"):
                assert "user@db" in user
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    steps = data['scenarios'][0]['steps']
    top_texts = [s['narration']['text'] for s in steps]
    assert 'a database' in top_texts
    assert 'an authenticated user' in top_texts
    # `db` is set up before `user`, so its recording grafts first.
    assert top_texts.index('a database') < top_texts.index('an authenticated user')
    db_step = next(s for s in steps if s['narration']['text'] == 'a database')
    user_step = next(
        s for s in steps if s['narration']['text'] == 'an authenticated user'
    )
    assert db_step['children'][0]['narration']['text'] == 'seeded'
    assert user_step['children'][0]['narration']['text'] == 'with admin role'


def test_tstring_in_non_parametrized_scenario_renders_value_with_no_placeholder(
    pytester, tmp_path
):
    pytester.makepyfile(
        """
        from pytest_given import scenario, when

        @scenario('Static')
        def test_one():
            cup_size = 200
            with when(t'a {cup_size} ml cup'):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    step = data['scenarios'][0]['steps'][0]
    assert step['narration']['text'] == 'a 200 ml cup'
    parts = step['narration']['parts']
    # Three parts: literal / value / literal — value preserved (no parametrize match)
    assert len(parts) == 3
    assert parts[1].get('rendered') == '200'
    assert parts[1].get('expression') == 'cup_size'


def test_tstring_expression_not_a_param_stays_as_value(pytester, tmp_path):
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, when

        @scenario('Cost')
        @pytest.mark.parametrize('price', [10, 20])
        def test_cost(price):
            with when(t'cost: {price * 1.2}'):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=2)
    data = json.loads(json_path.read_text())
    parts = data['scenarios'][0]['steps'][0]['narration']['parts']
    # Expression doesn't match any param name → stays as a value, not a placeholder
    val_parts = [p for p in parts if 'rendered' in p]
    assert len(val_parts) == 1
    assert val_parts[0]['expression'] == 'price * 1.2'


def test_tstring_same_value_different_names_disambiguates(pytester, tmp_path):
    """Two params with the same value get distinguished — str.replace couldn't."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, when

        @scenario('Dual')
        @pytest.mark.parametrize('cup_size,beans_g', [(200, 200)])
        def test_dual(cup_size, beans_g):
            with when(t'{cup_size}, {beans_g}'):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    parts = data['scenarios'][0]['steps'][0]['narration']['parts']
    placeholder_names = [p['name'] for p in parts if 'name' in p]
    assert placeholder_names == ['cup_size', 'beans_g']


def test_scenario_with_template_name_merges_and_renders(pytester, tmp_path):
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, then, Template

        @scenario(Template('Brew {cup_size} ml'))
        @pytest.mark.parametrize('cup_size', [200, 300])
        def test_brew(cup_size):
            with then('ok'):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=2)
    data = json.loads(json_path.read_text())
    # All cases share the Template's raw text as merge key → one scenario
    assert len(data['scenarios']) == 1
    s = data['scenarios'][0]
    assert s['narration']['text'] == 'Brew {cup_size} ml'
    assert s['narration']['parts'] != []
    assert s['parameters']['names'] == ['cup_size']
    assert [c['values'] for c in s['parameters']['cases']] == [[200], [300]]


def test_given_with_tstring_on_fixture_works(pytester, tmp_path):
    """T-strings on fixture @given decorators evaluate at module load time.
    Module-level values (e.g. Glossary handles) are in scope and interpolate."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import Glossary, scenario, given, then

        g = Glossary()
        guest = g.actor('Guest')

        @pytest.fixture
        @given(t'our guest {guest("Alice")}')
        def alice():
            return 'Alice'

        @scenario('x')
        def test_x(alice):
            with then('ok'):
                pass
        """
    )
    result = pytester.runpytest('-v')
    assert result.ret == 0


def test_attach_with_template_raises(pytester, tmp_path):
    pytester.makepyfile(
        """
        from pytest_given import scenario, then, attach, Template

        @scenario('x')
        def test_x():
            with then('ok'):
                attach(Template('label {x}'), 'content')
        """
    )
    result = pytester.runpytest('-v')
    assert result.ret != 0
    result.stdout.fnmatch_lines(['*attach*not supported*'])


def test_static_str_with_literal_braces_renders_verbatim(pytester, tmp_path):
    pytester.makepyfile(
        """
        from pytest_given import scenario, when

        @scenario('Static braces')
        def test_static():
            with when('config: {key: value}'):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    step = data['scenarios'][0]['steps'][0]
    assert step['narration']['text'] == 'config: {key: value}'
    assert step['narration']['parts'] == []


def test_template_in_scenario_without_parametrize_raises_at_collection(
    pytester, tmp_path
):
    pytester.makepyfile(
        """
        from pytest_given import scenario, then, Template

        @scenario(Template('Brew {cup_size} ml'))
        def test_brew():
            with then('ok'):
                pass
        """
    )
    result = pytester.runpytest('--collect-only')
    assert result.ret != 0
    result.stdout.fnmatch_lines(['*requires @pytest.mark.parametrize*'])


def test_template_placeholder_typo_raises_helpful_error(pytester, tmp_path):
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, then, Template

        @scenario(Template('Brew {cup_zize} ml'))
        @pytest.mark.parametrize('cup_size', [200])
        def test_brew(cup_size):
            with then('ok'):
                pass
        """
    )
    result = pytester.runpytest('-v')
    assert result.ret != 0
    result.stdout.fnmatch_lines(['*cup_zize*'])


def test_skipped_scenario_captures_mark_reason(pytester, tmp_path):
    """@pytest.mark.skip(reason=...) surfaces the reason in JSON."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, then

        @scenario("Skipped with reason")
        @pytest.mark.skip(reason="awaiting fixture")
        def test_skip():
            with then("never runs"):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    pytester.runpytest(f'--given-json={json_path}').assert_outcomes(skipped=1)
    data = json.loads(json_path.read_text())
    assert data['scenarios'][0]['status'] == 'skipped'
    assert data['scenarios'][0]['skip_reason'] == 'awaiting fixture'


def test_skipped_scenario_without_reason_has_none(pytester, tmp_path):
    """@pytest.mark.skip with no reason leaves skip_reason as None."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, then

        @scenario("Skipped no reason")
        @pytest.mark.skip
        def test_skip():
            with then("never runs"):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    pytester.runpytest(f'--given-json={json_path}').assert_outcomes(skipped=1)
    data = json.loads(json_path.read_text())
    assert data['scenarios'][0]['skip_reason'] is None


def test_call_time_pytest_skip_captures_reason(pytester, tmp_path):
    """An in-body pytest.skip('msg') surfaces 'msg' as skip_reason."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, when

        @scenario("Skipped mid-test")
        def test_skip():
            with when("we bail"):
                pytest.skip("missing prerequisite")
        """
    )
    json_path = tmp_path / 'report.json'
    pytester.runpytest(f'--given-json={json_path}').assert_outcomes(skipped=1)
    data = json.loads(json_path.read_text())
    assert data['scenarios'][0]['skip_reason'] == 'missing prerequisite'


def test_parametrized_all_cases_skipped_merges_as_skipped(pytester, tmp_path):
    """A parametrize where every case is skipped merges to status='skipped'."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, then

        @scenario("All cases skipped")
        @pytest.mark.parametrize(
            "n",
            [
                pytest.param(1, marks=pytest.mark.skip(reason="not yet")),
                pytest.param(2, marks=pytest.mark.skip(reason="not yet")),
            ],
        )
        def test_all_skipped(n):
            with then("never runs"):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    pytester.runpytest(f'--given-json={json_path}').assert_outcomes(skipped=2)
    data = json.loads(json_path.read_text())
    assert len(data['scenarios']) == 1
    assert data['scenarios'][0]['status'] == 'skipped'


def test_helper_function_decorator_with_template_substitutes_args(pytester, tmp_path):
    """@when(Template('...${arg}...')) renders per call from bound args."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, when, then, Template

        @when(Template('I insert ${amount}'))
        def insert(amount):
            return amount

        @scenario('Helper template substitutes args')
        def test_buy():
            insert(2)
            with then('done'):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}', '-v')
    assert result.ret == 0
    data = json.loads(json_path.read_text())
    [scn] = data['scenarios']
    helper_step = scn['steps'][0]
    assert helper_step['narration']['text'] == 'I insert $2'
    parts = helper_step['narration']['parts']
    assert parts[0] == {'value': 'I insert $'}
    assert parts[1]['rendered'] == '2'
    assert parts[1]['expression'] == 'amount'


def test_helper_function_template_placeholder_not_in_signature_raises(
    pytester, tmp_path
):
    """Placeholder name absent from the helper signature → collection error."""
    pytester.makepyfile(
        """
        from pytest_given import when, Template

        @when(Template('I insert ${amount}'))
        def insert(other):
            return other
        """
    )
    result = pytester.runpytest('-v')
    assert result.ret != 0
    result.stdout.fnmatch_lines(['*placeholder*amount*'])


def test_helper_function_template_on_fixture_raises(pytester, tmp_path):
    """@given(Template(...)) on a fixture is rejected with 'not yet supported'."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, given, then, Template

        @pytest.fixture
        @given(Template('a balance of ${initial}'))
        def balance(initial=10):
            return initial

        @scenario('x')
        def test_x(balance):
            with then('ok'):
                pass
        """
    )
    result = pytester.runpytest('-v')
    assert result.ret != 0
    result.stdout.fnmatch_lines(['*not yet supported*'])


def test_helper_function_decorator_called_outside_scenario_is_silent(pytester):
    """A @when helper called from a non-@scenario test runs without warning or error."""
    pytester.makepyfile(
        """
        from pytest_given import when

        @when('does work')
        def do_work():
            return 42

        def test_plain():
            assert do_work() == 42
        """
    )
    result = pytester.runpytest('-W', 'error', '-v')
    assert result.ret == 0


def test_scenario_source_captured_in_json(pytester, tmp_path):
    """Each scenario in the JSON carries a source {relpath, line}."""
    pytester.makepyfile(
        test_src_link="""
        from pytest_given import scenario, when

        @scenario("A")
        def test_a():
            with when("x"):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    src = data['scenarios'][0]['source']
    assert src is not None
    assert src['relpath'].endswith('test_src_link.py')
    assert isinstance(src['line'], int)
    assert src['line'] >= 1


def test_parameterized_scenario_source_captured_in_json(pytester, tmp_path):
    """Parameterized scenarios survive grouping with their source intact."""
    pytester.makepyfile(
        test_src_link_param="""
        import pytest
        from pytest_given import scenario, when

        @scenario("A")
        @pytest.mark.parametrize("x", [1, 2])
        def test_a(x):
            with when("x"):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=2)
    data = json.loads(json_path.read_text())
    assert len(data['scenarios']) == 1
    src = data['scenarios'][0]['source']
    assert src is not None
    assert src['relpath'].endswith('test_src_link_param.py')
    assert isinstance(src['line'], int)
    assert src['line'] >= 1


def test_story_source_captured_in_json(pytester, tmp_path):
    """story() records the source location of its construction site."""
    pytester.makepyfile(
        test_story_src="""
        from pytest_given import Glossary, activity, scenario, story, when

        g = Glossary()
        guest = g.actor('Guest')
        search = g.verb('search')
        room = g.work_object('Room')
        s = story('Booking', [activity(guest, search, room)])

        @scenario('A', story=s, activities=[1])
        def test_a():
            with when("x"):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    assert len(data['stories']) == 1
    src = data['stories'][0]['source']
    assert src is not None
    assert src['relpath'].endswith('test_story_src.py')
    assert isinstance(src['line'], int)
    assert src['line'] >= 1


def test_glossary_term_source_captured_in_json(pytester, tmp_path):
    """Glossary terms record the source location of first registration."""
    pytester.makepyfile(
        test_glossary_src="""
        from pytest_given import Glossary, activity, scenario, story, when

        g = Glossary()
        guest = g.actor('Guest')
        search = g.verb('search')
        room = g.work_object('Room')
        s = story('Booking', [activity(guest, search, room)])

        @scenario('A', story=s, activities=[1])
        def test_a():
            with when("x"):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    terms = data['glossary']['terms']
    assert terms, 'expected at least one glossary term'
    for term in terms:
        src = term['source']
        assert src is not None, f'term {term["canonical"]} missing source'
        assert src['relpath'].endswith('test_glossary_src.py')
        assert isinstance(src['line'], int)
        assert src['line'] >= 1


def test_glossary_term_source_captured_when_declared_in_conftest(pytester, tmp_path):
    """Glossary terms registered at the top level of conftest.py — a common
    shared-fixture pattern — must capture source even though conftest is
    imported before `pytest_configure`."""
    pytester.makeconftest(
        """
        from pytest_given import Glossary, activity, story
        g = Glossary()
        guest = g.actor('Guest')
        search = g.verb('search')
        room = g.work_object('Room')
        s = story('ConftestStory', [activity(guest, search, room)])
        """
    )
    pytester.makepyfile(
        test_conf_src="""
        from conftest import s
        from pytest_given import scenario, when

        @scenario('A', story=s, activities=[1])
        def test_a():
            with when("x"):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    terms = data['glossary']['terms']
    assert terms, 'expected at least one glossary term'
    for term in terms:
        src = term['source']
        assert src is not None, f'term {term["canonical"]} missing source'
        assert src['relpath'].endswith('conftest.py')
    assert data['stories']
    story_src = data['stories'][0]['source']
    assert story_src is not None
    assert story_src['relpath'].endswith('conftest.py')


def test_metadata_commit_sha_captured(pytester, tmp_path, monkeypatch):
    """metadata.commit_sha is populated from env vars."""
    monkeypatch.setenv('GITHUB_SHA', 'integration-sha')
    pytester.makepyfile(
        """
        from pytest_given import scenario, when

        @scenario("A")
        def test_a():
            with when("x"):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    pytester.runpytest(f'--given-json={json_path}')
    data = json.loads(json_path.read_text())
    assert data['metadata']['commit_sha'] == 'integration-sha'


def test_given_source_link_cli_flag_emits_anchor(pytester, tmp_path):
    pytester.makepyfile(
        """
        from pytest_given import scenario, when

        @scenario("A")
        def test_a():
            with when("x"):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    html_path = tmp_path / 'report.html'
    result = pytester.runpytest(
        f'--given-json={json_path}',
        '--given-html',
        f'--given-html-output={html_path}',
        '--given-source-link=vscode',
    )
    result.assert_outcomes(passed=1)
    content = html_path.read_text(encoding='utf-8')
    assert '<a href="vscode://file/' in content
    assert '<div class="scenario-source">' in content


def test_given_source_link_ini_value(pytester, tmp_path):
    pytester.makeini(
        """
        [pytest]
        given_source_link = zed
        """
    )
    pytester.makepyfile(
        """
        from pytest_given import scenario, when

        @scenario("A")
        def test_a():
            with when("x"):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    html_path = tmp_path / 'report.html'
    pytester.runpytest(
        f'--given-json={json_path}',
        '--given-html',
        f'--given-html-output={html_path}',
    )
    content = html_path.read_text(encoding='utf-8')
    assert '<a href="zed://file/' in content


def test_given_source_link_cli_overrides_ini(pytester, tmp_path):
    pytester.makeini(
        """
        [pytest]
        given_source_link = zed
        """
    )
    pytester.makepyfile(
        """
        from pytest_given import scenario, when

        @scenario("A")
        def test_a():
            with when("x"):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    html_path = tmp_path / 'report.html'
    pytester.runpytest(
        f'--given-json={json_path}',
        '--given-html',
        f'--given-html-output={html_path}',
        '--given-source-link=vscode',
    )
    content = html_path.read_text(encoding='utf-8')
    assert '<a href="vscode://file/' in content
    assert 'zed://file/' not in content


def test_given_source_link_unknown_preset_raises(pytester, tmp_path):
    pytester.makepyfile(
        """
        from pytest_given import scenario, when

        @scenario("A")
        def test_a():
            with when("x"):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(
        f'--given-json={json_path}',
        '--given-html',
        '--given-source-link=emacs',
    )
    assert 'emacs' in (result.stderr.str() + result.stdout.str())


def test_step_activity_kwarg_propagates_to_report(pytester):
    pytester.makepyfile("""
        from pytest_given import Glossary, activity, given, scenario, story, when

        g = Glossary()
        guest = g.actor('Guest')
        search = g.verb('search')
        room = g.work_object('Room')
        s = story('Activity Propagation', [
            activity(guest, search, room),
            activity(guest('Alice'), search, room),
            activity(guest, search, room('Suite'))])

        @scenario('a scenario', story=s, activities=[1, 2, 3])
        def test_x():
            with given('setup', activity=1):
                pass
            with when('action', activity=[2, 3]):
                pass
    """)
    result = pytester.runpytest('--given-json=report.json')
    result.assert_outcomes(passed=1)
    data = json.loads(pytester.path.joinpath('report.json').read_text())
    steps = data['scenarios'][0]['steps']
    assert steps[0]['activity_ids'] == [1]
    assert steps[1]['activity_ids'] == [2, 3]


# --- Task 7.3: Capture story_id and activity_ids at scenario start ---


def test_scenario_story_id_appears_in_report(pytester):
    pytester.makepyfile("""
        from pytest_given import Glossary, activity, given, scenario, story

        g = Glossary()
        guest = g.actor('Guest')
        search = g.verb('search')
        room = g.work_object('Room')
        s = story('Book', [activity(guest, search, room)])

        @scenario('x', story=s, activities=[1])
        def test_x():
            with given('setup', activity=1):
                pass
    """)
    pytester.runpytest('--given-json=report.json')
    data = json.loads(pytester.path.joinpath('report.json').read_text())
    scn = data['scenarios'][0]
    assert scn['story_id'] == 'book'
    assert scn['activity_ids'] == [1]


# --- Task 7.2: Validate scenario binding at collection / runtime ---


def test_scenario_activity_id_not_in_story_raises_at_collection(pytester):
    pytester.makepyfile("""
        from pytest_given import Glossary, activity, scenario, story

        g = Glossary()
        guest = g.actor('Guest')
        search = g.verb('search')
        room = g.work_object('Room')
        s = story('Book', [activity(guest, search, room)])

        @scenario('x', story=s, activities=[99])
        def test_x():
            pass
    """)
    result = pytester.runpytest('--collect-only')
    result.stdout.fnmatch_lines(['*activity id*99*not in story*'])


def test_step_activity_outside_scenario_scope_raises(pytester):
    pytester.makepyfile("""
        from pytest_given import Glossary, activity, given, scenario, story

        g = Glossary()
        guest = g.actor('Guest')
        search = g.verb('search')
        room = g.work_object('Room')
        s = story('Book', [
            activity(guest, search, room),
            activity(guest('Alice'), search, room)])

        @scenario('x', story=s, activities=[1])
        def test_x():
            with given('thing', activity=2):
                pass
    """)
    result = pytester.runpytest()
    assert result.ret != 0
    result.stdout.fnmatch_lines(['*step activity*2*outside scenario scope*'])


def test_decorator_form_helper_step_with_activity_validates_scope(pytester):
    pytester.makepyfile("""
        from pytest_given import Glossary, activity, given, scenario, story

        g = Glossary()
        guest = g.actor('Guest')
        search = g.verb('search')
        room = g.work_object('Room')
        s = story('Book', [activity(guest, search, room)])

        @given('a setup', activity=99)
        def helper():
            return None

        @scenario('x', story=s)
        def test_x():
            helper()
    """)
    result = pytester.runpytest()
    assert result.ret != 0
    result.stdout.fnmatch_lines(['*step activity=99 not in story*'])


def test_step_activity_without_scenario_story_raises(pytester):
    pytester.makepyfile("""
        from pytest_given import given, scenario

        @scenario('x')
        def test_x():
            with given('thing', activity=1):
                pass
    """)
    result = pytester.runpytest()
    assert result.ret != 0
    result.stdout.fnmatch_lines(['*step activity= requires a story on the scenario*'])


# --- Task 7.4: Session-finish discovery + serde underscore filter ---


def test_session_finish_populates_report_stories_and_glossary(pytester):
    pytester.makepyfile("""
        from pytest_given import Glossary, activity, scenario, story

        g = Glossary()
        guest = g.actor('Guest')
        search = g.verb('search')
        room = g.work_object('Room')
        s = story('Book', [activity(guest, search, room)])

        @scenario('x', story=s)
        def test_x():
            pass
    """)
    pytester.runpytest('--given-json=report.json')
    data = json.loads(pytester.path.joinpath('report.json').read_text())
    assert len(data['stories']) == 1
    assert data['stories'][0]['title'] == 'Book'
    assert data['glossary'] is not None
    assert {t['id'] for t in data['glossary']['terms']} == {'guest', 'search', 'room'}


def test_session_finish_with_no_stories_leaves_glossary_none(pytester):
    pytester.makepyfile("""
        from pytest_given import scenario

        @scenario('x')
        def test_x():
            pass
    """)
    pytester.runpytest('--given-json=report.json')
    data = json.loads(pytester.path.joinpath('report.json').read_text())
    assert data['stories'] == []
    assert data['glossary'] is None


def test_report_json_excludes_underscore_fields(pytester):
    """_by_id on Story/Glossary must not appear in the JSON output."""
    pytester.makepyfile("""
        from pytest_given import Glossary, activity, scenario, story

        g = Glossary()
        guest = g.actor('Guest')
        search = g.verb('search')
        room = g.work_object('Room')
        s = story('Book JSON Filter', [activity(guest, search, room)])

        @scenario('x', story=s)
        def test_x():
            pass
    """)
    pytester.runpytest('--given-json=report.json')
    raw = pytester.path.joinpath('report.json').read_text()
    assert '_by_id' not in raw


# --- Task 7.5: Conftest-scan fallback ---


def test_glossary_only_in_conftest_is_discovered(pytester):
    pytester.makeconftest("""
        from pytest_given import Glossary
        g = Glossary()
        g.actor('Guest')
        g.verb('search')
    """)
    pytester.makepyfile("""
        from pytest_given import scenario

        @scenario('x')
        def test_x():
            pass
    """)
    pytester.runpytest('--given-json=report.json')
    data = json.loads(pytester.path.joinpath('report.json').read_text())
    assert data['glossary'] is not None
    term_ids = {t['id'] for t in data['glossary']['terms']}
    assert term_ids == {'guest', 'search'}


def test_glossary_in_regular_module_not_discovered_without_story(pytester):
    pytester.makepyfile(
        domain="""
        from pytest_given import Glossary
        g = Glossary()
        g.actor('Guest')
    """
    )
    pytester.makepyfile("""
        from pytest_given import scenario
        import domain

        @scenario('x')
        def test_x():
            assert domain.g is not None
    """)
    pytester.runpytest('--given-json=report.json')
    data = json.loads(pytester.path.joinpath('report.json').read_text())
    assert data['glossary'] is None


def test_multiple_glossaries_in_conftests_raises(pytester):
    pytester.makeconftest("""
        from pytest_given import Glossary
        g1 = Glossary()
        g1.actor('Foo')
        g2 = Glossary()
        g2.actor('Bar')
    """)
    pytester.makepyfile("""
        from pytest_given import scenario

        @scenario('x')
        def test_x():
            pass
    """)
    result = pytester.runpytest('--given-json=report.json')
    result.stderr.fnmatch_lines(['*multiple Glossary*'])
