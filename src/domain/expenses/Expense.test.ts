import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { Expense, InvalidExpenseError, type ExpenseProps } from './Expense.js';
import { MAX_AMOUNT_CENTS } from './money.js';

const props = (overrides: Partial<ExpenseProps> = {}): ExpenseProps => ({
    date: '2026-10-01',
    amountCents: 5090,
    description: 'burger king',
    category: 'alimentacao',
    userId: 'telegram:1',
    messageKey: 'telegram:10:100#0',
    createdAt: '2026-10-01T12:00:00.000Z',
    ...overrides,
});

describe('Expense', () => {
    describe('construction', () => {
        it('keeps the given values and always uses BRL', () => {
            const expense = new Expense(props());

            assert.equal(expense.date, '2026-10-01');
            assert.equal(expense.amountCents, 5090);
            assert.equal(expense.currency, 'BRL');
            assert.equal(expense.description, 'burger king');
            assert.equal(expense.category, 'alimentacao');
            assert.equal(expense.userId, 'telegram:1');
            assert.equal(expense.messageKey, 'telegram:10:100#0');
            assert.equal(expense.createdAt, '2026-10-01T12:00:00.000Z');
        });

        it('trims the description', () => {
            assert.equal(new Expense(props({ description: '  uber  ' })).description, 'uber');
        });

        it('accepts the largest allowed amount', () => {
            assert.equal(
                new Expense(props({ amountCents: MAX_AMOUNT_CENTS })).amountCents,
                MAX_AMOUNT_CENTS,
            );
        });

        for (const [name, overrides, reason] of [
            ['a zero amount', { amountCents: 0 }, /amount/],
            ['a negative amount', { amountCents: -1 }, /amount/],
            ['a fractional amount of cents', { amountCents: 10.5 }, /amount/],
            ['an amount above the cap', { amountCents: MAX_AMOUNT_CENTS + 1 }, /amount/],
            ['a string amount', { amountCents: '5090' }, /amount/],
            ['a missing amount', { amountCents: undefined }, /amount/],
            ['a blank description', { description: '   ' }, /description/],
            ['a non-string description', { description: 50 }, /description/],
            ['an unknown category', { category: 'viagem' }, /category must be one of: alimentacao/],
            ['an impossible date', { date: '2026-02-30' }, /date/],
            ['a badly formatted date', { date: '30/09/2026' }, /date/],
            ['an empty userId', { userId: '' }, /userId/],
            ['an empty messageKey', { messageKey: '' }, /messageKey/],
            ['an unparseable createdAt', { createdAt: 'ontem' }, /createdAt/],
            ['a non-string createdAt', { createdAt: 123 }, /createdAt/],
        ] as const) {
            it(`rejects ${name}`, () => {
                assert.throws(
                    () => new Expense(props(overrides)),
                    (error: unknown) =>
                        error instanceof InvalidExpenseError && reason.test(error.message),
                );
            });
        }
    });

    describe('behavior', () => {
        const expense = new Expense(props({ date: '2026-10-15' }));

        it('knows who it belongs to', () => {
            assert.equal(expense.belongsTo('telegram:1'), true);
            assert.equal(expense.belongsTo('telegram:2'), false);
        });

        it('knows whether it falls in a date range, ends included', () => {
            assert.equal(expense.occursWithin({ from: '2026-10-01', to: '2026-10-31' }), true);
            assert.equal(expense.occursWithin({ from: '2026-10-15', to: '2026-10-15' }), true);
            assert.equal(expense.occursWithin({ from: '2026-10-16', to: '2026-10-31' }), false);
            assert.equal(expense.occursWithin({ from: '2026-09-01', to: '2026-10-14' }), false);
        });

        it('knows its category', () => {
            assert.equal(expense.hasCategory('alimentacao'), true);
            assert.equal(expense.hasCategory('lazer'), false);
        });
    });

    it('cannot be changed after construction', () => {
        const expense = new Expense(props());

        assert.throws(() => {
            (expense as { amountCents: number }).amountCents = 1;
        }, TypeError);
    });
});
