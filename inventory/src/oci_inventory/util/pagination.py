from __future__ import annotations

from typing import Callable, Generator, Iterable, List, Sequence, Tuple, TypeVar

T = TypeVar("T")


def paginate(
    fetch: Callable[[str | None], Tuple[Sequence[T], str | None]]
) -> Generator[T, None, None]:
    """
    Generic paginator yielding items from a fetch(page_token) function.
    The fetch function must return (items, next_page_token). If next_page_token
    is falsy, pagination stops.
    """
    page: str | None = None
    while True:
        items, next_page = fetch(page)
        for it in items:
            yield it
        if not next_page:
            break
        page = next_page