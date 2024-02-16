"""TODO: rename last -> end, first -> beg."""

import calendar
import contextlib
import datetime
import inspect
import logging
import os
import re
import time
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from functools import lru_cache, partial, wraps
from typing import Callable, Dict, List, Optional, Set, Tuple, Type, Union
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
import tzlocal
from dateutil import parser, relativedelta
from libb import config
from libb.util import suppresswarning

logger = logging.getLogger(__name__)


LCL = ZoneInfo(config.TZ or tzlocal.get_localzone_name())
UTC = ZoneInfo('UTC')
GMT = ZoneInfo('GMT')
EST = ZoneInfo('US/Eastern')


MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY = range(7)


def expect(func, typ: Type[datetime.date], exclkw: bool = False) -> Callable:
    """Decorator to force input type of date/datetime inputs"""

    def caller_entity(func):
        """Helper to get current entity from function"""
        # general frame args inspect
        frame = inspect.currentframe()
        outer_frames = inspect.getouterframes(frame)
        caller_frame = outer_frames[1][0]
        args = inspect.getargvalues(caller_frame)
        # find our entity
        param = inspect.signature(func).parameters.get('entity')
        default = param.default if param else NYSE
        entity = args.locals['kwargs'].get('entity', default)
        return entity

    @wraps(func)
    def wrapper(*args, **kwargs):
        args = list(args)
        entity = None
        for i, arg in enumerate(args):
            if isinstance(arg, (datetime.date, datetime.datetime)):
                if typ == datetime.datetime:
                    entity = entity or caller_entity(func)
                    args[i] = to_datetime(args[i], tzhint=entity.tz)
                    continue
                args[i] = to_date(args[i])
        if not exclkw:
            for k, v in kwargs.items():
                if isinstance(v, (datetime.date, datetime.datetime)):
                    if typ == datetime.datetime:
                        entity = entity or caller_entity(func)
                        kwargs[k] = to_datetime(v, tzhint=entity.tz)
                        continue
                    kwargs[k] = to_date(v)
        return func(*args, **kwargs)

    return wrapper


expect_date = partial(expect, typ=datetime.date)
expect_datetime = partial(expect, typ=datetime.datetime)


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


class Entity(metaclass=ABCMeta):
    """ABC for named entity types"""

    tz = UTC

    @staticmethod
    @abstractmethod
    def business_days(begdate: datetime.date, enddate: datetime.date):
        """Returns all business days over a range"""

    @staticmethod
    @abstractmethod
    def market_hours(begdate: datetime.date, enddate: datetime.date):
        """Returns all market open and close times over a range"""

    @staticmethod
    @abstractmethod
    def holidays(begdate: datetime.date, enddate: datetime.date):
        """Returns only holidays over a range"""


class NYSE(Entity):
    """New York Stock Exchange"""

    BEGDATE = datetime.date(1900, 1, 1)
    ENDDATE = datetime.date(2200, 1, 1)
    calendar = mcal.get_calendar('NYSE')

    tz = EST

    @staticmethod
    @lru_cache
    def business_days(begdate=BEGDATE, enddate=ENDDATE) -> Set[datetime.date]:
        return {d.date() for d in NYSE.calendar.valid_days(begdate, enddate)}

    @staticmethod
    @lru_cache
    @suppresswarning
    def market_hours(begdate=BEGDATE, enddate=ENDDATE) -> Dict:
        df = NYSE.calendar.schedule(begdate, enddate, tz=EST)
        open_close = [(o.to_pydatetime(), c.to_pydatetime())
                      for o, c in zip(df.market_open, df.market_close)]
        return dict(zip(df.index.date, open_close))

    @staticmethod
    @lru_cache
    def holidays(begdate=BEGDATE, enddate=ENDDATE) -> Set:
        return set(NYSE.calendar.holidays().holidays)


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
    thedate = thedate or today(tz=entity.tz)
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
def market_open(thedate, entity: Type[NYSE] = NYSE) -> bool:
    """Market open

    >>> thedate = datetime.date(2021, 4, 19) # Monday
    >>> market_open(thedate, NYSE)
    True
    >>> thedate = datetime.date(2021, 4, 17) # Saturday
    >>> market_open(thedate, NYSE)
    False
    >>> thedate = datetime.date(2021, 1, 18) # MLK Day
    >>> market_open(thedate, NYSE)
    False
    """
    return is_business_day(thedate, entity)


@expect_date
def market_hours(thedate, entity: Type[NYSE] = NYSE):
    """Market hours

    >>> thedate = datetime.date(2023, 1, 5)
    >>> market_hours(thedate, NYSE)
    (... 9, 30, ... 16, 0, ...)

    >>> thedate = datetime.date(2023, 7, 3)
    >>> market_hours(thedate, NYSE)
    (... 9, 30, ... 13, 0, ...)

    >>> thedate = datetime.date(2023, 11, 24)
    >>> market_hours(thedate, NYSE)
    (... 9, 30, ... 13, 0, ...)

    >>> thedate = datetime.date(2023, 11, 25)
    >>> market_hours(thedate, NYSE)
    (None, None)
    """
    return entity.market_hours(thedate, thedate).get(thedate, (None, None))


# Date functions


def now(tz=EST, current: Optional[datetime.datetime] = None):
    """Localizing now function"""
    if current is None:
        return datetime.datetime.now(tz=tz)
    # for testing
    assert isinstance(current, datetime.datetime)
    with contextlib.suppress(Exception):
        return current.astimezone(tz=tz)


def today(tz=EST, current: Optional[datetime.datetime] = None):
    """Localizing today function"""
    current = current or now(tz=tz)
    return datetime.date(current.year, current.month, current.day)


def epoch(obj):
    """Translate a datetime object into unix seconds since epoch"""
    return time.mktime(obj.timetuple())


def rfc3339(d: datetime.datetime):
    """
    >>> rfc3339('Fri, 31 Oct 2014 10:55:00')
    '2014-10-31T10:55:00-04:00'
    """
    return to_datetime(d, localize=EST).isoformat()


def first_of_year(thedate=None, tz=EST) -> datetime.date:
    """Does not need an arg, same with other funcs (`last_of_year`,
    `previous_eom`, &c.)

    >>> first_of_year()==datetime.date(today().year, 1, 1)
    True
    >>> first_of_year(datetime.date(2012, 12, 31))==datetime.date(2012, 1, 1)
    True
    """
    return datetime.date((thedate or today(tz=tz)).year, 1, 1)


def last_of_year(thedate=None, tz=EST):
    return datetime.date((thedate or today(tz=tz)).year, 12, 31)


# rename previous_last_of_month (reame business_day to business)
def previous_eom(
    thedate=None, business=False, entity: Type[NYSE] = NYSE
) -> datetime.date:
    """Previous EOM

    >>> previous_eom(datetime.date(2021, 5, 30))
    datetime.date(2021, 4, 30)
    """
    thedate = thedate or today(tz=entity.tz)
    if business:
        return previous_business_day(first_of_month(thedate))
    else:
        return first_of_month(thedate) + relativedelta.relativedelta(days=-1)


def first_of_month(
    thedate=None, business=False, entity: Type[NYSE] = NYSE
) -> datetime.date:
    thedate = thedate or today(tz=entity.tz)
    begdate = datetime.date(thedate.year, thedate.month, 1)
    if business:
        return business_date(begdate, or_next=True, entity=entity)
    return begdate


def previous_first_of_month(
    thedate=None, business=False, entity: Type[NYSE] = NYSE
) -> datetime.date:
    """Previous first of month

    >>> previous_first_of_month(datetime.date(2021, 6, 15))
    datetime.date(2021, 5, 1)
    """
    thedate = thedate or today(tz=entity.tz)
    return first_of_month(previous_eom(thedate, business, entity=entity),
                          business, entity=entity)


def last_of_month(
    thedate=None, business: bool = False, entity: Type[NYSE] = NYSE
) -> datetime.date:
    """Last of month

    >>> last_of_month(datetime.date(2021, 6, 15))
    datetime.date(2021, 6, 30)
    >>> last_of_month(datetime.date(2021, 6, 30))
    datetime.date(2021, 6, 30)
    >>> last_of_month(datetime.date(2023, 4, 30), True) # Sunday -> Friday
    datetime.date(2023, 4, 28)
    """
    thedate = thedate or today(tz=entity.tz)
    last_day = calendar.monthrange(thedate.year, thedate.month)[1]
    offset_date = datetime.date(thedate.year, thedate.month, last_day)
    if business:
        return business_date(offset_date, or_next=False, entity=entity)
    return offset_date


def is_first_of_month(thedate=None, business=False, entity: Type[NYSE] = NYSE) -> bool:
    thedate = thedate or today(tz=entity.tz)
    return first_of_month(thedate, business, entity=entity) == thedate


def is_last_of_month(thedate=None, business=False, entity: Type[NYSE] = NYSE) -> bool:
    thedate = thedate or today(tz=entity.tz)
    return last_of_month(thedate, business, entity=entity) == thedate


def offset_from_end_of_month(
    thedate, window=-1, business=False, entity: Type[NYSE] = NYSE
):
    """For last_business_day_of_month -> last_of_month ?"""
    raise NotImplementedError('Not Implemented')


def offset_from_beg_of_month(
    thedate, window=1, business=False, entity: Type[NYSE] = NYSE
):
    raise NotImplementedError('Not Implemented')


def third_wednesday(year, month):
    """Third Wednesday date of a given month/year

    >>> third_wednesday(2022, 6)
    datetime.date(2022, 6, 15)
    >>> third_wednesday(2023, 3)
    datetime.date(2023, 3, 15)
    >>> third_wednesday(2022, 12)
    datetime.date(2022, 12, 21)
    >>> third_wednesday(2023, 6)
    datetime.date(2023, 6, 21)
    """
    third = datetime.date(year, month, 15)  # lowest 3rd day
    w = third.weekday()
    if w != WEDNESDAY:
        third = third.replace(day=(15 + (WEDNESDAY - w) % 7))
    return third


@expect_date
def previous_business_day(
    thedate=None, numdays=1, entity: Type[NYSE] = NYSE
) -> datetime.date:
    """Previous business days at least N days prior
    - numdays are business days

    Closed on 12/5/2018 due to George H.W. Bush's death
    >>> previous_business_day(datetime.date(2018, 12, 7), 5)
    datetime.date(2018, 11, 29)
    >>> previous_business_day(datetime.date(2021, 11, 24), 5)
    datetime.date(2021, 11, 17)
    """
    thedate = thedate or today(tz=entity.tz)
    numdays = abs(numdays)
    while numdays > 0:
        try:
            thedate -= datetime.timedelta(days=1)
        except OverflowError:
            return thedate
        if is_business_day(thedate, entity):
            numdays -= 1
    return thedate


@expect_date
def next_business_day(
    thedate=None, numdays=1, entity: Type[NYSE] = NYSE
) -> datetime.date:
    """Next one business day

    Closed on 12/5/2018 due to George H.W. Bush's death
    >>> i, thedate = 5, datetime.date(2018, 11, 29)
    >>> while i > 0:
    ...     thedate = next_business_day(thedate)
    ...     i -= 1
    >>> thedate
    datetime.date(2018, 12, 7)

    >>> i, thedate = 5, datetime.date(2021, 11, 17)
    >>> while i > 0:
    ...     thedate = next_business_day(thedate)
    ...     i -= 1
    >>> thedate
    datetime.date(2021, 11, 24)

    >>> next_business_day(datetime.date(9999, 12, 31))
    datetime.date(9999, 12, 31)
    """
    thedate = thedate or today(tz=entity.tz)
    numdays = abs(numdays)
    while numdays > 0:
        try:
            thedate += datetime.timedelta(days=1)
        except OverflowError:
            return thedate
        if is_business_day(thedate, entity):
            numdays -= 1
    return thedate


def offset_date(
    thedate=None, window=0, business=False, entity: Type[NYSE] = NYSE
) -> datetime.date:
    """Offset thedate by N calendar or business days.

    In one week (from next_business_day doctests)
    >>> offset_date(datetime.date(2018, 11, 29), 5, True)
    datetime.date(2018, 12, 7)
    >>> offset_date(datetime.date(2021, 11, 17), 5, True)
    datetime.date(2021, 11, 24)

    One week ago (from next_business_day doctests)
    >>> offset_date(datetime.date(2018, 12, 7), -5, True)
    datetime.date(2018, 11, 29)
    >>> offset_date(datetime.date(2021, 11, 24), -7, False)
    datetime.date(2021, 11, 17)
    >>> offset_date(datetime.date(2018, 12, 7), -5, True)
    datetime.date(2018, 11, 29)
    >>> offset_date(datetime.date(2021, 11, 24), -7, False)
    datetime.date(2021, 11, 17)

    0 offset returns same date
    >>> offset_date(datetime.date(2018, 12, 7), 0, True)
    datetime.date(2018, 12, 7)
    >>> offset_date(datetime.date(2021, 11, 24), 0, False)
    datetime.date(2021, 11, 24)
    """
    thedate = thedate or today(tz=entity.tz)
    if window > 0:
        if business:
            offset_func = next_business_day
        else:
            offset_func = lambda: partial(relativedelta.relativedelta, days=1)
    if window < 0:
        if business:
            offset_func = previous_business_day
        else:
            offset_func = lambda: partial(relativedelta.relativedelta, days=-1)
    window = abs(window or 0)
    while window > 0:
        try:
            if business:
                thedate = offset_func(thedate, entity=entity)
            else:
                thedate += offset_func()()
        except OverflowError:
            return thedate
        window -= 1
    return thedate


@expect_date
def first_of_week(
    thedate=None, business=False, entity: Type[NYSE] = NYSE
) -> datetime.date:
    """First of week function (Monday unless not a holiday).

    Regular Monday
    >>> first_of_week(datetime.date(2023, 4, 24))
    datetime.date(2023, 4, 24)

    Regular Sunday
    >>> first_of_week(datetime.date(2023, 4, 30))
    datetime.date(2023, 4, 24)

    Memorial day 5/25
    >>> first_of_week(datetime.date(2020, 5, 25))
    datetime.date(2020, 5, 25)
    >>> first_of_week(datetime.date(2020, 5, 27))
    datetime.date(2020, 5, 25)
    >>> first_of_week(datetime.date(2020, 5, 26), business=True)
    datetime.date(2020, 5, 26)
    """
    thedate = thedate or today(tz=entity.tz)
    offset = relativedelta.relativedelta(weekday=relativedelta.MO(-1))
    date_offset = thedate + offset
    if business:
        return business_date(date_offset, or_next=True, entity=entity)
    return date_offset


@expect_date
def is_first_of_week(thedate=None, business=False, entity: Type[NYSE] = NYSE) -> bool:
    """First of week function.

    Business := if it's a holiday, get next business date
    """
    thedate = thedate or today(tz=entity.tz)
    return first_of_week(thedate, business) == thedate


@expect_date
def last_of_week(
    thedate=None, business=False, entity: Type[NYSE] = NYSE
) -> datetime.date:
    """Get the last date of the week.

    Regular Monday
    >>> last_of_week(datetime.date(2023, 4, 24))
    datetime.date(2023, 4, 30)

    Regular Sunday
    >>> last_of_week(datetime.date(2023, 4, 30))
    datetime.date(2023, 4, 30)

    Good Friday
    >>> last_of_week(datetime.date(2020, 4, 12))
    datetime.date(2020, 4, 12)
    >>> last_of_week(datetime.date(2020, 4, 10))
    datetime.date(2020, 4, 12)
    >>> last_of_week(datetime.date(2020, 4, 10), business=True)
    datetime.date(2020, 4, 9)
    >>> last_of_week(datetime.date(2020, 4, 9), business=True)
    datetime.date(2020, 4, 9)
    """
    thedate = thedate or today(tz=entity.tz)
    offset = relativedelta.relativedelta(weekday=relativedelta.SU(1))
    date_offset = thedate + offset
    if business:
        return business_date(date_offset, or_next=False, entity=entity)
    else:
        return date_offset


@expect_date
def is_last_of_week(thedate=None, business=False, entity: Type[NYSE] = NYSE) -> bool:
    return last_of_week(thedate, business, entity) == thedate


def get_first_weekday_of_month(thedate, weekday='MO'):
    """Get first X of the month

    >>> get_first_weekday_of_month(datetime.date(2014, 8, 1), 'WE')
    datetime.date(2014, 8, 6)
    >>> get_first_weekday_of_month(datetime.date(2014, 7, 31), 'WE')
    datetime.date(2014, 7, 2)
    >>> get_first_weekday_of_month(datetime.date(2014, 8, 6), 'WE')
    datetime.date(2014, 8, 6)
    """
    day_obj = getattr(relativedelta, weekday)
    return thedate + relativedelta.relativedelta(day=1, weekday=day_obj(1))


def get_last_weekday_of_month(thedate, weekday='SU'):
    """Like `get_first`, but for the last X of month"""
    day_obj = getattr(relativedelta, weekday)
    return thedate + relativedelta.relativedelta(day=31, weekday=day_obj(-1))


def next_first_of_month(thedate=None, window=1, snap=True, tz=EST):
    """Get next first of month
    if 'snap', round up to next month when date is past mid-month

    basic scenario
    >>> next_first_of_month(datetime.date(2015, 1, 1))
    datetime.date(2015, 1, 1)
    >>> next_first_of_month(datetime.date(2015, 1, 31))
    datetime.date(2015, 2, 1)

    advanced scenario
    >>> next_first_of_month(datetime.date(2015, 1, 1), 15)
    datetime.date(2015, 1, 1)
    >>> next_first_of_month(datetime.date(2015, 1, 1), 16)
    datetime.date(2015, 2, 1)
    >>> next_first_of_month(datetime.date(2015, 1, 1), 15, snap=False)
    datetime.date(2015, 1, 1)
    """
    window = window + 15 if snap else window
    thenext = (thedate or today(tz=tz)) + relativedelta.relativedelta(days=window)
    return first_of_month(thenext)


@expect_date
def next_last_date_of_week(thedate=None, business=False, entity: Type[NYSE] = NYSE):
    """Get next end of week (Friday).

    >>> next_last_date_of_week(datetime.datetime(2018, 10, 8, 0, 0, 0))
    datetime.date(2018, 10, 12)
    >>> next_last_date_of_week(datetime.date(2018, 10, 12))
    datetime.date(2018, 10, 19)
    """
    thedate = thedate or today(tz=entity.tz)
    offset = relativedelta.relativedelta(days=1, weekday=relativedelta.FR)
    if business:
        return business_date(thedate + offset, or_next=False, entity=entity)
    return thedate + offset


@expect_date
def next_relative_date_of_week_by_day(thedate, day='MO'):
    """Get next relative day of week by relativedelta code

    >>> next_relative_date_of_week_by_day(datetime.datetime(2020, 5, 18), 'SU')
    datetime.date(2020, 5, 24)
    >>> next_relative_date_of_week_by_day(datetime.datetime(2020, 5, 24), 'SU')
    datetime.date(2020, 5, 24)
    """
    _last_of_week = last_of_week(thedate)
    offset = relativedelta.relativedelta(days=1, weekday=getattr(relativedelta, day)(1))
    return min(thedate + offset, _last_of_week)


@expect_date
def business_date(thedate=None, or_next=True, tz=EST, entity: Type[NYSE] = NYSE):
    """Return the date if it is a business day, else the next business date.

    9/1 is Saturday, 9/3 is Labor Day
    >>> business_date(datetime.date(2018, 9, 1))
    datetime.date(2018, 9, 4)
    """
    thedate = thedate or today(tz=entity.tz)
    if is_business_day(thedate, entity):
        return thedate
    if or_next:
        return next_business_day(thedate, entity=entity)
    return previous_business_day(thedate, entity=entity)


@expect_date
def weekday_or_previous_friday(thedate=None, tz=EST):
    """Return the date if it is a weekday, else previous Friday

    >>> weekday_or_previous_friday(datetime.date(2019, 10, 6)) # Sunday
    datetime.date(2019, 10, 4)
    >>> weekday_or_previous_friday(datetime.date(2019, 10, 5)) # Saturday
    datetime.date(2019, 10, 4)
    >>> weekday_or_previous_friday(datetime.date(2019, 10, 4)) # Friday
    datetime.date(2019, 10, 4)
    >>> weekday_or_previous_friday(datetime.date(2019, 10, 3)) # Thursday
    datetime.date(2019, 10, 3)
    """
    thedate = thedate or today(tz=tz)
    dnum = thedate.weekday()
    if dnum in {SATURDAY, SUNDAY}:
        return thedate - relativedelta.relativedelta(days=dnum - 4)
    return thedate


@expect_date
def get_dates(since=None, until=None, window=0, business=False, entity: Type[NYSE] = NYSE):
    """Get a range of datetime.date objects.

    give the function since and until wherever possible (more explicit)
    else pass in a window to back out since or until
    - Window gives window=N additional days. So `until`-`window`=1
    defaults to include ALL days (not just business days)

    >>> next(get_dates(since=datetime.date(2014,7,16), until=datetime.date(2014,7,16)))
    datetime.date(2014, 7, 16)
    >>> next(get_dates(since=datetime.date(2014,7,12), until=datetime.date(2014,7,16)))
    datetime.date(2014, 7, 12)
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
            since = until - relativedelta.relativedelta(days=window)
    elif since and not until:
        if business:
            until = offset_date(since, window, entity)
        else:
            until = since + relativedelta.relativedelta(days=window)
    assert since <= until, 'Since date must be earlier or equal to Until date'
    thedate = since
    while thedate <= until:
        if business:
            if is_business_day(thedate, entity=entity):
                yield thedate
        else:
            yield thedate
        thedate += relativedelta.relativedelta(days=1)


def num_quarters(begdate, enddate=None, tz=EST):
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
    return 4 * days_between(begdate, enddate or today(tz=tz)) / 365.0


def get_quarter_date(thedate, end=True) -> datetime.date:
    """Return the quarter start or quarter end of a given date.

    >>> get_quarter_date(datetime.date(2013, 11, 5))
    datetime.date(2013, 12, 31)
    >>> get_quarter_date(datetime.date(2013, 11, 5), end=False)
    datetime.date(2013, 10, 1)
    >>> get_quarter_date(datetime.date(1999, 1, 19), end=False)
    datetime.date(1999, 1, 1)
    >>> get_quarter_date(datetime.date(2016, 3, 31))
    datetime.date(2016, 3, 31)
    """
    year = thedate.year
    q1_start, q1_end = datetime.date(year, 1, 1), datetime.date(year, 3, 31)
    q2_start, q2_end = datetime.date(year, 4, 1), datetime.date(year, 6, 30)
    q3_start, q3_end = datetime.date(year, 7, 1), datetime.date(year, 9, 30)
    q4_start, q4_end = datetime.date(year, 10, 1), datetime.date(year, 12, 31)

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


def get_previous_quarter_date(thedate, end=True) -> datetime.date:
    """Return the previous quarter start or quarter end of a given date.

    >>> get_previous_quarter_date(datetime.date(2013, 11, 5))
    datetime.date(2013, 9, 30)
    >>> get_previous_quarter_date(datetime.date(2013, 11, 5), end=False)
    datetime.date(2013, 7, 1)
    >>> get_previous_quarter_date(datetime.date(1999, 1, 19), end=False)
    datetime.date(1998, 10, 1)
    >>> get_previous_quarter_date(datetime.date(2016, 3, 31))
    datetime.date(2015, 12, 31)

    """
    return get_quarter_date(get_quarter_date(thedate, end=False) - relativedelta.relativedelta(days=1), end=end)


@expect_date
def get_eom_dates(begdate, enddate) -> List[datetime.date]:
    """Return a list of eom dates between and inclusive of begdate and enddate.

    >>> get_eom_dates(datetime.date(2018, 1, 5), datetime.date(2018, 4, 5))
    [datetime.date(2018, 1, 31), datetime.date(2018, 2, 28), datetime.date(2018, 3, 31), datetime.date(2018, 4, 30)]
    """
    assert begdate <= enddate
    begdate = last_of_month(begdate)
    r = relativedelta.relativedelta(day=31)
    dates = []
    d = begdate
    while d <= enddate:
        d += r
        dates.append(d)
        d += relativedelta.relativedelta(days=1)
    return dates


@expect_date
def lookback_date(thedate, lookback='last') -> datetime.date:
    """Date back based on lookback string, ie last, week, month.

    >>> lookback_date(datetime.date(2018, 12, 7), 'last')
    datetime.date(2018, 12, 6)
    >>> lookback_date(datetime.date(2018, 12, 7), 'week')
    datetime.date(2018, 11, 30)
    >>> lookback_date(datetime.date(2018, 12, 7), 'month')
    datetime.date(2018, 11, 7)
    """

    def _lookback(years=0, months=0, days=0):
        _offset = thedate - relativedelta.relativedelta(years=years, months=months, days=days)
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
    shortcodes: bool = True,
    entity: Type[NYSE] = NYSE,
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
    datetime.date(2006, 6, 23)

    m[/-]d[/-]yy    6/23/06
    >>> to_date('6/23/06')
    datetime.date(2006, 6, 23)

    m[/-]d          6/23
    >>> to_date('6/23') == datetime.date(today().year, 6, 23)
    True

    yyyy-mm-dd      2006-6-23
    >>> to_date('2006-6-23')
    datetime.date(2006, 6, 23)

    yyyymmdd        20060623
    >>> to_date('20060623')
    datetime.date(2006, 6, 23)

    dd-mon-yyyy     23-JUN-2006
    >>> to_date('23-JUN-2006')
    datetime.date(2006, 6, 23)

    mon-dd-yyyy     JUN-23-2006
    >>> to_date('20 Jan 2009')
    datetime.date(2009, 1, 20)

    month dd, yyyy  June 23, 2006
    >>> to_date('June 23, 2006')
    datetime.date(2006, 6, 23)

    dd-mon-yy
    >>> to_date('23-May-12')
    datetime.date(2012, 5, 23)

    ddmonyyyy
    >>> to_date('23May2012')
    datetime.date(2012, 5, 23)

    >>> to_date('Oct. 24, 2007', fmt='%b. %d, %Y')
    datetime.date(2007, 10, 24)

    >>> to_date('Yesterday') == today()-relativedelta.relativedelta(days=1)
    True
    >>> to_date('TODAY') == today()
    True
    >>> to_date('Jan. 13, 2014')
    datetime.date(2014, 1, 13)

    >>> to_date('March') == datetime.date(today().year, 3, today().day)
    True

    >>> to_date(np.datetime64('2000-01', 'D'))
    datetime.date(2000, 1, 1)

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
            return now(tz=entity.tz)
        if s == 'T':
            return today(tz=entity.tz)
        if s == 'Y':
            return today(tz=entity.tz) - relativedelta.relativedelta(days=1)
        if s == 'P':
            return previous_business_day(entity=entity)
        if s == 'M':
            return previous_eom(entity=entity)

    def year(m):
        try:
            yy = int(m.group('y'))
            if yy < 100:
                yy += 2000
        except IndexError:
            logger.warning('Using default this year')
            yy = today(tz=entity.tz).year
        return yy

    if not s:
        if raise_err:
            raise ValueError('Empty value')
        return

    if isinstance(s, (np.datetime64, pd.Timestamp)):
        s = to_datetime(s, localize=entity.tz)
    if isinstance(s, datetime.datetime):
        if any([s.hour, s.minute, s.second, s.microsecond]):
            logger.debug('Forced datetime with non-zero time to date')
        return s.date()
    if isinstance(s, datetime.date):
        return s
    if not isinstance(s, str):
        raise TypeError(f'Invalid type for date column: {s.__class__}')

    # always use the format if specified
    if fmt:
        try:
            return datetime.date(*time.strptime(s, fmt)[:3])
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
                    d = offset_date(d, n, business=True, entity=entity)
                else:
                    d += relativedelta.relativedelta(days=n)
            return d
        if 'today' in s.lower():
            return today(tz=entity.tz)
        if 'yester' in s.lower():
            return today(tz=entity.tz) - relativedelta.relativedelta(days=1)

    try:
        return parser.parse(s).date()
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
        raise ValueError('Failed to parse date: ' + s)


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
    datetime.time(9, 30)
    >>> to_time('9:30:15')
    datetime.time(9, 30, 15)
    >>> to_time('9:30:15.751')
    datetime.time(9, 30, 15, 751000)
    >>> to_time('9:30 AM')
    datetime.time(9, 30)
    >>> to_time('9:30 pm')
    datetime.time(21, 30)
    >>> to_time('9:30:15.751 PM')
    datetime.time(21, 30, 15, 751000)
    >>> to_time('0930')  # dateutil treats this as a date, careful!!
    datetime.time(9, 30)
    >>> to_time('093015')
    datetime.time(9, 30, 15)
    >>> to_time('093015,751')
    datetime.time(9, 30, 15, 751000)
    >>> to_time('0930 pm')
    datetime.time(21, 30)
    >>> to_time('093015,751 PM')
    datetime.time(21, 30, 15, 751000)
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
        return s.time()

    if isinstance(s, datetime.time):
        return s

    if fmt:
        return datetime.time(*time.strptime(s, fmt)[3:6])

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
            return datetime.time(hh, mm, ss, uu * 1000)
    else:
        logger.debug('Custom parsers failed, trying dateutil parser')

    try:
        parsed = parser.parse(s).time()
        if parsed:
            return parsed
    except (TypeError, ValueError):
        pass

    if raise_err:
        raise ValueError('Failed to parse time: ' + s)


def to_datetime(
    s: Union[str, datetime.date, datetime.datetime, pd.Timestamp, np.datetime64],
    raise_err=False,
    tzhint=LCL,
    localize=None,
    entity: Type[NYSE] = NYSE
) -> Optional[datetime.date]:
    """Thin layer on dateutil parser and our custom `to_date` and `to_time`
    = tzhint: Assumed time zone of input (default local time zone)
    = localize: Desired time zone of input (default None)

    Hint that the time is in EST
    >>> this_est = to_datetime('Fri, 31 Oct 2014 10:55:00', tzhint=EST)
    >>> this_est
    datetime.datetime(2014, 10, 31, 10, 55, tzinfo=zoneinfo.ZoneInfo(key='US/Eastern'))

    Assume UTC, conver to EST
    >>> this_est = to_datetime('Fri, 31 Oct 2014 14:55:00', tzhint=UTC, localize=EST)
    >>> this_est
    datetime.datetime(2014, 10, 31, 10, 55, tzinfo=zoneinfo.ZoneInfo(key='US/Eastern'))

    UTC time technically equals GMT
    >>> this_utc = to_datetime('Fri, 31 Oct 2014 14:55:00 GMT', tzhint=GMT, localize=UTC)
    >>> this_utc
    datetime.datetime(2014, 10, 31, 14, 55, tzinfo=zoneinfo.ZoneInfo(key='UTC'))
    >>> this_gmt = to_datetime('Fri, 31 Oct 2014 14:55:00 -0400', tzhint=UTC, localize=GMT)
    >>> this_gmt
    datetime.datetime(2014, 10, 31, 14, 55, tzinfo=zoneinfo.ZoneInfo(key='GMT'))

    We can freely compare time zones
    >>> this_est==this_gmt==this_utc
    True

    Format tests
    >>> epoch(to_datetime(1707856982, tzhint=UTC))
    1707856982.0
    >>> to_datetime('Jan 29  2010', tzhint=EST)
    datetime.datetime(2010, 1, 29, 0, 0, tzinfo=zoneinfo.ZoneInfo(key='US/Eastern'))
    >>> to_datetime(np.datetime64('2000-01', 'D'))
    datetime.datetime(2000, 1, 1, 0, 0)
    >>> _ = to_datetime('Sep 27 17:11', tzhint=EST)
    >>> _.month, _.day, _.hour, _.minute
    (9, 27, 17, 11)
    """
    if not s:
        if raise_err:
            raise ValueError('Empty value')
        return

    if isinstance(s, pd.Timestamp):
        return s.to_pydatetime()
    if isinstance(s, np.datetime64):
        return np.datetime64(s, 'us').astype(datetime.datetime)
    if isinstance(s, (int, float)):
        return to_datetime(datetime.datetime.fromtimestamp(s).isoformat(),
                           tzhint=tzhint, localize=localize, entity=entity)
    if isinstance(s, datetime.datetime) and not localize:
        return s
    if isinstance(s, datetime.datetime):
        s = str(s)
    if isinstance(tzhint, str):
        tzhint = ZoneInfo(tzhint)
    if isinstance(localize, str):
        localize = ZoneInfo(localize)
    if isinstance(s, datetime.date):
        logger.debug('Forced date without time to datetime')
        return datetime.datetime(s.year, s.month, s.day, tzinfo=tzhint)
    if not isinstance(s, str):
        raise TypeError(f'Invalid type for date column: {s.__class__}')

    try:
        parsed = parser.parse(s)
        if tzhint:
            parsed = parsed.replace(tzinfo=tzhint)
        if localize:
            parsed = parsed.astimezone(localize)
        return parsed
    except (TypeError, ValueError) as err:
        logger.debug('Dateutil parser failed .. trying our custom parsers')

    for delim in (' ', ':'):
        bits = s.split(delim, 1)
        if len(bits) == 2:
            d = to_date(bits[0])
            t = to_time(bits[1])
            if d is not None and t is not None:
                return datetime.datetime.combine(d, t)

    d = to_date(s, entity=entity)
    if d is not None:
        return datetime.datetime(d.year, d.month, d.day, 0, 0, 0)

    current = today(tz=tzhint)
    t = to_time(s)   # probably a bug when combining localized date with vanilla time
    if t is not None:
        return datetime.datetime.combine(current, t)

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
    else:
        if begdate < enddate:
            return len(list(get_dates(begdate, enddate, business=True, entity=entity))) - 1
        return -len(list(get_dates(enddate, begdate, business=True, entity=entity))) + 1


@expect_date
def years_between(begdate=None, enddate=None, basis: int = 0, tz=EST):
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

    begdate = begdate or today(tz=tz)
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

    >>> date_range(datetime.date(2014, 4, 3), None, 3)
    (datetime.date(2014, 4, 3), datetime.date(2014, 4, 8))
    >>> date_range(None, datetime.date(2014, 7, 27), 20, business=False)
    (datetime.date(2014, 7, 7), datetime.date(2014, 7, 27))
    >>> date_range(None, datetime.date(2014, 7, 27), 20)
    (datetime.date(2014, 6, 27), datetime.date(2014, 7, 27))
    """
    if begdate:
        begdate = to_date(begdate, entity=entity)
    if enddate:
        enddate = to_date(enddate, entity=entity)

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


def reference_date_13f(thedate):
    """Date on which 13F filings becomes public.

    13F due 45 days after the end of each quarter.

    12/31/22 -> 2/15/23
    >>> reference_date_13f(datetime.date(2023, 2, 14))
    datetime.date(2022, 9, 30)
    >>> reference_date_13f(datetime.date(2023, 2, 15))
    datetime.date(2022, 12, 31)

    3/31/23 -> 5/16/23
    >>> reference_date_13f(datetime.date(2023, 5, 15))
    datetime.date(2022, 12, 31)
    >>> reference_date_13f(datetime.date(2023, 5, 16))
    datetime.date(2023, 3, 31)

    6/30/23 -> 8/15/23
    >>> reference_date_13f(datetime.date(2023, 8, 14))
    datetime.date(2023, 3, 31)
    >>> reference_date_13f(datetime.date(2023, 8, 15))
    datetime.date(2023, 6, 30)

    """
    ref_date = get_previous_quarter_date(thedate)
    if thedate <= offset_date(ref_date, 45):
        ref_date = get_previous_quarter_date(ref_date)
    return ref_date


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
