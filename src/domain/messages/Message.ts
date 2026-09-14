export interface Message {
    readonly id: string;
    readonly author: MessageUser;
    readonly content: string;
    readonly chatJid: string;
}

export interface MessageUser {
    readonly jid: string;
}
