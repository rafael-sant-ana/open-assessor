import 'dotenv/config';

import AllowList from './application/security/AllowList.js';

const allowList = AllowList.fromEnv();

if (allowList.isEmpty) {
    console.error(
        'You must configure one of those environment variables: ALLOWED_USERS or ALLOWED_JIDS. Check the .env.example',
    );
    process.exit(1);
}

import type { Level } from 'pino';
import type { ChatProvider } from './providers/ChatProvider.js';
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

    const chatProviders: ChatProvider[] = [new BaileysWhatsAppProvider()];
    const messageHandler = new MessageHandler(llmProvider, allowList);

    for (const chat of chatProviders) {
        chat.onMessage((message) => messageHandler.handle(message, chat));

        logger.debug(`Connecting ${chat.platform}...`);
        await chat.connect();
    }

    process.once('SIGINT', async () => {
        await Promise.all(chatProviders.map((chat) => chat.disconnect()));
        process.exit(0);
    });

    logger.info('The bot is ready!');
}

main().catch((error) => {
    console.error(error instanceof Error ? error.message : error);
    process.exit(1);
});
