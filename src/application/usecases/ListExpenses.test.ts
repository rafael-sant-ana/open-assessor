import assert from 'node:assert/strict';
import { beforeEach, describe, it } from 'node:test';
import type { Expense } from '../../domain/expenses/Expense.js';
import InMemoryExpenseRepository from '../../infrastructure/expenses/InMemoryExpenseRepository.js';
import ListExpenses from './ListExpenses.js';

const expense = (overrides: Partial<Expense>): Expense => ({
    date: '2026-10-01',
    amountCents: 1000,
    currency: 'BRL',
    description: 'x',
    category: 'outros',
    userId: 'telegram:1',
    messageKey: `key-${Math.random()}`,
    createdAt: '2026-10-01T12:00:00.000Z',
    ...overrides,
});

describe('ListExpenses', () => {
    let repository: InMemoryExpenseRepository;
    let listExpenses: ListExpenses;

    beforeEach(async () => {
        repository = new InMemoryExpenseRepository();
        listExpenses = new ListExpenses(repository);

        await repository.add(expense({ date: '2026-10-01', amountCents: 5000, category: 'alimentacao' }));
        await repository.add(expense({ date: '2026-10-15', amountCents: 2000, category: 'transporte' }));
        await repository.add(expense({ date: '2026-11-01', amountCents: 9900 }));
        await repository.add(expense({ userId: 'telegram:2', amountCents: 7700 }));
    });

    it('lists the user expenses in the inclusive range with a summary', async () => {
        const result = await listExpenses.execute({
            userId: 'telegram:1',
            from: '2026-10-01',
            to: '2026-10-15',
        });

        assert.equal(result.status, 'ok');
        if (result.status !== 'ok') return;
        assert.equal(result.expenses.length, 2);
        assert.deepEqual(result.summary, {
            count: 2,
            totalCents: 7000,
            byCategory: { alimentacao: 5000, transporte: 2000 },
        });
    });

    it('filters by category', async () => {
        const result = await listExpenses.execute({
            userId: 'telegram:1',
            from: '2026-10-01',
            to: '2026-10-31',
            category: 'transporte',
        });

        assert.equal(result.status === 'ok' && result.summary.totalCents, 2000);
    });

    it('returns an empty summary when nothing matches', async () => {
        const result = await listExpenses.execute({
            userId: 'telegram:1',
            from: '2025-01-01',
            to: '2025-01-31',
        });

        assert.equal(result.status === 'ok' && result.summary.count, 0);
    });

    for (const [name, overrides, reason] of [
        ['a malformed from', { from: '01/10/2026' }, /YYYY-MM-DD/],
        ['an impossible to', { to: '2026-02-30' }, /YYYY-MM-DD/],
        ['a missing from', { from: undefined }, /YYYY-MM-DD/],
        ['from after to', { from: '2026-10-31', to: '2026-10-01' }, /after/],
        ['an unknown category', { category: 'viagem' }, /category/],
    ] as const) {
        it(`rejects ${name}`, async () => {
            const result = await listExpenses.execute({
                userId: 'telegram:1',
                from: '2026-10-01',
                to: '2026-10-31',
                ...overrides,
            });

            assert.equal(result.status, 'invalid');
            assert.match(result.status === 'invalid' ? result.reason : '', reason);
        });
    }
});
