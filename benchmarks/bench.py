"""Benchmark driver for the large-scenarios suite.

Regenerates the suite for each measurement. Standalone — does not write the
HTML report (use `uv run nox -s benchmark` for that).

Usage:
    uv run python benchmarks/bench.py                  # sweep default sizes
    uv run python benchmarks/bench.py --sizes 500 1000 # sweep custom sizes
    uv run python benchmarks/bench.py --profile        # cProfile at N=250
    uv run python benchmarks/bench.py --profile 1000   # cProfile at N=1000
"""

import argparse
import cProfile
import pstats
import subprocess
import sys
import time
from pathlib import Path

import pytest

GEN = Path(__file__).parent / 'gen_large_scenarios.py'
SUITE = Path(__file__).parent / 'test_large_scenarios.py'


def regen(count: int) -> None:
    subprocess.run(
        [sys.executable, str(GEN), '--count', str(count)],
        check=True,
        capture_output=True,
    )


def collect_count() -> int:
    r = subprocess.run(
        [
            'uv',
            'run',
            'pytest',
            str(SUITE),
            '--collect-only',
            '-q',
            '-p',
            'no:cacheprovider',
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    last = [ln for ln in r.stdout.splitlines() if ln.strip()][-1]
    return int(last.split()[0])


def run_phase(args: list[str]) -> float:
    t0 = time.perf_counter()
    r = subprocess.run(
        [
            'uv',
            'run',
            'pytest',
            str(SUITE),
            '-p',
            'no:cacheprovider',
            '--tb=no',
            '--no-header',
            '-q',
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    t1 = time.perf_counter()
    if r.returncode not in (0, 1):
        print('STDERR:', r.stderr[-2000:])
        raise SystemExit(f'pytest failed (exit {r.returncode})')
    return t1 - t0


def sweep(sizes: list[int]) -> None:
    print(f'{"funcs":>6} {"items":>7} {"no_report":>10} {"json":>8} {"html":>8}')
    for n in sizes:
        regen(n)
        items = collect_count()
        t_none = run_phase(['--given-json=/tmp/discard.json'])
        # JSON only
        t_json = run_phase(['--given-json=/tmp/pg.json'])
        t_html = run_phase(
            [
                '--given-json=/tmp/pg.json',
                '--given-html=/tmp/pg.html',
            ]
        )
        print(f'{n:>6} {items:>7} {t_none:>10.2f} {t_json:>8.2f} {t_html:>8.2f}')


def profile_run(count: int) -> None:
    """Run pytest in-process so cProfile sees the plugin code, not subprocess."""
    regen(count)
    profiler = cProfile.Profile()
    profiler.enable()
    pytest.main(
        [
            str(SUITE),
            '-p',
            'no:cacheprovider',
            '--tb=no',
            '--no-header',
            '-q',
            '--given-json=/tmp/pg.json',
            '--given-html=/tmp/pg.html',
        ]
    )
    profiler.disable()
    stats = pstats.Stats(profiler).sort_stats('cumulative')
    stats.print_stats(40)
    print('\n--- by tottime ---\n')
    pstats.Stats(profiler).sort_stats('tottime').print_stats(40)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--profile',
        type=int,
        nargs='?',
        const=250,
        default=None,
        metavar='N',
        help='cProfile a single run after generating N functions (default 250)',
    )
    parser.add_argument(
        '--sizes', type=int, nargs='+', default=[250, 500, 1000, 2000, 4000]
    )
    args = parser.parse_args()
    if args.profile is not None:
        profile_run(args.profile)
    else:
        sweep(args.sizes)
