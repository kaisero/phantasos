from prisma_browser.extras import paginate


class _Page:
    def __init__(self, data, cursor):
        self.data = data
        self.page_info = type("PI", (), {"has_next_page": cursor is not None, "cursor": cursor})()


def test_paginate_follows_cursor():
    calls = []
    def list_method(**kw):
        calls.append(kw.get("cursor"))
        return _Page(["a", "b"], "C1") if kw.get("cursor") is None else _Page(["c"], None)
    assert list(paginate(list_method, limit=2)) == ["a", "b", "c"]
    assert calls == [None, "C1"]


def test_paginate_empty():
    assert list(paginate(lambda **k: _Page([], None))) == []
