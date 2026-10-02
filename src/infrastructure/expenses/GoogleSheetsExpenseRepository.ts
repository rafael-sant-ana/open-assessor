import type { sheets_v4 } from '@googleapis/sheets';
import { Expense, InvalidExpenseError } from '../../domain/expenses/Expense.js';
import type {
    DateRange,
    ExpenseRepository,
} from '../../providers/ExpenseRepository.js';

export const SHEET_HEADER = [
    'data',
    'valor',
    'descricao',
    'categoria',
    'criado_em',
    'message_key',
    'user_id',
] as const;

const DEFAULT_TAB_NAME = 'gastos';
const MAX_ATTEMPTS = 3;
const BASE_BACKOFF_MS = 200;
const TRANSIENT_NETWORK_CODES = new Set([
    'ECONNRESET',
    'ETIMEDOUT',
    'ECONNREFUSED',
    'EAI_AGAIN',
    'ENOTFOUND',
]);

/** Sheets counts days from 1899-12-30. */
const SHEETS_EPOCH_MS = Date.UTC(1899, 11, 30);
const MS_PER_DAY = 86_400_000;

type Sleep = (ms: number) => Promise<void>;

export interface GoogleSheetsOptions {
    /** Tab the bot owns. Defaults to `gastos`. */
    readonly tabName?: string;
    readonly sleep?: Sleep;
}

/**
 * Stores expenses in one tab of a Google spreadsheet that the bot owns: rows are only
 * appended (or deleted by undo) and never reordered, so charts on other tabs can safely
 * reference `gastos!A:G`.
 */
export default class GoogleSheetsExpenseRepository implements ExpenseRepository {
    /** All operations run one at a time so check-then-write sequences never interleave. */
    private queue: Promise<unknown> = Promise.resolve();
    private keys: Set<string> | undefined;

    private constructor(
        private readonly sheets: sheets_v4.Sheets,
        private readonly spreadsheetId: string,
        private readonly tabName: string,
        private readonly sheetId: number,
        private readonly sleep: Sleep,
    ) {}

    /** Creates the tab (with header and formats) if missing and validates it otherwise. */
    static async create(
        sheets: sheets_v4.Sheets,
        spreadsheetId: string,
        options: GoogleSheetsOptions = {},
    ): Promise<GoogleSheetsExpenseRepository> {
        const tabName = options.tabName ?? DEFAULT_TAB_NAME;
        const sleep = options.sleep ?? defaultSleep;
        const sheetId = await ensureSchema(sheets, spreadsheetId, tabName, sleep);

        return new GoogleSheetsExpenseRepository(
            sheets,
            spreadsheetId,
            tabName,
            sheetId,
            sleep,
        );
    }

    add(expense: Expense): Promise<void> {
        return this.enqueue(async () => {
            if ((await this.loadKeys()).has(expense.messageKey)) return;

            await retry(async (attempt) => {
                // A failed attempt may still have reached the sheet; look before writing again.
                if (attempt > 1) {
                    this.keys = undefined;
                    if ((await this.loadKeys()).has(expense.messageKey)) return;
                }

                await this.sheets.spreadsheets.values.append({
                    spreadsheetId: this.spreadsheetId,
                    range: this.range(),
                    valueInputOption: 'RAW',
                    insertDataOption: 'INSERT_ROWS',
                    requestBody: { values: [toRow(expense)] },
                });
            }, this.sleep);

            (await this.loadKeys()).add(expense.messageKey);
        });
    }

    existsByMessageId(messageKey: string): Promise<boolean> {
        return this.enqueue(async () => (await this.loadKeys()).has(messageKey));
    }

    listBy(userId: string, range: DateRange): Promise<Expense[]> {
        return this.enqueue(async () =>
            (await this.readExpenses())
                .map(({ expense }) => expense)
                .filter((e) => e.belongsTo(userId) && e.occursWithin(range)),
        );
    }

    removeLastBy(userId: string): Promise<Expense | null> {
        return this.enqueue(async () => {
            const last = (await this.readExpenses())
                .filter(({ expense }) => expense.belongsTo(userId))
                .at(-1);
            if (!last) return null;

            await retry(
                () =>
                    this.sheets.spreadsheets.batchUpdate({
                        spreadsheetId: this.spreadsheetId,
                        requestBody: {
                            requests: [
                                {
                                    deleteDimension: {
                                        range: {
                                            sheetId: this.sheetId,
                                            dimension: 'ROWS',
                                            startIndex: last.rowIndex,
                                            endIndex: last.rowIndex + 1,
                                        },
                                    },
                                },
                            ],
                        },
                    }),
                this.sleep,
            );

            this.keys?.delete(last.expense.messageKey);
            return last.expense;
        });
    }

    private enqueue<T>(operation: () => Promise<T>): Promise<T> {
        const result = this.queue.then(operation);
        // A failed operation must not block the ones queued after it.
        this.queue = result.catch(() => {});
        return result;
    }

    private async loadKeys(): Promise<Set<string>> {
        this.keys ??= new Set(
            (await this.readExpenses()).map(({ expense }) => expense.messageKey),
        );
        return this.keys;
    }

    /** Valid rows only; `rowIndex` is the 0-based row in the tab (the header is row 0). */
    private async readExpenses(): Promise<
        Array<{ expense: Expense; rowIndex: number }>
    > {
        const response = await retry(
            () =>
                this.sheets.spreadsheets.values.get({
                    spreadsheetId: this.spreadsheetId,
                    range: this.range(),
                    valueRenderOption: 'UNFORMATTED_VALUE',
                }),
            this.sleep,
        );

        return (response.data.values ?? []).flatMap((row, rowIndex) => {
            const expense = rowIndex === 0 ? null : fromRow(row);
            return expense ? [{ expense, rowIndex }] : [];
        });
    }

    private range(): string {
        return `'${this.tabName}'!A:G`;
    }
}

async function ensureSchema(
    sheets: sheets_v4.Sheets,
    spreadsheetId: string,
    tabName: string,
    sleep: Sleep,
): Promise<number> {
    const metadata = await retry(
        () =>
            sheets.spreadsheets.get({
                spreadsheetId,
                fields: 'sheets.properties(sheetId,title)',
            }),
        sleep,
    );
    const existing = metadata.data.sheets?.find(
        (s) => s.properties?.title === tabName,
    )?.properties;

    let sheetId = existing?.sheetId;

    if (sheetId === undefined || sheetId === null) {
        const created = await retry(
            () =>
                sheets.spreadsheets.batchUpdate({
                    spreadsheetId,
                    requestBody: {
                        requests: [{ addSheet: { properties: { title: tabName } } }],
                    },
                }),
            sleep,
        );
        sheetId = created.data.replies?.[0]?.addSheet?.properties?.sheetId;
        if (sheetId === undefined || sheetId === null)
            throw new Error(`Failed to create the "${tabName}" tab`);

        await writeHeaderAndFormats(sheets, spreadsheetId, tabName, sheetId, sleep);
        return sheetId;
    }

    const response = await retry(
        () =>
            sheets.spreadsheets.values.get({
                spreadsheetId,
                range: `'${tabName}'!A1:G1`,
            }),
        sleep,
    );
    const header = response.data.values?.[0] ?? [];

    if (header.length === 0) {
        await writeHeaderAndFormats(sheets, spreadsheetId, tabName, sheetId, sleep);
        return sheetId;
    }

    if (!SHEET_HEADER.every((name, i) => header[i] === name) || header.length !== SHEET_HEADER.length)
        throw new Error(
            `The "${tabName}" tab has unexpected headers (${header.join(', ')}). ` +
                `Expected: ${SHEET_HEADER.join(', ')}. Fix or rename the tab; it is never overwritten.`,
        );

    return sheetId;
}

async function writeHeaderAndFormats(
    sheets: sheets_v4.Sheets,
    spreadsheetId: string,
    tabName: string,
    sheetId: number,
    sleep: Sleep,
): Promise<void> {
    await retry(
        () =>
            sheets.spreadsheets.values.update({
                spreadsheetId,
                range: `'${tabName}'!A1:G1`,
                valueInputOption: 'RAW',
                requestBody: { values: [[...SHEET_HEADER]] },
            }),
        sleep,
    );

    const format = (column: number, type: string, pattern: string) => ({
        repeatCell: {
            range: {
                sheetId,
                startRowIndex: 1,
                startColumnIndex: column,
                endColumnIndex: column + 1,
            },
            cell: { userEnteredFormat: { numberFormat: { type, pattern } } },
            fields: 'userEnteredFormat.numberFormat',
        },
    });

    await retry(
        () =>
            sheets.spreadsheets.batchUpdate({
                spreadsheetId,
                requestBody: {
                    requests: [
                        format(0, 'DATE', 'dd/mm/yyyy'),
                        format(1, 'CURRENCY', '"R$" #,##0.00'),
                    ],
                },
            }),
        sleep,
    );
}

function toRow(expense: Expense): Array<string | number> {
    return [
        isoToSerial(expense.date),
        expense.amountCents / 100,
        expense.description,
        expense.category,
        expense.createdAt,
        expense.messageKey,
        expense.userId,
    ];
}

function fromRow(row: unknown[]): Expense | null {
    const [serial, valor, description, category, createdAt, messageKey, userId] = row;

    // The sheet is only a store: a row someone mangled by hand is skipped, not fatal.
    if (typeof serial !== 'number' || typeof valor !== 'number') return null;

    try {
        return new Expense({
            date: serialToIso(serial),
            amountCents: Math.round(valor * 100),
            description,
            category,
            userId,
            messageKey,
            createdAt,
        });
    } catch (error) {
        if (error instanceof InvalidExpenseError) return null;
        throw error;
    }
}

function isoToSerial(date: string): number {
    const [year, month, day] = date.split('-').map(Number) as [number, number, number];
    return Math.round((Date.UTC(year, month - 1, day) - SHEETS_EPOCH_MS) / MS_PER_DAY);
}

function serialToIso(serial: number): string {
    return new Date(SHEETS_EPOCH_MS + Math.floor(serial) * MS_PER_DAY)
        .toISOString()
        .slice(0, 10);
}

async function retry<T>(
    operation: (attempt: number) => Promise<T>,
    sleep: Sleep,
): Promise<T> {
    for (let attempt = 1; ; attempt++) {
        try {
            return await operation(attempt);
        } catch (err) {
            if (attempt >= MAX_ATTEMPTS || !isTransient(err)) throw err;
            await sleep(BASE_BACKOFF_MS * 2 ** (attempt - 1));
        }
    }
}

function isTransient(err: unknown): boolean {
    if (typeof err !== 'object' || err === null) return false;

    const { status, code, response } = err as {
        status?: unknown;
        code?: unknown;
        response?: { status?: unknown };
    };
    const httpStatus = [status, response?.status, code]
        .map(Number)
        .find((n) => Number.isInteger(n) && n >= 100);

    if (httpStatus !== undefined) return httpStatus === 429 || httpStatus >= 500;
    return typeof code === 'string' && TRANSIENT_NETWORK_CODES.has(code);
}

function defaultSleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
}
