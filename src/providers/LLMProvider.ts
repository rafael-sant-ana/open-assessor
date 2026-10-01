import type { ToolContext } from './Tool.js';

export interface LLMProvider {
    generateResponse(
        chatId: string,
        message: string,
        context: ToolContext,
    ): Promise<string>;
}
