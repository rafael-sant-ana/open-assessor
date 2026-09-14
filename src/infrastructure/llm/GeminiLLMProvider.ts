import { GoogleGenAI, Chat } from '@google/genai';
import type { LLMProvider } from '../../providers/LLMProvider.js';

export default class OpenAILLMProvider implements LLMProvider {
    private client: GoogleGenAI;
    private conversations: Map<string, Chat> = new Map();

    constructor() {
        if (!process.env.GEMINI_API_KEY)
            throw new Error(
                'Missing required environment variable: GEMINI_API_KEY. Check the .env.example',
            );

        this.client = new GoogleGenAI({
            apiKey: process.env.GEMINI_API_KEY!,
        });
    }

    async generateResponse(chatId: string, message: string) {
        let chat = this.conversations.get(chatId);

        if (chat === undefined) {
            chat = this.client.chats.create({
                model: process.env.GEMINI_MODEL ?? 'gemini-3.6-flash',
                config: {
                    systemInstruction: `
Você é um assistente financeiro de WhatsApp, chamado Open Assessor.

Regras:
- Responda sempre em português.
- Seja direto e objetivo.
- Classifique as mensagens do usuário como gasto ou não.
- Se for um gasto, você apenas deve registrá-lo.
- Não diga coisas sobre as quais o usuário não quer saber.
- Não tente sugerir ações ao usuário a não ser que isso realmente possa ser interessante pra ele.`,
                },
            });

            //  TODO: Cuidar para limpar chats não utilizados durante muito tempo (possível vazamento de memória)
            this.conversations.set(chatId, chat);
        }

        const response = await chat.sendMessage({
            message,
        });

        if (!response.text)
            throw new Error('Failed to generate response: empty body');

        return response.text;
    }
}
