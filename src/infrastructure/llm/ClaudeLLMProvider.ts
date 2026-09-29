import Anthropic from '@anthropic-ai/sdk';
import type { LLMProvider } from '../../providers/LLMProvider.js';

const MAX_HISTORY_MESSAGES = 20;

const SYSTEM_PROMPT = `
Você é um assistente financeiro de WhatsApp, chamado Open Assessor.

Regras:
- Responda sempre em português.
- Seja direto e objetivo.
- Classifique as mensagens do usuário como gasto ou não.
- Se for um gasto, você apenas deve registrá-lo.
- Não diga coisas sobre as quais o usuário não quer saber.
- Não tente sugerir ações ao usuário a não ser que isso realmente possa ser interessante pra ele.`;

export default class ClaudeLLMProvider implements LLMProvider {
    private client: Anthropic;
    //  TODO: Cuidar para limpar conversas não utilizadas durante muito tempo (possível vazamento de memória)
    private conversations: Map<string, Anthropic.MessageParam[]> = new Map();

    constructor(client?: Anthropic) {
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

    async generateResponse(chatId: string, message: string) {
        const history = this.conversations.get(chatId) ?? [];
        const messages: Anthropic.MessageParam[] = [
            ...history,
            { role: 'user', content: message },
        ];

        const response = await this.client.messages.create({
            model: process.env.ANTHROPIC_MODEL ?? 'claude-haiku-4-5-20251001',
            max_tokens: 1024,
            system: SYSTEM_PROMPT,
            messages,
        });

        const text = response.content
            .flatMap((block) => (block.type === 'text' ? [block.text] : []))
            .join('');

        if (!text) throw new Error('Failed to generate response: empty body');

        this.conversations.set(
            chatId,
            this.trim([...messages, { role: 'assistant', content: text }]),
        );

        return text;
    }

    private trim(messages: Anthropic.MessageParam[]) {
        const trimmed = messages.slice(-MAX_HISTORY_MESSAGES);
        // The API requires the conversation to start with a user turn.
        while (trimmed[0]?.role === 'assistant') trimmed.shift();
        return trimmed;
    }
}
