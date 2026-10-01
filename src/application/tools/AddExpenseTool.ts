import { CATEGORIES } from '../../domain/categories.js';
import { formatBRL } from '../../domain/expenses/money.js';
import type { Tool, ToolContext } from '../../providers/Tool.js';
import type AddExpense from '../usecases/AddExpense.js';

export default class AddExpenseTool implements Tool {
    readonly name = 'add_expense';
    readonly description =
        'Records one or more expenses the user just told you about (e.g. "gastei 50 no burger king"). ' +
        'Call it once with every expense mentioned in the message. ' +
        'Never guess a missing amount or description: ask the user instead of calling this tool. ' +
        'The result says what was saved, duplicated or rejected; confirm to the user what was saved.';
    readonly parameters = {
        type: 'object',
        properties: {
            expenses: {
                type: 'array',
                minItems: 1,
                items: {
                    type: 'object',
                    properties: {
                        amount: {
                            type: 'number',
                            description: 'Amount in BRL as a decimal number, e.g. 50.9.',
                        },
                        description: {
                            type: 'string',
                            description: 'What was bought, as written by the user.',
                        },
                        category: { type: 'string', enum: [...CATEGORIES] },
                        date: {
                            type: 'string',
                            description:
                                'Day of the expense as YYYY-MM-DD. Omit it when the expense is from today.',
                        },
                    },
                    required: ['amount', 'description', 'category'],
                },
            },
        },
        required: ['expenses'],
    };

    constructor(private readonly addExpense: AddExpense) {}

    async execute(
        args: Record<string, unknown>,
        context: ToolContext,
    ): Promise<string> {
        const { expenses } = args;
        if (!Array.isArray(expenses) || expenses.length === 0)
            return JSON.stringify({
                results: [
                    { status: 'invalid', reason: 'expenses must be a non-empty array' },
                ],
            });

        const results = [];
        for (const [index, item] of expenses.entries()) {
            const fields = isRecord(item) ? item : {};
            const result = await this.addExpense.execute({
                userId: context.userId,
                // One message may hold several expenses; the index keeps their keys apart
                // while a replay of the same message still deduplicates each one.
                messageKey: `${context.messageKey}#${index}`,
                amount: fields.amount,
                description: fields.description,
                category: fields.category,
                date: fields.date,
            });

            results.push(
                result.status === 'saved'
                    ? {
                          status: 'saved',
                          date: result.expense.date,
                          amount: formatBRL(result.expense.amountCents),
                          description: result.expense.description,
                          category: result.expense.category,
                      }
                    : result,
            );
        }

        return JSON.stringify({ results });
    }
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
}
