"""Grouping a parametrized test's cases into one scenario plus a parameter table.

The rule: the grouped step tree shows only what every case shares; anything that
varies becomes a column. See
docs/specs/2026-08-14-parametrized-case-columns-design.md.

`group` runs the pass over a `context.Group`, `checks` holds the six authoring
rules that keep the grouped tree honest, and `templatize` and `attachments` are
the two halves of the baseline walk, filling `columns`. `percase` is the other
exit: `group_parametrized=False` declines the merge, and each case leaves as a
scenario of its own.
"""

from .group import group_parametrized

__all__ = ['group_parametrized']
