import Anthropic from '@anthropic-ai/sdk';
import type { LLMProvider } from '../../providers/LLMProvider.js';
import type { Tool, ToolContext } from '../../providers/Tool.js';
import { MAX_TOOL_ROUNDS, runTool } from './runTool.js';
import { SYSTEM_PROMPT } from './systemPrompt.js';

const MAX_HISTORY_MESSAGES = 20;

export default class ClaudeLLMProvider implements LLMProvider {
    private client: Anthropic;
    //  TODO: Cuidar para limpar conversas não utilizadas durante muito tempo (possível vazamento de memória)
    private conversations: Map<string, Anthropic.MessageParam[]> = new Map();

    constructor(
        client?: Anthropic,
        private readonly tools: readonly Tool[] = [],
    ) {
        if (client) {
            this.client = client;
            return;
        }

        if (!process.env.ANTHROPIC_API_KEY)
            throw new Error(
                'Missing required environment variable: ANTHROPIC_API_KEY. Check the .env.example',
            );

        this.client = new Anthropic({
            apiKey: process.env.ANTHROPIC_API_KEY,
        });
    }

    async generateResponse(
        chatId: string,
        message: string,
        context: ToolContext,
    ) {
        const history = this.conversations.get(chatId) ?? [];
        const messages: Anthropic.MessageParam[] = [
            ...history,
            { role: 'user', content: message },
        ];

        for (let round = 0; round <= MAX_TOOL_ROUNDS; round++) {
            const response = await this.client.messages.create({
                model:
                    process.env.ANTHROPIC_MODEL ?? 'claude-haiku-4-5-20251001',
                max_tokens: 1024,
                system: SYSTEM_PROMPT,
                messages,
                ...(this.tools.length > 0 && {
                    tools: this.tools.map((tool) => ({
                        name: tool.name,
                        description: tool.description,
                        input_schema:
                            tool.parameters as Anthropic.Tool.InputSchema,
                    })),
                }),
            });

            const toolUses = response.content.filter(
                (block) => block.type === 'tool_use',
            );

            if (toolUses.length === 0) {
                const text = response.content
                    .flatMap((block) =>
                        block.type === 'text' ? [block.text] : [],
                    )
                    .join('');

                if (!text)
                    throw new Error('Failed to generate response: empty body');

                this.conversations.set(
                    chatId,
                    this.trim([
                        ...messages,
                        { role: 'assistant', content: text },
                    ]),
                );

                return text;
            }

            const results: Anthropic.ToolResultBlockParam[] = [];
            for (const toolUse of toolUses) {
                const { output, isError } = await runTool(
                    this.tools,
                    toolUse.name,
                    (toolUse.input ?? {}) as Record<string, unknown>,
                    context,
                );
                results.push({
                    type: 'tool_result',
                    tool_use_id: toolUse.id,
                    content: output,
                    ...(isError && { is_error: true }),
                });
            }

            messages.push(
                { role: 'assistant', content: response.content },
                { role: 'user', content: results },
            );
        }

        throw new Error(
            `Failed to generate response: more than ${MAX_TOOL_ROUNDS} tool rounds`,
        );
    }

    private trim(messages: Anthropic.MessageParam[]) {
        const trimmed = messages.slice(-MAX_HISTORY_MESSAGES);
        // The API requires the conversation to start with a plain user turn:
        // not an assistant turn, and not a tool_result whose tool_use was cut off.
        while (
            trimmed.length > 0 &&
            !(trimmed[0]!.role === 'user' && typeof trimmed[0]!.content === 'string')
        )
            trimmed.shift();
        return trimmed;
    }
}
