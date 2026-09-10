import datetime
import email.utils


def parse_http_date(txt: str) -> datetime.datetime:
    """
    Parse an date from a standard HTTP header. Returned datetime is tz-aware.
    """
    dt = email.utils.parsedate_to_datetime(txt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def format_http_date(dt: datetime.datetime) -> str:
    """
    Format a datetime for HTTP.
    """
    return email.utils.format_datetime(dt, usegmt=True)
