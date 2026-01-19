from __future__ import annotations

from itertools import islice
from typing import Iterable

from oci_inventory.util.concurrency import parallel_map_ordered_iter


def test_parallel_map_ordered_iter_batches_generator() -> None:
    consumed: list[int] = []

    def gen() -> Iterable[int]:
        for i in range(5):
            consumed.append(i)
            yield i

    results = list(islice(parallel_map_ordered_iter(lambda x: x, gen(), max_workers=1, batch_size=2), 2))

    assert results == [0, 1]
    assert consumed == [0, 1]


def test_parallel_map_ordered_iter_preserves_order() -> None:
    results = list(parallel_map_ordered_iter(lambda x: x * 2, range(6), max_workers=2, batch_size=2))

    assert results == [0, 2, 4, 6, 8, 10]
