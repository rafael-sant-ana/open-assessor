import assert from 'node:assert/strict';
import { afterEach, beforeEach, describe, it, mock } from 'node:test';
import type Anthropic from '@anthropic-ai/sdk';
import ClaudeLLMProvider from './ClaudeLLMProvider.js';

type Block = { type: string; text?: string };

function setup(...replies: Array<Block[] | Error>) {
    const create = mock.fn(async (..._args: unknown[]) => {
        const reply = replies.shift() ?? [{ type: 'text', text: 'ok' }];
        if (reply instanceof Error) throw reply;
        return { content: reply };
    });
    const client = { messages: { create } } as unknown as Anthropic;
    const requestAt = (n: number) =>
        create.mock.calls[n]!.arguments[0] as {
            model: string;
            messages: Array<{ role: string; content: string }>;
        };

    return { provider: new ClaudeLLMProvider(client), create, requestAt };
}

const text = (t: string): Block[] => [{ type: 'text', text: t }];

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

        assert.equal(await provider.generateResponse('chat', 'oi'), 'olá');
        assert.deepEqual(requestAt(0).messages, [
            { role: 'user', content: 'oi' },
        ]);
    });

    it('sends the previous turns on the next call', async () => {
        const { provider, requestAt } = setup(text('a1'), text('a2'));

        await provider.generateResponse('chat', 'q1');
        await provider.generateResponse('chat', 'q2');

        assert.deepEqual(requestAt(1).messages, [
            { role: 'user', content: 'q1' },
            { role: 'assistant', content: 'a1' },
            { role: 'user', content: 'q2' },
        ]);
    });

    it('keeps conversations isolated per chat', async () => {
        const { provider, requestAt } = setup(text('a1'), text('b1'));

        await provider.generateResponse('chat-a', 'from a');
        await provider.generateResponse('chat-b', 'from b');

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

        assert.equal(await provider.generateResponse('chat', 'x'), 'foobar');
    });

    it('throws on an empty reply without storing the turn', async () => {
        const { provider, requestAt } = setup([], text('fine'));

        await assert.rejects(
            provider.generateResponse('chat', 'lost'),
            /empty body/,
        );
        await provider.generateResponse('chat', 'next');

        assert.deepEqual(requestAt(1).messages, [
            { role: 'user', content: 'next' },
        ]);
    });

    it('does not store the turn when the API call fails', async () => {
        const { provider, requestAt } = setup(new Error('429'), text('fine'));

        await assert.rejects(provider.generateResponse('chat', 'lost'), /429/);
        await provider.generateResponse('chat', 'next');

        assert.deepEqual(requestAt(1).messages, [
            { role: 'user', content: 'next' },
        ]);
    });

    it('caps history at 20 messages and starts on a user turn', async () => {
        const { provider, requestAt } = setup();

        for (let i = 0; i < 12; i++)
            await provider.generateResponse('chat', `q${i}`);
        await provider.generateResponse('chat', 'last');

        const { messages } = requestAt(12);
        // 20 stored messages + the new user message
        assert.equal(messages.length, 21);
        assert.equal(messages[0]!.role, 'user');
        assert.equal(messages.at(-1)!.content, 'last');
    });

    it('uses ANTHROPIC_MODEL when set and a default otherwise', async () => {
        const { provider, requestAt } = setup();

        await provider.generateResponse('chat', 'a');
        process.env.ANTHROPIC_MODEL = 'custom-model';
        await provider.generateResponse('chat', 'b');

        assert.equal(requestAt(0).model, 'claude-haiku-4-5-20251001');
        assert.equal(requestAt(1).model, 'custom-model');
    });
});
