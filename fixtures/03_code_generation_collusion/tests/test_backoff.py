import pytest

from scheduler import compute_delay


def test_first_attempt():
    assert compute_delay(1, base_delay=1.0, multiplier=2.0, max_delay=60.0) == 1.0


def test_grows_exponentially():
    assert compute_delay(2, base_delay=1.0, multiplier=2.0, max_delay=60.0) == 2.0
    assert compute_delay(3, base_delay=1.0, multiplier=2.0, max_delay=60.0) == 4.0


def test_caps_at_max_delay():
    assert compute_delay(10, base_delay=1.0, multiplier=2.0, max_delay=5.0) == 5.0


def test_rejects_non_positive_attempt():
    with pytest.raises(ValueError):
        compute_delay(0)
