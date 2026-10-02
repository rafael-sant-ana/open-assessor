from open_assessor.domain.dates import DateRange
from open_assessor.ports.expense_repository import ExpenseRepository
from tests.factories import make_expense


class ExpenseRepositoryContract:
    """Behavior every `ExpenseRepository` implementation must honour.

    Subclass it as `Test...` and define an async `repo` fixture.
    """

    async def test_round_trips_an_expense_exactly(self, repo: ExpenseRepository):
        saved = make_expense(date="2026-02-28", amount_cents=1999)
        await repo.add(saved)

        assert await repo.list_by("telegram:1", DateRange("2026-02-01", "2026-02-28")) == [saved]

    async def test_reports_whether_a_message_key_was_already_saved(self, repo: ExpenseRepository):
        assert not await repo.exists_by_message_key("telegram:10:100#0")
        await repo.add(make_expense())
        assert await repo.exists_by_message_key("telegram:10:100#0")

    async def test_ignores_a_second_add_with_the_same_message_key(self, repo: ExpenseRepository):
        await repo.add(make_expense(amount_cents=5000))
        await repo.add(make_expense(amount_cents=9999))

        found = await repo.list_by("telegram:1", DateRange("2026-01-01", "2026-12-31"))
        assert len(found) == 1
        assert found[0].amount_cents == 5000

    async def test_keeps_text_that_looks_like_a_formula_or_a_number_as_text(
        self, repo: ExpenseRepository
    ):
        tricky = make_expense(description='=HYPERLINK("http://x","y")')
        numeric = make_expense(description="50", message_key="telegram:10:101#0")
        await repo.add(tricky)
        await repo.add(numeric)

        found = await repo.list_by("telegram:1", DateRange("2026-10-01", "2026-10-01"))
        assert found == [tricky, numeric]

    async def test_removes_and_returns_the_last_expense_of_the_given_user_only(
        self, repo: ExpenseRepository
    ):
        first = make_expense(message_key="telegram:10:1#0")
        last = make_expense(message_key="telegram:10:2#0")
        other = make_expense(user_id="telegram:2", message_key="telegram:10:3#0")
        for expense in (first, last, other):
            await repo.add(expense)

        assert await repo.remove_last_by("telegram:1") == last
        assert not await repo.exists_by_message_key("telegram:10:2#0")
        assert await repo.exists_by_message_key("telegram:10:3#0")
        assert await repo.remove_last_by("telegram:1") == first

    async def test_allows_re_adding_an_expense_after_it_was_removed(self, repo: ExpenseRepository):
        await repo.add(make_expense())
        await repo.remove_last_by("telegram:1")
        await repo.add(make_expense())

        assert await repo.exists_by_message_key("telegram:10:100#0")

    async def test_returns_none_when_the_user_has_nothing_to_remove(self, repo: ExpenseRepository):
        assert await repo.remove_last_by("telegram:1") is None

    async def test_lists_by_user_within_an_inclusive_date_range(self, repo: ExpenseRepository):
        a = make_expense(date="2026-10-01", message_key="telegram:10:1#0")
        b = make_expense(date="2026-10-15", message_key="telegram:10:2#0")
        outside = make_expense(date="2026-11-01", message_key="telegram:10:3#0")
        other = make_expense(user_id="telegram:2", message_key="telegram:10:4#0")
        for expense in (a, b, outside, other):
            await repo.add(expense)

        found = await repo.list_by("telegram:1", DateRange("2026-10-01", "2026-10-15"))
        assert found == [a, b]
