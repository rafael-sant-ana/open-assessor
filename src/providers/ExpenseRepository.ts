import type { Expense } from '../domain/expenses/Expense.js';

/** Inclusive range of calendar days, `YYYY-MM-DD`. */
export interface DateRange {
    readonly from: string;
    readonly to: string;
}

export interface ExpenseRepository {
    /** Idempotent: adding an expense whose `messageKey` is already stored does nothing. */
    add(expense: Expense): Promise<void>;
    /** Deletes the last expense created by the user and returns it, or `null` if there is none. */
    removeLastBy(userId: string): Promise<Expense | null>;
    existsByMessageId(messageKey: string): Promise<boolean>;
    listBy(userId: string, range: DateRange): Promise<Expense[]>;
}
