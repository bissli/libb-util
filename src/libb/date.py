import contextlib
import datetime
import logging
import warnings
from collections import namedtuple
from typing import List, Optional, Tuple, Type, Union

import numpy as np
import pandas as pd
from libb import patch_module

__date = patch_module('date', '__date')
import date as libb_date

warnings.simplefilter(action='ignore', category=DeprecationWarning)

logger = logging.getLogger(__name__)

__all__ = [
    'EST',
    'GMT',
    'LCL',
    'UTC',
    'business_date',
    'business_hours',
    'business_open',
    'create_ics',
    'date_range',
    'days_between',
    'days_overlap',
    'epoch',
    'first_of_month',
    'first_of_week',
    'first_of_year',
    'get_dates',
    'get_eom_dates',
    'get_first_weekday_of_month',
    'get_last_weekday_of_month',
    'get_previous_quarter_date',
    'get_quarter_date',
    'is_business_day',
    'is_business_day_range',
    'is_first_of_month',
    'is_first_of_week',
    'is_last_of_month',
    'is_last_of_week',
    'isoweek',
    'last_of_month',
    'last_of_week',
    'last_of_year',
    'lookback_date',
    'next_business_day',
    'next_first_of_month',
    'next_last_date_of_week',
    'next_relative_date_of_week_by_day',
    'now',
    'num_quarters',
    'offset_date',
    'previous_business_day',
    'previous_eom',
    'previous_first_of_month',
    'rfc3339',
    'third_wednesday',
    'to_date',
    'to_datetime',
    'to_string',
    'to_time',
    'today',
    'weekday_or_previous_friday',
    'years_between',
    # libb_date
    'timezone',
    'Date',
    'DateTime',
    'Interval',
    'Time',
    'WeekDay',
    'expect_native_timezone',
    'expect_utc_timezone',
    'prefer_native_timezone',
    'prefer_utc_timezone',
    'expect_date',
    'expect_datetime',
    'Entity',
    'NYSE',
    ]

LCL = libb_date.LCL
Date = libb_date.Date
Interval = libb_date.Interval
DateTime = libb_date.DateTime
Time = libb_date.Time
WeekDay = libb_date.WeekDay
now = libb_date.now
today = libb_date.today
timezone = libb_date.timezone
expect_native_timezone = libb_date.expect_native_timezone
expect_utc_timezone = libb_date.expect_utc_timezone
prefer_native_timezone = libb_date.prefer_native_timezone
prefer_utc_timezone = libb_date.prefer_utc_timezone
expect_date = libb_date.expect_date
expect_datetime = libb_date.expect_datetime

Entity = libb_date.Entity
NYSE = libb_date.NYSE

UTC = timezone('UTC')
GMT = timezone('GMT')
EST = timezone('US/Eastern')


day_obj = {
    'MO': WeekDay.MONDAY,
    'TU': WeekDay.TUESDAY,
    'WE': WeekDay.WEDNESDAY,
    'TH': WeekDay.THURSDAY,
    'FR': WeekDay.FRIDAY,
    'SA': WeekDay.SATURDAY,
    'SU': WeekDay.SUNDAY
}


@expect_date
def isoweek(thedate: datetime.date):
    """Week number 1-52 following ISO week-numbering

    Standard weeks
    >>> isoweek(datetime.date(2023, 1, 2))
    1
    >>> isoweek(datetime.date(2023, 4, 27))
    17
    >>> isoweek(datetime.date(2023, 12, 31))
    52

    Belongs to week of previous year
    >>> isoweek(datetime.date(2023, 1, 1))
    52
    """
    with contextlib.suppress(Exception):
        return thedate.isocalendar()[1]


Range = namedtuple('Range', ['start', 'end'])


def days_overlap(range_one, range_two, days=False):
    """Test by how much two date ranges overlap
    if `days=True`, we return an actual day count,
    otherwise we just return if it overlaps True/False
    poached from Raymond Hettinger http://stackoverflow.com/a/9044111

    >>> date1 = datetime.date(2016, 3, 1)
    >>> date2 = datetime.date(2016, 3, 2)
    >>> date3 = datetime.date(2016, 3, 29)
    >>> date4 = datetime.date(2016, 3, 30)

    >>> assert days_overlap((date1, date3), (date2, date4))
    >>> assert days_overlap((date2, date4), (date1, date3))
    >>> assert not days_overlap((date1, date2), (date3, date4))

    >>> assert days_overlap((date1, date4), (date1, date4))
    >>> assert days_overlap((date1, date4), (date2, date3))
    >>> days_overlap((date1, date4), (date1, date4), True)
    30

    >>> assert days_overlap((date2, date3), (date1, date4))
    >>> days_overlap((date2, date3), (date1, date4), True)
    28

    >>> assert not days_overlap((date3, date4), (date1, date2))
    >>> days_overlap((date3, date4), (date1, date2), True)
    -26
    """
    r1 = Range(*range_one)
    r2 = Range(*range_two)
    latest_start = max(r1.start, r2.start)
    earliest_end = min(r1.end, r2.end)
    overlap = (earliest_end - latest_start).days + 1
    if days:
        return overlap
    return overlap >= 0


def create_ics(begdate, enddate, summary, location):
    """Create a simple .ics file per RFC 5545 guidelines."""

    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//hacksw/handcal//NONSGML v1.0//EN
BEGIN:VEVENT
DTSTART;TZID=America/New_York:{begdate:%Y%m%dT%H%M%S}
DTEND;TZID=America/New_York:{enddate:%Y%m%dT%H%M%S}
SUMMARY:{summary}
LOCATION:{location}
END:VEVENT
END:VCALENDAR
    """


@expect_date
def is_business_day(thedate=None, entity: Type[NYSE] = NYSE) -> bool:
    """Is business date.

    >>> thedate = datetime.date(2021, 4, 19) # Monday
    >>> is_business_day(thedate)
    True
    >>> thedate = datetime.date(2021, 4, 17) # Saturday
    >>> is_business_day(thedate)
    False
    >>> thedate = datetime.date(2021, 1, 18) # MLK Day
    >>> is_business_day(thedate)
    False
    >>> thedate = datetime.date(2021, 11, 25) # Thanksgiving
    >>> is_business_day(thedate)
    False
    >>> thedate = datetime.date(2021, 11, 26) # Day after ^
    >>> is_business_day(thedate)
    True
    """
    thedate = Date(thedate)
    return thedate in entity.business_days()


@expect_date
def is_business_day_range(begdate, enddate, entity: Type[NYSE] = NYSE) -> List[bool]:
    """Is business date range

    >>> list(is_business_day_range(datetime.date(2018, 11, 19), datetime.date(2018, 11, 25)))
    [True, True, True, False, True, False, False]
    >>> list(is_business_day_range(datetime.date(2021, 11, 22), datetime.date(2021, 11, 28)))
    [True, True, True, False, True, False, False]
    """
    assert begdate <= enddate
    for thedate in Interval(begdate, enddate).series():
        yield is_business_day(thedate, entity)


@expect_date
def business_open(thedate, entity: Type[NYSE] = NYSE) -> bool:
    """Business open

    >>> thedate = datetime.date(2021, 4, 19) # Monday
    >>> business_open(thedate, NYSE)
    True
    >>> thedate = datetime.date(2021, 4, 17) # Saturday
    >>> business_open(thedate, NYSE)
    False
    >>> thedate = datetime.date(2021, 1, 18) # MLK Day
    >>> business_open(thedate, NYSE)
    False
    """
    return is_business_day(thedate, entity)


@expect_date
def business_hours(thedate, entity: Type[NYSE] = NYSE):
    """Business hours

    >>> thedate = datetime.date(2023, 1, 5)
    >>> business_hours(thedate, NYSE)
    (... 9, 30, ... 16, 0, ...)

    >>> thedate = datetime.date(2023, 7, 3)
    >>> business_hours(thedate, NYSE)
    (... 9, 30, ... 13, 0, ...)

    >>> thedate = datetime.date(2023, 11, 24)
    >>> business_hours(thedate, NYSE)
    (... 9, 30, ... 13, 0, ...)

    >>> thedate = datetime.date(2023, 11, 25)
    >>> business_hours(thedate, NYSE)
    (None, None)
    """
    return entity.business_hours(thedate, thedate).get(thedate, (None, None))


# Date functions


def epoch(d: datetime.datetime):
    """Translate a datetime object into unix seconds since epoch"""
    return DateTime(d).epoch()


def rfc3339(d: datetime.datetime):
    """
    >>> rfc3339('Fri, 31 Oct 2014 10:55:00')
    '2014-10-31T10:55:00+00:00'
    """
    return DateTime.parse(d).rfc3339()


@expect_date
def first_of_year(thedate=None, tz=LCL) -> Date:
    """Does not need an arg, same with other funcs (`last_of_year`,
    `previous_eom`, &c.)

    >>> first_of_year()==datetime.date(today().year, 1, 1)
    True
    >>> first_of_year(datetime.date(2012, 12, 31))==datetime.date(2012, 1, 1)
    True
    """
    return Date(thedate).first_of('year')


@expect_date
def last_of_year(thedate=None, tz=LCL):
    return Date(thedate).last_of('year')


# rename previous_last_of_month (reame business_day to business)
@expect_date
def previous_eom(
    thedate=None, business=False, entity: Type[NYSE] = NYSE) -> Date:
    """Previous EOM

    >>> previous_eom(datetime.date(2021, 5, 30))
    Date(2021, 4, 30)
    """
    if business:
        return Date(thedate).start_of('month').business().subtract(days=1)
    return Date(thedate).start_of('month').subtract(days=1)


@expect_date
def first_of_month(
    thedate=None, business=False, entity: Type[NYSE] = NYSE
) -> Date:
    if business:
        return Date(thedate).start_of('month').business().add()
    return Date(thedate).start_of('month')


@expect_date
def previous_first_of_month(
    thedate=None, business=False, entity: Type[NYSE] = NYSE
) -> Date:
    """Previous first of month

    >>> previous_first_of_month(datetime.date(2021, 6, 15))
    Date(2021, 5, 1)
    """
    d = Date(thedate).start_of('month').subtract(days=1).start_of('month')
    if business:
        return d.business().add()
    return d


@expect_date
def last_of_month(
    thedate=None, business: bool = False, entity: Type[NYSE] = NYSE
) -> Date:
    """Last of month

    >>> last_of_month(datetime.date(2021, 6, 15))
    Date(2021, 6, 30)
    >>> last_of_month(datetime.date(2021, 6, 30))
    Date(2021, 6, 30)
    >>> last_of_month(datetime.date(2023, 4, 30), True) # Sunday -> Friday
    Date(2023, 4, 28)
    """
    if business:
        return Date(thedate).end_of('month').business().subtract()
    return Date(thedate).end_of('month')


@expect_date
def is_first_of_month(thedate=None, business=False, entity: Type[NYSE] = NYSE) -> bool:
    thedate = Date(thedate)
    return first_of_month(thedate, business, entity=entity) == thedate


@expect_date
def is_last_of_month(thedate=None, business=False, entity: Type[NYSE] = NYSE) -> bool:
    thedate = Date(thedate)
    return last_of_month(thedate, business, entity=entity) == thedate


@expect_date
def third_wednesday(year, month):
    """Third Wednesday date of a given month/year

    >>> third_wednesday(2022, 6)
    Date(2022, 6, 15)
    >>> third_wednesday(2023, 3)
    Date(2023, 3, 15)
    >>> third_wednesday(2022, 12)
    Date(2022, 12, 21)
    >>> d = third_wednesday(2023, 6)
    >>> d
    Date(2023, 6, 21)
    >>> assert hasattr(d, '_business')
    """
    third = Date(year, month, 15)  # lowest 3rd day
    w = third.weekday()
    if w != WeekDay.WEDNESDAY:
        third = third.replace(day=(15 + (WeekDay.WEDNESDAY - w) % 7))
    return Date(third)


@expect_date
def previous_business_day(
    thedate=None, numdays=1, entity: Type[NYSE] = NYSE
) -> Date:
    """Previous business days at least N days prior
    - numdays are business days

    Closed on 12/5/2018 due to George H.W. Bush's death
    >>> previous_business_day(datetime.date(2018, 12, 7), 5)
    Date(2018, 11, 29)
    >>> previous_business_day(datetime.date(2021, 11, 24), 5)
    Date(2021, 11, 17)
    """
    return Date(thedate).business().subtract(days=numdays)


@expect_date
def next_business_day(
    thedate=None, numdays=1, entity: Type[NYSE] = NYSE
) -> Date:
    """Next one business day

    Closed on 12/5/2018 due to George H.W. Bush's death
    >>> i, thedate = 5, datetime.date(2018, 11, 29)
    >>> while i > 0:
    ...     thedate = next_business_day(thedate)
    ...     i -= 1
    >>> thedate
    Date(2018, 12, 7)

    >>> i, thedate = 5, datetime.date(2021, 11, 17)
    >>> while i > 0:
    ...     thedate = next_business_day(thedate)
    ...     i -= 1
    >>> thedate
    Date(2021, 11, 24)

    >>> next_business_day(datetime.date(9999, 12, 31))
    Date(9999, 12, 31)
    """
    return Date(thedate).business().add(days=numdays)


@expect_date
def offset_date(
    thedate=None, window=0, business=False, entity: Type[NYSE] = NYSE
) -> Date:
    """Offset thedate by N calendar or business days.

    In one week (from next_business_day doctests)
    >>> offset_date(datetime.date(2018, 11, 29), 5, True)
    Date(2018, 12, 7)
    >>> offset_date(datetime.date(2021, 11, 17), 5, True)
    Date(2021, 11, 24)

    One week ago (from next_business_day doctests)
    >>> offset_date(datetime.date(2018, 12, 7), -5, True)
    Date(2018, 11, 29)
    >>> offset_date(datetime.date(2021, 11, 24), -7, False)
    Date(2021, 11, 17)
    >>> offset_date(datetime.date(2018, 12, 7), -5, True)
    Date(2018, 11, 29)
    >>> offset_date(datetime.date(2021, 11, 24), -7, False)
    Date(2021, 11, 17)

    0 offset returns same date
    >>> offset_date(datetime.date(2018, 12, 7), 0, True)
    Date(2018, 12, 7)
    >>> offset_date(datetime.date(2021, 11, 24), 0, False)
    Date(2021, 11, 24)
    """
    if business:
        return Date(thedate).business().add(days=window)
    return Date(thedate).add(days=window)


@expect_date
def first_of_week(
    thedate=None, business=False, entity: Type[NYSE] = NYSE
) -> Date:
    """First of week function (Monday unless not a holiday).

    Regular Monday
    >>> first_of_week(datetime.date(2023, 4, 24))
    Date(2023, 4, 24)

    Regular Sunday
    >>> first_of_week(datetime.date(2023, 4, 30))
    Date(2023, 4, 24)

    Memorial day 5/25
    >>> first_of_week(datetime.date(2020, 5, 25))
    Date(2020, 5, 25)
    >>> first_of_week(datetime.date(2020, 5, 27))
    Date(2020, 5, 25)
    >>> first_of_week(datetime.date(2020, 5, 26), business=True)
    Date(2020, 5, 26)
    """
    if business:
        return Date(thedate).start_of('week').business().add()
    return Date(thedate).start_of('week')


@expect_date
def is_first_of_week(thedate=None, business=False, entity: Type[NYSE] = NYSE) -> bool:
    """First of week function.

    Business := if it's a holiday, get next business date
    """
    thedate = Date(thedate)
    return first_of_week(thedate, business) == thedate


@expect_date
def last_of_week(
    thedate=None, business=False, entity: Type[NYSE] = NYSE
) -> Date:
    """Get the last date of the week.

    Regular Monday
    >>> last_of_week(datetime.date(2023, 4, 24))
    Date(2023, 4, 30)

    Regular Sunday
    >>> last_of_week(datetime.date(2023, 4, 30))
    Date(2023, 4, 30)

    Good Friday
    >>> last_of_week(datetime.date(2020, 4, 12))
    Date(2020, 4, 12)
    >>> last_of_week(datetime.date(2020, 4, 10))
    Date(2020, 4, 12)
    >>> last_of_week(datetime.date(2020, 4, 10), business=True)
    Date(2020, 4, 9)
    >>> last_of_week(datetime.date(2020, 4, 9), business=True)
    Date(2020, 4, 9)
    """
    if business:
        return Date(thedate).end_of('week').business().subtract()
    return Date(thedate).end_of('week')


@expect_date
def is_last_of_week(thedate=None, business=False, entity: Type[NYSE] = NYSE) -> bool:
    return last_of_week(thedate, business, entity) == thedate


@expect_date
def get_first_weekday_of_month(thedate, weekday='MO'):
    """Get first X of the month

    >>> get_first_weekday_of_month(datetime.date(2014, 8, 1), 'WE')
    Date(2014, 8, 6)
    >>> get_first_weekday_of_month(datetime.date(2014, 7, 31), 'WE')
    Date(2014, 7, 2)
    >>> get_first_weekday_of_month(datetime.date(2014, 8, 6), 'WE')
    Date(2014, 8, 6)
    """
    d = Date(thedate).start_of('month')
    if d.weekday() == day_obj.get(weekday):
        return d
    return d.next(day_obj.get(weekday))


@expect_date
def get_last_weekday_of_month(thedate, weekday='SU'):
    """Like `get_first`, but for the last X of month"""
    d = Date(thedate).end_of('month')
    if d.weekday() == day_obj.get(weekday):
        return d
    return d.previous(day_obj.get(weekday))


@expect_date
def next_first_of_month(thedate=None, window=1, snap=True, tz=LCL):
    """Get next first of month
    if 'snap', round up to next month when date is past mid-month

    basic scenario
    >>> next_first_of_month(datetime.date(2015, 1, 1))
    Date(2015, 1, 1)
    >>> next_first_of_month(datetime.date(2015, 1, 31))
    Date(2015, 2, 1)

    advanced scenario
    >>> next_first_of_month(datetime.date(2015, 1, 1), 15)
    Date(2015, 1, 1)
    >>> next_first_of_month(datetime.date(2015, 1, 1), 16)
    Date(2015, 2, 1)
    >>> next_first_of_month(datetime.date(2015, 1, 1), 15, snap=False)
    Date(2015, 1, 1)
    """
    window = window + 15 if snap else window
    thenext = Date(thedate).add(days=window)
    return first_of_month(thenext)


@expect_date
def next_last_date_of_week(thedate=None, business=False, entity: Type[NYSE] = NYSE):
    """Get next end of week (Friday).

    >>> next_last_date_of_week(datetime.datetime(2018, 10, 8, 0, 0, 0))
    Date(2018, 10, 12)
    >>> next_last_date_of_week(datetime.date(2018, 10, 12))
    Date(2018, 10, 19)
    """
    if business:
        return Date(thedate).business().next(WeekDay.FRIDAY)
    return Date(thedate).next(WeekDay.FRIDAY)


@expect_date
def next_relative_date_of_week_by_day(thedate, day='MO'):
    """Get next relative day of week by relativedelta code

    >>> next_relative_date_of_week_by_day(datetime.datetime(2020, 5, 18), 'SU')
    Date(2020, 5, 24)
    >>> next_relative_date_of_week_by_day(datetime.datetime(2020, 5, 24), 'SU')
    Date(2020, 5, 24)
    """
    if thedate.weekday() == day_obj.get(day):
        return Date(thedate)
    return Date(thedate).next(day_obj.get(day))


@expect_date
def business_date(thedate=None, or_next=True, tz=LCL, entity: Type[NYSE] = NYSE):
    """Return the date if it is a business day, else the next business date.

    9/1 is Saturday, 9/3 is Labor Day
    >>> business_date(datetime.date(2018, 9, 1))
    Date(2018, 9, 4)
    """
    if or_next:
        return Date(thedate).business().add()
    return Date(thedate).business().subtract()


@expect_date
def weekday_or_previous_friday(thedate=None, tz=LCL):
    """Return the date if it is a weekday, else previous Friday

    >>> weekday_or_previous_friday(datetime.date(2019, 10, 6)) # Sunday
    Date(2019, 10, 4)
    >>> weekday_or_previous_friday(datetime.date(2019, 10, 5)) # Saturday
    Date(2019, 10, 4)
    >>> weekday_or_previous_friday(datetime.date(2019, 10, 4)) # Friday
    Date(2019, 10, 4)
    >>> weekday_or_previous_friday(datetime.date(2019, 10, 3)) # Thursday
    Date(2019, 10, 3)
    """
    thedate = Date(thedate)
    dnum = thedate.weekday()
    if dnum in {WeekDay.SATURDAY, WeekDay.SUNDAY}:
        return thedate.previous(WeekDay.FRIDAY)
    return thedate


@expect_date
def get_dates(since=None, until=None, window=0, business=False, entity: Type[NYSE] = NYSE):
    """Get a range of datetime.date objects.

    give the function since and until wherever possible (more explicit)
    else pass in a window to back out since or until
    - Window gives window=N additional days. So `until`-`window`=1
    defaults to include ALL days (not just business days)

    >>> next(get_dates(since=datetime.date(2014,7,16), until=datetime.date(2014,7,16)))
    Date(2014, 7, 16)
    >>> next(get_dates(since=datetime.date(2014,7,12), until=datetime.date(2014,7,16)))
    Date(2014, 7, 12)
    >>> len(list(get_dates(since=datetime.date(2014,7,12), until=datetime.date(2014,7,16))))
    5
    >>> len(list(get_dates(since=datetime.date(2014,7,12), window=4)))
    5
    >>> len(list(get_dates(until=datetime.date(2014,7,16), window=4)))
    5

    Weekend and a holiday
    >>> len(list(get_dates(since=datetime.date(2014,7,3), until=datetime.date(2014,7,5), business=True)))
    1
    >>> len(list(get_dates(since=datetime.date(2014,7,17), until=datetime.date(2014,7,16))))
    Traceback (most recent call last):
    ...
    AssertionError: Since date must be earlier or equal to Until date

    since != business day and want business days
    1/[3,10]/2015 is a Saturday, 1/7/2015 is a Wednesday
    >>> len(list(get_dates(since=datetime.date(2015,1,3), until=datetime.date(2015,1,7), business=True)))
    3
    >>> len(list(get_dates(since=datetime.date(2015,1,3), window=3, business=True)))
    3
    >>> len(list(get_dates(since=datetime.date(2015,1,3), until=datetime.date(2015,1,10), business=True)))
    5
    >>> len(list(get_dates(since=datetime.date(2015,1,3), window=5, business=True)))
    5
    """
    if business:
        return Interval(since, until).business().series(window)
    return Interval(since, until).series(window)


@expect_date
def num_quarters(begdate, enddate=None, tz=LCL):
    """Return the number of quarters between two dates
    TODO: good enough implementation; refine rules to be heuristically precise

    >>> round(num_quarters(datetime.date(2020, 1, 1), datetime.date(2020, 2, 16)), 2)
    0.5
    >>> round(num_quarters(datetime.date(2020, 1, 1), datetime.date(2020, 4, 1)), 2)
    1.0
    >>> round(num_quarters(datetime.date(2020, 1, 1), datetime.date(2020, 7, 1)), 2)
    1.99
    >>> round(num_quarters(datetime.date(2020, 1, 1), datetime.date(2020, 8, 1)), 2)
    2.33
    """
    return Interval(begdate, enddate).quarters()


@expect_date
def get_quarter_date(thedate, end=True) -> Date:
    """Return the quarter start or quarter end of a given date.

    >>> get_quarter_date(datetime.date(2013, 11, 5))
    Date(2013, 12, 31)
    >>> get_quarter_date(datetime.date(2013, 11, 5), end=False)
    Date(2013, 10, 1)
    >>> get_quarter_date(datetime.date(1999, 1, 19), end=False)
    Date(1999, 1, 1)
    >>> get_quarter_date(datetime.date(2016, 3, 31))
    Date(2016, 3, 31)
    """
    if end:
        return Date(thedate).last_of('quarter')
    return Date(thedate).first_of('quarter')


@expect_date
def get_previous_quarter_date(thedate, end=True) -> Date:
    """Return the previous quarter start or quarter end of a given date.

    >>> get_previous_quarter_date(datetime.date(2013, 11, 5))
    Date(2013, 9, 30)
    >>> get_previous_quarter_date(datetime.date(2013, 11, 5), end=False)
    Date(2013, 7, 1)
    >>> get_previous_quarter_date(datetime.date(1999, 1, 19), end=False)
    Date(1998, 10, 1)
    >>> get_previous_quarter_date(datetime.date(2016, 3, 31))
    Date(2015, 12, 31)

    """
    if end:
        return Date(thedate).first_of('quarter').subtract(days=1).last_of('quarter')
    return Date(thedate).first_of('quarter').subtract(days=1).first_of('quarter')


@expect_date
def get_eom_dates(begdate, enddate) -> List[Date]:
    """Return a list of eom dates between and inclusive of begdate and enddate.

    >>> get_eom_dates(datetime.date(2018, 1, 5), datetime.date(2018, 4, 5))
    [Date(2018, 1, 31), Date(2018, 2, 28), Date(2018, 3, 31), Date(2018, 4, 30)]
    """
    assert begdate <= enddate
    return Interval(begdate, enddate).end_of_series('month')


@expect_date
def lookback_date(thedate, lookback='last') -> Date:
    """Date back based on lookback string, ie last, week, month.

    >>> lookback_date(datetime.date(2018, 12, 7), 'last')
    Date(2018, 12, 6)
    >>> lookback_date(datetime.date(2018, 12, 7), 'week')
    Date(2018, 11, 30)
    >>> lookback_date(datetime.date(2018, 12, 7), 'month')
    Date(2018, 11, 7)
    """
    return Date(thedate).lookback(lookback)


# === Parsing Strings into Dates and Times ===


MONTH_SHORTNAME = {
    'jan': 1,
    'feb': 2,
    'mar': 3,
    'apr': 4,
    'may': 5,
    'jun': 6,
    'jul': 7,
    'aug': 8,
    'sep': 9,
    'oct': 10,
    'nov': 11,
    'dec': 12,
}

DATEMATCH = r'^(N|T|Y|P|M)([-+]\d+b?)?$'


def to_date(
    s: Union[str, datetime.date, datetime.datetime, pd.Timestamp, np.datetime64],
    fmt: str = None,
    raise_err: bool = False,
    shortcodes: bool = True
) -> Optional[datetime.date]:
    """Convert a string to a date handling many different formats.

    previous business day accessed with 'P'
    >>> to_date('P')==previous_business_day()
    True
    >>> to_date('T-3b')==offset_date(window=-3, business=True)
    True
    >>> to_date('M')==previous_eom()
    True

    m[/-]d[/-]yyyy  6-23-2006
    >>> to_date('6-23-2006')
    Date(2006, 6, 23)

    m[/-]d[/-]yy    6/23/06
    >>> to_date('6/23/06')
    Date(2006, 6, 23)

    m[/-]d          6/23
    >>> to_date('6/23') == datetime.date(today().year, 6, 23)
    True

    yyyy-mm-dd      2006-6-23
    >>> to_date('2006-6-23')
    Date(2006, 6, 23)

    yyyymmdd        20060623
    >>> to_date('20060623')
    Date(2006, 6, 23)

    dd-mon-yyyy     23-JUN-2006
    >>> to_date('23-JUN-2006')
    Date(2006, 6, 23)

    mon-dd-yyyy     JUN-23-2006
    >>> to_date('20 Jan 2009')
    Date(2009, 1, 20)

    month dd, yyyy  June 23, 2006
    >>> to_date('June 23, 2006')
    Date(2006, 6, 23)

    ddmonyyyy
    >>> to_date('23May2012')
    Date(2012, 5, 23)

    >>> to_date('Oct. 24, 2007', fmt='%b. %d, %Y')
    Date(2007, 10, 24)

    >>> to_date('Yesterday') == today().subtract(days=1)
    True
    >>> to_date('TODAY') == today()
    True
    >>> to_date('Jan. 13, 2014')
    Date(2014, 1, 13)

    >>> to_date('March') == datetime.date(today().year, 3, today().day)
    True

    >>> to_date(np.datetime64('2000-01', 'D'))
    Date(2000, 1, 1)

    only raise error when we explicitly say so
    >>> to_date('bad date') is None
    True
    >>> to_date('bad date', raise_err=True)
    Traceback (most recent call last):
    ...
    ValueError: Failed to parse date: bad date
    """
    return Date.parse(s, fmt, raise_err, shortcodes)


@prefer_utc_timezone
def to_time(s, fmt=None, raise_err=False):
    """Convert a string to a time handling many formats::

        handle many time formats:
        hh[:.]mm
        hh[:.]mm am/pm
        hh[:.]mm[:.]ss
        hh[:.]mm[:.]ss[.,]uuu am/pm
        hhmmss[.,]uuu
        hhmmss[.,]uuu am/pm

    >>> to_time('9:30')
    Time(9, 30, 0, tzinfo=Timezone('UTC'))
    >>> to_time('9:30:15')
    Time(9, 30, 15, tzinfo=Timezone('UTC'))
    >>> to_time('9:30:15.751')
    Time(9, 30, 15, 751000, tzinfo=Timezone('UTC'))
    >>> to_time('9:30 AM')
    Time(9, 30, 0, tzinfo=Timezone('UTC'))
    >>> to_time('9:30 pm')
    Time(21, 30, 0, tzinfo=Timezone('UTC'))
    >>> to_time('9:30:15.751 PM')
    Time(21, 30, 15, 751000, tzinfo=Timezone('UTC'))
    >>> to_time('0930')  # dateutil treats this as a date, careful!!
    Time(9, 30, 0, tzinfo=Timezone('UTC'))
    >>> to_time('093015')
    Time(9, 30, 15, tzinfo=Timezone('UTC'))
    >>> to_time('093015,751')
    Time(9, 30, 15, 751000, tzinfo=Timezone('UTC'))
    >>> to_time('0930 pm')
    Time(21, 30, 0, tzinfo=Timezone('UTC'))
    >>> to_time('093015,751 PM')
    Time(21, 30, 15, 751000, tzinfo=Timezone('UTC'))
    """
    return Time.parse(s, fmt, raise_err)


def to_datetime(
    s: Union[str, datetime.date, datetime.datetime, pd.Timestamp, np.datetime64],
    raise_err=False,
) -> Optional[datetime.date]:
    """Thin layer on dateutil parser and our custom `to_date` and `to_time`

    Assume UTC, convert to EST
    >>> this_est1 = to_datetime('Fri, 31 Oct 2014 18:55:00').in_timezone(EST)
    >>> this_est1
    DateTime(2014, 10, 31, 14, 55, 0, tzinfo=Timezone('US/Eastern'))

    This is actually 18:55 UTC with -4 hours applied = EST
    >>> this_est2 = to_datetime('Fri, 31 Oct 2014 14:55:00 -0400')
    >>> this_est2
    DateTime(2014, 10, 31, 14, 55, 0, tzinfo=FixedTimezone(-14400, name="-04:00"))

    UTC time technically equals GMT
    >>> this_utc = to_datetime('Fri, 31 Oct 2014 18:55:00 GMT')
    >>> this_utc
    DateTime(2014, 10, 31, 18, 55, 0, tzinfo=Timezone('UTC'))

    We can freely compare time zones
    >>> this_est1==this_est2==this_utc
    True

    Convert date to datetime (will use native time zone)
    >>> to_datetime(datetime.date(2000, 1, 1))
    DateTime(2000, 1, 1, 0, 0, 0, tzinfo=Timezone('...'))

    Format tests
    >>> epoch(to_datetime(1707856982))
    1707856982.0
    >>> to_datetime('Jan 29  2010')
    DateTime(2010, 1, 29, 0, 0, 0, tzinfo=Timezone('UTC'))
    >>> to_datetime(np.datetime64('2000-01', 'D'))
    DateTime(2000, 1, 1, 0, 0, 0, tzinfo=Timezone('UTC'))
    >>> _ = to_datetime('Sep 27 17:11')
    >>> _.month, _.day, _.hour, _.minute
    (9, 27, 17, 11)
    """
    return DateTime.parse(s, raise_err)


@expect_date
def days_between(
    begdate, enddate, business: bool = False, entity: Type[NYSE] = NYSE
) -> int:
    """Return days between (begdate, enddate] or negative (enddate, begdate].

    >>> days_between(to_date('2018/9/6'), to_date('2018/9/10'))
    4
    >>> days_between(to_date('2018/9/10'), to_date('2018/9/6'))
    -4
    >>> days_between(to_date('2018/9/6'), to_date('2018/9/10'), True)
    2
    >>> days_between(to_date('2018/9/10'), to_date('2018/9/6'), True)
    -2
    """
    if business:
        return Interval(begdate, enddate).business().days()
    return Interval(begdate, enddate).days()


@expect_date
def years_between(begdate=None, enddate=None, basis: int = 0):
    """Years with Fractions (matches Excel YEARFRAC)

    Adapted from https://web.archive.org/web/20200915094905/https://dwheeler.com/yearfrac/calc_yearfrac.py

    Basis:
    0 = US (NASD) 30/360
    1 = Actual/actual
    2 = Actual/360
    3 = Actual/365
    4 = European 30/360

    >>> begdate = datetime.datetime(1978, 2, 28)
    >>> enddate = datetime.datetime(2020, 5, 17)

    Tested Against Excel
    >>> "{:.4f}".format(years_between(begdate, enddate, 0))
    '42.2139'
    >>> '{:.4f}'.format(years_between(begdate, enddate, 1))
    '42.2142'
    >>> '{:.4f}'.format(years_between(begdate, enddate, 2))
    '42.8306'
    >>> '{:.4f}'.format(years_between(begdate, enddate, 3))
    '42.2438'
    >>> '{:.4f}'.format(years_between(begdate, enddate, 4))
    '42.2194'
    >>> '{:.4f}'.format(years_between(enddate, begdate, 4))
    '-42.2194'

    Excel has a known leap year bug when year == 1900 (=YEARFRAC("1900-1-1", "1900-12-1", 1) -> 0.9178)
    The bug originated from Lotus 1-2-3, and was purposely implemented in Excel for the purpose of backward compatibility.
    >>> begdate = datetime.datetime(1900, 1, 1)
    >>> enddate = datetime.datetime(1900, 12, 1)
    >>> '{:.4f}'.format(years_between(begdate, enddate, 4))
    '0.9167'
    """
    return Interval(begdate, enddate).years(basis)


# === Parsing Range of Dates ===


@expect_date
def date_range(
    begdate=None, enddate=None, window=None, business=True, entity: Type[NYSE] = NYSE
) -> Tuple[datetime.date, datetime.date]:
    """Set date ranges based on begdate, enddate and window.

    The combinations are as follows:

      beg end num    action
      --- --- ---    ---------------------
       -   -   -     Error, underspecified
      set set set    Error, overspecified
      set set  -
      set  -   -     end=max date
       -  set  -     beg=min date
       -   -  set    end=max date, beg=end - num
      set  -  set    end=beg + num
       -  set set    beg=end - num

    >>> date_range(Date(2014, 4, 3), None, 3)
    (Date(2014, 4, 3), Date(2014, 4, 8))
    >>> date_range(None, Date(2014, 7, 27), 20, business=False)
    (Date(2014, 7, 7), Date(2014, 7, 27))
    >>> date_range(None, Date(2014, 7, 27), 20)
    (Date(2014, 6, 27), Date(2014, 7, 27))
    """
    if business:
        return Interval(begdate, enddate).business().range(window)
    return Interval(begdate, enddate).range(window)


def to_string(thedate, fmt: str) -> str:
    """Format cleaner https://stackoverflow.com/a/2073189.

    >>> to_string(datetime.date(2022, 1, 5), '%-m/%-d/%Y')
    '1/5/2022'
    """
    return Date.to_string(thedate, fmt)


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
