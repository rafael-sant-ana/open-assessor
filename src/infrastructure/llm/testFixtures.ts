import type { Tool, ToolContext } from '../../providers/Tool.js';

/** Fixture shared by the LLM provider tests. */
export const ctx: ToolContext = {
    userId: 'telegram:1',
    messageKey: 'telegram:10:100',
};

/** Minimal tool with an optional argument, used to exercise the providers' tool loops. */
export class GreeterTool implements Tool {
    readonly name = 'greet';
    readonly description = 'Greets someone.';
    readonly parameters = {
        type: 'object',
        properties: { name: { type: 'string' } },
    };

    async execute(args: Record<string, unknown>): Promise<string> {
        return `Hello, ${typeof args.name === 'string' ? args.name : 'World'}!`;
    }
}
