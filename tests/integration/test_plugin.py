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
    assert steps[0]['source'] == 'fixture'


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
    html = html_path.read_text()
    assert 'Basic addition' in html
    assert 'Failing test' in html
    assert 'a calculator' in html
    assert 'x-data' in html  # Alpine.js reactive
