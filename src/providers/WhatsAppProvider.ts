export interface WhatsAppProvider {
    isConnected: boolean;

    connect(): Promise<void>;
    sendMessage(chatId: string, text: string): Promise<void>;
    sendPresenceUpdate(
        status: 'composing' | 'recording' | 'paused',
        chatJid: string,
    ): Promise<void>;
}
