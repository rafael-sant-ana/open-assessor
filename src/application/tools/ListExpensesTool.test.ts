import assert from 'node:assert/strict';
import { beforeEach, describe, it } from 'node:test';
import { Expense, type ExpenseProps } from '../../domain/expenses/Expense.js';
import InMemoryExpenseRepository from '../../infrastructure/expenses/InMemoryExpenseRepository.js';
import type { ToolContext } from '../../providers/Tool.js';
import ListExpenses from '../usecases/ListExpenses.js';
import ListExpensesTool, { MAX_LISTED_EXPENSES } from './ListExpensesTool.js';

const context: ToolContext = {
    userId: 'telegram:1',
    messageKey: 'telegram:10:100',
};

const expense = (i: number, overrides: Partial<ExpenseProps> = {}) => new Expense({
    date: '2026-10-01',
    amountCents: 1000,
    description: `item ${i}`,
    category: 'outros',
    userId: 'telegram:1',
    messageKey: `key-${i}`,
    createdAt: '2026-10-01T12:00:00.000Z',
    ...overrides,
});

describe('ListExpensesTool', () => {
    let repository: InMemoryExpenseRepository;
    let tool: ListExpensesTool;

    const run = async (args: Record<string, unknown>) =>
        JSON.parse(await tool.execute(args, context)) as Record<string, any>;

    beforeEach(() => {
        repository = new InMemoryExpenseRepository();
        tool = new ListExpensesTool(new ListExpenses(repository));
    });

    it('returns formatted totals, per-category totals and the expenses', async () => {
        await repository.add(expense(1, { amountCents: 5000, category: 'alimentacao' }));
        await repository.add(expense(2, { amountCents: 2090, category: 'transporte' }));
        await repository.add(expense(3, { userId: 'telegram:2', amountCents: 9999 }));

        const result = await run({ from: '2026-10-01', to: '2026-10-31' });

        assert.equal(result.status, 'ok');
        assert.equal(result.count, 2);
        assert.equal(result.total, 'R$ 70,90');
        assert.deepEqual(result.byCategory, {
            alimentacao: 'R$ 50,00',
            transporte: 'R$ 20,90',
        });
        assert.deepEqual(result.expenses[0], {
            date: '2026-10-01',
            amount: 'R$ 50,00',
            description: 'item 1',
            category: 'alimentacao',
        });
        assert.equal(result.truncated, false);
    });

    it('caps the listed expenses but summarizes all of them', async () => {
        for (let i = 0; i < MAX_LISTED_EXPENSES + 5; i++)
            await repository.add(expense(i));

        const result = await run({ from: '2026-10-01', to: '2026-10-31' });

        assert.equal(result.expenses.length, MAX_LISTED_EXPENSES);
        assert.equal(result.count, MAX_LISTED_EXPENSES + 5);
        assert.equal(result.truncated, true);
    });

    it('passes the category filter through', async () => {
        await repository.add(expense(1, { category: 'lazer' }));
        await repository.add(expense(2, { category: 'outros' }));

        const result = await run({
            from: '2026-10-01',
            to: '2026-10-31',
            category: 'lazer',
        });

        assert.equal(result.count, 1);
    });

    it('reports invalid arguments to the model', async () => {
        const result = await run({ from: 'ontem', to: '2026-10-31' });

        assert.equal(result.status, 'invalid');
        assert.match(result.reason, /YYYY-MM-DD/);
    });
});
