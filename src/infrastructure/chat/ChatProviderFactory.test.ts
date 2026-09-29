import assert from 'node:assert/strict';
import { afterEach, beforeEach, describe, it } from 'node:test';
import ChatProviderFactory from './ChatProviderFactory.js';
import BaileysWhatsAppProvider from './BaileysWhatsAppProvider.js';
import TelegramProvider from './TelegramProvider.js';

const KEYS = ['CHAT_PROVIDER', 'TELEGRAM_BOT_TOKEN'];

describe('ChatProviderFactory', () => {
    const original: Record<string, string | undefined> = {};

    beforeEach(() => {
        for (const key of KEYS) {
            original[key] = process.env[key];
            delete process.env[key];
        }
    });

    afterEach(() => {
        for (const key of KEYS) {
            if (original[key] === undefined) delete process.env[key];
            else process.env[key] = original[key];
        }
    });

    it('defaults to WhatsApp', () => {
        const provider = ChatProviderFactory.create();

        assert.ok(provider instanceof BaileysWhatsAppProvider);
        assert.equal(provider.platform, 'whatsapp');
    });

    it('creates the Telegram provider', () => {
        process.env.TELEGRAM_BOT_TOKEN = '123:abc';

        const provider = ChatProviderFactory.create('telegram');

        assert.ok(provider instanceof TelegramProvider);
        assert.equal(provider.platform, 'telegram');
    });

    it('reads CHAT_PROVIDER from the environment', () => {
        process.env.CHAT_PROVIDER = 'telegram';
        process.env.TELEGRAM_BOT_TOKEN = '123:abc';

        assert.ok(ChatProviderFactory.create() instanceof TelegramProvider);
    });

    it('throws for an unsupported platform', () => {
        assert.throws(
            () => ChatProviderFactory.create('signal'),
            /Unsupported CHAT_PROVIDER "signal"/,
        );
    });
});
