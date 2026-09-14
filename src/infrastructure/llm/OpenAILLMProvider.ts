import OpenAI from 'openai';
import type { LLMProvider } from '../../providers/LLMProvider.js';

export default class OpenAILLMProvider implements LLMProvider {
    private client: OpenAI;
    private conversations: Map<string, string> = new Map();

    constructor() {
        if (!process.env.OPENAI_API_KEY)
            throw new Error(
                'Missing required environment key: OPENAI_API_KEY. Check the .env.example',
            );

        this.client = new OpenAI({
            apiKey: process.env.OPENAI_API_KEY,
        });
    }

    async generateResponse(chatId: string, message: string) {
        const previousId = this.conversations.get(chatId);

        const response = await this.client.responses.create({
            model: process.env.OPENAI_MODEL ?? 'gpt-5.6-luna',
            instructions:
                'Você é um assistente financeiro de WhatsApp, chamado de Open Assessor.',
            ...(previousId && {
                previous_response_id: previousId,
            }),
            input: message,
        });

        this.conversations.set(chatId, response.id);
        return response.output_text;
    }
}
