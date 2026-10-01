import assert from 'node:assert/strict';
import { afterEach, beforeEach, describe, it, mock } from 'node:test';
import type Anthropic from '@anthropic-ai/sdk';
import ClaudeLLMProvider from './ClaudeLLMProvider.js';
import { ctx, GreeterTool } from './testFixtures.js';
import type { Tool } from '../../providers/Tool.js';

type Block = {
    type: string;
    text?: string;
    id?: string;
    name?: string;
    input?: unknown;
};

function setup(...replies: Array<Block[] | Error>) {
    return setupWithTools([], ...replies);
}

function setupWithTools(
    tools: Tool[],
    ...replies: Array<Block[] | Error>
) {
    const create = mock.fn(async (..._args: unknown[]) => {
        const reply = replies.shift() ?? [{ type: 'text', text: 'ok' }];
        if (reply instanceof Error) throw reply;
        return { content: reply };
    });
    const client = { messages: { create } } as unknown as Anthropic;
    const requestAt = (n: number) =>
        create.mock.calls[n]!.arguments[0] as {
            model: string;
            messages: Array<{ role: string; content: any }>;
            tools?: Array<{ name: string; input_schema: unknown }>;
        };

    return {
        provider: new ClaudeLLMProvider(client, tools),
        create,
        requestAt,
    };
}

const text = (t: string): Block[] => [{ type: 'text', text: t }];
const toolUse = (name: string, input: unknown, id = 'tu_1'): Block[] => [
    { type: 'tool_use', id, name, input },
];

describe('ClaudeLLMProvider', () => {
    let originalKey: string | undefined;
    let originalModel: string | undefined;

    beforeEach(() => {
        originalKey = process.env.ANTHROPIC_API_KEY;
        originalModel = process.env.ANTHROPIC_MODEL;
        delete process.env.ANTHROPIC_MODEL;
    });

    afterEach(() => {
        if (originalKey === undefined) delete process.env.ANTHROPIC_API_KEY;
        else process.env.ANTHROPIC_API_KEY = originalKey;
        if (originalModel === undefined) delete process.env.ANTHROPIC_MODEL;
        else process.env.ANTHROPIC_MODEL = originalModel;
    });

    it('throws when ANTHROPIC_API_KEY is missing and no client is given', () => {
        delete process.env.ANTHROPIC_API_KEY;

        assert.throws(() => new ClaudeLLMProvider(), /ANTHROPIC_API_KEY/);
    });

    it('returns the reply text and sends the user message', async () => {
        const { provider, requestAt } = setup(text('olá'));

        assert.equal(await provider.generateResponse('chat', 'oi', ctx), 'olá');
        assert.deepEqual(requestAt(0).messages, [
            { role: 'user', content: 'oi' },
        ]);
    });

    it('sends the previous turns on the next call', async () => {
        const { provider, requestAt } = setup(text('a1'), text('a2'));

        await provider.generateResponse('chat', 'q1', ctx);
        await provider.generateResponse('chat', 'q2', ctx);

        assert.deepEqual(requestAt(1).messages, [
            { role: 'user', content: 'q1' },
            { role: 'assistant', content: 'a1' },
            { role: 'user', content: 'q2' },
        ]);
    });

    it('keeps conversations isolated per chat', async () => {
        const { provider, requestAt } = setup(text('a1'), text('b1'));

        await provider.generateResponse('chat-a', 'from a', ctx);
        await provider.generateResponse('chat-b', 'from b', ctx);

        assert.deepEqual(requestAt(1).messages, [
            { role: 'user', content: 'from b' },
        ]);
    });

    it('joins text blocks and ignores other block types', async () => {
        const { provider } = setup([
            { type: 'text', text: 'foo' },
            { type: 'thinking' },
            { type: 'text', text: 'bar' },
        ]);

        assert.equal(await provider.generateResponse('chat', 'x', ctx), 'foobar');
    });

    it('throws on an empty reply without storing the turn', async () => {
        const { provider, requestAt } = setup([], text('fine'));

        await assert.rejects(
            provider.generateResponse('chat', 'lost', ctx),
            /empty body/,
        );
        await provider.generateResponse('chat', 'next', ctx);

        assert.deepEqual(requestAt(1).messages, [
            { role: 'user', content: 'next' },
        ]);
    });

    it('does not store the turn when the API call fails', async () => {
        const { provider, requestAt } = setup(new Error('429'), text('fine'));

        await assert.rejects(provider.generateResponse('chat', 'lost', ctx), /429/);
        await provider.generateResponse('chat', 'next', ctx);

        assert.deepEqual(requestAt(1).messages, [
            { role: 'user', content: 'next' },
        ]);
    });

    it('caps history at 20 messages and starts on a user turn', async () => {
        const { provider, requestAt } = setup();

        for (let i = 0; i < 12; i++)
            await provider.generateResponse('chat', `q${i}`, ctx);
        await provider.generateResponse('chat', 'last', ctx);

        const { messages } = requestAt(12);
        // 20 stored messages + the new user message
        assert.equal(messages.length, 21);
        assert.equal(messages[0]!.role, 'user');
        assert.equal(messages.at(-1)!.content, 'last');
    });

    it('uses ANTHROPIC_MODEL when set and a default otherwise', async () => {
        const { provider, requestAt } = setup();

        await provider.generateResponse('chat', 'a', ctx);
        process.env.ANTHROPIC_MODEL = 'custom-model';
        await provider.generateResponse('chat', 'b', ctx);

        assert.equal(requestAt(0).model, 'claude-haiku-4-5-20251001');
        assert.equal(requestAt(1).model, 'custom-model');
    });
    describe('tools', () => {
        it('does not send a tools field when none are configured', async () => {
            const { provider, requestAt } = setup();

            await provider.generateResponse('chat', 'oi', ctx);

            assert.equal('tools' in requestAt(0), false);
        });

        it('runs the requested tool and returns the final reply', async () => {
            const { provider, requestAt } = setupWithTools(
                [new GreeterTool()],
                toolUse('greet', { name: 'Rafa' }),
                text('Olá, Rafa!'),
            );

            const reply = await provider.generateResponse('chat', 'hello world, sou o Rafa', ctx);

            assert.equal(reply, 'Olá, Rafa!');
            assert.equal(requestAt(1).tools?.[0]?.name, 'greet');
            const [, assistant, result] = requestAt(1).messages;
            assert.equal(assistant!.role, 'assistant');
            assert.deepEqual(result, {
                role: 'user',
                content: [
                    {
                        type: 'tool_result',
                        tool_use_id: 'tu_1',
                        content: 'Hello, Rafa!',
                    },
                ],
            });
        });

        it('reports a failing tool to the model instead of throwing', async () => {
            const broken: Tool = {
                name: 'broken',
                description: 'always fails',
                parameters: { type: 'object', properties: {} },
                execute: async () => {
                    throw new Error('boom');
                },
            };
            const { provider, requestAt } = setupWithTools(
                [broken],
                toolUse('broken', {}),
                text('desculpe'),
            );

            assert.equal(await provider.generateResponse('chat', 'x', ctx), 'desculpe');
            const result = requestAt(1).messages[2]!.content[0];
            assert.equal(result.is_error, true);
            assert.equal(result.content, 'boom');
        });

        it('reports an unknown tool to the model', async () => {
            const { provider, requestAt } = setupWithTools(
                [],
                toolUse('nope', {}),
                text('ok'),
            );

            await provider.generateResponse('chat', 'x', ctx);

            assert.equal(requestAt(1).messages[2]!.content[0].is_error, true);
        });

        it('passes the message context to the tool', async () => {
            const seen: unknown[] = [];
            const spy: Tool = {
                name: 'spy',
                description: 'records its context',
                parameters: { type: 'object', properties: {} },
                execute: async (_args, context) => {
                    seen.push(context);
                    return 'ok';
                },
            };
            const { provider } = setupWithTools([spy], toolUse('spy', {}), text('ok'));

            await provider.generateResponse('chat', 'x', ctx);

            assert.deepEqual(seen, [ctx]);
        });

        it('gives up after too many tool rounds', async () => {
            const { provider } = setupWithTools(
                [new GreeterTool()],
                ...Array.from({ length: 10 }, () => toolUse('greet', {})),
            );

            await assert.rejects(
                provider.generateResponse('chat', 'x', ctx),
                /tool rounds/,
            );
        });

        it('never starts the history on an orphaned tool_result', async () => {
            const { provider, requestAt, create } = setupWithTools(
                [new GreeterTool()],
                toolUse('greet', {}),
            );

            await provider.generateResponse('chat', 'hello world', ctx);
            for (let i = 0; i < 12; i++)
                await provider.generateResponse('chat', `q${i}`, ctx);

            for (let n = 0; n < create.mock.callCount(); n++) {
                const first = requestAt(n).messages[0]!;
                assert.equal(first.role, 'user');
                assert.equal(typeof first.content, 'string');
            }
        });
    });
});
