import assert from 'node:assert/strict';
import { afterEach, beforeEach, describe, it } from 'node:test';
import LLMProviderFactory from './LLMProviderFactory.js';
import OpenAILLMProvider from './OpenAILLMProvider.js';
import ClaudeLLMProvider from './ClaudeLLMProvider.js';
import GeminiLLMProvider from './GeminiLLMProvider.js';
import HelloWorldTool from '../../application/tools/HelloWorldTool.js';
import type { Tool } from '../../providers/Tool.js';

const KEYS = ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GEMINI_API_KEY'];

describe('LLMProviderFactory', () => {
    const original: Record<string, string | undefined> = {};

    beforeEach(() => {
        for (const key of KEYS) {
            original[key] = process.env[key];
            delete process.env[key];
        }
    });

    afterEach(() => {
        for (const key of KEYS) {
            if (original[key] === undefined) delete process.env[key];
            else process.env[key] = original[key];
        }
    });

    it('creates the OpenAI provider when only OPENAI_API_KEY is set', () => {
        process.env.OPENAI_API_KEY = 'openai-key';

        const { name, provider } = LLMProviderFactory.create();

        assert.equal(name, 'OpenAI');
        assert.ok(provider instanceof OpenAILLMProvider);
    });

    it('creates the Claude provider when only ANTHROPIC_API_KEY is set', () => {
        process.env.ANTHROPIC_API_KEY = 'anthropic-key';

        const { name, provider } = LLMProviderFactory.create();

        assert.equal(name, 'Claude');
        assert.ok(provider instanceof ClaudeLLMProvider);
    });

    it('creates the Gemini provider when only GEMINI_API_KEY is set', () => {
        process.env.GEMINI_API_KEY = 'gemini-key';

        const { name, provider } = LLMProviderFactory.create();

        assert.equal(name, 'Gemini');
        assert.ok(provider instanceof GeminiLLMProvider);
    });

    it('prefers OpenAI over Claude and Gemini when all keys are set', () => {
        process.env.OPENAI_API_KEY = 'openai-key';
        process.env.ANTHROPIC_API_KEY = 'anthropic-key';
        process.env.GEMINI_API_KEY = 'gemini-key';

        assert.equal(LLMProviderFactory.create().name, 'OpenAI');
    });

    it('prefers Claude over Gemini when OpenAI is not configured', () => {
        process.env.ANTHROPIC_API_KEY = 'anthropic-key';
        process.env.GEMINI_API_KEY = 'gemini-key';

        assert.equal(LLMProviderFactory.create().name, 'Claude');
    });

    it('passes the tools on to the created provider', async () => {
        process.env.ANTHROPIC_API_KEY = 'anthropic-key';

        const { provider } = LLMProviderFactory.create([new HelloWorldTool()]);

        assert.deepEqual(
            (provider as unknown as { tools: Tool[] }).tools.map((t) => t.name),
            ['hello_world'],
        );
    });

    it('ignores keys set to an empty string', () => {
        process.env.OPENAI_API_KEY = '';
        process.env.GEMINI_API_KEY = 'gemini-key';

        assert.equal(LLMProviderFactory.create().name, 'Gemini');
    });

    it('throws listing every accepted variable when no key is configured', () => {
        assert.throws(
            () => LLMProviderFactory.create(),
            /OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY/,
        );
    });
});
