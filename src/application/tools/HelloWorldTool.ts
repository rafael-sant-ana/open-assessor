import type { Tool } from '../../providers/Tool.js';

export default class HelloWorldTool implements Tool {
    readonly name = 'hello_world';
    readonly description =
        'Greets the user. Call it every time the user says "hello world" or something similar ' +
        '(e.g. "olá mundo", "hello, world"). If the user also says a name, pass it as `name`. ' +
        'Reply to the user with exactly the text this tool returns, without rephrasing or translating it.';
    readonly parameters = {
        type: 'object',
        properties: {
            name: {
                type: 'string',
                description: 'Who to greet. Omit to greet the world.',
            },
        },
    };

    async execute(args: Record<string, unknown>): Promise<string> {
        const name =
            typeof args.name === 'string' && args.name.trim()
                ? args.name.trim()
                : 'World';
        return `Hello, ${name}! (sent by the hello_world tool)`;
    }
}
