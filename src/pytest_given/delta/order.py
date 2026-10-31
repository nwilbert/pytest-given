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
    after_index = {item: index for index, item in enumerate(after)}
    partner_of = {partner: item for item, partner in paired.items()}
    # A slot is a row a before-only item can follow: an after row (by index), a
    # before-only row (by index), or the top.
    following: dict[tuple[str, int], int] = {}
    for index, item in enumerate(before):
        if item in paired:
            continue
        if index == 0:
            following[('top', 0)] = index
        elif before[index - 1] in paired:
            following[('after', after_index[paired[before[index - 1]]])] = index
        else:
            following[('before', index - 1)] = index

    rows: list[tuple[T | None, T | None]] = []

    def follow(slot: tuple[str, int]) -> None:
        while slot in following:
            index = following[slot]
            rows.append((before[index], None))
            slot = ('before', index)

    follow(('top', 0))
    for index, item in enumerate(after):
        rows.append((partner_of.get(item), item))
        follow(('after', index))
    return rows
