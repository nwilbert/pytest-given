"""pytest-given plugin entry point — the hook surface pluggy registers.

`pytest11` points at this package, and pluggy collects hooks by scanning a
module's attributes for `pytest_*` names, so re-exporting them here is what
registers them; the `hookimpl` options ride on the function objects and survive
the re-export untouched.

The implementations live one module per concern, each one's docstring saying
which. `state` is the leaf every other module here reads.

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
