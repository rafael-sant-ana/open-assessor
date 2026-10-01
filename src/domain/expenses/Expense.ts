import type { Category } from '../categories.js';

export interface Expense {
    /** Resolved calendar day in the configured timezone, `YYYY-MM-DD`. Not the message timestamp. */
    readonly date: string;
    /** Positive integer amount in the smallest currency unit. */
    readonly amountCents: number;
    readonly currency: 'BRL';
    /** As written by the user. */
    readonly description: string;
    readonly category: Category;
    /** `<platform>:<authorId>`, same format as `ALLOWED_USERS`. */
    readonly userId: string;
    /** `<platform>:<messageId>`, used to make writes idempotent. */
    readonly messageKey: string;
    /** ISO 8601 instant at which the row was written. */
    readonly createdAt: string;
}
