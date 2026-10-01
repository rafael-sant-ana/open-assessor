import type { Category } from '../categories.js';
import type { Expense } from './Expense.js';

export interface ExpenseSummary {
    readonly count: number;
    readonly totalCents: number;
    readonly byCategory: Readonly<Partial<Record<Category, number>>>;
}

export function summarize(expenses: readonly Expense[]): ExpenseSummary {
    const byCategory: Partial<Record<Category, number>> = {};
    let totalCents = 0;

    for (const expense of expenses) {
        totalCents += expense.amountCents;
        byCategory[expense.category] =
            (byCategory[expense.category] ?? 0) + expense.amountCents;
    }

    return { count: expenses.length, totalCents, byCategory };
}
