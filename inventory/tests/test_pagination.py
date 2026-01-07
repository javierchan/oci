from __future__ import annotations

from oci_inventory.util.pagination import paginate


def test_paginate_yields_all_items_and_pages_in_order() -> None:
    calls = []
    pages = {
        None: (["a", "b"], "next"),
        "next": (["c"], None),
    }

    def fetch(page):
        calls.append(page)
        return pages[page]

    items = list(paginate(fetch))
    assert items == ["a", "b", "c"]
    assert calls == [None, "next"]
