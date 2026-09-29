import type { Message } from '../domain/messages/Message.js';

export type ChatPlatform = 'whatsapp' | 'telegram';

export interface ChatProvider {
    readonly platform: ChatPlatform;
    readonly isConnected: boolean;

    connect(): Promise<void>;
    disconnect(): Promise<void>;
    sendMessage(chatId: string, text: string): Promise<void>;
    sendTyping(chatId: string, active: boolean): Promise<void>;
    onMessage(handler: (message: Message) => Promise<void>): Disposable;
}
