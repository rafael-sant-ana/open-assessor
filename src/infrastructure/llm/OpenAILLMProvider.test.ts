import assert from 'node:assert/strict';
import { afterEach, beforeEach, describe, it, mock } from 'node:test';
import type OpenAI from 'openai';
import OpenAILLMProvider from './OpenAILLMProvider.js';

function setup() {
    let counter = 0;
    const create = mock.fn(async (..._args: unknown[]) => ({
        id: `resp_${++counter}`,
        output_text: `reply ${counter}`,
    }));
    const client = { responses: { create } } as unknown as OpenAI;
    const requestAt = (n: number) =>
        create.mock.calls[n]!.arguments[0] as {
            model: string;
            input: string;
            previous_response_id?: string;
        };

    return { provider: new OpenAILLMProvider(client), requestAt };
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

        assert.equal(await provider.generateResponse('chat', 'oi'), 'reply 1');
        assert.equal(requestAt(0).input, 'oi');
        assert.equal('previous_response_id' in requestAt(0), false);
    });

    it('chains the previous response id on the next call', async () => {
        const { provider, requestAt } = setup();

        await provider.generateResponse('chat', 'q1');
        await provider.generateResponse('chat', 'q2');

        assert.equal(requestAt(1).previous_response_id, 'resp_1');
    });

    it('does not share response ids between chats', async () => {
        const { provider, requestAt } = setup();

        await provider.generateResponse('chat-a', 'a');
        await provider.generateResponse('chat-b', 'b');

        assert.equal('previous_response_id' in requestAt(1), false);
    });

    it('uses OPENAI_MODEL when set', async () => {
        const { provider, requestAt } = setup();

        process.env.OPENAI_MODEL = 'custom-model';
        await provider.generateResponse('chat', 'x');

        assert.equal(requestAt(0).model, 'custom-model');
    });
});
