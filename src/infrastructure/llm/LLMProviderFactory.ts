import type { LLMProvider } from '../../providers/LLMProvider.js';
import type { Tool } from '../../providers/Tool.js';
import OpenAILLMProvider from './OpenAILLMProvider.js';
import ClaudeLLMProvider from './ClaudeLLMProvider.js';
import GeminiLLMProvider from './GeminiLLMProvider.js';

interface LLMProviderEntry {
    name: string;
    apiKeyVariable: string;
    create: (tools: readonly Tool[]) => LLMProvider;
}

// Order defines priority when more than one API key is configured.
const ENTRIES: LLMProviderEntry[] = [
    {
        name: 'OpenAI',
        apiKeyVariable: 'OPENAI_API_KEY',
        create: (tools) => new OpenAILLMProvider(undefined, tools),
    },
    {
        name: 'Claude',
        apiKeyVariable: 'ANTHROPIC_API_KEY',
        create: (tools) => new ClaudeLLMProvider(undefined, tools),
    },
    {
        name: 'Gemini',
        apiKeyVariable: 'GEMINI_API_KEY',
        create: (tools) => new GeminiLLMProvider(undefined, tools),
    },
];

export const LLM_API_KEY_VARIABLES = ENTRIES.map((e) => e.apiKeyVariable);

export default class LLMProviderFactory {
    static create(tools: readonly Tool[] = []): {
        name: string;
        provider: LLMProvider;
    } {
        const entry = ENTRIES.find((e) => process.env[e.apiKeyVariable]);

        if (!entry)
            throw new Error(
                `You must configure one of those environment variables: ${LLM_API_KEY_VARIABLES.join(', ')}`,
            );

        return { name: entry.name, provider: entry.create(tools) };
    }
}
