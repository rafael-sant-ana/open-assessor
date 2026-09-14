import P from 'pino';
import qrcode from 'qrcode-terminal';
import PinoLogger from '../logging/PinoLogger.js';
import type { Boom } from '@hapi/boom';
import type { Message } from '../../domain/messages/Message.js';
import {
    type WASocket,
    makeWASocket,
    DisconnectReason,
    useMultiFileAuthState,
} from '@whiskeysockets/baileys';
import type { WhatsAppProvider } from '../../providers/WhatsAppProvider.js';

export default class BaileysWhatsAppProvider implements WhatsAppProvider {
    #sock: WASocket | null = null;
    #logger = new PinoLogger(
        'Baileys Provider',
        (process.env.LOG_LEVEL as P.Level) ?? 'info',
    );
    #isConnected: boolean = false;
    #messageHandlers: Set<(message: Message) => Promise<void>> = new Set();

    get isConnected() {
        return this.#isConnected;
    }

    async connect() {
        if (this.#isConnected) return;

        const loggingLevel = process.env.BAILEYS_LOG_LEVEL ?? 'info';
        const credentialsPath = process.env.AUTH_STATE_PATH ?? './.auth';

        const { state, saveCreds } =
            await useMultiFileAuthState(credentialsPath);

        if (this.#sock !== null) this.#sock.end(undefined);

        this.#sock = makeWASocket({
            auth: state,
            logger: P({ level: loggingLevel }),
        });

        this.#sock.ev.on('messages.upsert', async ({ type, messages }) => {
            if (type !== 'notify') {
                this.#logger.debug('Ignoring message history');
                return;
            }

            for (const message of messages) {
                const jid = message.key.remoteJid;

                this.#logger.debug('Message received from', {
                    chatJid: jid!,
                    messageId: message.key.id!,
                });

                // Ignora mensagens de grupos
                if (jid?.endsWith('@g.us')) continue;
                if (jid === 'status@broadcast') continue;
                if (jid?.endsWith('@newsletter')) continue;

                // Aceita apenas mensagens de texto
                const text =
                    message.message?.conversation ??
                    message.message?.extendedTextMessage?.text;

                if (!text) continue;

                const allowedJids = new Set(
                    process.env.ALLOWED_JIDS!.split(','),
                );

                if (text.toLowerCase() === '/meu-jid') {
                    await this.sendMessage(jid!, `Seu JID é:\n> ${jid}`);
                    continue;
                }

                // Verifica se o JID do usuário está na whitelist
                if (
                    !allowedJids.has(jid!) &&
                    !allowedJids.has(message.key.remoteJidAlt!)
                ) {
                    continue;
                }

                for (const handler of this.#messageHandlers) {
                    await handler({
                        author: {
                            jid: jid!,
                        },
                        chatJid: jid!,
                        content: text,
                        id: message.key.id!,
                    });
                }
            }
        });

        this.#sock.ev.on('creds.update', saveCreds);
        this.#sock.ev.on(
            'connection.update',
            ({ qr, connection, lastDisconnect }) => {
                if (qr) {
                    console.log('Escaneie o QR Code com o WhatsApp:\n');
                    qrcode.generate(qr, { small: true });
                }

                if (connection === 'connecting') {
                    this.#isConnected = false;
                    console.log('Conectando...');
                    return;
                }

                if (connection === 'open') {
                    this.#isConnected = true;
                    console.log('Conectado!');
                    return;
                }

                if (connection === 'close') {
                    this.#isConnected = false;
                    const statusCode = (lastDisconnect?.error as Boom)?.output
                        .statusCode;
                    console.log(`Desconectado: ${statusCode}`);

                    if (statusCode === DisconnectReason.loggedOut) {
                        console.log('Sessão encerrada.');
                        return;
                    }

                    console.log('Reconectando...');
                    this.connect();
                }
            },
        );
    }

    async sendMessage(chatId: string, text: string) {
        if (this.#sock === null)
            throw new Error("The provider isn't connected");

        await this.#sock.sendMessage(chatId, {
            text,
        });
    }

    async sendPresenceUpdate(
        status: 'composing' | 'recording' | 'paused',
        chatJid: string,
    ) {
        if (this.#sock === null)
            throw new Error("The provider isn't connected");

        this.#sock.sendPresenceUpdate(status, chatJid);
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
