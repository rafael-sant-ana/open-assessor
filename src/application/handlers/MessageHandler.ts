import PinoLogger from '../../infrastructure/logging/PinoLogger.js';
import type { Level } from 'pino';
import type { Message } from '../../domain/messages/Message.js';
import type { LLMProvider } from '../../providers/LLMProvider.js';
import type { WhatsAppProvider } from '../../providers/WhatsAppProvider.js';

export default class MessageHandler {
    private logger: PinoLogger = new PinoLogger(
        'Handler',
        (process.env.LOG_LEVEL as Level) ?? 'info',
    );

    constructor(
        private readonly whatsapp: WhatsAppProvider,
        private readonly llm: LLMProvider,
    ) {}

    async handle(message: Message): Promise<void> {
        await this.whatsapp.sendPresenceUpdate('composing', message.chatJid);

        this.logger.debug('Generating response', {
            chatJid: message.chatJid,
            messageId: message.id,
        });
        const response = await this.llm
            .generateResponse(message.chatJid, message.content)
            .catch((err: Error) => {
                this.logger.error('Failed to generate response', {
                    chatJid: message.chatJid,
                    messageId: message.id,
                });
                console.error(err);
            });

        if (response === undefined) {
            await this.whatsapp
                .sendMessage(
                    message.chatJid,
                    'Desculpe, houve um erro interno ao tentar processar sua mensagem.',
                )
                .catch((err: Error) => {
                    this.logger.error('Failed to send message response', {
                        chatJid: message.chatJid,
                        messageId: message.id,
                    });
                    console.error(err);
                })
                .finally(async () => {
                    await this.whatsapp.sendPresenceUpdate(
                        'paused',
                        message.chatJid,
                    );
                });
            return;
        }

        await this.whatsapp
            .sendMessage(message.chatJid, response)
            .catch((err: Error) => {
                this.logger.error('Failed to send message response', {
                    chatJid: message.chatJid,
                    messageId: message.id,
                });
                console.error(err);
            });
    }
}
