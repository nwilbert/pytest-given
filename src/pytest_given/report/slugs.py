"""The URL-fragment slug each scenario is addressed by (`#scenario=<slug>`).

Its own module rather than another rollup in `aggregations`: naming a scenario
for a URL shares no input, no output and no vocabulary with those.
"""

import re
from collections import Counter

from ..model import NodeId, ReportData, node_base


def build_scenario_slug_index(report: ReportData) -> dict[NodeId, str]:
    """Map each scenario's node id to a short, readable slug for the URL
    fragment (`#scenario=<slug>`).

    The short form is `<file>/<func>`: the node id's basename with `.py` and a
    leading `test_` removed, the part after `::` with a leading `test_`
    removed, and the parametrization tail (`[water]`) dropped — a parametrized
    test usually groups into one scenario, so the tail is just noise.

    What was dropped comes back when it has to disambiguate, and only for the
    scenarios that need it, so the common case stays short and stable across
    re-runs. The tail returns first, for several scenarios out of one
    parametrized function; then directory components, innermost first, for two
    test files sharing a basename. Colliding scenarios escalate together, never
    greedily — which slug a scenario gets must not depend on the order the
    report lists them in.

    A pair that survives a full path (`a/test_x.py` beside `a/x.py`, both
    defining `test_y`) falls back to the node id, which is unique by
    construction.
    """
    bases = {s.id: _scenario_slug(s.id, with_tail=False) for s in report.scenarios}
    base_counts = Counter(bases.values())
    tails = {node_id: base_counts[base] > 1 for node_id, base in bases.items()}
    slugs = {
        s.id: _scenario_slug(s.id, with_tail=tails[s.id]) for s in report.scenarios
    }
    depth = 0
    while colliding := _colliding_ids(slugs):
        depth += 1
        moved = False
        for node_id in colliding:
            candidate = _scenario_slug(node_id, with_tail=tails[node_id], depth=depth)
            moved = moved or candidate != slugs[node_id]
            slugs[node_id] = candidate
        if not moved:
            # Every directory is already in the slug and the pair still reads
            # the same. Nothing shorter than the node id can separate them.
            slugs.update({node_id: node_id for node_id in colliding})
            break
    return slugs


def _colliding_ids(slugs: dict[NodeId, str]) -> list[NodeId]:
    counts = Counter(slugs.values())
    return [node_id for node_id, slug in slugs.items() if counts[slug] > 1]


# What actually breaks a `#scenario=<slug>` round trip, rather than every
# character a strict URI grammar would escape: `&` ends the value, `=`
# splits it, `+` decodes to a space, and `#` ends the fragment. Brackets
# and the rest of pytest's parametrize punctuation survive, so a slug
# still reads like the node id it came from.
_UNSAFE_IN_FRAGMENT = re.compile(r'[^A-Za-z0-9._~()\[\]!$\'*,;:@/-]+|[+&=#]')


def _scenario_slug(node_id: NodeId, *, with_tail: bool, depth: int = 0) -> str:
    file_part, _, func_part = node_id.partition('::')
    segments = file_part.split('/')
    basename = segments[-1].removesuffix('.py').removeprefix('test_')
    parents = segments[max(len(segments) - 1 - depth, 0) : -1]
    func = func_part.removeprefix('test_')
    if not with_tail:
        func = node_base(func)
    return '/'.join([*parents, basename, _fragment_safe(func)])


def _fragment_safe(text: str) -> str:
    """`text` with anything that would break the fragment folded to a `-`.

    The slug is addressed as `#scenario=<slug>` and the page parses the
    fragment with `URLSearchParams`, so a parametrize tail carrying `&` would
    truncate the value and one carrying `+` would decode to a space — either
    way the reverse map misses and the deep link silently does nothing. pytest
    keeps all three, plus `#` and spaces, in a node id.

    Folding can make two tails collide; the escalation loop above already
    handles that, down to the node-id fallback.
    """
    return _UNSAFE_IN_FRAGMENT.sub('-', text)
