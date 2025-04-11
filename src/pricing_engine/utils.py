# src/pricing_engine/utils.py

import datetime

def format_date(d: datetime.date) -> str:
    """
    Formats a date or datetime object into a 'YYYY-MM-DD' string.

    Args:
        d: The date or datetime object to format.

    Returns:
        The formatted date string.

    Raises:
        TypeError: If the input is not a date or datetime object.
    """
    if not isinstance(d, (datetime.date, datetime.datetime)):
        raise TypeError("Input must be a datetime.date or datetime.datetime object")
    return d.strftime('%Y-%m-%d')

def add_days(d: datetime.date, days: int) -> datetime.date:
    """
    Adds a specified number of days to a date object.

    Args:
        d: The starting date or datetime object.
        days: The number of days to add (can be negative).

    Returns:
        A new date object representing the resulting date.

    Raises:
        TypeError: If the input date is not a date or datetime object.
    """
    if not isinstance(d, (datetime.date, datetime.datetime)):
        raise TypeError("Input date must be a datetime.date or datetime.datetime object")
    # If it's a datetime object, ensure we return only the date part
    if isinstance(d, datetime.datetime):
        d = d.date()
    return d + datetime.timedelta(days=days)

def get_day_group(d: datetime.date) -> str:
    """
    Determines the day group ('Mon-Wed', 'Thu-Sun', 'Fri-Sat') for a given date.

    Args:
        d: The date or datetime object.

    Returns:
        A string representing the day group.

    Raises:
        TypeError: If the input is not a date or datetime object.
    """
    if not isinstance(d, (datetime.date, datetime.datetime)):
        raise TypeError("Input must be a datetime.date or datetime.datetime object")
    day_of_week = d.weekday() # Monday is 0 and Sunday is 6

    if day_of_week in [0, 1, 2]: # Monday, Tuesday, Wednesday
        return 'Mon-Wed'
    elif day_of_week in [3, 6]: # Thursday, Sunday
        return 'Thu-Sun'
    else: # Friday (4), Saturday (5)
        return 'Fri-Sat'

def get_booking_window_label(target_date: datetime.date, today: datetime.date) -> str:
    """
    Calculates the booking window label (e.g., '0-9 Days (W1)') based on the
    number of days between today and the target date.

    Args:
        target_date: The future date for which the rate is being calculated.
        today: The current date (typically the date the script is run).

    Returns:
        A string representing the booking window label.

    Raises:
        TypeError: If inputs are not date or datetime objects.
    """
    if not isinstance(target_date, (datetime.date, datetime.datetime)):
        raise TypeError("target_date must be a date or datetime object")
    if not isinstance(today, (datetime.date, datetime.datetime)):
        raise TypeError("today must be a date or datetime object")

    # Ensure we are comparing dates only, ignoring time component
    if isinstance(target_date, datetime.datetime):
        target_date = target_date.date()
    if isinstance(today, datetime.datetime):
        today = today.date()

    diff_days = (target_date - today).days

    # Handle cases where target_date is in the past relative to today
    if diff_days < 0:
        # Or return a specific label like "Past Date"? For now, maps to shortest window.
        return "0-9 Days (W1)" # Or potentially an empty string or error?

    if diff_days <= 9: return "0-9 Days (W1)"
    if diff_days <= 21: return "10-21 Days (W2)"
    if diff_days <= 30: return "22-30 Days (W3)"
    if diff_days <= 45: return "31-45 Days (W4)"
    if diff_days <= 59: return "46-59 Days (W5)"
    if diff_days <= 120: return "60-120 Days (W6)"
    # This covers all cases where diff_days > 120
    return ">120 Days (W7)"

def get_urgency_band(target_date: datetime.date, today: datetime.date) -> str:
    """
    Calculates the urgency band ('0-1', '2-3', '4-6', '7-9') for close-in
    bookings (target dates within 0-9 days from today). Returns an empty
    string for dates further out or in the past.

    Args:
        target_date: The future date for which the rate is being calculated.
        today: The current date.

    Returns:
        A string representing the urgency band or an empty string.

    Raises:
        TypeError: If inputs are not date or datetime objects.
    """
    if not isinstance(target_date, (datetime.date, datetime.datetime)):
        raise TypeError("target_date must be a date or datetime object")
    if not isinstance(today, (datetime.date, datetime.datetime)):
        raise TypeError("today must be a date or datetime object")

    # Ensure we are comparing dates only
    if isinstance(target_date, datetime.datetime):
        target_date = target_date.date()
    if isinstance(today, datetime.datetime):
        today = today.date()

    diff_days = (target_date - today).days

    if diff_days < 0: return "" # No urgency band for past dates
    if diff_days <= 1: return "0-1"
    if diff_days <= 3: return "2-3"
    if diff_days <= 6: return "4-6"
    if diff_days <= 9: return "7-9"
    # For dates > 9 days out, there's no specific urgency band in this logic
    return ""