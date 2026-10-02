import { DEFAULT_TIMEZONE, todayIn, type Clock } from '../../domain/dates.js';
import { Expense, InvalidExpenseError } from '../../domain/expenses/Expense.js';
import { toCents } from '../../domain/expenses/money.js';
import type { ExpenseRepository } from '../../providers/ExpenseRepository.js';

export interface AddExpenseInput {
    readonly userId: string;
    /** Idempotency key: replaying the same key never creates a second expense. */
    readonly messageKey: string;
    /** BRL decimal, e.g. 50.9. */
    readonly amount: unknown;
    readonly description: unknown;
    readonly category: unknown;
    /** `YYYY-MM-DD`; defaults to today in the configured timezone. */
    readonly date?: unknown;
}

export type AddExpenseResult =
    | { readonly status: 'saved'; readonly expense: Expense }
    | { readonly status: 'duplicate' }
    | { readonly status: 'invalid'; readonly reason: string };

export default class AddExpense {
    constructor(
        private readonly repository: ExpenseRepository,
        private readonly clock: Clock,
        private readonly timezone: string = DEFAULT_TIMEZONE,
    ) {}

    async execute(input: AddExpenseInput): Promise<AddExpenseResult> {
        const amountCents = toCents(input.amount);
        if (amountCents === null)
            return { status: 'invalid', reason: 'amount must be a positive number in BRL' };

        const now = this.clock();
        let expense: Expense;
        try {
            expense = new Expense({
                date: input.date ?? todayIn(this.timezone, now),
                amountCents,
                description: input.description,
                category: input.category,
                userId: input.userId,
                messageKey: input.messageKey,
                createdAt: now.toISOString(),
            });
        } catch (error) {
            if (error instanceof InvalidExpenseError)
                return { status: 'invalid', reason: error.message };
            throw error;
        }

        if (await this.repository.existsByMessageId(expense.messageKey))
            return { status: 'duplicate' };

        await this.repository.add(expense);

        return { status: 'saved', expense };
    }
}
