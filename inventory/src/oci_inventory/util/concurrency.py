from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, List, Sequence, Tuple, TypeVar

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

    For large iterables, prefer passing a Sequence to avoid materializing twice.
    """
    # Ensure we can index to preserve order deterministically
    if not isinstance(items, Sequence):
        items = list(items)

    results: List[R] = [None] * len(items)  # type: ignore[list-item]
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures: List[Tuple[int, Future[R]]] = []
        for idx, item in enumerate(items):
            futures.append((idx, executor.submit(func, item)))

        for idx, fut in futures:
            results[idx] = fut.result()

    return results


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