import json

import pytest


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


def _failing_scenario_error(pytester, tmp_path, *extra):
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
    result = pytester.runpytest(f'--given-json={json_path}', *extra)
    result.assert_outcomes(failed=1)
    return json.loads(json_path.read_text())['scenarios'][0]['error']


def test_internal_frames_dropped_by_default(pytester, tmp_path):
    """The pluggy/_pytest/decorator frames are filtered before getrepr, so they
    never reach the JSON — only user frames survive."""
    error = _failing_scenario_error(pytester, tmp_path)
    assert error['frames'], 'expected the user frame to survive'
    assert all(not f['is_internal'] for f in error['frames']), (
        f'expected only user frames, got {error["frames"]!r}'
    )
    assert any(f['func'] == 'test_fail' for f in error['frames'])


def test_given_all_frames_retains_internal_frames(pytester, tmp_path):
    """--given-all-frames skips the pre-filter, so internal frames ride in the
    JSON classified as is_internal=True for the renderer's toggle."""
    error = _failing_scenario_error(pytester, tmp_path, '--given-all-frames')
    assert any(f['is_internal'] for f in error['frames']), (
        f'expected internal frames to be retained, got {error["frames"]!r}'
    )
    assert any(f['func'] == 'test_fail' for f in error['frames'])


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


def test_attach_outside_a_step_fails_the_test(pytester, tmp_path):
    """Attaching from the test body, before any step is open, fails loudly.

    The payload has no step to bind to, and the report would otherwise come out
    complete-looking with the attachment silently missing.
    """
    pytester.makepyfile(
        """
        from pytest_given import scenario, then, attach

        @scenario("Attach test")
        def test_attach():
            attach("my log", "log content")
            with then("check"):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(['*no step is open*'])


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


def test_parametrized_test_as_table(pytester, tmp_path):
    """Parametrized tests produce a parameter table in the report."""
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
    # Parametrized tests are grouped into one scenario with a parameter table
    assert len(data['scenarios']) == 1
    s = data['scenarios'][0]
    assert s['narration']['text'] == 'Param test'
    assert s['parameters'] is not None
    columns = s['parameters']['columns']
    assert [c['name'] for c in columns] == ['a', 'b', 'expected']
    assert all(c['kind'] == 'param' for c in columns)
    assert all(c['id'] == c['name'] for c in columns)
    assert len(s['parameters']['cases']) == 2
    assert s['parameters']['cases'][0]['values'] == [1, 2, 3]
    assert s['parameters']['cases'][0]['status'] == 'passed'
    assert s['parameters']['cases'][1]['values'] == [2, 3, 5]
    # The grouped step's narration parts carry placeholders for matching param names.
    given_parts = s['steps'][0]['narration']['parts']
    placeholder_names = [p['name'] for p in given_parts if 'name' in p]
    assert placeholder_names == ['a', 'b']
    then_parts = s['steps'][1]['narration']['parts']
    then_placeholders = [p['name'] for p in then_parts if 'name' in p]
    assert then_placeholders == ['expected']


def test_parametrized_non_json_values_are_captured_as_str(pytester, tmp_path):
    """Non-JSON-primitive parametrize values (dates, objects) must not crash
    the JSON sink; they are captured as their str() while primitives keep
    their type."""
    pytester.makepyfile(
        """
        from datetime import date
        import pytest
        from pytest_given import scenario, then

        @scenario("Date param")
        @pytest.mark.parametrize("day,fee", [(date(2026, 3, 15), 0)])
        def test_fee(day, fee):
            with then(t"the fee on {day} is {fee}"):
                assert fee == 0
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    cases = data['scenarios'][0]['parameters']['cases']
    assert cases[0]['values'] == ['2026-03-15', 0]


def test_indirect_parametrize_narrates_the_fixture_value(pytester, tmp_path):
    """An `indirect=True` parameter reaches the test as whatever its fixture
    returned, and that is what the narration renders. Comparing the narration
    against `callspec.params` instead accuses a faithful interpolation of
    rebinding the name and suppresses every sink in the session — with no local
    to rename, since the name is the fixture's argname."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, when

        @pytest.fixture
        def cup_size(request):
            return request.param * 2

        @scenario("Brew indirectly")
        @pytest.mark.parametrize("cup_size", [200, 350], indirect=True)
        def test_brew(cup_size):
            with when(t"it brews {cup_size} ml"):
                assert cup_size > 0
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=2)
    assert 'report not written' not in result.stdout.str()
    data = json.loads(json_path.read_text())
    cases = data['scenarios'][0]['parameters']['cases']
    # The cell holds what the test argument held, so row hover substitutes the
    # value the step actually narrated.
    assert [c['values'] for c in cases] == [[400], [700]]


def test_a_mutated_parametrize_value_is_captured_as_it_was_at_setup(pytester, tmp_path):
    """Parametrize values are read again at session finish, so a test body that
    mutates one in place would otherwise put the post-test state in the table —
    and make rule 3 compare the narration against a value that no longer
    matches what it rendered."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, given, when

        @scenario("Fill a cart")
        @pytest.mark.parametrize("cart", [['latte'], ['mocha']])
        def test_cart(cart):
            with given(t"a cart holding {cart}"):
                pass
            with when("a cup is added"):
                cart.append('cup')
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=2)
    assert 'report not written' not in result.stdout.str()
    data = json.loads(json_path.read_text())
    cases = data['scenarios'][0]['parameters']['cases']
    assert [c['values'] for c in cases] == [["['latte']"], ["['mocha']"]]


def test_a_grouping_error_discards_the_previous_report(pytester, tmp_path):
    """The run writes no sink because the report would be false — but the sink
    from the last run is still on disk, and a reader who opens it (or a CI step
    that publishes it) gets a report that looks current and says nothing about
    the failure."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, when

        @scenario("Brew")
        @pytest.mark.parametrize("cup_size", [200, 350])
        def test_brew(cup_size):
            with when(f"it brews {cup_size} ml"):
                assert cup_size > 0
        """
    )
    json_path = tmp_path / 'report.json'
    html_path = tmp_path / 'report.html'
    json_path.write_text('{"stale": true}')
    html_path.write_text('<html>stale</html>')
    result = pytester.runpytest(
        f'--given-json={json_path}', f'--given-html={html_path}'
    )
    assert 'report not written' in result.stdout.str()
    assert not json_path.exists()
    assert not html_path.exists()
    assert 'report.json' in result.stdout.str()


def test_two_test_files_sharing_a_basename_render_fine(pytester, tmp_path):
    """`tests/unit/test_x.py` beside `tests/integration/test_x.py` is an
    ordinary layout; the HTML report used to abort on it."""
    pytester.makepyfile(
        test_dup="""
        from pytest_given import scenario, then

        @scenario("A")
        def test_thing():
            with then("it holds"):
                assert True
        """,
    )
    sub = pytester.mkpydir('pkg')
    (sub / 'test_dup.py').write_text(
        'from pytest_given import scenario, then\n'
        '\n'
        '@scenario("B")\n'
        'def test_thing():\n'
        '    with then("it holds"):\n'
        '        assert True\n'
    )
    html_path = tmp_path / 'report.html'
    result = pytester.runpytest(f'--given-html={html_path}')
    result.assert_outcomes(passed=2)
    assert html_path.exists()
    assert 'pkg/dup/thing' in html_path.read_text(encoding='utf-8')


def test_an_unknown_source_link_preset_fails_before_the_suite_runs(pytester):
    """A typo in --given-source-link is a usage error, caught at configure time.

    Learning about it only at session finish means paying for the whole suite
    first, and the error arrived as a bare traceback with no summary line.
    """
    pytester.makepyfile(
        """
        from pytest_given import scenario, then

        @scenario("Brew")
        def test_brew():
            with then("it brews"):
                assert True
        """
    )
    result = pytester.runpytest('--given-html=report.html', '--given-source-link=bogus')
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(['*Unknown given_source_link preset*'])
    # No outcome line at all: the run stopped at configure, before collection.
    assert 'passed' not in result.stdout.str()


def test_a_render_failure_leaves_no_half_replaced_report(pytester, tmp_path):
    """Every sink is rendered before any is written.

    Otherwise the JSON lands, the HTML render raises, and the pair on disk
    describes two different runs with nothing saying so.
    """
    pytester.makepyfile(
        """
        from pytest_given import scenario, then

        @scenario("Brew")
        def test_brew():
            with then("it brews"):
                assert True
        """
    )
    json_path = tmp_path / 'report.json'
    html_path = tmp_path / 'report.html'
    json_path.write_text('{"stale": true}')
    html_path.write_text('<html>stale</html>')
    # A raw template passes preset resolution at configure time and fails when
    # the renderer compiles it — the last point a sink can still raise.
    result = pytester.runpytest(
        f'--given-json={json_path}',
        f'--given-html={html_path}',
        '--given-source-link={bogus}',
    )
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(['*report not written*'])
    # Neither the stale pair nor a half-written new one survives.
    assert not json_path.exists()
    assert not html_path.exists()


def test_an_unwritable_report_shows_in_the_summary_line(pytester, tmp_path):
    """A run that writes no report must not print a green summary.

    Same reason as the lint's — see
    `test_an_error_finding_shows_in_the_summary_line`. `-ra` is passed because
    the short summary renders whatever the failure was registered as, so this
    covers that path too.
    """
    pytester.makepyfile(
        """
        from pytest_given import scenario, when

        @scenario('brews')
        def test_brew():
            with when('it brews'):
                pass
        """
    )
    result = pytester.runpytest(
        '-ra',
        f'--given-html={tmp_path / "report.html"}',
        '--given-source-link={bogus}',
    )
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(['*1 passed*1 error*'])


def test_parametrized_with_failure(pytester, tmp_path):
    """A parametrized test with a failing case marks the scenario as failed."""
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
        f'--given-html={html_path}',
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


def test_fixture_teardown_failure_fails_the_scenario(pytester, tmp_path):
    """A scenario whose fixture errors *after* its yield must not stay green.

    The teardown report arrives once `finish_scenario` has already cleared the
    active scenario, so without an explicit teardown path the error is dropped
    and the report shows `passed` for a run pytest counted as an error.
    """
    pytester.makepyfile(
        """
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
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1, errors=1)
    data = json.loads(json_path.read_text())
    s = data['scenarios'][0]
    assert s['status'] == 'failed'
    assert s['error'] is not None
    assert 'teardown boom' in s['error']['message']


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


def test_tstring_expression_not_a_param_but_constant_stays_as_value(pytester, tmp_path):
    """An expression that doesn't match any param name renders as a plain value,
    not a placeholder — as long as it doesn't vary across cases (see rule 2 for
    the varying case, below)."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, when

        @scenario('Cost')
        @pytest.mark.parametrize('price', [10, 20])
        def test_cost(price):
            with when(t'cost: {1.2}'):
                pass
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=2)
    data = json.loads(json_path.read_text())
    parts = data['scenarios'][0]['steps'][0]['narration']['parts']
    val_parts = [p for p in parts if 'rendered' in p]
    assert len(val_parts) == 1
    assert val_parts[0]['expression'] == '1.2'


def test_tstring_varying_compound_expression_fails_the_run(pytester, tmp_path):
    """A varying interpolation whose expression is not a bare parametrize name
    cannot be honestly promoted to a column (there is no sensible name to give
    it) — rule 2 rejects the run instead of silently freezing case 1's value."""
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
    assert result.ret != 0
    result.stdout.fnmatch_lines(['*varies across parametrize cases*'])
    assert not json_path.exists()


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


def test_scenario_with_template_name_groups_and_renders(pytester, tmp_path):
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
    # All cases share the Template's raw text as grouping key → one scenario
    assert len(data['scenarios']) == 1
    s = data['scenarios'][0]
    assert s['narration']['text'] == 'Brew {cup_size} ml'
    assert s['narration']['parts'] != []
    columns = s['parameters']['columns']
    assert [c['name'] for c in columns] == ['cup_size']
    assert all(c['kind'] == 'param' for c in columns)
    assert all(c['id'] == c['name'] for c in columns)
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
    result.stdout.fnmatch_lines(['*attachment labels are plain text*'])


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
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(['*requires @pytest.mark.parametrize*'])
    assert 'INTERNALERROR' not in result.stdout.str()


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
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(['*cup_zize*'])
    assert 'INTERNALERROR' not in result.stdout.str()


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
    # A skip carries a structured reason, never a traceback — makereport
    # short-circuits before getrepr so no error/frames are captured.
    assert data['scenarios'][0]['error'] is None


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


def test_parametrized_all_cases_skipped_groups_as_skipped(pytester, tmp_path):
    """A parametrize where every case is skipped groups to status='skipped'."""
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


def test_parametrized_scenario_source_captured_in_json(pytester, tmp_path):
    """Parametrized scenarios survive grouping with their source intact."""
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
        f'--given-html={html_path}',
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
        f'--given-html={html_path}',
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
        f'--given-html={html_path}',
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
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(['*activity id*99*not in story*'])
    assert 'INTERNALERROR' not in result.stdout.str()


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
    """`_by_id` on Glossary and `_glossaries` on the story tree must not
    appear in the JSON output."""
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
    assert '_glossaries' not in raw


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
    # Reported through the terminal summary and the exit code, not as a bare
    # traceback out of console_main: the tests themselves all passed, and the
    # run has to say what went wrong with the report instead of dumping a stack.
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(['*report not written*', '*multiple Glossary*'])
    assert not (pytester.path / 'report.json').exists()


def test_annotated_given_on_parametrize_value_synthesizes_leaf(pytester, tmp_path):
    """A parametrize column annotated with given(Template(...)) grows a leaf
    given step; grouped view carries a placeholder for the column."""
    pytester.makepyfile(
        """
        from typing import Annotated
        import pytest
        from pytest_given import scenario, given, when, Template

        @scenario('slug rejects empties')
        @pytest.mark.parametrize('text', ['---', ''])
        def test_it(text: Annotated[str, given(Template('the name {text}'))]):
            with when('it is slugified'):
                pass
        """
    )
    json_path = tmp_path / 'out.json'
    pytester.runpytest(f'--given-json={json_path}')
    data = json.loads(json_path.read_text())
    (grouped,) = data['scenarios']
    given_step = grouped['steps'][0]
    assert given_step['phase'] == 'given'
    parts = given_step['narration']['parts']
    names = [p.get('name') for p in parts]
    assert 'text' in names
    placeholder = next(p for p in parts if p.get('name') == 'text')
    assert placeholder['column_id'] == 'text'
    columns = grouped['parameters']['columns']
    assert [c['name'] for c in columns] == ['text']
    assert all(c['kind'] == 'param' for c in columns)
    assert all(c['id'] == c['name'] for c in columns)


def test_annotated_given_on_multiple_param_columns(pytester, tmp_path):
    """Each annotated column of a multi-name parametrize gets its own leaf."""
    pytester.makepyfile(
        """
        from typing import Annotated
        import pytest
        from pytest_given import scenario, given, when, Template

        @scenario('two inputs')
        @pytest.mark.parametrize('a,b', [(1, 2)])
        def test_it(
            a: Annotated[int, given(Template('a is {a}'))],
            b: Annotated[int, given(Template('b is {b}'))],
        ):
            with when('added'):
                pass
        """
    )
    json_path = tmp_path / 'out.json'
    pytester.runpytest(f'--given-json={json_path}')
    data = json.loads(json_path.read_text())
    (grouped,) = data['scenarios']
    given_texts = [
        s['narration']['text'] for s in grouped['steps'] if s['phase'] == 'given'
    ]
    assert given_texts == ['a is {a}', 'b is {b}']


def test_annotated_given_plain_string_on_param_renders_verbatim(pytester, tmp_path):
    pytester.makepyfile(
        """
        from typing import Annotated
        import pytest
        from pytest_given import scenario, given, when

        @scenario('verbatim')
        @pytest.mark.parametrize('cup', [200])
        def test_it(cup: Annotated[int, given('a {cup} ml cup')]):
            with when('brewed'):
                pass
        """
    )
    json_path = tmp_path / 'out.json'
    pytester.runpytest(f'--given-json={json_path}')
    data = json.loads(json_path.read_text())
    (grouped,) = data['scenarios']
    assert grouped['steps'][0]['narration']['text'] == 'a {cup} ml cup'


def test_annotated_given_on_builtin_fixture_synthesizes_leaf(pytester, tmp_path):
    pytester.makepyfile(
        """
        from pathlib import Path
        from typing import Annotated
        from pytest_given import scenario, given, when

        @scenario('uses a temp dir')
        def test_it(tmp_path: Annotated[Path, given('a temporary directory')]):
            with when('something happens'):
                pass
        """
    )
    json_path = tmp_path / 'out.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    (s,) = data['scenarios']
    assert s['steps'][0]['phase'] == 'given'
    assert s['steps'][0]['narration']['text'] == 'a temporary directory'


def test_annotated_given_overrides_decorated_fixture_label_keeps_body(
    pytester, tmp_path
):
    pytester.makepyfile(
        """
        from typing import Annotated
        import pytest
        from pytest_given import scenario, given, when

        @pytest.fixture
        @given('the default label')
        def machine():
            with given('a recorded child'):
                pass
            return object()

        @scenario('override')
        def test_it(machine: Annotated[object, given('a fancy machine')]):
            with when('used'):
                pass
        """
    )
    json_path = tmp_path / 'out.json'
    pytester.runpytest(f'--given-json={json_path}')
    data = json.loads(json_path.read_text())
    (s,) = data['scenarios']
    root = s['steps'][0]
    assert root['narration']['text'] == 'a fancy machine'
    assert [c['narration']['text'] for c in root['children']] == ['a recorded child']


def test_annotated_given_indirect_parametrize_override_keeps_body(pytester, tmp_path):
    pytester.makepyfile(
        """
        from typing import Annotated
        import pytest
        from pytest_given import scenario, given, when

        @pytest.fixture
        @given('the default label')
        def machine(request):
            with given('a recorded child'):
                pass
            return request.param

        @scenario('indirect override')
        @pytest.mark.parametrize('machine', ['m1'], indirect=True)
        def test_it(machine: Annotated[object, given('an overridden machine')]):
            with when('used'):
                pass
        """
    )
    json_path = tmp_path / 'out.json'
    pytester.runpytest(f'--given-json={json_path}')
    data = json.loads(json_path.read_text())
    (s,) = data['scenarios']
    root = s['steps'][0]
    assert root['narration']['text'] == 'an overridden machine'
    assert [c['narration']['text'] for c in root['children']] == ['a recorded child']


def test_annotated_when_on_param_fails_scenario(pytester, tmp_path):
    pytester.makepyfile(
        """
        from typing import Annotated
        import pytest
        from pytest_given import scenario, when

        @scenario('bad')
        @pytest.mark.parametrize('x', [1])
        def test_it(x: Annotated[int, when('nope')]):
            pass
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(['*only given*'])


def test_annotated_given_tstring_on_param_fails_scenario(pytester, tmp_path):
    pytester.makepyfile(
        """
        from typing import Annotated
        import pytest
        from pytest_given import scenario, given

        NAME = 'frozen'

        @scenario('bad')
        @pytest.mark.parametrize('x', [1])
        def test_it(x: Annotated[int, given(t'a {NAME} label')]):
            pass
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(['*t-string*'])


def test_param_without_annotated_stays_table_only(pytester, tmp_path):
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, when

        @scenario('plain param')
        @pytest.mark.parametrize('n', [1, 2])
        def test_it(n):
            with when('acted'):
                pass
        """
    )
    json_path = tmp_path / 'out.json'
    pytester.runpytest(f'--given-json={json_path}')
    data = json.loads(json_path.read_text())
    (grouped,) = data['scenarios']
    assert [s['phase'] for s in grouped['steps']] == ['when']


def test_mixed_fixture_and_param_annotated_order(pytester, tmp_path):
    """Fixture graft (setup order) precedes the parametrize leaf (signature
    order): given steps read [a machine, the name {text}]."""
    pytester.makepyfile(
        """
        from typing import Annotated
        import pytest
        from pytest_given import scenario, given, when, Template

        @pytest.fixture
        @given('a machine')
        def machine():
            return object()

        @scenario('mixed')
        @pytest.mark.parametrize('text', ['x'])
        def test_it(
            machine,
            text: Annotated[str, given(Template('the name {text}'))],
        ):
            with when('run'):
                pass
        """
    )
    json_path = tmp_path / 'out.json'
    pytester.runpytest(f'--given-json={json_path}')
    data = json.loads(json_path.read_text())
    (grouped,) = data['scenarios']
    given_texts = [
        s['narration']['text'] for s in grouped['steps'] if s['phase'] == 'given'
    ]
    assert given_texts == ['a machine', 'the name {text}']


_SUITE = """
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
"""


def test_no_output_flags_writes_nothing(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(_SUITE)
    result = pytester.runpytest()
    assert result.ret == 0
    assert not (pytester.path / 'given-report').exists()


def test_given_md_prints_fenced_block(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(_SUITE)
    result = pytester.runpytest('--given-md')
    out = result.stdout.str()
    assert '<!-- pytest-given:md:start -->' in out
    assert '<!-- pytest-given:md:end -->' in out
    assert '## ✓ Buy coffee' in out


def test_given_md_path_writes_file_no_stdout(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(_SUITE)
    md_path = pytester.path / 'out.md'
    result = pytester.runpytest(f'--given-md={md_path}')
    assert '## ✓ Buy coffee' in md_path.read_text(encoding='utf-8')
    assert 'pytest-given:md:start' not in result.stdout.str()


def test_given_html_alone_writes_no_json(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(_SUITE)
    html_path = pytester.path / 'r.html'
    pytester.runpytest(f'--given-html={html_path}')
    assert html_path.exists()
    assert not (pytester.path / 'given-report' / 'report-data.json').exists()


def test_given_json_alone_writes_json(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(_SUITE)
    json_path = pytester.path / 'r.json'
    pytester.runpytest(f'--given-json={json_path}')
    assert json_path.exists()


_VIOLATING_SUITE = """
import pytest
from pytest_given import scenario, when

@pytest.mark.parametrize('cup_size', [200, 350])
@scenario('Brew')
def test_brew(cup_size):
    with when(f'the machine brews {cup_size} ml'):
        pass
"""


def test_a_rejected_form_fails_the_run_and_writes_no_sink(pytester):
    pytester.makepyfile(test_brew=_VIOLATING_SUITE)
    result = pytester.runpytest(
        '--given-json=out/report.json',
        '--given-html=out/report.html',
        '--given-md=out/report.md',
    )
    assert result.ret != 0
    result.stdout.fnmatch_lines(['*varies across parametrize cases*'])
    assert not (pytester.path / 'out').exists()
    assert 'Traceback (most recent call last)' not in result.stdout.str()


def test_a_rejected_form_fails_the_run_with_no_sink_flag(pytester):
    pytester.makepyfile(test_brew=_VIOLATING_SUITE)
    result = pytester.runpytest()
    assert result.ret != 0
    result.stdout.fnmatch_lines(['*varies across parametrize cases*'])


def test_given_title_cli_flag_names_the_report(pytester, tmp_path):
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
    md_path = tmp_path / 'report.md'
    result = pytester.runpytest(
        f'--given-json={json_path}',
        f'--given-md={md_path}',
        '--given-title=Coffee Shop Example',
    )
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    assert data['metadata']['title'] == 'Coffee Shop Example'
    assert md_path.read_text(encoding='utf-8').startswith(
        '# pytest-given — Coffee Shop Example'
    )


def test_given_title_absent_leaves_the_title_unset(pytester, tmp_path):
    """Without the flag the title stays None and the rootdir name still names
    the report — the pre-title behavior, unchanged."""
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
    assert data['metadata']['title'] is None


def test_given_title_ini_value(pytester, tmp_path):
    pytester.makeini(
        """
        [pytest]
        given_title = Hotel Booking Example
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
    pytester.runpytest(f'--given-json={json_path}')
    data = json.loads(json_path.read_text())
    assert data['metadata']['title'] == 'Hotel Booking Example'


def test_given_title_cli_overrides_ini(pytester, tmp_path):
    pytester.makeini(
        """
        [pytest]
        given_title = From Ini
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
    pytester.runpytest(
        f'--given-json={json_path}',
        '--given-title=From CLI',
    )
    data = json.loads(json_path.read_text())
    assert data['metadata']['title'] == 'From CLI'


def test_group_parametrized_false_without_parametrize_raises_at_collection(
    pytester, tmp_path
):
    pytester.makepyfile(
        """
        from pytest_given import scenario, then

        @scenario('Brew coffee', group_parametrized=False)
        def test_brew():
            with then('ok'):
                pass
        """
    )
    result = pytester.runpytest('--collect-only')
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(['*nothing to opt out of*'])
    assert 'INTERNALERROR' not in result.stdout.str()


def test_group_parametrized_false_emits_one_scenario_per_case(pytester, tmp_path):
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, then, Template

        @scenario(Template('Brew {cup_size} ml'), group_parametrized=False)
        @pytest.mark.parametrize('cup_size', [200, 300])
        def test_brew(cup_size):
            with then('it brews'):
                assert cup_size
        """
    )
    json_path = tmp_path / 'report.json'
    pytester.runpytest(f'--given-json={json_path}').assert_outcomes(passed=2)
    data = json.loads(json_path.read_text())
    assert [s['narration']['text'] for s in data['scenarios']] == [
        'Brew 200 ml [200]',
        'Brew 300 ml [300]',
    ]
    assert all(s['parameters'] is None for s in data['scenarios'])
