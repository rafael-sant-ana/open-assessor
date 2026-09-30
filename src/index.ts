import 'dotenv/config';

if (!process.env.ALLOWED_JIDS) {
    console.error(
        'Missing required environment key: ALLOWED_JIDS. Check the .env.example',
    );
    process.exit(1);
}

import type { Level } from 'pino';
import PinoLogger from './infrastructure/logging/PinoLogger.js';
import MessageHandler from './application/handlers/MessageHandler.js';
import LLMProviderFactory from './infrastructure/llm/LLMProviderFactory.js';
import BaileysWhatsAppProvider from './infrastructure/whatsapp/BaileysWhatsAppProvider.js';

async function main() {
    const logger = new PinoLogger(
        'MAIN',
        (process.env.LOG_LEVEL as Level) ?? 'info',
    );

    logger.debug('Initializing...');
    const { name, provider: llmProvider } = LLMProviderFactory.create();
    logger.info(`Using ${name} LLM provider`);

    const whatsappProvider = new BaileysWhatsAppProvider();

    logger.debug('Connecting...');
    await whatsappProvider.connect();

    const messageHandler = new MessageHandler(whatsappProvider, llmProvider);
    whatsappProvider.onMessage((message) => messageHandler.handle(message));
    logger.info('The bot is ready!');
}

main().catch((error) => {
    console.error(error instanceof Error ? error.message : error);
    process.exit(1);
});
