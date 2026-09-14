import 'dotenv/config';

if (!process.env.ALLOWED_JIDS) {
    console.error(
        'Missing required environment key: ALLOWED_JIDS. Check the .env.example',
    );
    process.exit(1);
}

if (!process.env.OPENAI_API_KEY && !process.env.GEMINI_API_KEY) {
    console.error(
        'You must configure one of those environment variables: OPENAI_API_KEY or GEMINI_API_KEY',
    );
    process.exit(1);
}

import type { Level } from 'pino';
import PinoLogger from './infrastructure/logging/PinoLogger.js';
import MessageHandler from './application/handlers/MessageHandler.js';
import OpenAILLMProvider from './infrastructure/llm/OpenAILLMProvider.js';
import GeminiLLMProvider from './infrastructure/llm/GeminiLLMProvider.js';
import BaileysWhatsAppProvider from './infrastructure/whatsapp/BaileysWhatsAppProvider.js';

async function main() {
    const logger = new PinoLogger(
        'MAIN',
        (process.env.LOG_LEVEL as Level) ?? 'info',
    );

    logger.debug('Initializing...');
    const llmProvider = process.env.OPENAI_API_KEY
        ? new OpenAILLMProvider()
        : new GeminiLLMProvider();

    if (llmProvider instanceof OpenAILLMProvider)
        logger.info('Using OpenAI LLM provider');
    else logger.info('Using Gemini LLM provider');

    const whatsappProvider = new BaileysWhatsAppProvider();

    logger.debug('Connecting...');
    await whatsappProvider.connect();

    const messageHandler = new MessageHandler(whatsappProvider, llmProvider);
    whatsappProvider.onMessage((message) => messageHandler.handle(message));
    logger.info('The bot is ready!');
}

main();
