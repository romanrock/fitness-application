import time

from apps.api.cache import clear, get_or_set


def test_cache_ttl():
    clear()
    counter = {"n": 0}

    def compute():
        counter["n"] += 1
        return counter["n"]

    first = get_or_set("key", 1, None, compute)
    second = get_or_set("key", 1, None, compute)
    assert first == second == 1

    time.sleep(1.1)
    third = get_or_set("key", 1, None, compute)
    assert third == 2
