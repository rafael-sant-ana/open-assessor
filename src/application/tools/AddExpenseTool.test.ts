import assert from 'node:assert/strict';
import { beforeEach, describe, it } from 'node:test';
import InMemoryExpenseRepository from '../../infrastructure/expenses/InMemoryExpenseRepository.js';
import type { ToolContext } from '../../providers/Tool.js';
import AddExpense from '../usecases/AddExpense.js';
import AddExpenseTool from './AddExpenseTool.js';

const NOW = new Date('2026-10-01T15:00:00Z');
const context: ToolContext = {
    userId: 'telegram:1',
    messageKey: 'telegram:10:100',
};

describe('AddExpenseTool', () => {
    let repository: InMemoryExpenseRepository;
    let tool: AddExpenseTool;

    const run = async (args: Record<string, unknown>, ctx = context) =>
        JSON.parse(await tool.execute(args, ctx)) as {
            results: Array<Record<string, unknown>>;
        };

    beforeEach(() => {
        repository = new InMemoryExpenseRepository();
        tool = new AddExpenseTool(new AddExpense(repository, () => NOW));
    });

    it('exposes the categories as an enum in its schema', () => {
        const schema = tool.parameters as any;

        assert.ok(schema.properties.expenses.items.properties.category.enum.includes('alimentacao'));
    });

    it('saves an expense for the context user and reports it', async () => {
        const { results } = await run({
            expenses: [{ amount: 50, description: 'burger king', category: 'alimentacao' }],
        });

        assert.deepEqual(results, [
            {
                status: 'saved',
                date: '2026-10-01',
                amount: 'R$ 50,00',
                description: 'burger king',
                category: 'alimentacao',
            },
        ]);
        const saved = await repository.listBy('telegram:1', { from: '2026-10-01', to: '2026-10-01' });
        assert.equal(saved[0]!.messageKey, 'telegram:10:100#0');
    });

    it('saves several expenses from one message under distinct keys', async () => {
        const { results } = await run({
            expenses: [
                { amount: 20, description: 'uber', category: 'transporte' },
                { amount: 30, description: 'almoço', category: 'alimentacao' },
            ],
        });

        assert.deepEqual(results.map((r) => r.status), ['saved', 'saved']);
        assert.equal(await repository.existsByMessageId('telegram:10:100#0'), true);
        assert.equal(await repository.existsByMessageId('telegram:10:100#1'), true);
    });

    it('reports a replayed message as duplicate instead of saving again', async () => {
        const args = {
            expenses: [{ amount: 20, description: 'uber', category: 'transporte' }],
        };

        await run(args);
        const { results } = await run(args);

        assert.deepEqual(results, [{ status: 'duplicate' }]);
    });

    it('reports invalid items without blocking the valid ones', async () => {
        const { results } = await run({
            expenses: [
                { amount: 'muito', description: 'uber', category: 'transporte' },
                { amount: 30, description: 'almoço', category: 'alimentacao' },
            ],
        });

        assert.equal(results[0]!.status, 'invalid');
        assert.equal(results[1]!.status, 'saved');
    });

    for (const [name, args] of [
        ['a missing expenses field', {}],
        ['an empty list', { expenses: [] }],
        ['a non-array', { expenses: 'gastei 50' }],
    ] as const) {
        it(`rejects ${name}`, async () => {
            const { results } = await run(args);

            assert.equal(results[0]!.status, 'invalid');
        });
    }

    it('treats a non-object item as invalid', async () => {
        const { results } = await run({ expenses: ['50'] });

        assert.equal(results[0]!.status, 'invalid');
    });
});
