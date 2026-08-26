"""pytest-given plugin entry point — the hook surface pluggy registers.

`pytest11` points at this package, and pluggy collects hooks by scanning a
module's attributes for `pytest_*` names, so re-exporting them here is what
registers them; the `hookimpl` options ride on the function objects and survive
the re-export untouched.

The implementations live one module per concern, which is why this package
exists at all — as a single module the plugin held the option table, the
collection-time validation, the fixture machinery, the per-item hooks, the
report path and the terminal presentation in one 900-line file, while every
other module in the tree holds one thing:

- `state` — what the session keeps in `config.stash` (the leaf; every other
  module here reads it, none of them reads each other except as noted)
- `options` — the option table and the one place options are resolved
- `collection` — collection-time validation of what `@scenario` declared
- `fixtures` — recording a decorated fixture and grafting what it recorded
- `runtest` — the per-item hooks (reads `collection` and `fixtures`)
- `session` — the session's two edges: capture globals in, report and lint out

Only what needs pytest belongs anywhere in here. The pytest-free work is the
subpackages': `capture` records, `grouping` merges, `lint` checks, `report`
renders, and this layer resolves options into the shapes those take.
"""

from .collection import pytest_collection_modifyitems
from .fixtures import pytest_fixture_setup
from .options import pytest_addoption, pytest_configure
from .runtest import (
    pytest_runtest_logreport,
    pytest_runtest_makereport,
    pytest_runtest_setup,
    pytest_runtest_teardown,
)
from .session import (
    pytest_load_initial_conftests,
    pytest_sessionfinish,
    pytest_sessionstart,
    pytest_terminal_summary,
)

__all__ = [
    'pytest_addoption',
    'pytest_collection_modifyitems',
    'pytest_configure',
    'pytest_fixture_setup',
    'pytest_load_initial_conftests',
    'pytest_runtest_logreport',
    'pytest_runtest_makereport',
    'pytest_runtest_setup',
    'pytest_runtest_teardown',
    'pytest_sessionfinish',
    'pytest_sessionstart',
    'pytest_terminal_summary',
]
