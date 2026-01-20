from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, as_completed, wait
from itertools import islice
from typing import Callable, Dict, Iterable, List, Sequence, Tuple, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def parallel_map_ordered(
    func: Callable[[T], R],
    items: Sequence[T] | Iterable[T],
    max_workers: int,
) -> List[R]:
    """
    Execute func over items in a thread pool and return results preserving the
    input order. Exceptions from workers are propagated.

    Uses a sliding window of futures so large iterables are not materialized.
    """
    results: List[R] = []
    iterator = iter(items)
    inflight: Dict[Future[R], int] = {}
    pending: Dict[int, R] = {}
    next_index = 0
    submitted = 0

    def _submit_next() -> bool:
        nonlocal submitted
        try:
            item = next(iterator)
        except StopIteration:
            return False
        inflight[executor.submit(func, item)] = submitted
        submitted += 1
        return True

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for _ in range(max_workers):
            if not _submit_next():
                break

        while inflight:
            done, _ = wait(inflight.keys(), return_when=FIRST_COMPLETED)
            for fut in done:
                idx = inflight.pop(fut)
                try:
                    pending[idx] = fut.result()
                except BaseException:
                    for pending_fut in inflight:
                        pending_fut.cancel()
                    raise
            for _ in range(len(done)):
                if not _submit_next():
                    break
            while next_index in pending:
                results.append(pending.pop(next_index))
                next_index += 1

    return results


def parallel_map_ordered_iter(
    func: Callable[[T], R],
    items: Sequence[T] | Iterable[T],
    max_workers: int,
    *,
    batch_size: int = 500,
) -> Iterable[R]:
    """
    Execute func over items in ordered batches, yielding results in input order.
    This bounds in-flight futures for large inputs.
    """
    if batch_size <= 0:
        batch_size = 1

    iterator = iter(items)
    while True:
        batch = list(islice(iterator, batch_size))
        if not batch:
            break
        for item in parallel_map_ordered(func, batch, max_workers=max_workers):
            yield item


def parallel_for_each(
    func: Callable[[T], None],
    items: Sequence[T] | Iterable[T],
    max_workers: int,
) -> None:
    """
    Execute func over items in a thread pool. Exceptions are propagated once all
    futures have completed to ensure work is not silently dropped.
    """
    if not isinstance(items, Sequence):
        items = list(items)
    errors: List[BaseException] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(func, item) for item in items]
        for fut in as_completed(futures):
            try:
                fut.result()
            except BaseException as e:  # collect and continue
                errors.append(e)
    if errors:
        # Raise first error to signal failure while preserving original traceback
        raise errors[0]
