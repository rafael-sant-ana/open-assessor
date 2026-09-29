import assert from 'node:assert/strict';
import { afterEach, beforeEach, describe, it, mock } from 'node:test';
import type { Bot } from 'grammy';
import type { Message } from '../../domain/messages/Message.js';
import TelegramProvider, { splitMessage } from './TelegramProvider.js';

type Update = {
    message_id: number;
    text?: string;
    chat: { id: number; type: string };
    from?: { id: number } | undefined;
};

function setup() {
    let textHandler: ((ctx: { message: Update }) => Promise<void>) | undefined;
    let errorHandler: ((error: { error: unknown }) => void) | undefined;
    let filter: string | undefined;
    const sendMessage = mock.fn(async (..._args: unknown[]) => ({}));
    const sendChatAction = mock.fn(async (..._args: unknown[]) => true);
    const init = mock.fn(async () => {});
    const start = mock.fn(() => new Promise<void>(() => {}));
    const stop = mock.fn(async () => {});
    const bot = {
        api: { sendMessage, sendChatAction },
        on: (f: string, handler: typeof textHandler) => {
            filter = f;
            textHandler = handler;
        },
        catch: (handler: typeof errorHandler) => {
            errorHandler = handler;
        },
        init,
        start,
        stop,
    } as unknown as Bot;

    return {
        provider: new TelegramProvider(bot),
        sendMessage,
        sendChatAction,
        init,
        start,
        stop,
        filter: () => filter,
        deliver: (message: Update) => textHandler!({ message }),
        errorHandler: () => errorHandler,
    };
}

const privateText: Update = {
    message_id: 7,
    text: 'oi',
    chat: { id: 42, type: 'private' },
    from: { id: 99 },
};

describe('TelegramProvider', () => {
    let originalToken: string | undefined;

    beforeEach(() => {
        originalToken = process.env.TELEGRAM_BOT_TOKEN;
    });

    afterEach(() => {
        mock.timers.reset();
        if (originalToken === undefined) delete process.env.TELEGRAM_BOT_TOKEN;
        else process.env.TELEGRAM_BOT_TOKEN = originalToken;
    });

    it('throws when TELEGRAM_BOT_TOKEN is missing', () => {
        delete process.env.TELEGRAM_BOT_TOKEN;

        assert.throws(
            () => new TelegramProvider(),
            /Missing required environment variable: TELEGRAM_BOT_TOKEN/,
        );
    });

    it('has the telegram platform', () => {
        assert.equal(setup().provider.platform, 'telegram');
    });

    it('listens only to text messages (message:text filter)', () => {
        assert.equal(setup().filter(), 'message:text');
    });

    it('connect validates the token, starts polling and sets isConnected', async () => {
        const { provider, init, start } = setup();

        await provider.connect();

        assert.equal(init.mock.callCount(), 1);
        assert.equal(start.mock.callCount(), 1);
        assert.equal(provider.isConnected, true);
    });

    it('connect fails fast when init rejects', async () => {
        const { provider, init, start } = setup();
        init.mock.mockImplementation(async () => {
            throw new Error('Unauthorized');
        });

        await assert.rejects(provider.connect(), /Unauthorized/);
        assert.equal(start.mock.callCount(), 0);
        assert.equal(provider.isConnected, false);
    });

    it('disconnect stops the bot', async () => {
        const { provider, stop } = setup();
        await provider.connect();

        await provider.disconnect();

        assert.equal(stop.mock.callCount(), 1);
        assert.equal(provider.isConnected, false);
    });

    it('maps private text messages', async () => {
        const { provider, deliver } = setup();
        const received: Message[] = [];
        using _sub = provider.onMessage(async (m) => {
            received.push(m);
        });

        await deliver(privateText);

        assert.deepEqual(received, [
            {
                id: '7',
                platform: 'telegram',
                author: { id: '99' },
                chatId: '42',
                content: 'oi',
            },
        ]);
    });

    it('ignores groups and channels', async () => {
        const { provider, deliver } = setup();
        const handler = mock.fn(async (_m: Message) => {});
        using _sub = provider.onMessage(handler);

        for (const type of ['group', 'supergroup', 'channel']) {
            await deliver({ ...privateText, chat: { id: -1, type } });
        }

        assert.equal(handler.mock.callCount(), 0);
    });

    it('ignores messages without sender', async () => {
        const { provider, deliver } = setup();
        const handler = mock.fn(async (_m: Message) => {});
        using _sub = provider.onMessage(handler);

        await deliver({ ...privateText, from: undefined });

        assert.equal(handler.mock.callCount(), 0);
    });

    it('keeps working when a handler throws', async () => {
        const { provider, deliver } = setup();
        const second = mock.fn(async (_m: Message) => {});
        using _a = provider.onMessage(async () => {
            throw new Error('boom');
        });
        using _b = provider.onMessage(second);

        await deliver(privateText);

        assert.equal(second.mock.callCount(), 1);
    });

    it('registers a bot.catch handler that does not throw', () => {
        const { errorHandler } = setup();

        assert.doesNotThrow(() => errorHandler()!({ error: new Error('x') }));
    });

    it('stops delivering after the handler is disposed', async () => {
        const { provider, deliver } = setup();
        const handler = mock.fn(async (_m: Message) => {});
        const sub = provider.onMessage(handler);

        sub[Symbol.dispose]();
        await deliver(privateText);

        assert.equal(handler.mock.callCount(), 0);
    });

    it('sends short messages as a single chunk', async () => {
        const { provider, sendMessage } = setup();

        await provider.sendMessage('42', 'olá');

        assert.deepEqual(sendMessage.mock.calls[0]!.arguments, ['42', 'olá']);
        assert.equal(sendMessage.mock.callCount(), 1);
    });

    it('splits long messages into ordered chunks of at most 4096 chars', async () => {
        const { provider, sendMessage } = setup();
        const text = 'a'.repeat(4096) + 'b'.repeat(4096) + 'c'.repeat(10);

        await provider.sendMessage('42', text);

        const sent = sendMessage.mock.calls.map(
            (c) => c.arguments[1] as string,
        );
        assert.equal(sent.length, 3);
        assert.ok(sent.every((s) => s.length <= 4096));
        assert.equal(sent.join(''), text);
    });

    it('prefers newline boundaries when splitting', () => {
        const line = 'x'.repeat(3000);
        const text = `${line}\n${line}\n${line}`;
        const chunks = splitMessage(text);

        assert.equal(chunks.length, 3);
        assert.equal(chunks[0], `${line}\n`);
        assert.equal(chunks.join(''), text);
    });

    it('sends typing immediately and refreshes until stopped', async () => {
        mock.timers.enable({ apis: ['setInterval'] });
        const { provider, sendChatAction } = setup();

        await provider.sendTyping('42', true);
        assert.equal(sendChatAction.mock.callCount(), 1);
        assert.deepEqual(sendChatAction.mock.calls[0]!.arguments, [
            '42',
            'typing',
        ]);

        mock.timers.tick(4000);
        mock.timers.tick(4000);
        assert.equal(sendChatAction.mock.callCount(), 3);

        await provider.sendTyping('42', false);
        mock.timers.tick(8000);
        assert.equal(sendChatAction.mock.callCount(), 3);
    });

    it('keeps one typing timer per chat', async () => {
        mock.timers.enable({ apis: ['setInterval'] });
        const { provider, sendChatAction } = setup();

        await provider.sendTyping('42', true);
        await provider.sendTyping('42', true);
        mock.timers.tick(4000);

        assert.equal(sendChatAction.mock.callCount(), 2);
        await provider.sendTyping('42', false);
    });

    it('does not crash when the typing refresh fails', async () => {
        mock.timers.enable({ apis: ['setInterval'] });
        const { provider, sendChatAction } = setup();
        await provider.sendTyping('42', true);
        sendChatAction.mock.mockImplementation(async () => {
            throw new Error('network');
        });

        mock.timers.tick(4000);
        await new Promise((resolve) => setImmediate(resolve));

        assert.equal(sendChatAction.mock.callCount(), 2);
        await provider.sendTyping('42', false);
    });

    it('clears typing timers on disconnect', async () => {
        mock.timers.enable({ apis: ['setInterval'] });
        const { provider, sendChatAction } = setup();
        await provider.sendTyping('42', true);

        await provider.disconnect();
        mock.timers.tick(8000);

        assert.equal(sendChatAction.mock.callCount(), 1);
    });
});
