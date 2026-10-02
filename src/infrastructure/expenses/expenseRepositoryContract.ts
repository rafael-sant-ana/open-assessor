import assert from 'node:assert/strict';
import { beforeEach, describe, it } from 'node:test';
import { Expense, type ExpenseProps } from '../../domain/expenses/Expense.js';
import type { ExpenseRepository } from '../../providers/ExpenseRepository.js';

const expense = (overrides: Partial<ExpenseProps> = {}) => new Expense({
    date: '2026-10-01',
    amountCents: 5090,
    description: 'burger king',
    category: 'alimentacao',
    userId: 'telegram:1',
    messageKey: 'telegram:10:100#0',
    createdAt: '2026-10-01T12:00:00.000Z',
    ...overrides,
});

/** Behavior every `ExpenseRepository` implementation must honour. */
export function expenseRepositoryContract(
    name: string,
    create: () => ExpenseRepository | Promise<ExpenseRepository>,
): void {
    describe(`${name} (ExpenseRepository contract)`, () => {
        let repo: ExpenseRepository;

        beforeEach(async () => {
            repo = await create();
        });

        it('round-trips an expense exactly', async () => {
            const saved = expense({ date: '2026-02-28', amountCents: 1999 });
            await repo.add(saved);

            assert.deepEqual(
                await repo.listBy('telegram:1', { from: '2026-02-01', to: '2026-02-28' }),
                [saved],
            );
        });

        it('reports whether a message key was already saved', async () => {
            assert.equal(await repo.existsByMessageId('telegram:10:100#0'), false);
            await repo.add(expense());
            assert.equal(await repo.existsByMessageId('telegram:10:100#0'), true);
        });

        it('ignores a second add with the same message key', async () => {
            await repo.add(expense({ amountCents: 5000 }));
            await repo.add(expense({ amountCents: 9999 }));

            const found = await repo.listBy('telegram:1', { from: '2026-01-01', to: '2026-12-31' });
            assert.equal(found.length, 1);
            assert.equal(found[0]!.amountCents, 5000);
        });

        it('keeps text that looks like a formula or a number as text', async () => {
            const tricky = expense({ description: '=HYPERLINK("http://x","y")' });
            const numeric = expense({ description: '50', messageKey: 'telegram:10:101#0' });
            await repo.add(tricky);
            await repo.add(numeric);

            const found = await repo.listBy('telegram:1', { from: '2026-10-01', to: '2026-10-01' });
            assert.deepEqual(found, [tricky, numeric]);
        });

        it('removes and returns the last expense of the given user only', async () => {
            const first = expense({ messageKey: 'telegram:10:1#0' });
            const last = expense({ messageKey: 'telegram:10:2#0' });
            const other = expense({ userId: 'telegram:2', messageKey: 'telegram:10:3#0' });
            await repo.add(first);
            await repo.add(last);
            await repo.add(other);

            assert.deepEqual(await repo.removeLastBy('telegram:1'), last);
            assert.equal(await repo.existsByMessageId('telegram:10:2#0'), false);
            assert.equal(await repo.existsByMessageId('telegram:10:3#0'), true);
            assert.deepEqual(await repo.removeLastBy('telegram:1'), first);
        });

        it('allows re-adding an expense after it was removed', async () => {
            await repo.add(expense());
            await repo.removeLastBy('telegram:1');
            await repo.add(expense());

            assert.equal(await repo.existsByMessageId('telegram:10:100#0'), true);
        });

        it('returns null when the user has nothing to remove', async () => {
            assert.equal(await repo.removeLastBy('telegram:1'), null);
        });

        it('lists by user within an inclusive date range', async () => {
            const a = expense({ date: '2026-10-01', messageKey: 'telegram:10:1#0' });
            const b = expense({ date: '2026-10-15', messageKey: 'telegram:10:2#0' });
            const outside = expense({ date: '2026-11-01', messageKey: 'telegram:10:3#0' });
            const other = expense({ userId: 'telegram:2', messageKey: 'telegram:10:4#0' });
            for (const e of [a, b, outside, other]) await repo.add(e);

            assert.deepEqual(
                await repo.listBy('telegram:1', { from: '2026-10-01', to: '2026-10-15' }),
                [a, b],
            );
        });
    });
}
