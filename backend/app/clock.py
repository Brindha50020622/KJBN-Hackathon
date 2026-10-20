from datetime import UTC, datetime
from typing import Annotated

from fastapi import Header

from app.config import settings
from app.errors import InvalidRequestError


def get_now(x_test_clock: Annotated[str | None, Header()] = None) -> datetime:
    """Current time in UTC. Reviewers can override it with the X-Test-Clock header."""
    if x_test_clock and settings.enable_test_clock:
        try:
            value = datetime.fromisoformat(x_test_clock)
        except ValueError as exc:
            raise InvalidRequestError("X-Test-Clock must be an ISO 8601 datetime") from exc
        if value.tzinfo is None:
            raise InvalidRequestError(
                "X-Test-Clock needs a timezone, e.g. 2026-10-18T12:00:00+05:30"
            )
        return value.astimezone(UTC)
    return datetime.now(UTC)
