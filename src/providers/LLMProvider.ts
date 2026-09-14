export interface LLMProvider {
    generateResponse(chatId: string, message: string): Promise<string>;
}
