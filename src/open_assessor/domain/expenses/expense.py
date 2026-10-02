from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Literal

from open_assessor.domain.categories import CATEGORIES, Category, is_category
from open_assessor.domain.dates import DateRange, is_valid_iso_date
from open_assessor.domain.expenses.money import MAX_AMOUNT_CENTS


class InvalidExpenseError(ValueError):
    """Carries a reason the model can relay to the user."""


@dataclass(frozen=True, slots=True, init=False)
class Expense:
    """A recorded expense. Immutable, and it cannot be constructed in an invalid state.

    The raw values come from the model or from a spreadsheet, so none of them is trusted:
    the constructor checks every field.
    """

    CURRENCY: ClassVar[Literal["BRL"]] = "BRL"

    date: str
    """Resolved calendar day in the configured timezone, `YYYY-MM-DD`. Not the message timestamp."""
    amount_cents: int
    """Positive integer amount in cents (BRL)."""
    description: str
    """As written by the user."""
    category: Category
    user_id: str
    """`<platform>:<authorId>`, same format as `ALLOWED_USERS`."""
    message_key: str
    """`<platform>:<chatId>:<messageId>#<n>`, makes writes idempotent."""
    created_at: str
    """ISO 8601 instant at which the expense was recorded."""

    def __init__(
        self,
        *,
        date: object,
        amount_cents: object,
        description: object,
        category: object,
        user_id: object,
        message_key: object,
        created_at: object,
    ) -> None:
        """Raises `InvalidExpenseError` when a field is not usable."""
        if (
            isinstance(amount_cents, bool)
            or not isinstance(amount_cents, int)
            or amount_cents <= 0
            or amount_cents > MAX_AMOUNT_CENTS
        ):
            raise InvalidExpenseError("amount must be a positive number in BRL")

        if not isinstance(description, str) or not description.strip():
            raise InvalidExpenseError("description is required")

        if not is_category(category):
            raise InvalidExpenseError(f"category must be one of: {', '.join(CATEGORIES)}")

        if not is_valid_iso_date(date):
            raise InvalidExpenseError("date must be a real day formatted as YYYY-MM-DD")

        if not isinstance(user_id, str) or not user_id:
            raise InvalidExpenseError("userId is required")

        if not isinstance(message_key, str) or not message_key:
            raise InvalidExpenseError("messageKey is required")

        if not isinstance(created_at, str) or not _is_iso_instant(created_at):
            raise InvalidExpenseError("createdAt must be an ISO 8601 timestamp")

        # The dataclass is frozen, so fields can only be set through object.__setattr__.
        set_field = object.__setattr__
        set_field(self, "date", date)
        set_field(self, "amount_cents", amount_cents)
        set_field(self, "description", description.strip())
        set_field(self, "category", category)
        set_field(self, "user_id", user_id)
        set_field(self, "message_key", message_key)
        set_field(self, "created_at", created_at)

    @property
    def currency(self) -> Literal["BRL"]:
        return self.CURRENCY

    def belongs_to(self, user_id: str) -> bool:
        return self.user_id == user_id

    def occurs_within(self, date_range: DateRange) -> bool:
        """Both ends of the range are included."""
        return date_range.from_ <= self.date <= date_range.to

    def has_category(self, category: Category) -> bool:
        return self.category == category


def _is_iso_instant(value: str) -> bool:
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True
