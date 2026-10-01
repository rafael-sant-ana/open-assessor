import { CATEGORIES, type Category } from '../../domain/categories.js';
import {
    DEFAULT_TIMEZONE,
    isValidIsoDate,
    todayIn,
    type Clock,
} from '../../domain/dates.js';
import type { Expense } from '../../domain/expenses/Expense.js';
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
            return invalid('amount must be a positive number in BRL');

        const description =
            typeof input.description === 'string' ? input.description.trim() : '';
        if (!description) return invalid('description is required');

        if (!isCategory(input.category))
            return invalid(`category must be one of: ${CATEGORIES.join(', ')}`);

        const now = this.clock();
        const date = input.date ?? todayIn(this.timezone, now);
        if (!isValidIsoDate(date))
            return invalid('date must be a real day formatted as YYYY-MM-DD');

        if (await this.repository.existsByMessageId(input.messageKey))
            return { status: 'duplicate' };

        const expense: Expense = {
            date,
            amountCents,
            currency: 'BRL',
            description,
            category: input.category,
            userId: input.userId,
            messageKey: input.messageKey,
            createdAt: now.toISOString(),
        };
        await this.repository.add(expense);

        return { status: 'saved', expense };
    }
}

function invalid(reason: string): AddExpenseResult {
    return { status: 'invalid', reason };
}

function isCategory(value: unknown): value is Category {
    return (CATEGORIES as readonly unknown[]).includes(value);
}
