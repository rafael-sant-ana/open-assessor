import type { ChatPlatform } from '../../providers/ChatProvider.js';
import type { MessageUser } from '../../domain/messages/Message.js';

export default class AllowList {
    private constructor(private readonly entries: ReadonlySet<string>) {}

    /**
     * Reads `ALLOWED_USERS` (comma-separated `platform:id`, e.g.
     * `telegram:123456`) and the legacy `ALLOWED_JIDS` (WhatsApp JIDs).
     */
    static fromEnv(env: NodeJS.ProcessEnv = process.env): AllowList {
        const entries = new Set<string>();

        for (const entry of env.ALLOWED_USERS?.split(',') ?? []) {
            if (entry.trim()) entries.add(entry.trim());
        }

        for (const jid of env.ALLOWED_JIDS?.split(',') ?? []) {
            if (jid.trim()) entries.add(`whatsapp:${jid.trim()}`);
        }

        return new AllowList(entries);
    }

    get isEmpty() {
        return this.entries.size === 0;
    }

    isAllowed(platform: ChatPlatform, user: MessageUser) {
        return [user.id, ...(user.aliases ?? [])].some((id) =>
            this.entries.has(`${platform}:${id}`),
        );
    }
}
