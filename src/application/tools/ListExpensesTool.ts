import { CATEGORIES } from '../../domain/categories.js';
import { formatBRL } from '../../domain/expenses/money.js';
import type { Tool, ToolContext } from '../../providers/Tool.js';
import type ListExpenses from '../usecases/ListExpenses.js';

/** Items returned to the model; the summary always covers the whole period. */
export const MAX_LISTED_EXPENSES = 50;

export default class ListExpensesTool implements Tool {
    readonly name = 'list_expenses';
    readonly description =
        'Looks up the user\'s recorded expenses in a period and returns the total, the total per category and the expenses. ' +
        'Call it when the user asks how much they spent (e.g. "quanto gastei esse mês?"). ' +
        'Work out `from` and `to` from the date returned by get_current_date. Both days are included.';
    readonly parameters = {
        type: 'object',
        properties: {
            from: { type: 'string', description: 'First day, YYYY-MM-DD.' },
            to: { type: 'string', description: 'Last day, YYYY-MM-DD.' },
            category: {
                type: 'string',
                enum: [...CATEGORIES],
                description: 'Only expenses of this category. Omit for all.',
            },
        },
        required: ['from', 'to'],
    };

    constructor(private readonly listExpenses: ListExpenses) {}

    async execute(
        args: Record<string, unknown>,
        context: ToolContext,
    ): Promise<string> {
        const result = await this.listExpenses.execute({
            userId: context.userId,
            from: args.from,
            to: args.to,
            category: args.category,
        });

        if (result.status === 'invalid') return JSON.stringify(result);

        const { expenses, summary } = result;
        return JSON.stringify({
            status: 'ok',
            from: args.from,
            to: args.to,
            count: summary.count,
            total: formatBRL(summary.totalCents),
            byCategory: Object.fromEntries(
                Object.entries(summary.byCategory).map(([category, cents]) => [
                    category,
                    formatBRL(cents),
                ]),
            ),
            expenses: expenses.slice(0, MAX_LISTED_EXPENSES).map((e) => ({
                date: e.date,
                amount: formatBRL(e.amountCents),
                description: e.description,
                category: e.category,
            })),
            truncated: expenses.length > MAX_LISTED_EXPENSES,
        });
    }
}
