import datetime

__all__ = ['UTC_TZ']

# This class is needed to create timezone-aware datetime objects in Python 2
# the only alternative is to use external modules.
class UTC(datetime.tzinfo):
    ZERO = datetime.timedelta(0)
    def utcoffset(self, dt):
        return UTC.ZERO
    def tzname(self, dt):
        return "UTC"
    def dst(self, dt):
        return UTC.ZERO
UTC_TZ = UTC()