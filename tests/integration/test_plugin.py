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
    assert s['name'] == 'My scenario'
    assert s['tags'] == ['smoke']
    assert s['status'] == 'passed'
    assert len(s['steps']) == 3
    assert s['steps'][0]['phase'] == 'given'
    assert s['steps'][0]['text'] == 'a value'


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
    assert steps[0]['text'] == 'outer'
    assert len(steps[0]['children']) == 1
    assert steps[0]['children'][0]['text'] == 'inner'


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
    assert s['error'] is not None


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


def test_decorated_fixture_appears_as_given_step(pytester, tmp_path):
    """A fixture decorated with @given appears as a given step."""
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
    assert steps[0]['text'] == 'a prepared value'


def test_parameterized_test_as_table(pytester, tmp_path):
    """Parameterized tests produce a parameter table in the report."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, given, when, then

        @scenario("Param test", tags=["math"])
        @pytest.mark.parametrize("a,b,expected", [(1, 2, 3), (2, 3, 5)])
        def test_add(a, b, expected):
            with given(f"a={a} and b={b}"):
                pass
            with then(f"sum is {expected}"):
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
    assert s['name'] == 'Param test'
    assert s['parameters'] is not None
    assert s['parameters']['names'] == ['a', 'b', 'expected']
    assert len(s['parameters']['cases']) == 2
    assert s['parameters']['cases'][0]['values'] == [1, 2, 3]
    assert s['parameters']['cases'][0]['status'] == 'passed'
    assert s['parameters']['cases'][1]['values'] == [2, 3, 5]


def test_parameterized_with_failure(pytester, tmp_path):
    """A parameterized test with a failing case marks the scenario as failed."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, then

        @scenario("Fail param")
        @pytest.mark.parametrize("n", [1, 2])
        def test_check(n):
            with then(f"n={n} is 1"):
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
    names = {s['name'] for s in data['scenarios']}
    assert names == {'Basic addition', 'Failing test'}

    # Verify HTML content
    html = html_path.read_text(encoding='utf-8')
    assert 'Basic addition' in html
    assert 'Failing test' in html
    assert 'a calculator' in html
    assert 'x-data' in html  # Alpine.js reactive


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
    """Nested `with given(...)` in a decorated fixture body lands under its step."""
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
    assert steps[0]['text'] == 'a shop'
    assert len(steps[0]['children']) == 1
    assert steps[0]['children'][0]['text'] == 'with 3 items'
    assert steps[1]['text'] == 'items == 3'


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


def test_session_scoped_fixture_records_for_each_consumer(pytester, tmp_path):
    """A session-scoped decorated fixture body runs once but each consumer's
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
    scenarios = {s['name']: s for s in data['scenarios']}
    for name in ('First consumer', 'Second consumer'):
        steps = scenarios[name]['steps']
        assert steps[0]['text'] == 'a database'
        assert steps[0]['children'][0]['text'] == 'seeded with 2 users'


def test_module_scoped_fixture_records_for_each_consumer(pytester, tmp_path):
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, given, then

        @pytest.fixture(scope='module')
        @given("a service")
        def svc():
            with given("with credentials"):
                pass
            return "svc"

        @scenario("A")
        def test_a(svc):
            with then("ok"):
                assert svc == "svc"

        @scenario("B")
        def test_b(svc):
            with then("ok"):
                assert svc == "svc"
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=2)
    data = json.loads(json_path.read_text())
    for s in data['scenarios']:
        assert s['steps'][0]['children'][0]['text'] == 'with credentials'


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
        assert s['steps'][0]['children'][0]['text'] == 'navigated to /'


def test_parametrized_fixture_records_per_variant(pytester, tmp_path):
    """Each parametrize variant of a fixture produces a case in the parameter table.

    In pytest >= 9, direct fixture params (via `params=[...]`) ARE included in
    callspec.params, so both variants get grouped into one scenario with a
    parameter table — just like indirect parametrize.  The fixture body's step
    text is templatized to the `{shop}` placeholder and both values appear in
    the cases table.
    """
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, given, then

        @pytest.fixture(params=[3, 7])
        @given("a shop")
        def shop(request):
            with given(f"with {request.param} items"):
                pass
            return request.param

        @scenario("Shop test")
        def test_shop(shop):
            with then(f"count is {shop}"):
                assert shop in (3, 7)
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=2)
    data = json.loads(json_path.read_text())
    # pytest >= 9 puts direct fixture params in callspec.params, so the two
    # variants are grouped into one scenario with a parameter table.
    assert len(data['scenarios']) == 1
    s = data['scenarios'][0]
    assert s['parameters'] is not None
    case_values = [c['values'] for c in s['parameters']['cases']]
    assert [3] in case_values
    assert [7] in case_values
    # The fixture body's nested step text is templatized.
    nested_text = s['steps'][0]['children'][0]['text']
    assert nested_text == 'with {shop} items'


def test_indirect_parametrize_templatizes_fixture_step_text(pytester, tmp_path):
    """Indirect parametrize of a fixture lets the templatizer collapse step
    text in the fixture body into a `{name}` placeholder."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, given, then

        @pytest.fixture
        @given("a shop")
        def shop(request):
            with given(f"with {request.param} items"):
                pass
            return request.param

        @scenario("Shop test")
        @pytest.mark.parametrize("shop", [3, 7], indirect=True)
        def test_shop(shop):
            with then("ok"):
                assert shop in (3, 7)
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=2)
    data = json.loads(json_path.read_text())
    # Indirect parametrize is in callspec.params → templatized to one scenario.
    assert len(data['scenarios']) == 1
    s = data['scenarios'][0]
    assert s['parameters'] is not None
    # Inside the fixture's recorded child step, the variant value is replaced
    # with the param name placeholder.
    nested = s['steps'][0]['children'][0]['text']
    assert nested == 'with {shop} items'


def test_nested_decorated_fixtures_appear_as_siblings(pytester, tmp_path):
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
    top_texts = [s['text'] for s in steps]
    assert 'a database' in top_texts
    assert 'an authenticated user' in top_texts
    # `db` is set up before `user`, so its recording grafts first.
    assert top_texts.index('a database') < top_texts.index('an authenticated user')
    db_step = next(s for s in steps if s['text'] == 'a database')
    user_step = next(s for s in steps if s['text'] == 'an authenticated user')
    assert db_step['children'][0]['text'] == 'seeded'
    assert user_step['children'][0]['text'] == 'with admin role'
