import assert from 'node:assert/strict';
import { afterEach, beforeEach, describe, it, mock } from 'node:test';
import type { GoogleGenAI } from '@google/genai';
import GeminiLLMProvider from './GeminiLLMProvider.js';
import { ctx, GreeterTool } from './testFixtures.js';
import type { Tool } from '../../providers/Tool.js';

type Reply =
    | string
    | undefined
    | { functionCalls: Array<{ id?: string; name: string; args?: unknown }> };

const call = (name: string, args: unknown = {}, id = 'fc_1'): Reply => ({
    functionCalls: [{ id, name, args }],
});

function setup(...replies: Reply[]) {
    return setupWithTools([], ...replies);
}

function setupWithTools(tools: Tool[], ...replies: Reply[]) {
    const sendMessage = mock.fn(async (..._args: unknown[]) => {
        const reply = replies.length ? replies.shift() : 'ok';
        return typeof reply === 'object'
            ? { text: undefined, functionCalls: reply.functionCalls }
            : { text: reply, functionCalls: undefined };
    });
    const createChat = mock.fn((..._args: unknown[]) => ({ sendMessage }));
    const client = { chats: { create: createChat } } as unknown as GoogleGenAI;

    return {
        provider: new GeminiLLMProvider(client, tools),
        sendMessage,
        createChat,
    };
}

describe('GeminiLLMProvider', () => {
    let originalKey: string | undefined;
    let originalModel: string | undefined;

    beforeEach(() => {
        originalKey = process.env.GEMINI_API_KEY;
        originalModel = process.env.GEMINI_MODEL;
        delete process.env.GEMINI_MODEL;
    });

    afterEach(() => {
        if (originalKey === undefined) delete process.env.GEMINI_API_KEY;
        else process.env.GEMINI_API_KEY = originalKey;
        if (originalModel === undefined) delete process.env.GEMINI_MODEL;
        else process.env.GEMINI_MODEL = originalModel;
    });

    it('throws when GEMINI_API_KEY is missing and no client is given', () => {
        delete process.env.GEMINI_API_KEY;

        assert.throws(() => new GeminiLLMProvider(), /GEMINI_API_KEY/);
    });

    it('sends the message and returns the reply text', async () => {
        const { provider, sendMessage } = setup('olá');

        assert.equal(await provider.generateResponse('chat', 'oi', ctx), 'olá');
        assert.deepEqual(sendMessage.mock.calls[0]!.arguments[0], {
            message: 'oi',
        });
    });

    it('reuses the same chat for the same chatId', async () => {
        const { provider, createChat } = setup();

        await provider.generateResponse('chat', 'q1', ctx);
        await provider.generateResponse('chat', 'q2', ctx);

        assert.equal(createChat.mock.callCount(), 1);
    });

    it('creates a separate chat per chatId', async () => {
        const { provider, createChat } = setup();

        await provider.generateResponse('chat-a', 'a', ctx);
        await provider.generateResponse('chat-b', 'b', ctx);

        assert.equal(createChat.mock.callCount(), 2);
    });

    it('uses GEMINI_MODEL when set', async () => {
        const { provider, createChat } = setup();

        process.env.GEMINI_MODEL = 'custom-model';
        await provider.generateResponse('chat', 'x', ctx);

        const config = createChat.mock.calls[0]!.arguments[0] as {
            model: string;
        };
        assert.equal(config.model, 'custom-model');
    });

    it('throws when the reply is empty', async () => {
        const { provider } = setup(undefined);

        await assert.rejects(
            provider.generateResponse('chat', 'x', ctx),
            /empty body/,
        );
    });

    describe('tools', () => {
        it('does not declare tools when none are configured', async () => {
            const { provider, createChat } = setup();

            await provider.generateResponse('chat', 'oi', ctx);

            const { config } = createChat.mock.calls[0]!.arguments[0] as {
                config: Record<string, unknown>;
            };
            assert.equal('tools' in config, false);
        });

        it('declares tools and sends the function response back', async () => {
            const { provider, createChat, sendMessage } = setupWithTools(
                [new GreeterTool()],
                call('greet', { name: 'Rafa' }),
                'Olá, Rafa!',
            );

            const reply = await provider.generateResponse('chat', 'hello world', ctx);

            assert.equal(reply, 'Olá, Rafa!');
            const { config } = createChat.mock.calls[0]!.arguments[0] as {
                config: {
                    tools: Array<{
                        functionDeclarations: Array<{ name: string }>;
                    }>;
                };
            };
            assert.equal(
                config.tools[0]!.functionDeclarations[0]!.name,
                'greet',
            );
            assert.deepEqual(sendMessage.mock.calls[1]!.arguments[0], {
                message: [
                    {
                        functionResponse: {
                            id: 'fc_1',
                            name: 'greet',
                            response: { output: 'Hello, Rafa!' },
                        },
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
            const { provider, sendMessage } = setupWithTools(
                [broken],
                call('broken'),
                'desculpe',
            );

            assert.equal(
                await provider.generateResponse('chat', 'x', ctx),
                'desculpe',
            );
            const sent = sendMessage.mock.calls[1]!.arguments[0] as {
                message: Array<{ functionResponse: { response: unknown } }>;
            };
            assert.deepEqual(sent.message[0]!.functionResponse.response, {
                error: 'boom',
            });
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
            const { provider } = setupWithTools([spy], call('spy'), 'ok');

            await provider.generateResponse('chat', 'x', ctx);

            assert.deepEqual(seen, [ctx]);
        });

        it('gives up after too many tool rounds', async () => {
            const { provider } = setupWithTools(
                [new GreeterTool()],
                ...Array.from({ length: 10 }, () => call('greet')),
            );

            await assert.rejects(
                provider.generateResponse('chat', 'x', ctx),
                /tool rounds/,
            );
        });
    });
});
