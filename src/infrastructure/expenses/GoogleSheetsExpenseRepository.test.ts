import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { Expense, type ExpenseProps } from '../../domain/expenses/Expense.js';
import { expenseRepositoryContract } from './expenseRepositoryContract.js';
import FakeSheets from './FakeSheets.js';
import GoogleSheetsExpenseRepository, { SHEET_HEADER } from './GoogleSheetsExpenseRepository.js';

const SPREADSHEET_ID = 'sheet-id';
const noSleep = async () => {};

const create = (fake: FakeSheets, sleep: (ms: number) => Promise<void> = noSleep) =>
    GoogleSheetsExpenseRepository.create(fake.asClient(), SPREADSHEET_ID, { sleep });

const expense = (overrides: Partial<ExpenseProps> = {}) => new Expense({
    date: '2026-10-01',
    amountCents: 5090,
    description: 'burger king',
    category: 'alimentacao',
    userId: 'telegram:1',
    messageKey: 'telegram:10:100#0',
    createdAt: '2026-10-01T12:00:00.000Z',
    ...overrides,
});

const httpError = (status: number) => Object.assign(new Error(`HTTP ${status}`), { status });

expenseRepositoryContract('GoogleSheetsExpenseRepository', () => create(new FakeSheets()));

describe('GoogleSheetsExpenseRepository', () => {
    describe('schema', () => {
        it('creates the gastos tab with header and formats when missing', async () => {
            const fake = new FakeSheets();
            await create(fake);

            assert.deepEqual(fake.tabs.get('gastos')!.rows, [[...SHEET_HEADER]]);
            const patterns = fake.formats.map(
                (f: any) => f.cell.userEnteredFormat.numberFormat.type,
            );
            assert.deepEqual(patterns, ['DATE', 'CURRENCY']);
        });

        it('writes the header into an existing empty tab', async () => {
            const fake = new FakeSheets();
            fake.seedTab('gastos', []);
            await create(fake);

            assert.deepEqual(fake.tabs.get('gastos')!.rows, [[...SHEET_HEADER]]);
        });

        it('leaves a valid existing tab and its rows untouched', async () => {
            const fake = new FakeSheets();
            fake.seedTab('gastos', [[...SHEET_HEADER], [46000, 10, 'x', 'outros', 't', 'k', 'u']]);
            await create(fake);

            assert.equal(fake.tabs.get('gastos')!.rows.length, 2);
            assert.equal(fake.callsTo('values.update').length, 0);
        });

        it('refuses to touch a tab with unexpected headers', async () => {
            const fake = new FakeSheets();
            fake.seedTab('gastos', [['date', 'amount']]);

            await assert.rejects(create(fake), /unexpected headers/);
            assert.deepEqual(fake.tabs.get('gastos')!.rows, [['date', 'amount']]);
        });

        it('ignores other tabs', async () => {
            const fake = new FakeSheets();
            fake.seedTab('Dashboard', [['charts live here']]);
            await create(fake);

            assert.deepEqual(fake.tabs.get('Dashboard')!.rows, [['charts live here']]);
        });
    });

    describe('writes', () => {
        it('appends typed values with RAW input, a serial date and a decimal amount', async () => {
            const fake = new FakeSheets();
            const repo = await create(fake);

            await repo.add(expense({ date: '2026-10-01', amountCents: 5090 }));

            const [append] = fake.callsTo('values.append');
            assert.equal(append.valueInputOption, 'RAW');
            assert.equal(append.insertDataOption, 'INSERT_ROWS');
            assert.deepEqual(append.requestBody.values[0], [
                46296, // days since 1899-12-30
                50.9,
                'burger king',
                'alimentacao',
                '2026-10-01T12:00:00.000Z',
                'telegram:10:100#0',
                'telegram:1',
            ]);
        });

        it('deletes exactly the row of the removed expense and leaves the header', async () => {
            const fake = new FakeSheets();
            const repo = await create(fake);
            await repo.add(expense({ messageKey: 'k1' }));
            await repo.add(expense({ messageKey: 'k2', description: 'segundo' }));
            await repo.add(expense({ messageKey: 'k3', userId: 'telegram:2' }));

            await repo.removeLastBy('telegram:1');

            const rows = fake.tabs.get('gastos')!.rows;
            assert.deepEqual(rows.map((r) => r[5] ?? 'header'), ['message_key', 'k1', 'k3']);
        });

        it('does not write a duplicate key twice in parallel', async () => {
            const fake = new FakeSheets();
            const repo = await create(fake);

            await Promise.all([repo.add(expense()), repo.add(expense()), repo.add(expense())]);

            assert.equal(fake.callsTo('values.append').length, 1);
        });
    });

    describe('message key cache', () => {
        it('reads the sheet once for any number of existence checks and adds', async () => {
            const fake = new FakeSheets();
            const repo = await create(fake);
            const readsBefore = fake.callsTo('values.get').length;

            await repo.existsByMessageId('a');
            await repo.add(expense({ messageKey: 'a' }));
            await repo.add(expense({ messageKey: 'b' }));
            await repo.existsByMessageId('b');

            assert.equal(fake.callsTo('values.get').length - readsBefore, 1);
        });

        it('knows the keys already in the sheet after a restart', async () => {
            const fake = new FakeSheets();
            await (await create(fake)).add(expense());

            const restarted = await create(fake);

            assert.equal(await restarted.existsByMessageId('telegram:10:100#0'), true);
        });
    });

    describe('reading', () => {
        it('skips malformed rows instead of failing', async () => {
            const fake = new FakeSheets();
            fake.seedTab('gastos', [
                [...SHEET_HEADER],
                ['not a date', 10, 'x', 'outros', 't', 'k1', 'telegram:1'],
                [46296, 10, 'x', 'viagem', 't', 'k2', 'telegram:1'],
                [46296],
                [46296, 12.5, 'bom', 'outros', '2026-10-01T12:00:00.000Z', 'k3', 'telegram:1'],
            ]);
            const repo = await create(fake);

            const found = await repo.listBy('telegram:1', { from: '2026-01-01', to: '2026-12-31' });

            assert.deepEqual(found.map((e) => e.messageKey), ['k3']);
            assert.equal(found[0]!.amountCents, 1250);
        });
    });

    describe('retries', () => {
        it('retries a rate-limited write with backoff and then succeeds', async () => {
            const fake = new FakeSheets();
            const sleeps: number[] = [];
            const repo = await create(fake, async (ms) => void sleeps.push(ms));
            fake.failOn('values.append', { error: httpError(429), times: 2 });

            await repo.add(expense());

            assert.deepEqual(sleeps, [200, 400]);
            assert.equal(fake.tabs.get('gastos')!.rows.length, 2);
        });

        it('retries server errors and network errors', async () => {
            for (const error of [httpError(503), Object.assign(new Error('reset'), { code: 'ECONNRESET' })]) {
                const fake = new FakeSheets();
                const repo = await create(fake);
                fake.failOn('values.append', { error, times: 1 });

                await repo.add(expense());

                assert.equal(fake.tabs.get('gastos')!.rows.length, 2);
            }
        });

        it('gives up after three attempts and reports the error', async () => {
            const fake = new FakeSheets();
            const repo = await create(fake);
            fake.failOn('values.append', { error: httpError(500), times: 10 });

            await assert.rejects(repo.add(expense()), /HTTP 500/);
            assert.equal(fake.callsTo('values.append').length, 3);
        });

        it('does not retry client errors', async () => {
            const fake = new FakeSheets();
            const repo = await create(fake);
            fake.failOn('values.append', { error: httpError(404), times: 10 });

            await assert.rejects(repo.add(expense()), /HTTP 404/);
            assert.equal(fake.callsTo('values.append').length, 1);
        });

        it('does not write twice when a failed attempt had actually reached the sheet', async () => {
            const fake = new FakeSheets();
            const repo = await create(fake);
            fake.failOn('values.append', {
                error: httpError(503),
                times: 1,
                applyBeforeFailing: true,
            });

            await repo.add(expense());

            assert.equal(fake.tabs.get('gastos')!.rows.length, 2);
            assert.equal(await repo.existsByMessageId('telegram:10:100#0'), true);
        });

        it('keeps working after a failed operation', async () => {
            const fake = new FakeSheets();
            const repo = await create(fake);
            fake.failOn('values.append', { error: httpError(404), times: 1 });

            await assert.rejects(repo.add(expense({ messageKey: 'lost' })));
            await repo.add(expense({ messageKey: 'fine' }));

            assert.equal(await repo.existsByMessageId('fine'), true);
            assert.equal(await repo.existsByMessageId('lost'), false);
        });
    });
});
