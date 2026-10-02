import pytest

from open_assessor.infrastructure.expenses.in_memory_expense_repository import (
    InMemoryExpenseRepository,
)
from tests.infrastructure.expenses.expense_repository_contract import ExpenseRepositoryContract


class TestInMemoryExpenseRepository(ExpenseRepositoryContract):
    @pytest.fixture
    async def repo(self) -> InMemoryExpenseRepository:
        return InMemoryExpenseRepository()
