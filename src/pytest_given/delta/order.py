"""The one order rule for cases, scenarios and glossary terms."""

from collections.abc import Mapping, Sequence


def interleaved[T](
    after: Sequence[T], before: Sequence[T], paired: Mapping[T, T]
) -> list[tuple[T | None, T | None]]:
    """Rows in the after order, as (before, after) — not the argument order.
    `paired` maps a before item to its after partner.

    A before-only item follows the item that preceded it on the before side, or
    that item's partner when it has one, and leads the list without a predecessor.
    """
    partner_of = {partner: item for item, partner in paired.items()}
    trailing: dict[T | None, list[T]] = {}
    anchor: T | None = None
    for item in before:
        if item in paired:
            anchor = paired[item]
        else:
            trailing.setdefault(anchor, []).append(item)

    rows: list[tuple[T | None, T | None]] = [
        (item, None) for item in trailing.get(None, ())
    ]
    for item in after:
        rows.append((partner_of.get(item), item))
        rows.extend((follower, None) for follower in trailing.get(item, ()))
    return rows
