import {
    GoogleGenAI,
    Chat,
    type GenerateContentConfig,
    type Part,
} from '@google/genai';
import type { LLMProvider } from '../../providers/LLMProvider.js';
import type { Tool, ToolContext } from '../../providers/Tool.js';
import { MAX_TOOL_ROUNDS, runTool } from './runTool.js';
import { SYSTEM_PROMPT } from './systemPrompt.js';

export default class GeminiLLMProvider implements LLMProvider {
    private client: GoogleGenAI;
    private conversations: Map<string, Chat> = new Map();

    constructor(
        client?: GoogleGenAI,
        private readonly tools: readonly Tool[] = [],
    ) {
        if (client) {
            this.client = client;
            return;
        }

        if (!process.env.GEMINI_API_KEY)
            throw new Error(
                'Missing required environment variable: GEMINI_API_KEY. Check the .env.example',
            );

        this.client = new GoogleGenAI({
            apiKey: process.env.GEMINI_API_KEY!,
        });
    }

    async generateResponse(
        chatId: string,
        message: string,
        context: ToolContext,
    ) {
        let chat = this.conversations.get(chatId);

        if (chat === undefined) {
            chat = this.client.chats.create({
                model: process.env.GEMINI_MODEL ?? 'gemini-3.6-flash',
                config: this.buildConfig(),
            });

            //  TODO: Cuidar para limpar chats não utilizados durante muito tempo (possível vazamento de memória)
            this.conversations.set(chatId, chat);
        }

        let response = await chat.sendMessage({ message });

        for (let round = 0; ; round++) {
            const calls = response.functionCalls ?? [];
            if (calls.length === 0) break;

            if (round >= MAX_TOOL_ROUNDS)
                throw new Error(
                    `Failed to generate response: more than ${MAX_TOOL_ROUNDS} tool rounds`,
                );

            const parts: Part[] = [];
            for (const call of calls) {
                const name = call.name ?? '';
                const { output, isError } = await runTool(
                    this.tools,
                    name,
                    call.args ?? {},
                    context,
                );
                parts.push({
                    functionResponse: {
                        ...(call.id && { id: call.id }),
                        name,
                        response: isError ? { error: output } : { output },
                    },
                });
            }

            response = await chat.sendMessage({ message: parts });
        }

        if (!response.text)
            throw new Error('Failed to generate response: empty body');

        return response.text;
    }

    private buildConfig(): GenerateContentConfig {
        return {
            systemInstruction: SYSTEM_PROMPT,
            ...(this.tools.length > 0 && {
                tools: [
                    {
                        functionDeclarations: this.tools.map((tool) => ({
                            name: tool.name,
                            description: tool.description,
                            parametersJsonSchema: tool.parameters,
                        })),
                    },
                ],
                automaticFunctionCalling: { disable: true },
            }),
        };
    }
}
