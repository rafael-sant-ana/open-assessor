import { CATEGORIES, type Category } from '../../domain/categories.js';
import { isValidIsoDate } from '../../domain/dates.js';
import type { Expense } from '../../domain/expenses/Expense.js';
import { summarize, type ExpenseSummary } from '../../domain/expenses/summarize.js';
import type { ExpenseRepository } from '../../providers/ExpenseRepository.js';

export interface ListExpensesInput {
    readonly userId: string;
    /** Inclusive `YYYY-MM-DD`. */
    readonly from: unknown;
    /** Inclusive `YYYY-MM-DD`. */
    readonly to: unknown;
    readonly category?: unknown;
}

export type ListExpensesResult =
    | {
          readonly status: 'ok';
          readonly expenses: readonly Expense[];
          readonly summary: ExpenseSummary;
      }
    | { readonly status: 'invalid'; readonly reason: string };

export default class ListExpenses {
    constructor(private readonly repository: ExpenseRepository) {}

    async execute(input: ListExpensesInput): Promise<ListExpensesResult> {
        const { from, to, category } = input;

        if (!isValidIsoDate(from) || !isValidIsoDate(to))
            return invalid('from and to must be real days formatted as YYYY-MM-DD');
        if (from > to) return invalid('from must not be after to');
        if (category !== undefined && !isCategory(category))
            return invalid(`category must be one of: ${CATEGORIES.join(', ')}`);

        const found = await this.repository.listBy(input.userId, { from, to });
        const expenses =
            category === undefined
                ? found
                : found.filter((e) => e.category === category);

        return { status: 'ok', expenses, summary: summarize(expenses) };
    }
}

function invalid(reason: string): ListExpensesResult {
    return { status: 'invalid', reason };
}

function isCategory(value: unknown): value is Category {
    return (CATEGORIES as readonly unknown[]).includes(value);
}
