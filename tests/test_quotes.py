import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from quotes import FRUGAL_QUOTES, EXCESS_QUOTES, pick_quote

def test_pools_have_enough_quotes():
    assert 30 <= len(FRUGAL_QUOTES) <= 50
    assert 30 <= len(EXCESS_QUOTES) <= 50

def test_pools_have_no_duplicates():
    assert len(set(FRUGAL_QUOTES)) == len(FRUGAL_QUOTES)
    assert len(set(EXCESS_QUOTES)) == len(EXCESS_QUOTES)

def test_quotes_are_text_philosopher_pairs():
    for quote, philosopher in FRUGAL_QUOTES + EXCESS_QUOTES:
        assert isinstance(quote, str) and len(quote) > 0
        assert isinstance(philosopher, str) and len(philosopher) > 0

def test_pick_quote_returns_from_pool():
    for _ in range(20):
        result = pick_quote(FRUGAL_QUOTES)
        assert result in FRUGAL_QUOTES
