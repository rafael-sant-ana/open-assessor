import type { Tool } from '../../providers/Tool.js';

/** Upper bound of model → tool → model round trips for a single user message. */
export const MAX_TOOL_ROUNDS = 5;

export interface ToolResult {
    readonly output: string;
    readonly isError: boolean;
}

/** Runs a tool the model asked for. Failures become results so the model can recover. */
export async function runTool(
    tools: readonly Tool[],
    name: string,
    args: Record<string, unknown>,
): Promise<ToolResult> {
    const tool = tools.find((t) => t.name === name);
    if (!tool) return { output: `Unknown tool: ${name}`, isError: true };

    try {
        return { output: await tool.execute(args), isError: false };
    } catch (err) {
        console.error(err);
        return {
            output: err instanceof Error ? err.message : String(err),
            isError: true,
        };
    }
}
