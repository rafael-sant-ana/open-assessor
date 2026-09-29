import type {
    ChatPlatform,
    ChatProvider,
} from '../../providers/ChatProvider.js';
import BaileysWhatsAppProvider from './BaileysWhatsAppProvider.js';

const DEFAULT_PLATFORM: ChatPlatform = 'whatsapp';

const PROVIDERS: Partial<Record<ChatPlatform, () => ChatProvider>> = {
    whatsapp: () => new BaileysWhatsAppProvider(),
};

export default class ChatProviderFactory {
    static create(
        platform: string = process.env.CHAT_PROVIDER ?? DEFAULT_PLATFORM,
    ): ChatProvider {
        const create = PROVIDERS[platform as ChatPlatform];

        if (!create)
            throw new Error(
                `Unsupported CHAT_PROVIDER "${platform}". Supported: ${Object.keys(PROVIDERS).join(', ')}`,
            );

        return create();
    }
}
