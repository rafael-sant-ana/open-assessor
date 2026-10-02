import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { Expense, type ExpenseProps } from './Expense.js';
import { summarize } from './summarize.js';

const expense = (overrides: Partial<ExpenseProps>) => new Expense({
    date: '2026-10-01',
    amountCents: 1000,
    description: 'x',
    category: 'outros',
    userId: 'telegram:1',
    messageKey: 'telegram:1:1#0',
    createdAt: '2026-10-01T12:00:00.000Z',
    ...overrides,
});

describe('summarize', () => {
    it('returns zeros for no expenses', () => {
        assert.deepEqual(summarize([]), {
            count: 0,
            totalCents: 0,
            byCategory: {},
        });
    });

    it('totals everything and per category', () => {
        const result = summarize([
            expense({ amountCents: 5000, category: 'alimentacao' }),
            expense({ amountCents: 2500, category: 'alimentacao' }),
            expense({ amountCents: 1000, category: 'transporte' }),
        ]);

        assert.deepEqual(result, {
            count: 3,
            totalCents: 8500,
            byCategory: { alimentacao: 7500, transporte: 1000 },
        });
    });
});
