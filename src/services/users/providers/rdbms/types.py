from datetime import UTC, datetime

import sqlalchemy.types as sa_types


class CustomDateTime(sa_types.TypeDecorator):
    """Make sure a `sa.DateTime` object read from the DB has a TZinfo.

    If TZinfo is missing, UTC is set.

    Handles `-infinity` timestamps.
    """

    impl = sa_types.DateTime
    cache_ok = True

    def process_result_value(self, value: datetime | None, dialect) -> datetime:
        assert value is not None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
