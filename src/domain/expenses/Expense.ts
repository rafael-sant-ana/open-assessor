import { CATEGORIES, type Category } from '../categories.js';
import { isValidIsoDate, type DateRange } from '../dates.js';
import { MAX_AMOUNT_CENTS } from './money.js';

/**
 * Raw values for an expense. They come from the model or from a spreadsheet, so none of
 * them is trusted: the `Expense` constructor checks every field.
 */
export interface ExpenseProps {
    /** Resolved calendar day in the configured timezone, `YYYY-MM-DD`. Not the message timestamp. */
    readonly date: unknown;
    /** Positive integer amount in cents (BRL). */
    readonly amountCents: unknown;
    /** As written by the user. */
    readonly description: unknown;
    readonly category: unknown;
    /** `<platform>:<authorId>`, same format as `ALLOWED_USERS`. */
    readonly userId: unknown;
    /** `<platform>:<chatId>:<messageId>#<n>`, makes writes idempotent. */
    readonly messageKey: unknown;
    /** ISO 8601 instant at which the expense was recorded. */
    readonly createdAt: unknown;
}

export class InvalidExpenseError extends Error {
    constructor(reason: string) {
        super(reason);
        this.name = 'InvalidExpenseError';
    }
}

/** A recorded expense. Immutable, and it cannot be constructed in an invalid state. */
export class Expense {
    readonly date: string;
    readonly amountCents: number;
    readonly currency = 'BRL' as const;
    readonly description: string;
    readonly category: Category;
    readonly userId: string;
    readonly messageKey: string;
    readonly createdAt: string;

    /** @throws {InvalidExpenseError} with a reason the model can relay to the user. */
    constructor(props: ExpenseProps) {
        const { date, amountCents, description, category, userId, messageKey, createdAt } = props;

        if (
            typeof amountCents !== 'number' ||
            !Number.isInteger(amountCents) ||
            amountCents <= 0 ||
            amountCents > MAX_AMOUNT_CENTS
        )
            throw new InvalidExpenseError('amount must be a positive number in BRL');

        if (typeof description !== 'string' || !description.trim())
            throw new InvalidExpenseError('description is required');

        if (!isCategory(category))
            throw new InvalidExpenseError(`category must be one of: ${CATEGORIES.join(', ')}`);

        if (!isValidIsoDate(date))
            throw new InvalidExpenseError('date must be a real day formatted as YYYY-MM-DD');

        if (typeof userId !== 'string' || !userId)
            throw new InvalidExpenseError('userId is required');

        if (typeof messageKey !== 'string' || !messageKey)
            throw new InvalidExpenseError('messageKey is required');

        if (typeof createdAt !== 'string' || Number.isNaN(Date.parse(createdAt)))
            throw new InvalidExpenseError('createdAt must be an ISO 8601 timestamp');

        this.date = date;
        this.amountCents = amountCents;
        this.description = description.trim();
        this.category = category;
        this.userId = userId;
        this.messageKey = messageKey;
        this.createdAt = createdAt;

        Object.freeze(this);
    }

    belongsTo(userId: string): boolean {
        return this.userId === userId;
    }

    /** Both ends of the range are included. */
    occursWithin(range: DateRange): boolean {
        return this.date >= range.from && this.date <= range.to;
    }

    hasCategory(category: Category): boolean {
        return this.category === category;
    }
}

function isCategory(value: unknown): value is Category {
    return (CATEGORIES as readonly unknown[]).includes(value);
}
