import type { Expense } from '../../domain/expenses/Expense.js';
import type { DateRange, ExpenseRepository } from '../../providers/ExpenseRepository.js';

export default class InMemoryExpenseRepository implements ExpenseRepository {
    private readonly expenses: Expense[] = [];

    async add(expense: Expense): Promise<void> {
        this.expenses.push(expense);
    }

    async removeLastBy(userId: string): Promise<Expense | null> {
        const index = this.expenses.findLastIndex((e) => e.userId === userId);
        if (index === -1) return null;
        return this.expenses.splice(index, 1)[0] ?? null;
    }

    async existsByMessageId(messageKey: string): Promise<boolean> {
        return this.expenses.some((e) => e.messageKey === messageKey);
    }

    async listBy(userId: string, range: DateRange): Promise<Expense[]> {
        return this.expenses.filter(
            (e) => e.userId === userId && e.date >= range.from && e.date <= range.to,
        );
    }
}
