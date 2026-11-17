from datetime import datetime, timezone


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def calculate_urgency(deadline_at: datetime | None, now: datetime | None = None) -> bool:
    if deadline_at is None:
        return False
    current = as_utc(now or datetime.now(timezone.utc))
    return (as_utc(deadline_at) - current).total_seconds() <= 3 * 86400


def calculate_days_until_deadline(deadline_at: datetime | None, now: datetime | None = None) -> int | None:
    if deadline_at is None:
        return None
    current = as_utc(now or datetime.now(timezone.utc))
    return (as_utc(deadline_at).date() - current.date()).days


def determine_quadrant(is_important: bool, is_urgent: bool) -> str:
    return {
        (True, True): "Q1",
        (True, False): "Q2",
        (False, True): "Q3",
        (False, False): "Q4",
    }[(is_important, is_urgent)]
