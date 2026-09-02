"""Grouping a parametrized test's cases into one scenario plus a parameter table.

The rule: the grouped step tree shows only what every case shares; anything
that varies becomes a column. See
docs/specs/2026-08-14-parametrized-case-columns-design.md.
"""

from .group import group_parametrized

__all__ = ['group_parametrized']
