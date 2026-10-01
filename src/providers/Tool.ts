/** Facts about the current message that the model must never choose itself. */
export interface ToolContext {
    /** `<platform>:<authorId>`, same format as `ALLOWED_USERS`. */
    readonly userId: string;
    /** `<platform>:<chatId>:<messageId>`, unique per incoming message. */
    readonly messageKey: string;
}

export interface Tool {
    readonly name: string;
    readonly description: string;
    /** JSON Schema describing the arguments object. */
    readonly parameters: Record<string, unknown>;
    execute(args: Record<string, unknown>, context: ToolContext): Promise<string>;
}
