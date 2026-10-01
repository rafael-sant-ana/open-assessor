import OpenAI from 'openai';
import type { ResponseInputItem } from 'openai/resources/responses/responses.js';
import type { LLMProvider } from '../../providers/LLMProvider.js';
import type { Tool, ToolContext } from '../../providers/Tool.js';
import { MAX_TOOL_ROUNDS, runTool } from './runTool.js';
import { SYSTEM_PROMPT } from './systemPrompt.js';

function parseArguments(raw: string): Record<string, unknown> {
    try {
        const parsed: unknown = JSON.parse(raw || '{}');
        return typeof parsed === 'object' && parsed !== null
            ? (parsed as Record<string, unknown>)
            : {};
    } catch {
        return {};
    }
}

export default class OpenAILLMProvider implements LLMProvider {
    private client: OpenAI;
    private conversations: Map<string, string> = new Map();

    constructor(
        client?: OpenAI,
        private readonly tools: readonly Tool[] = [],
    ) {
        if (client) {
            this.client = client;
            return;
        }

        if (!process.env.OPENAI_API_KEY)
            throw new Error(
                'Missing required environment key: OPENAI_API_KEY. Check the .env.example',
            );

        this.client = new OpenAI({
            apiKey: process.env.OPENAI_API_KEY,
        });
    }

    async generateResponse(
        chatId: string,
        message: string,
        context: ToolContext,
    ) {
        let previousId = this.conversations.get(chatId);
        let input: string | ResponseInputItem[] = message;

        for (let round = 0; round <= MAX_TOOL_ROUNDS; round++) {
            const response = await this.client.responses.create({
                model: process.env.OPENAI_MODEL ?? 'gpt-5.6-luna',
                instructions: SYSTEM_PROMPT,
                ...(previousId && {
                    previous_response_id: previousId,
                }),
                ...(this.tools.length > 0 && {
                    tools: this.tools.map((tool) => ({
                        type: 'function' as const,
                        name: tool.name,
                        description: tool.description,
                        parameters: tool.parameters,
                        strict: false,
                    })),
                }),
                input,
            });

            const calls = (response.output ?? []).filter(
                (item) => item.type === 'function_call',
            );

            if (calls.length === 0) {
                this.conversations.set(chatId, response.id);
                return response.output_text;
            }

            input = [];
            for (const call of calls) {
                const { output } = await runTool(
                    this.tools,
                    call.name,
                    parseArguments(call.arguments),
                    context,
                );
                input.push({
                    type: 'function_call_output',
                    call_id: call.call_id,
                    output,
                });
            }
            previousId = response.id;
        }

        throw new Error(
            `Failed to generate response: more than ${MAX_TOOL_ROUNDS} tool rounds`,
        );
    }
}
