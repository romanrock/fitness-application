import time

from apps.api.rate_limit import check_rate_limit


def test_rate_limit_blocks_after_limit():
    key = f"test:{time.time()}"
    for _ in range(5):
        assert check_rate_limit(key, limit=5, window_sec=1)
    assert not check_rate_limit(key, limit=5, window_sec=1)
