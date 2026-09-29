import assert from 'node:assert/strict';
import { afterEach, beforeEach, describe, it, mock } from 'node:test';
import type { GoogleGenAI } from '@google/genai';
import GeminiLLMProvider from './GeminiLLMProvider.js';

function setup(...replies: Array<string | undefined>) {
    const sendMessage = mock.fn(async (..._args: unknown[]) => ({
        text: replies.length ? replies.shift() : 'ok',
    }));
    const createChat = mock.fn((..._args: unknown[]) => ({ sendMessage }));
    const client = { chats: { create: createChat } } as unknown as GoogleGenAI;

    return {
        provider: new GeminiLLMProvider(client),
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

        assert.equal(await provider.generateResponse('chat', 'oi'), 'olá');
        assert.deepEqual(sendMessage.mock.calls[0]!.arguments[0], {
            message: 'oi',
        });
    });

    it('reuses the same chat for the same chatId', async () => {
        const { provider, createChat } = setup();

        await provider.generateResponse('chat', 'q1');
        await provider.generateResponse('chat', 'q2');

        assert.equal(createChat.mock.callCount(), 1);
    });

    it('creates a separate chat per chatId', async () => {
        const { provider, createChat } = setup();

        await provider.generateResponse('chat-a', 'a');
        await provider.generateResponse('chat-b', 'b');

        assert.equal(createChat.mock.callCount(), 2);
    });

    it('uses GEMINI_MODEL when set', async () => {
        const { provider, createChat } = setup();

        process.env.GEMINI_MODEL = 'custom-model';
        await provider.generateResponse('chat', 'x');

        const config = createChat.mock.calls[0]!.arguments[0] as {
            model: string;
        };
        assert.equal(config.model, 'custom-model');
    });

    it('throws when the reply is empty', async () => {
        const { provider } = setup(undefined);

        await assert.rejects(
            provider.generateResponse('chat', 'x'),
            /empty body/,
        );
    });
});
