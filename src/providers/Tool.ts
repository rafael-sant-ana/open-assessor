export interface Tool {
    readonly name: string;
    readonly description: string;
    /** JSON Schema describing the arguments object. */
    readonly parameters: Record<string, unknown>;
    execute(args: Record<string, unknown>): Promise<string>;
}
