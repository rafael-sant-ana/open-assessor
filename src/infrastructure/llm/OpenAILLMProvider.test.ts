import assert from 'node:assert/strict';
import { afterEach, beforeEach, describe, it, mock } from 'node:test';
import type OpenAI from 'openai';
import OpenAILLMProvider from './OpenAILLMProvider.js';
import { ctx, GreeterTool } from './testFixtures.js';
import type { Tool } from '../../providers/Tool.js';

type OutputItem = {
    type: string;
    name?: string;
    call_id?: string;
    arguments?: string;
};

const functionCall = (
    name: string,
    args: unknown,
    callId = 'call_1',
): OutputItem => ({
    type: 'function_call',
    name,
    call_id: callId,
    arguments: JSON.stringify(args),
});

function setup(outputs: OutputItem[][] = [], tools: Tool[] = []) {
    let counter = 0;
    const create = mock.fn(async (..._args: unknown[]) => ({
        id: `resp_${++counter}`,
        output: outputs.shift() ?? [],
        output_text: `reply ${counter}`,
    }));
    const client = { responses: { create } } as unknown as OpenAI;
    const requestAt = (n: number) =>
        create.mock.calls[n]!.arguments[0] as {
            model: string;
            input: any;
            previous_response_id?: string;
            tools?: Array<{ type: string; name: string; parameters: unknown }>;
        };

    return { provider: new OpenAILLMProvider(client, tools), requestAt };
}

describe('OpenAILLMProvider', () => {
    let originalKey: string | undefined;
    let originalModel: string | undefined;

    beforeEach(() => {
        originalKey = process.env.OPENAI_API_KEY;
        originalModel = process.env.OPENAI_MODEL;
        delete process.env.OPENAI_MODEL;
    });

    afterEach(() => {
        if (originalKey === undefined) delete process.env.OPENAI_API_KEY;
        else process.env.OPENAI_API_KEY = originalKey;
        if (originalModel === undefined) delete process.env.OPENAI_MODEL;
        else process.env.OPENAI_MODEL = originalModel;
    });

    it('throws when OPENAI_API_KEY is missing and no client is given', () => {
        delete process.env.OPENAI_API_KEY;

        assert.throws(() => new OpenAILLMProvider(), /OPENAI_API_KEY/);
    });

    it('returns the output text without a previous response id at first', async () => {
        const { provider, requestAt } = setup();

        assert.equal(await provider.generateResponse('chat', 'oi', ctx), 'reply 1');
        assert.equal(requestAt(0).input, 'oi');
        assert.equal('previous_response_id' in requestAt(0), false);
    });

    it('chains the previous response id on the next call', async () => {
        const { provider, requestAt } = setup();

        await provider.generateResponse('chat', 'q1', ctx);
        await provider.generateResponse('chat', 'q2', ctx);

        assert.equal(requestAt(1).previous_response_id, 'resp_1');
    });

    it('does not share response ids between chats', async () => {
        const { provider, requestAt } = setup();

        await provider.generateResponse('chat-a', 'a', ctx);
        await provider.generateResponse('chat-b', 'b', ctx);

        assert.equal('previous_response_id' in requestAt(1), false);
    });

    it('uses OPENAI_MODEL when set', async () => {
        const { provider, requestAt } = setup();

        process.env.OPENAI_MODEL = 'custom-model';
        await provider.generateResponse('chat', 'x', ctx);

        assert.equal(requestAt(0).model, 'custom-model');
    });

    describe('tools', () => {
        it('does not send a tools field when none are configured', async () => {
            const { provider, requestAt } = setup();

            await provider.generateResponse('chat', 'oi', ctx);

            assert.equal('tools' in requestAt(0), false);
        });

        it('runs the requested tool and sends its output back', async () => {
            const { provider, requestAt } = setup(
                [[functionCall('greet', { name: 'Rafa' })]],
                [new GreeterTool()],
            );

            const reply = await provider.generateResponse('chat', 'hello world', ctx);

            assert.equal(reply, 'reply 2');
            assert.equal(requestAt(0).tools?.[0]?.name, 'greet');
            assert.equal(requestAt(0).tools?.[0]?.type, 'function');
            assert.equal(requestAt(1).previous_response_id, 'resp_1');
            assert.deepEqual(requestAt(1).input, [
                {
                    type: 'function_call_output',
                    call_id: 'call_1',
                    output: 'Hello, Rafa!',
                },
            ]);
        });

        it('chains the next user message to the final response, not the tool round', async () => {
            const { provider, requestAt } = setup(
                [[functionCall('greet', {})]],
                [new GreeterTool()],
            );

            await provider.generateResponse('chat', 'hello world', ctx);
            await provider.generateResponse('chat', 'obrigado', ctx);

            assert.equal(requestAt(2).previous_response_id, 'resp_2');
        });

        it('tolerates malformed arguments', async () => {
            const { provider, requestAt } = setup(
                [
                    [
                        {
                            type: 'function_call',
                            name: 'greet',
                            call_id: 'c',
                            arguments: '{oops',
                        },
                    ],
                ],
                [new GreeterTool()],
            );

            await provider.generateResponse('chat', 'x', ctx);

            assert.equal(requestAt(1).input[0].output, 'Hello, World!');
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
            const { provider, requestAt } = setup(
                [[functionCall('broken', {})]],
                [broken],
            );

            assert.equal(
                await provider.generateResponse('chat', 'x', ctx),
                'reply 2',
            );
            assert.equal(requestAt(1).input[0].output, 'boom');
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
            const { provider } = setup([[functionCall('spy', {})]], [spy]);

            await provider.generateResponse('chat', 'x', ctx);

            assert.deepEqual(seen, [ctx]);
        });

        it('gives up after too many tool rounds', async () => {
            const { provider } = setup(
                Array.from({ length: 10 }, () => [
                    functionCall('greet', {}),
                ]),
                [new GreeterTool()],
            );

            await assert.rejects(
                provider.generateResponse('chat', 'x', ctx),
                /tool rounds/,
            );
        });
    });
});
