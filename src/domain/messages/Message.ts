import type { ChatPlatform } from '../../providers/ChatProvider.js';

export interface Message {
    readonly id: string;
    readonly platform: ChatPlatform;
    readonly author: MessageUser;
    readonly content: string;
    readonly chatId: string;
}

export interface MessageUser {
    readonly id: string;
    /** Other identifiers the platform may know this user by (e.g. WhatsApp LID vs phone JID). */
    readonly aliases?: readonly string[];
}
