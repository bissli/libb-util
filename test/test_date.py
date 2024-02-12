import datetime

import pytest
from asserts import assert_equal
from libb.date import offset_date


def test_offset_date():
    thedate = datetime.date(2018, 9, 12)
    assert_equal(thedate, offset_date(thedate, window=0, business=True))
    assert_equal(thedate, offset_date(thedate, window=0, business=False))
    assert_equal(thedate, offset_date(thedate, window=0, business=False))
    assert_equal(thedate, offset_date(thedate, window=0))

    offone = datetime.date(2018, 9, 11)
    assert_equal(offone, offset_date(thedate, window=-1, business=True))
    assert_equal(offone, offset_date(thedate, window=-1, business=False))
    assert_equal(offone, offset_date(thedate, window=-1, business=False))
    assert_equal(offone, offset_date(thedate, window=-1))

    plusone = datetime.date(2018, 9, 13)
    assert_equal(plusone, offset_date(thedate, window=1, business=True))
    assert_equal(plusone, offset_date(thedate, window=1, business=False))
    assert_equal(plusone, offset_date(thedate, window=1, business=False))
    assert_equal(plusone, offset_date(thedate, window=1))

    bdate = datetime.date(2019, 3, 1)
    plusone = datetime.date(2019, 3, 2)
    bplusone = datetime.date(2019, 3, 4)
    assert_equal(bplusone, offset_date(bdate, window=1, business=True))
    assert_equal(plusone, offset_date(bdate, window=1, business=False))
    assert_equal(plusone, offset_date(bdate, window=1, business=False))
    assert_equal(plusone, offset_date(bdate, window=1))


if __name__ == '__main__':
    pytest.main([__file__])
