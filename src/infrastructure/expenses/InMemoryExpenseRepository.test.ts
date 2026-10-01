import assert from 'node:assert/strict';
import { beforeEach, describe, it } from 'node:test';
import type { Expense } from '../../domain/expenses/Expense.js';
import InMemoryExpenseRepository from './InMemoryExpenseRepository.js';

const expense = (overrides: Partial<Expense> = {}): Expense => ({
    date: '2026-10-01',
    amountCents: 5000,
    currency: 'BRL',
    description: 'burger king',
    category: 'alimentacao',
    userId: 'telegram:1',
    messageKey: 'telegram:100',
    createdAt: '2026-10-01T12:00:00.000Z',
    ...overrides,
});

describe('InMemoryExpenseRepository', () => {
    let repo: InMemoryExpenseRepository;

    beforeEach(() => {
        repo = new InMemoryExpenseRepository();
    });

    it('reports whether a message key was already saved', async () => {
        assert.equal(await repo.existsByMessageId('telegram:100'), false);
        await repo.add(expense());
        assert.equal(await repo.existsByMessageId('telegram:100'), true);
    });

    it('removes and returns the last expense of the given user only', async () => {
        const first = expense({ messageKey: 'telegram:1' });
        const last = expense({ messageKey: 'telegram:2' });
        const other = expense({ userId: 'telegram:2', messageKey: 'telegram:3' });
        await repo.add(first);
        await repo.add(last);
        await repo.add(other);

        assert.deepEqual(await repo.removeLastBy('telegram:1'), last);
        assert.equal(await repo.existsByMessageId('telegram:2'), false);
        assert.equal(await repo.existsByMessageId('telegram:3'), true);
        assert.deepEqual(await repo.removeLastBy('telegram:1'), first);
    });

    it('returns null when the user has nothing to remove', async () => {
        assert.equal(await repo.removeLastBy('telegram:1'), null);
    });

    it('lists by user within an inclusive date range', async () => {
        const a = expense({ date: '2026-10-01', messageKey: 'telegram:1' });
        const b = expense({ date: '2026-10-15', messageKey: 'telegram:2' });
        const outside = expense({ date: '2026-11-01', messageKey: 'telegram:3' });
        const other = expense({ userId: 'telegram:2', messageKey: 'telegram:4' });
        for (const e of [a, b, outside, other]) await repo.add(e);

        const result = await repo.listBy('telegram:1', { from: '2026-10-01', to: '2026-10-15' });

        assert.deepEqual(result, [a, b]);
    });
});
