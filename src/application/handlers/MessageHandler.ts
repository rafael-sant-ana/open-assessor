import PinoLogger from '../../infrastructure/logging/PinoLogger.js';
import type { Level } from 'pino';
import type { Message } from '../../domain/messages/Message.js';
import type { LLMProvider } from '../../providers/LLMProvider.js';
import type { ChatProvider } from '../../providers/ChatProvider.js';
import type AllowList from '../security/AllowList.js';

const WHOAMI_COMMANDS = new Set(['/meu-id', '/meu-jid']);

export default class MessageHandler {
    private logger: PinoLogger = new PinoLogger(
        'Handler',
        (process.env.LOG_LEVEL as Level) ?? 'info',
    );

    constructor(
        private readonly llm: LLMProvider,
        private readonly allowList: AllowList,
    ) {}

    async handle(message: Message, chat: ChatProvider): Promise<void> {
        const context = { chatId: message.chatId, messageId: message.id };

        if (WHOAMI_COMMANDS.has(message.content.trim().toLowerCase())) {
            await this.reply(chat, message, `Seu ID é:\n> ${message.author.id}`);
            return;
        }

        if (!this.allowList.isAllowed(message.platform, message.author)) {
            this.logger.debug('Ignoring message from unauthorized user', context);
            return;
        }

        await chat.sendTyping(message.chatId, true);

        try {
            this.logger.debug('Generating response', context);
            const response = await this.llm
                .generateResponse(
                    `${message.platform}:${message.chatId}`,
                    message.content,
                    {
                        userId: `${message.platform}:${message.author.id}`,
                        messageKey: `${message.platform}:${message.chatId}:${message.id}`,
                    },
                )
                .catch((err: Error) => {
                    this.logger.error('Failed to generate response', context);
                    console.error(err);
                });

            await this.reply(
                chat,
                message,
                response ??
                    'Desculpe, houve um erro interno ao tentar processar sua mensagem.',
            );
        } finally {
            await chat.sendTyping(message.chatId, false).catch(() => {});
        }
    }

    private async reply(chat: ChatProvider, message: Message, text: string) {
        await chat.sendMessage(message.chatId, text).catch((err: Error) => {
            this.logger.error('Failed to send message response', {
                chatId: message.chatId,
                messageId: message.id,
            });
            console.error(err);
        });
    }
}
