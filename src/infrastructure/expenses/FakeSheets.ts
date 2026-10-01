import type { sheets_v4 } from '@googleapis/sheets';

type Row = unknown[];
interface Tab {
    sheetId: number;
    rows: Row[];
}

/** Whether the call really happened before failing decides how a retry must behave. */
export interface FailurePlan {
    readonly error: Error;
    readonly times: number;
    /** Apply the write before throwing, like a request whose response got lost. */
    readonly applyBeforeFailing?: boolean;
}

/** In-memory stand-in for the parts of the Sheets API the repository uses. For tests only. */
export default class FakeSheets {
    readonly tabs = new Map<string, Tab>();
    readonly formats: unknown[] = [];
    readonly calls: Array<{ method: string; params: any }> = [];
    private readonly failures = new Map<string, FailurePlan & { left: number }>();
    private nextSheetId = 1;

    /** Pre-existing tab, e.g. one with a foreign header. */
    seedTab(title: string, rows: Row[]): void {
        this.tabs.set(title, { sheetId: this.nextSheetId++, rows });
    }

    failOn(method: string, plan: FailurePlan): void {
        this.failures.set(method, { ...plan, left: plan.times });
    }

    callsTo(method: string): any[] {
        return this.calls.filter((c) => c.method === method).map((c) => c.params);
    }

    asClient(): sheets_v4.Sheets {
        const fake = this;
        return {
            spreadsheets: {
                get: (params: any) =>
                    fake.run('spreadsheets.get', params, () => ({
                        data: {
                            sheets: [...fake.tabs].map(([title, tab]) => ({
                                properties: { sheetId: tab.sheetId, title },
                            })),
                        },
                    })),
                batchUpdate: (params: any) =>
                    fake.run('spreadsheets.batchUpdate', params, () => ({
                        data: { replies: params.requestBody.requests.map((r: any) => fake.apply(r)) },
                    })),
                values: {
                    get: (params: any) =>
                        fake.run('values.get', params, () => ({
                            data: { values: fake.read(params.range) },
                        })),
                    update: (params: any) =>
                        fake.run('values.update', params, () => {
                            fake.tab(params.range).rows[0] = structuredClone(params.requestBody.values[0]);
                            return { data: {} };
                        }),
                    append: (params: any) =>
                        fake.run('values.append', params, () => {
                            fake.tab(params.range).rows.push(structuredClone(params.requestBody.values[0]));
                            return { data: {} };
                        }),
                },
            },
        } as unknown as sheets_v4.Sheets;
    }

    private async run<T>(method: string, params: any, action: () => T): Promise<T> {
        this.calls.push({ method, params: structuredClone(params) });

        const plan = this.failures.get(method);
        if (plan && plan.left > 0) {
            plan.left--;
            if (plan.applyBeforeFailing) action();
            throw plan.error;
        }

        return action();
    }

    private apply(request: any): unknown {
        if (request.addSheet) {
            const title = request.addSheet.properties.title as string;
            this.seedTab(title, []);
            return { addSheet: { properties: { sheetId: this.tabs.get(title)!.sheetId, title } } };
        }
        if (request.repeatCell) {
            this.formats.push(request.repeatCell);
            return {};
        }
        if (request.deleteDimension) {
            const { sheetId, startIndex, endIndex } = request.deleteDimension.range;
            const tab = [...this.tabs.values()].find((t) => t.sheetId === sheetId)!;
            tab.rows.splice(startIndex, endIndex - startIndex);
            return {};
        }
        throw new Error(`FakeSheets: unsupported request ${Object.keys(request)[0]}`);
    }

    private tab(range: string): Tab {
        const title = /^'(.+)'!/.exec(range)![1]!;
        const tab = this.tabs.get(title);
        if (!tab) throw new Error(`FakeSheets: no tab "${title}"`);
        return tab;
    }

    private read(range: string): Row[] | undefined {
        const rows = this.tab(range).rows;
        const selected = range.endsWith('A1:G1') ? rows.slice(0, 1) : rows;
        // Like the real API, trailing empty rows are not returned at all.
        return selected.length === 0 ? undefined : structuredClone(selected);
    }
}
