"""Emit a large pure-scenario suite for performance benchmarking.

Generates `benchmarks/test_large_scenarios.py` with ~12k scenarios across a
mix of authoring shapes (plain, parametrized, nested when/then, attachments,
t-strings, templated names) and no story/glossary surface. Run via
`python benchmarks/gen_large_scenarios.py` or `uv run nox -s benchmark`.

The generated suite is gitignored; only this generator is committed.
"""

import argparse
import random
from pathlib import Path

OUT_PATH = Path(__file__).parent / 'test_large_scenarios.py'

DOMAINS = [
    ('order', 'customer', 'process', 'orders'),
    ('invoice', 'vendor', 'issue', 'invoices'),
    ('shipment', 'warehouse', 'dispatch', 'shipments'),
    ('payment', 'merchant', 'capture', 'payments'),
    ('reservation', 'guest', 'confirm', 'reservations'),
    ('ticket', 'agent', 'resolve', 'tickets'),
    ('account', 'user', 'verify', 'accounts'),
    ('lease', 'tenant', 'renew', 'leases'),
    ('claim', 'adjuster', 'settle', 'claims'),
    ('subscription', 'subscriber', 'renew', 'subscriptions'),
    ('shipment', 'courier', 'deliver', 'parcels'),
    ('booking', 'traveler', 'reschedule', 'bookings'),
]

TAGS = [
    'happy-path',
    'edge-case',
    'regression',
    'smoke',
    'billing',
    'fulfillment',
    'integration',
    'flaky',
    'security',
    'retry',
]


def render_tags(rng: random.Random) -> str:
    """Pick 0-2 tags, formatted for inline use in the @scenario call."""
    n = rng.choice([0, 0, 1, 1, 2])
    if n == 0:
        return ''
    picks = rng.sample(TAGS, n)
    return ', tags=[' + ', '.join(repr(t) for t in picks) + ']'


def emit_fixture(name: str, kind: str) -> str:
    """Emit a fixture decorated with `@given` and yielded teardown variant."""
    if kind == 'plain':
        return (
            f'@pytest.fixture\n'
            f"@given('a {name} record')\n"
            f'def {name}_record():\n'
            f"    return {{'id': 1, 'status': 'new'}}\n"
        )
    return (
        f'@pytest.fixture\n'
        f"@given('an open {name} session')\n"
        f'def {name}_session():\n'
        f"    session = {{'open': True, 'events': []}}\n"
        f'    yield session\n'
        f"    session['open'] = False\n"
    )


def emit_plain(idx: int, rng: random.Random, domain: tuple[str, ...]) -> str:
    """Plain scenario: a couple of when/then blocks, optional attachment."""
    noun, actor, verb, _ = domain
    tags = render_tags(rng)
    attach = rng.random() < 0.2
    body = [
        f"@scenario('{verb.capitalize()} {noun} #{idx} for the {actor}'{tags})",
        f'def test_{verb}_{noun}_{idx}({noun}_record):',
        f"    with when('the {actor} submits a {noun}'):",
        f"        {noun}_record['status'] = 'submitted'",
        f"    with then('the {noun} is {verb}ed'):",
        f"        assert {noun}_record['status'] == 'submitted'",
    ]
    if attach:
        body.append(f"        attach('{noun} state', {noun}_record)")
    return '\n'.join(body) + '\n'


def emit_parametrized(idx: int, rng: random.Random, domain: tuple[str, ...]) -> str:
    """Parametrized scenario with a t-string step and templated name."""
    noun, actor, verb, _ = domain
    cases = rng.randint(6, 14)
    tags = render_tags(rng)
    params = [(rng.randint(1, 99), rng.choice([True, False])) for _ in range(cases)]
    params_repr = ', '.join(f'({a}, {b})' for a, b in params)
    body = [
        '@scenario(',
        f"    Template('{verb.capitalize()} {{amount}} {noun}s (case #{idx})'){tags},",
        ')',
        f"@pytest.mark.parametrize('amount,allowed', [{params_repr}])",
        f'def test_{verb}_{noun}_param_{idx}({noun}_record, amount, allowed):',
        f"    with when(t'the {actor} requests {{amount}} {noun}s'):",
        f"        {noun}_record['requested'] = amount",
        "    with then(t'the request is allowed: {allowed}'):",
        '        assert isinstance(amount, int) and isinstance(allowed, bool)',
    ]
    return '\n'.join(body) + '\n'


def emit_nested(idx: int, rng: random.Random, domain: tuple[str, ...]) -> str:
    """Scenario with nested when/then blocks and a top-level given."""
    noun, actor, verb, _ = domain
    tags = render_tags(rng)
    attach = rng.random() < 0.3
    body = [
        f"@scenario('Nested {verb} flow for {noun} #{idx}'{tags})",
        f'def test_nested_{verb}_{noun}_{idx}({noun}_record):',
        f"    with given('an in-flight {noun} batch'):",
        f"        batch = {{'items': [{noun}_record['id']], 'verified': False}}",
        f"    with when('the {actor} reviews the batch'):",
        "        with when('the items are enumerated'):",
        "            count = len(batch['items'])",
        "        with when('the batch is verified'):",
        "            batch['verified'] = count > 0",
        "    with then('the batch advances to processing'):",
        f"        with then('the {noun} count is correct'):",
        '            assert count == 1',
        "        with then('the batch is marked verified'):",
        "            assert batch['verified']",
    ]
    if attach:
        body.append("            attach('batch state', batch)")
    return '\n'.join(body) + '\n'


def emit_session(idx: int, rng: random.Random, domain: tuple[str, ...]) -> str:
    """Scenario using a yield-fixture (teardown variant)."""
    noun, actor, verb, _ = domain
    tags = render_tags(rng)
    body = [
        f"@scenario('Session-backed {verb} for {noun} #{idx}'{tags})",
        f'def test_session_{verb}_{noun}_{idx}({noun}_session):',
        f"    with when('the {actor} logs an event'):",
        f"        {noun}_session['events'].append('{verb}.{idx}')",
        "    with then('the session has the event'):",
        f"        assert {noun}_session['open']",
        f"        assert '{verb}.{idx}' in {noun}_session['events']",
    ]
    return '\n'.join(body) + '\n'


EMITTERS = [
    (emit_plain, 0.45),
    (emit_parametrized, 0.30),
    (emit_nested, 0.15),
    (emit_session, 0.10),
]


FIXED_FAILURES = """\
@scenario('Fixed failure: assertion mismatch')
def test_fixed_failure_assert(order_record):
    with then('the status should be settled'):
        assert order_record['status'] == 'settled'


@scenario('Fixed failure: KeyError in step body')
def test_fixed_failure_keyerror(invoice_record):
    with when('the missing field is read'):
        _ = invoice_record['nonexistent']
    with then('this never runs'):
        assert False


@scenario('Fixed failure: ZeroDivisionError')
def test_fixed_failure_zerodiv(payment_record):
    with when('the denominator is zero'):
        rate = 100 / 0
    with then('this never runs'):
        assert rate > 0


@scenario('Fixed failure: nested then asserts')
def test_fixed_failure_nested(claim_record):
    with given('a claim under review'):
        review = {'open': True}
    with then('the claim is closed'):
        with then('the review flag is unset'):
            assert not review['open']


@scenario('Fixed failure: parametrized — some cases fail')
@pytest.mark.parametrize('value', [1, 2, 3, 4, 5])
def test_fixed_failure_param(value):
    with then(t'the value is at most 2'):
        assert value <= 2


@scenario('Skipped: feature flag off')
@pytest.mark.skip(reason='feature flag off')
def test_skipped_feature_flag():
    with then('this never runs'):
        assert False


@scenario('Skipped: awaiting fixture')
@pytest.mark.skip(reason='awaiting fixture')
def test_skipped_awaiting_fixture():
    with then('this never runs'):
        assert False


@scenario('Skipped: parametrized — mixed skip')
@pytest.mark.parametrize(
    'n',
    [
        1,
        pytest.param(2, marks=pytest.mark.skip(reason='under investigation')),
        3,
    ],
)
def test_skipped_param_mixed(n):
    with then(t'the value is positive: {n}'):
        assert n > 0
"""


def weighted_choice(rng: random.Random) -> object:
    """Pick an emitter by weight."""
    r = rng.random()
    acc = 0.0
    for emitter, weight in EMITTERS:
        acc += weight
        if r < acc:
            return emitter
    return EMITTERS[-1][0]


HEADER = '''\
"""Auto-generated large-scenario suite for performance benchmarking.

Do not edit by hand — regenerate via `python examples/_gen_large_scenarios.py`.
Pure scenarios only (no story/glossary). Aims for ~12k test items across a mix
of plain, parametrized, nested, and session-backed shapes.
"""

import pytest

from pytest_given import Template, attach, given, scenario, then, when


'''


def main(seed: int = 42, function_count: int = 3500) -> None:
    rng = random.Random(seed)
    parts: list[str] = [HEADER]

    for noun in sorted({d[0] for d in DOMAINS}):
        parts.append(emit_fixture(noun, 'plain'))
        parts.append('\n')
        parts.append(emit_fixture(noun, 'session'))
        parts.append('\n')

    for i in range(function_count):
        domain = rng.choice(DOMAINS)
        emitter = weighted_choice(rng)
        parts.append(emitter(i, rng, domain))
        parts.append('\n')

    parts.append(FIXED_FAILURES)

    OUT_PATH.write_text(''.join(parts), encoding='utf-8')
    print(f'wrote {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--count',
        type=int,
        default=3500,
        help='Number of distinct scenario functions to emit',
    )
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    main(seed=args.seed, function_count=args.count)
