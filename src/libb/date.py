"""TODO: rename last -> end, first -> beg."""

import calendar
import contextlib
import datetime
import logging
import os
import re
import time
import warnings
from collections import namedtuple
from typing import List, Optional, Tuple, Type, Union

import libb_date
import numpy as np
import pandas as pd
import pendulum
from dateutil import parser

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
    'offset_from_beg_of_month',
    'offset_from_end_of_month',
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
    'DateRange',
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
DateRange = libb_date.DateRange
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
    thedate = thedate or today()
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
    for thedate in get_dates(since=begdate, until=enddate, business=False):
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
    return time.mktime(d.timetuple())


def rfc3339(d: datetime.datetime):
    """
    >>> rfc3339('Fri, 31 Oct 2014 10:55:00')
    '2014-10-31T10:55:00+00:00'
    """
    return to_datetime(d).isoformat()


@expect_date
def first_of_year(thedate=None, tz=LCL) -> Date:
    """Does not need an arg, same with other funcs (`last_of_year`,
    `previous_eom`, &c.)

    >>> first_of_year()==datetime.date(now().year, 1, 1)
    True
    >>> first_of_year(datetime.date(2012, 12, 31))==datetime.date(2012, 1, 1)
    True
    """
    return Date((thedate or today()).year, 1, 1)


@expect_date
def last_of_year(thedate=None, tz=LCL):
    return Date((thedate or today()).year, 12, 31)


# rename previous_last_of_month (reame business_day to business)
@expect_date
def previous_eom(
    thedate=None, business=False, entity: Type[NYSE] = NYSE
) -> Date:
    """Previous EOM

    >>> previous_eom(datetime.date(2021, 5, 30))
    Date(2021, 4, 30)
    """
    thedate = thedate or today()
    if business:
        return previous_business_day(first_of_month(thedate))
    return first_of_month(thedate).subtract(days=1)


@expect_date
def first_of_month(
    thedate=None, business=False, entity: Type[NYSE] = NYSE
) -> Date:
    thedate = thedate or today()
    begdate = Date(thedate.year, thedate.month, 1)
    if business:
        return business_date(begdate, or_next=True, entity=entity)
    return begdate


@expect_date
def previous_first_of_month(
    thedate=None, business=False, entity: Type[NYSE] = NYSE
) -> Date:
    """Previous first of month

    >>> previous_first_of_month(datetime.date(2021, 6, 15))
    Date(2021, 5, 1)
    """
    thedate = thedate or today()
    return first_of_month(previous_eom(thedate, business, entity=entity),
                          business, entity=entity)


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
    thedate = thedate or today()
    offset_date = thedate.end_of('month')
    if business:
        return business_date(offset_date, or_next=False, entity=entity)
    return offset_date


@expect_date
def is_first_of_month(thedate=None, business=False, entity: Type[NYSE] = NYSE) -> bool:
    thedate = thedate or today()
    return first_of_month(thedate, business, entity=entity) == thedate


@expect_date
def is_last_of_month(thedate=None, business=False, entity: Type[NYSE] = NYSE) -> bool:
    thedate = thedate or today()
    return last_of_month(thedate, business, entity=entity) == thedate


@expect_date
def offset_from_end_of_month(
    thedate, window=-1, business=False, entity: Type[NYSE] = NYSE
):
    """For last_business_day_of_month -> last_of_month ?"""
    raise NotImplementedError('Not Implemented')


@expect_date
def offset_from_beg_of_month(
    thedate, window=1, business=False, entity: Type[NYSE] = NYSE
):
    raise NotImplementedError('Not Implemented')


@expect_date
def third_wednesday(year, month):
    """Third Wednesday date of a given month/year

    >>> third_wednesday(2022, 6)
    Date(2022, 6, 15)
    >>> third_wednesday(2023, 3)
    Date(2023, 3, 15)
    >>> third_wednesday(2022, 12)
    Date(2022, 12, 21)
    >>> third_wednesday(2023, 6)
    Date(2023, 6, 21)
    """
    third = Date(year, month, 15)  # lowest 3rd day
    w = third.weekday()
    if w != WeekDay.WEDNESDAY:
        third = third.replace(day=(15 + (WeekDay.WEDNESDAY - w) % 7))
    return third


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
    thedate = thedate or today()
    numdays = abs(numdays)
    while numdays > 0:
        try:
            thedate = thedate.subtract(days=1)
        except OverflowError:
            return thedate
        if is_business_day(thedate, entity):
            numdays -= 1
    return thedate


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
    thedate = thedate or today()
    numdays = abs(numdays)
    while numdays > 0:
        try:
            thedate = thedate.add(days=1)
        except OverflowError:
            return thedate
        if is_business_day(thedate, entity):
            numdays -= 1
    return thedate


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
    thedate = thedate or today()
    while window != 0:
        try:
            if business:
                if window > 0:
                    thedate = next_business_day(thedate, 1, entity)
                if window < 0:
                    thedate = previous_business_day(thedate, 1, entity)
            else:
                if window > 0:
                    thedate = thedate.add(days=1)
                if window < 0:
                    thedate = thedate.subtract(days=1)
        except OverflowError:
            return thedate
        if window > 0:
            window -= 1
        else:
            window += 1
    return thedate


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
    thedate = thedate or today()
    if thedate.weekday() == WeekDay.MONDAY:
        date_offset = thedate
    else:
        date_offset = thedate.previous(WeekDay.MONDAY)
    if business:
        return business_date(date_offset, or_next=True, entity=entity)
    return date_offset


@expect_date
def is_first_of_week(thedate=None, business=False, entity: Type[NYSE] = NYSE) -> bool:
    """First of week function.

    Business := if it's a holiday, get next business date
    """
    thedate = thedate or today()
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
    thedate = thedate or today()
    date_offset = thedate.end_of('week')
    if business:
        return business_date(date_offset, or_next=False, entity=entity)
    return date_offset


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
    d = thedate.start_of('month')
    if d.weekday() == day_obj.get(weekday):
        return d
    return d.next(day_obj.get(weekday))


@expect_date
def get_last_weekday_of_month(thedate, weekday='SU'):
    """Like `get_first`, but for the last X of month"""
    d = thedate.end_of('month')
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
    thenext = (thedate or today()).add(days=window)
    return first_of_month(thenext)


@expect_date
def next_last_date_of_week(thedate=None, business=False, entity: Type[NYSE] = NYSE):
    """Get next end of week (Friday).

    >>> next_last_date_of_week(datetime.datetime(2018, 10, 8, 0, 0, 0))
    Date(2018, 10, 12)
    >>> next_last_date_of_week(datetime.date(2018, 10, 12))
    Date(2018, 10, 19)
    """
    thedate = thedate or today()
    offset = thedate.next(WeekDay.FRIDAY)
    if business:
        return business_date(thedate, or_next=False, entity=entity)
    return offset


@expect_date
def next_relative_date_of_week_by_day(thedate, day='MO'):
    """Get next relative day of week by relativedelta code

    >>> next_relative_date_of_week_by_day(datetime.datetime(2020, 5, 18), 'SU')
    Date(2020, 5, 24)
    >>> next_relative_date_of_week_by_day(datetime.datetime(2020, 5, 24), 'SU')
    Date(2020, 5, 24)
    """
    if thedate.weekday() == day_obj.get(day):
        return thedate
    return thedate.next(day_obj.get(day))


@expect_date
def business_date(thedate=None, or_next=True, tz=LCL, entity: Type[NYSE] = NYSE):
    """Return the date if it is a business day, else the next business date.

    9/1 is Saturday, 9/3 is Labor Day
    >>> business_date(datetime.date(2018, 9, 1))
    Date(2018, 9, 4)
    """
    thedate = thedate or today()
    if is_business_day(thedate, entity):
        return thedate
    if or_next:
        return next_business_day(thedate, entity=entity)
    return previous_business_day(thedate, entity=entity)


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
    thedate = thedate or today()
    dnum = thedate.weekday()
    if dnum in {WeekDay.SATURDAY, WeekDay.SUNDAY}:
        return thedate.subtract(days=dnum - 4)
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
    window = abs(int(window))
    assert until or since, 'Since or until is required'
    if until and not since:
        if business:
            since = offset_date(until, -window, entity)
        else:
            since = until.subtract(days=window)
    elif since and not until:
        if business:
            until = offset_date(since, window, entity)
        else:
            until = since.add(days=window)
    assert since <= until, 'Since date must be earlier or equal to Until date'
    thedate = since
    while thedate <= until:
        if business:
            if is_business_day(thedate, entity=entity):
                yield thedate
        else:
            yield thedate
        thedate = thedate.add(days=1)


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
    return 4 * days_between(begdate, enddate or today()) / 365.0


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
    year = thedate.year
    q1_start, q1_end = Date(year, 1, 1), Date(year, 3, 31)
    q2_start, q2_end = Date(year, 4, 1), Date(year, 6, 30)
    q3_start, q3_end = Date(year, 7, 1), Date(year, 9, 30)
    q4_start, q4_end = Date(year, 10, 1), Date(year, 12, 31)

    if q1_start <= thedate <= q1_end:
        if end:
            return q1_end
        return q1_start

    if q2_start <= thedate <= q2_end:
        if end:
            return q2_end
        return q2_start

    if q3_start <= thedate <= q3_end:
        if end:
            return q3_end
        return q3_start

    if q4_start <= thedate <= q4_end:
        if end:
            return q4_end
        return q4_start


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
    return get_quarter_date(get_quarter_date(thedate, end=False).subtract(days=1), end=end)


@expect_date
def get_eom_dates(begdate, enddate) -> List[Date]:
    """Return a list of eom dates between and inclusive of begdate and enddate.

    >>> get_eom_dates(datetime.date(2018, 1, 5), datetime.date(2018, 4, 5))
    [Date(2018, 1, 31), Date(2018, 2, 28), Date(2018, 3, 31), Date(2018, 4, 30)]
    """
    assert begdate <= enddate
    interval = pendulum.interval(last_of_month(begdate), last_of_month(enddate))
    return list(interval.range('months'))


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

    def _lookback(years=0, months=0, days=0):
        _offset = thedate.subtract(years=years, months=months, days=days)
        return business_date(_offset, or_next=False)

    return {
        'last': _lookback(days=1),
        'week': _lookback(days=7),
        'month': _lookback(months=1),
        'quarter': _lookback(months=3),
        'year': _lookback(years=1),
    }.get(lookback)


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
    >>> to_date('6/23') == datetime.date(now().year, 6, 23)
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

    dd-mon-yy
    >>> to_date('23-May-12')
    Date(2012, 5, 23)

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

    >>> to_date('March') == datetime.date(now().year, 3, now().day)
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

    def date_for_symbol(s):
        if s == 'N':
            return today()
        if s == 'T':
            return today()
        if s == 'Y':
            return today().subtract(days=1)
        if s == 'P':
            return previous_business_day()
        if s == 'M':
            return previous_eom()

    def year(m):
        try:
            yy = int(m.group('y'))
            if yy < 100:
                yy += 2000
        except IndexError:
            logger.warning('Using default this year')
            yy = today().year
        return yy

    if not s:
        if raise_err:
            raise ValueError('Empty value')
        return

    if isinstance(s, (np.datetime64, pd.Timestamp)):
        s = to_datetime(s)
    if isinstance(s, datetime.datetime):
        if any([s.hour, s.minute, s.second, s.microsecond]):
            logger.debug('Forced datetime with non-zero time to date')
        return pendulum.instance(s).date()
    if isinstance(s, datetime.date):
        return pendulum.instance(s)
    if not isinstance(s, str):
        raise TypeError(f'Invalid type for date column: {s.__class__}')

    # always use the format if specified
    if fmt:
        try:
            return Date(*time.strptime(s, fmt)[:3])
        except ValueError:
            logger.debug('Format string passed to strptime failed')

    # handle special symbolic values: T, Y-2, P-1b
    if shortcodes:
        if m := re.match(DATEMATCH, s):
            d = date_for_symbol(m.group(1))
            if m.group(2):
                bus = m.group(2)[-1] == 'b'
                n = int(m.group(2).replace('b', ''))
                if bus:
                    d = offset_date(d, n, business=True)
                else:
                    d = d.add(days=n)
            return d
        if 'today' in s.lower():
            return today()
        if 'yester' in s.lower():
            return today().subtract(days=1)

    try:
        return pendulum.instance(parser.parse(s).date())
    except (TypeError, ValueError):
        logger.debug('Dateutil parser failed .. trying our custom parsers')

    # Regex with Month Numbers
    exps = (
        r'^(?P<m>\d{1,2})[/-](?P<d>\d{1,2})[/-](?P<y>\d{4})$',
        r'^(?P<m>\d{1,2})[/-](?P<d>\d{1,2})[/-](?P<y>\d{1,2})$',
        r'^(?P<m>\d{1,2})[/-](?P<d>\d{1,2})$',
        r'^(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})$',
        r'^(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})$',
    )
    for exp in exps:
        if m := re.match(exp, s):
            mm = int(m.group('m'))
            dd = int(m.group('d'))
            yy = year(m)
            return datetime.date(yy, mm, dd)

    # Regex with Month Name
    exps = (
        r'^(?P<d>\d{1,2})[- ](?P<m>[A-Za-z]{3,})[- ](?P<y>\d{4})$',
        r'^(?P<m>[A-Za-z]{3,})[- ](?P<d>\d{1,2})[- ](?P<y>\d{4})$',
        r'^(?P<m>[A-Za-z]{3,}) (?P<d>\d{1,2}), (?P<y>\d{4})$',
        r'^(?P<d>\d{2})(?P<m>[A-Z][a-z]{2})(?P<y>\d{4})$',
        r'^(?P<d>\d{1,2})-(?P<m>[A-Z][a-z][a-z])-(?P<y>\d{2})$',
        r'^(?P<d>\d{1,2})-(?P<m>[A-Z]{3})-(?P<y>\d{2})$',
    )
    for exp in exps:
        if m := re.match(exp, s):
            logger.debug('Matched month name')
            try:
                mm = MONTH_SHORTNAME[m.group('m').lower()[:3]]
            except KeyError:
                logger.debug('Month name did not match MONTH_SHORTNAME')
                continue
            dd = int(m.group('d'))
            yy = year(m)
            return datetime.date(yy, mm, dd)

    if raise_err:
        raise ValueError('Failed to parse date: %s', s)


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

    def seconds(m):
        try:
            return int(m.group('s'))
        except Exception:
            return 0

    def micros(m):
        try:
            return int(m.group('u'))
        except Exception:
            return 0

    def is_pm(m):
        try:
            return m.group('ap').lower() == 'pm'
        except Exception:
            return False

    if not s:
        if raise_err:
            raise ValueError('Empty value')
        return

    if isinstance(s, datetime.datetime):
        return pendulum.instance(s).time()

    if isinstance(s, datetime.time):
        return pendulum.instance(s)

    if fmt:
        return Time(*time.strptime(s, fmt)[3:6])

    exps = (
        r'^(?P<h>\d{1,2})[:.](?P<m>\d{2})([:.](?P<s>\d{2})([.,](?P<u>\d+))?)?( +(?P<ap>[aApP][mM]))?$',
        r'^(?P<h>\d{2})(?P<m>\d{2})((?P<s>\d{2})([.,](?P<u>\d+))?)?( +(?P<ap>[aApP][mM]))?$',
    )

    for exp in exps:
        if m := re.match(exp, s):
            hh = int(m.group('h'))
            mm = int(m.group('m'))
            ss = seconds(m)
            uu = micros(m)
            if is_pm(m) and hh < 12:
                hh += 12
            return Time(hh, mm, ss, uu * 1000).replace(tzinfo=UTC)
    logger.debug('Custom parsers failed, trying dateutil parser')

    try:
        return pendulum.instance(parser.parse(s)).time()
    except (TypeError, ValueError):
        pass

    if raise_err:
        raise ValueError('Failed to parse time: %s', s)


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
    if not s:
        if raise_err:
            raise ValueError('Empty value')
        return

    if isinstance(s, pd.Timestamp):
        return pendulum.instance(s.to_pydatetime())
    if isinstance(s, np.datetime64):
        dtm = np.datetime64(s, 'us').astype(datetime.datetime)
        return pendulum.instance(dtm)
    if isinstance(s, (int, float)):
        iso = datetime.datetime.fromtimestamp(s).isoformat()
        return to_datetime(iso).replace(tzinfo=LCL)
    if isinstance(s, datetime.datetime):
        return pendulum.instance(s)
    if isinstance(s, datetime.date):
        logger.debug('Forced date without time to datetime')
        return DateTime(s.year, s.month, s.day, tzinfo=LCL)
    if not isinstance(s, str):
        raise TypeError(f'Invalid type for date column: {s.__class__}')

    try:
        return pendulum.instance(parser.parse(s))
    except (TypeError, ValueError) as err:
        logger.debug('Dateutil parser failed .. trying our custom parsers')

    for delim in (' ', ':'):
        bits = s.split(delim, 1)
        if len(bits) == 2:
            d = to_date(bits[0])
            t = to_time(bits[1])
            if d is not None and t is not None:
                return DateTime.combine(d, t)

    d = to_date(s)
    if d is not None:
        return DateTime(d.year, d.month, d.day, 0, 0, 0)

    current = today()
    t = to_time(s)
    if t is not None:
        return DateTime.combine(current, t)

    if raise_err:
        raise ValueError('Invalid date-time format: ' + s)


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
    if begdate == enddate:
        return 0
    if not business:
        return (enddate - begdate).days
    if begdate < enddate:
        return len(list(get_dates(begdate, enddate, business=True, entity=entity))) - 1
    return -len(list(get_dates(enddate, begdate, business=True, entity=entity))) + 1


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

    def average_year_length(date1, date2):
        """Algorithm for average year length"""
        days = days_between(datetime.date(date1.year, 1, 1), datetime.date(date2.year + 1, 1, 1))
        years = (date2.year - date1.year) + 1
        return days / years

    def feb29_between(date1, date2):
        """Requires date2.year = (date1.year + 1) or date2.year = date1.year.

        Returns True if "Feb 29" is between the two dates (date1 may be Feb29).
        Two possibilities: date1.year is a leap year, and date1 <= Feb 29 y1,
        or date2.year is a leap year, and date2 > Feb 29 y2.
        """
        mar1_date1_year = datetime.date(date1.year, 3, 1)
        if calendar.isleap(date1.year) and (date1 < mar1_date1_year) and (date2 >= mar1_date1_year):
            return True
        mar1_date2_year = datetime.date(date2.year, 3, 1)
        if calendar.isleap(date2.year) and (date2 >= mar1_date2_year) and (date1 < mar1_date2_year):
            return True
        return False

    def appears_lte_one_year(date1, date2):
        """Returns True if date1 and date2 "appear" to be 1 year or less apart.

        This compares the values of year, month, and day directly to each other.
        Requires date1 <= date2; returns boolean. Used by basis 1.
        """
        if date1.year == date2.year:
            return True
        if ((date1.year + 1) == date2.year) and (
            (date1.month > date2.month) or ((date1.month == date2.month) and (date1.day >= date2.day))
        ):
            return True
        return False

    def basis0(date1, date2):
        # change day-of-month for purposes of calculation.
        date1day, date1month, date1year = date1.day, date1.month, date1.year
        date2day, date2month, date2year = date2.day, date2.month, date2.year
        if date1day == 31 and date2day == 31:
            date1day = 30
            date2day = 30
        elif date1day == 31:
            date1day = 30
        elif date1day == 30 and date2day == 31:
            date2day = 30
        # Note: If date2day==31, it STAYS 31 if date1day < 30.
        # Special fixes for February:
        elif date1month == 2 and date2month == 2 and is_last_of_month(date1) \
            and is_last_of_month(date2):
            date1day = 30  # Set the day values to be equal
            date2day = 30
        elif date1month == 2 and is_last_of_month(date1):
            date1day = 30  # "Illegal" Feb 30 date.
        daydiff360 = (date2day + date2month * 30 + date2year * 360) \
            - (date1day + date1month * 30 + date1year * 360)
        return daydiff360 / 360

    def basis1(date1, date2):
        if appears_lte_one_year(date1, date2):
            if date1.year == date2.year and calendar.isleap(date1.year):
                year_length = 366.0
            elif feb29_between(date1, date2) or (date2.month == 2 and date2.day == 29):
                year_length = 366.0
            else:
                year_length = 365.0
            return days_between(date1, date2) / year_length
        return days_between(date1, date2) / average_year_length(date1, date2)

    def basis2(date1, date2):
        return days_between(date1, date2) / 360.0

    def basis3(date1, date2):
        return days_between(date1, date2) / 365.0

    def basis4(date1, date2):
        # change day-of-month for purposes of calculation.
        date1day, date1month, date1year = date1.day, date1.month, date1.year
        date2day, date2month, date2year = date2.day, date2.month, date2.year
        if date1day == 31:
            date1day = 30
        if date2day == 31:
            date2day = 30
        # Remarkably, do NOT change Feb. 28 or 29 at ALL.
        daydiff360 = (date2day + date2month * 30 + date2year * 360) - \
            (date1day + date1month * 30 + date1year * 360)
        return daydiff360 / 360

    begdate = begdate or today()
    if enddate is None:
        return

    sign = 1
    if begdate > enddate:
        begdate, enddate = enddate, begdate
        sign = -1
    if begdate == enddate:
        return 0.0

    if basis == 0:
        return basis0(begdate, enddate) * sign
    if basis == 1:
        return basis1(begdate, enddate) * sign
    if basis == 2:
        return basis2(begdate, enddate) * sign
    if basis == 3:
        return basis3(begdate, enddate) * sign
    if basis == 4:
        return basis4(begdate, enddate) * sign

    raise ValueError('Basis range [0, 4]. Unknown basis {basis}.')


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
    if begdate:
        begdate = to_date(begdate)
    if enddate:
        enddate = to_date(enddate)

    if begdate and enddate:
        return begdate, enddate

    window = int(window) if window else 0

    if (not begdate and not enddate) or enddate:
        begdate = offset_date(enddate, -abs(window), business, entity)
    else:
        enddate = offset_date(begdate, abs(window), business, entity)

    return begdate, enddate


def to_string(thedate, fmt: str) -> str:
    """Format cleaner https://stackoverflow.com/a/2073189.

    >>> to_string(datetime.date(2022, 1, 5), '%-m/%-d/%Y')
    '1/5/2022'
    """
    return thedate.strftime(fmt.replace('%-', '%#') if os.name == 'nt' else fmt)


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
