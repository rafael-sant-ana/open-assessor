import assert from 'node:assert/strict';
import { beforeEach, describe, it } from 'node:test';
import { Expense } from '../../domain/expenses/Expense.js';
import InMemoryExpenseRepository from '../../infrastructure/expenses/InMemoryExpenseRepository.js';
import AddExpense, { type AddExpenseInput } from './AddExpense.js';

// 02:30 UTC on Oct 2nd is still Oct 1st in São Paulo.
const NOW = new Date('2026-10-02T02:30:00Z');

const input = (overrides: Partial<AddExpenseInput> = {}): AddExpenseInput => ({
    userId: 'telegram:1',
    messageKey: 'telegram:10:100#0',
    amount: 50.9,
    description: ' burger king ',
    category: 'alimentacao',
    ...overrides,
});

describe('AddExpense', () => {
    let repository: InMemoryExpenseRepository;
    let addExpense: AddExpense;

    beforeEach(() => {
        repository = new InMemoryExpenseRepository();
        addExpense = new AddExpense(repository, () => NOW);
    });

    it('saves a normalized expense dated today in the configured timezone', async () => {
        const result = await addExpense.execute(input());

        assert.equal(result.status, 'saved');
        assert.ok(result.status === 'saved' && result.expense instanceof Expense);
        assert.deepEqual(result.status === 'saved' && { ...result.expense }, {
            date: '2026-10-01',
            amountCents: 5090,
            currency: 'BRL',
            description: 'burger king',
            category: 'alimentacao',
            userId: 'telegram:1',
            messageKey: 'telegram:10:100#0',
            createdAt: '2026-10-02T02:30:00.000Z',
        });
        assert.equal(await repository.existsByMessageId('telegram:10:100#0'), true);
    });

    it('uses the given date', async () => {
        const result = await addExpense.execute(input({ date: '2026-09-30' }));

        assert.equal(result.status === 'saved' && result.expense.date, '2026-09-30');
    });

    it('does not write twice for a replayed message key', async () => {
        await addExpense.execute(input());
        const result = await addExpense.execute(input({ amount: 99 }));

        assert.deepEqual(result, { status: 'duplicate' });
        const saved = await repository.listBy('telegram:1', {
            from: '2026-01-01',
            to: '2026-12-31',
        });
        assert.equal(saved.length, 1);
        assert.equal(saved[0]!.amountCents, 5090);
    });

    for (const [name, overrides, reason] of [
        ['a missing amount', { amount: undefined }, /amount/],
        ['a zero amount', { amount: 0 }, /amount/],
        ['a negative amount', { amount: -3 }, /amount/],
        ['a string amount', { amount: '50' }, /amount/],
        ['a blank description', { description: '   ' }, /description/],
        ['a missing description', { description: undefined }, /description/],
        ['an unknown category', { category: 'viagem' }, /category/],
        ['an impossible date', { date: '2026-02-30' }, /date/],
        ['a badly formatted date', { date: '30/09/2026' }, /date/],
    ] as const) {
        it(`rejects ${name} without writing`, async () => {
            const result = await addExpense.execute(input(overrides));

            assert.equal(result.status, 'invalid');
            assert.match(result.status === 'invalid' ? result.reason : '', reason);
            assert.equal(await repository.existsByMessageId('telegram:10:100#0'), false);
        });
    }
});
