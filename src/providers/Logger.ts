export interface MessageContext {
    chatJid: string;
    messageId: string;
}

export interface Logger {
    debug(message: string, context?: MessageContext): void;
    info(message: string, context?: MessageContext): void;
    warn(message: string, context?: MessageContext): void;
    error(message: string, context?: MessageContext): void;
}
