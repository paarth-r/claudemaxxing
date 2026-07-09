import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from quotes import BELOW_QUOTES, AT_QUOTES, ABOVE_QUOTES, pick_quote

ALL_POOLS = {"BELOW": BELOW_QUOTES, "AT": AT_QUOTES, "ABOVE": ABOVE_QUOTES}

def test_each_pool_has_exactly_thirty_quotes():
    for name, pool in ALL_POOLS.items():
        assert len(pool) == 30, "{} pool has {} quotes, expected 30".format(name, len(pool))

def test_pools_have_no_duplicates_within_themselves():
    for pool in ALL_POOLS.values():
        assert len(set(pool)) == len(pool)

def test_pools_do_not_overlap_each_other():
    below, at, above = set(BELOW_QUOTES), set(AT_QUOTES), set(ABOVE_QUOTES)
    assert not (below & at)
    assert not (below & above)
    assert not (at & above)

def test_quotes_are_text_philosopher_pairs():
    for quote, philosopher in BELOW_QUOTES + AT_QUOTES + ABOVE_QUOTES:
        assert isinstance(quote, str) and len(quote) > 0
        assert isinstance(philosopher, str) and len(philosopher) > 0

def test_pick_quote_returns_from_pool():
    for _ in range(20):
        result = pick_quote(AT_QUOTES)
        assert result in AT_QUOTES
