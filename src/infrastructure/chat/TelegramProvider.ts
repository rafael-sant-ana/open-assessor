import type P from 'pino';
import { Bot } from 'grammy';
import PinoLogger from '../logging/PinoLogger.js';
import type { Message } from '../../domain/messages/Message.js';
import type { ChatProvider } from '../../providers/ChatProvider.js';

const MAX_MESSAGE_LENGTH = 4096;
const TYPING_REFRESH_MS = 4000;

export function splitMessage(
    text: string,
    limit: number = MAX_MESSAGE_LENGTH,
): string[] {
    const chunks: string[] = [];
    let rest = text;

    while (rest.length > limit) {
        const newline = rest.lastIndexOf('\n', limit - 1);
        // Prefere quebrar em uma nova linha, senão corta no limite
        const cut = newline > 0 ? newline + 1 : limit;
        chunks.push(rest.slice(0, cut));
        rest = rest.slice(cut);
    }

    if (rest.length > 0 || chunks.length === 0) chunks.push(rest);
    return chunks;
}

export default class TelegramProvider implements ChatProvider {
    readonly platform = 'telegram' as const;
    #bot: Bot;
    #logger = new PinoLogger(
        'Telegram Provider',
        (process.env.LOG_LEVEL as P.Level) ?? 'info',
    );
    #isConnected: boolean = false;
    #messageHandlers: Set<(message: Message) => Promise<void>> = new Set();
    #typingTimers: Map<string, NodeJS.Timeout> = new Map();

    constructor(bot?: Bot) {
        if (bot) {
            this.#bot = bot;
        } else {
            const token = process.env.TELEGRAM_BOT_TOKEN;
            if (!token)
                throw new Error(
                    'Missing required environment variable: TELEGRAM_BOT_TOKEN. Check the .env.example',
                );
            this.#bot = new Bot(token);
        }

        this.#bot.on('message:text', async (ctx) => {
            const { message } = ctx;
            if (message.chat.type !== 'private' || !message.from) return;

            const messageId = String(message.message_id);
            const chatId = String(message.chat.id);

            this.#logger.debug('Message received from', { chatId, messageId });

            for (const handler of this.#messageHandlers) {
                try {
                    await handler({
                        id: messageId,
                        platform: this.platform,
                        author: { id: String(message.from.id) },
                        chatId,
                        content: message.text,
                    });
                } catch (error) {
                    this.#logger.error(
                        `Message handler failed: ${String(error)}`,
                        { chatId, messageId },
                    );
                }
            }
        });

        this.#bot.catch((error) => {
            this.#logger.error(`Telegram bot error: ${String(error.error)}`);
        });
    }

    get isConnected() {
        return this.#isConnected;
    }

    async connect() {
        if (this.#isConnected) return;

        // Valida o token e falha rápido
        await this.#bot.init();

        // Long polling em segundo plano: a promise só resolve quando o bot para
        this.#bot.start().catch((error) => {
            this.#isConnected = false;
            this.#logger.error(`Telegram polling stopped: ${String(error)}`);
        });
        this.#isConnected = true;
        console.log('Telegram conectado!');
    }

    async disconnect() {
        for (const timer of this.#typingTimers.values()) clearInterval(timer);
        this.#typingTimers.clear();
        this.#isConnected = false;
        await this.#bot.stop();
    }

    async sendMessage(chatId: string, text: string) {
        for (const chunk of splitMessage(text)) {
            await this.#bot.api.sendMessage(chatId, chunk);
        }
    }

    async sendTyping(chatId: string, active: boolean) {
        if (!active) {
            const timer = this.#typingTimers.get(chatId);
            if (timer) clearInterval(timer);
            this.#typingTimers.delete(chatId);
            return;
        }

        if (this.#typingTimers.has(chatId)) return;

        // A ação 'typing' expira em ~5s, então é renovada enquanto ativa
        const send = () =>
            this.#bot.api.sendChatAction(chatId, 'typing').catch((error) => {
                this.#logger.warn(`Failed to send typing action: ${String(error)}`);
            });

        const timer = setInterval(send, TYPING_REFRESH_MS);
        timer.unref();
        this.#typingTimers.set(chatId, timer);
        await send();
    }

    onMessage(handler: (message: Message) => Promise<void>) {
        this.#messageHandlers.add(handler);
        return {
            [Symbol.dispose]: () => {
                this.#messageHandlers.delete(handler);
            },
        };
    }
}
