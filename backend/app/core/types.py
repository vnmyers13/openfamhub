from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """Datetime column that always stores UTC and always returns aware UTC values.

    SQLite has no timezone support: SQLAlchemy drops the offset and stores the
    wall-clock value, so a 15:00-04:00 input would be saved as "15:00" and read
    back as a naive 15:00. Normalising to UTC on the way in and attaching UTC on
    the way out keeps every stored value comparable and every API value explicit.
    Naive inputs are treated as UTC.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
