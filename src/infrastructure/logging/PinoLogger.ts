import pino from 'pino';
import type { Logger, MessageContext } from '../../providers/Logger.js';

export default class PinoLogger implements Logger {
    private readonly logger: pino.Logger;

    constructor(name: string, level: pino.Level) {
        this.logger = pino({
            name,
            level,
            ...(process.env.NODE_ENV !== 'production' && {
                transport: {
                    target: 'pino-pretty',
                    options: {
                        colorize: true,
                        translateTime: 'SYS:standard',
                        ignore: 'pid,hostname',
                    },
                },
            }),
        });
    }

    debug(message: string, context?: MessageContext): void {
        this.logger.debug(context, message);
    }

    info(message: string, context?: MessageContext): void {
        this.logger.info(context, message);
    }

    warn(message: string, context?: MessageContext): void {
        this.logger.warn(context, message);
    }

    error(message: string, context?: MessageContext): void {
        this.logger.error(context, message);
    }
}
